#!/usr/bin/env python3
"""Build a client release for thinksmart-update (run on the Mac).

  python3 make-release.py CLIENT_DIR OUT_DIR --note "改了什么" [--note ...] [--env-cache DIR]
      packs the client's tracked files, the Python environment for its requirements.lock (built in
      an arm64 Ubuntu 24.04 container, cached by lock hash) and latest.json (version, notes, size
      and sha256 of each file) into OUT_DIR, laid out like GitHub Releases so OUT_DIR can be
      served as a test source as it is:
        OUT_DIR/latest/download/latest.json
        OUT_DIR/download/client-vX.Y.Z/thinksmart-client-X.Y.Z.tar.gz, client-env-<id>.tar.gz
      Publishing = upload the three files to a release tagged client-vX.Y.Z (done by a person).

No signature (decided 2026-11-01): devices fetch only over HTTPS and check every file's sha256.

The environment is built at its final device path, /opt/thinksmart/envs/<id>, with the same Python
(3.12, Ubuntu 24.04 arm64) as the device. pip in the container uses PIP_PROXY or PIP_INDEX_URL
from the environment when set.
"""
import argparse
import datetime
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path


def _tar(out_path, members):
    """Deterministic tar.gz: root-owned, fixed mtime, sorted; members = [(arcname, path)]."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w', format=tarfile.PAX_FORMAT) as t:
        for arc, path in sorted(members):
            info = t.gettarinfo(str(path), arc)
            info.uid = info.gid = 0
            info.uname = info.gname = 'root'
            info.mtime = 0
            info.mode = 0o755 if info.isdir() or os.access(path, os.X_OK) else 0o644
            if info.isreg():
                with open(path, 'rb') as f:
                    t.addfile(info, f)
            else:
                t.addfile(info)
    with open(out_path, 'wb') as f, gzip.GzipFile(fileobj=f, mode='wb', mtime=0) as gz:
        gz.write(buf.getvalue())


def client_version(client):
    for line in (client / 'thinksmart_client' / '__init__.py').read_text().splitlines():
        if line.startswith('__version__'):
            return line.split('=', 1)[1].strip().strip('\'"')
    sys.exit('no __version__ in thinksmart_client/__init__.py')


def build_env(lock, env_id, cache):
    """client-env-<id>.tar.gz from the cache, or built in an arm64 ubuntu:24.04 container."""
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f'client-env-{env_id}.tar.gz'
    if out.exists():
        return out
    script = f'''set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq python3-venv >/dev/null
python3 -m venv /opt/thinksmart/envs/{env_id}
/opt/thinksmart/envs/{env_id}/bin/pip install -q --no-cache-dir -r /out/requirements-{env_id}.lock
/opt/thinksmart/envs/{env_id}/bin/pip uninstall -q -y pip
find /opt/thinksmart/envs/{env_id} -name __pycache__ -prune -exec rm -rf {{}} +
tar --owner=0 --group=0 --numeric-owner -czf /out/{out.name}.part -C /opt/thinksmart/envs/{env_id} .
'''
    # only the cache is mounted (Docker Desktop shares /Users but not every temp directory)
    (cache / f'requirements-{env_id}.lock').write_bytes(lock.read_bytes())
    cmd = ['docker', 'run', '--rm', '--platform', 'linux/arm64', '-v', f'{cache}:/out']
    # apt goes direct (ports.ubuntu.com is fine from here); pip takes PIP_PROXY / PIP_INDEX_URL if set
    for var in ('PIP_PROXY', 'PIP_INDEX_URL'):
        if os.environ.get(var):
            cmd += ['-e', f'{var}={os.environ[var]}']
    subprocess.run(cmd + ['ubuntu:24.04', 'bash', '-c', script], check=True)
    os.replace(cache / f'{out.name}.part', out)
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def build(args):
    client = Path(args.client).resolve()
    out = Path(args.out).resolve()
    version = client_version(client)
    tag = f'client-v{version}'
    rel = out / 'download' / tag
    rel.mkdir(parents=True, exist_ok=True)

    files = subprocess.run(['git', '-C', str(client), 'ls-files', '-z'], capture_output=True,
                           check=True).stdout.decode().split('\0')
    members = [(f, client / f) for f in files if f and (client / f).is_file()]
    code = rel / f'thinksmart-client-{version}.tar.gz'
    _tar(code, members)

    lock = client / 'requirements.lock'
    env_id = hashlib.sha256(lock.read_bytes()).hexdigest()[:16]
    cached = build_env(lock, env_id, Path(args.env_cache).expanduser().resolve())
    env = rel / cached.name
    if not env.exists():
        env.write_bytes(cached.read_bytes())

    manifest = {
        'component': 'client',
        'version': version,
        'published': datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec='seconds'),
        'notes': args.note,
        'files': {
            'code': {'path': f'{tag}/{code.name}', 'sha256': sha256(code), 'size': code.stat().st_size},
            'env': {'id': env_id, 'path': f'{tag}/{env.name}', 'sha256': sha256(env), 'size': env.stat().st_size},
        },
    }
    data = json.dumps(manifest, ensure_ascii=False, indent=1).encode()
    latest = out / 'latest' / 'download'
    latest.mkdir(parents=True, exist_ok=True)
    (latest / 'latest.json').write_bytes(data)
    print(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f'\nrelease {tag} in {out}: upload latest.json, {code.name}, {env.name}')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('client')
    p.add_argument('out')
    p.add_argument('--note', action='append', default=[])
    p.add_argument('--env-cache', default='~/.cache/thinksmart-release/envs')
    build(p.parse_args())


if __name__ == '__main__':
    main()
