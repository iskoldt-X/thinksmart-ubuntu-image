# 客户端在线更新（thinksmart-update）

只检查不自动装，用户在屏幕上点「更新」才装；只从 HTTPS 地址下载，每个文件按清单核对大小和 sha256；保留上一版；装完自检，不过就自动退回；用户数据不碰。

## 组成

| 文件 | 装到设备哪里 | 作用 |
| --- | --- | --- |
| `thinksmart-update` | `/usr/local/sbin/` | root 运行：`check` 检查、`run` 处理页面请求、`install` 安装、`boot` 断电恢复、`adopt` 把现有客户端目录收编为一个版本 |
| `thinksmart-update.conf` | `/etc/thinksmart-update.conf` | 更新地址（可多个，依次试，必须 https；本机 127.0.0.1/localhost 的测试源可以 http）、代理 |
| `thinksmart-update-check.timer/.service` | `/etc/systemd/system/` | 开机 2 分钟后和每天一次检查（只检查） |
| `thinksmart-update-request.path` + `-run.service` | 同上 | 页面放进 `/var/lib/thinksmart-update/requests/` 的请求由 root 服务处理；最多跑 3 小时（国内直连 GitHub 慢），超时被杀或崩溃时 `OnFailure` 立刻跑一次检查，把停在「正在更新」的状态收尾 |
| `thinksmart-update-boot.service` | 同上 | 开机时把「切换后还没自检完」的更新重新自检或退回 |

`check`、`run`、`install` 拿到锁后也先做一遍 `boot` 的收尾：能拿到锁说明上一个进程已经不在了，还停在准备/下载/安装/自检/退回的任务都是被中断的，切换后没自检完的补测或退回，其余标成失败，页面的更新按钮重新出现。
| `install.sh` | — | 在设备上 `sudo sh install.sh` 装好以上全部，并把 `~/thinksmart-client` 收编为当前版本 |
| `make-release.py` | Mac 上用 | 打包、建依赖环境（arm64 容器）、写清单（版本、更新内容、每个文件的大小和 sha256） |

设备上的目录：`/opt/thinksmart/client/<版本>/`（root 所有）、`current`/`previous` 链接、`/opt/thinksmart/envs/<依赖哈希>/`；状态 `/var/lib/thinksmart-update/status.json`（所有人可读，客户端和欢迎页读它显示）。

## 发一个版本

```bash
# 改 thinksmart_client/__init__.py 的 __version__，提交，然后
python3 make-release.py ../../thinksmart-client /tmp/release --note "这次改了什么" --note "……"
```

2026-11-01 起不签名、不用密钥（用户定）：设备只从 HTTPS 地址取清单和文件，每个文件都要和清单里的大小、sha256 对上才装，所以下坏的、没下完的包不会装上。代价：谁能改 Release 上的文件（拿到 GitHub 账号）或冒充 HTTPS 服务器，谁就能给设备推包。

产物按 GitHub Releases 的路径排好：把 `latest.json`、代码包、依赖包三个文件上传到标签为 `client-vX.Y.Z` 的 Release（每个组件一个仓库，`releases/latest` 才指得对）。上传由人来做。

## 测试

本机起一个静态文件服务指向 `build` 的输出目录，经 SSH 反向隧道给设备用，设备上 `/etc/thinksmart-update.conf` 的 `SOURCES` 改成 `http://127.0.0.1:<端口>/`。单元测试：`uv run --no-project --with pytest python -m pytest -q update`。步骤和结果见交付文档。

更新没有签名（2026-11-01 定）：设备只认 HTTPS 和清单里每个文件的 sha256，更新地址上放什么就会以 root 身份装什么。`SOURCES` 只填自己的或信任的地址，不要填公共的 GitHub 加速镜像或代理站。
