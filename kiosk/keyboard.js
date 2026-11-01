/*
 * On-screen keyboard for the ThinkSmart kiosk (the Weston kiosk has no system keyboard).
 * Letters, digits and symbols: enough for Wi-Fi passwords, URLs and English text.
 *
 *   const kb = ThinkSmartKeyboard.create(parentElement, {
 *     enterLabel: '连接',
 *     onKey(ch) {},        // a character was typed
 *     onBackspace() {},
 *     onEnter() {},
 *   });
 *   kb.setEnterEnabled(false);
 *
 * Shift: one tap capitalises the next letter, a second tap locks caps.
 * Only transform/opacity change on press, which the CPU and GPU paths both draw cheaply.
 */
(function () {
  const LAYOUTS = {
    abc: [
      'qwertyuiop'.split(''),
      'asdfghjkl'.split(''),
      ['{shift}', ...'zxcvbnm'.split(''), '{bksp}'],
      ['{123}', '{space}', '{enter}'],
    ],
    num: [
      '1234567890'.split(''),
      ['-', '/', ':', ';', '(', ')', '$', '&', '@', '"'],
      ['{sym}', '.', ',', '?', '!', "'", '_', '{bksp}'],
      ['{abc}', '{space}', '{enter}'],
    ],
    sym: [
      ['[', ']', '{', '}', '#', '%', '^', '*', '+', '='],
      ['\\', '|', '~', '<', '>', '€', '£', '¥', '`', '·'],
      ['{123}', '.', ',', '?', '!', "'", '_', '{bksp}'],
      ['{abc}', '{space}', '{enter}'],
    ],
  };
  const LABEL = { '{shift}': '⇧', '{bksp}': '⌫', '{123}': '123', '{sym}': '#+=', '{abc}': 'ABC', '{space}': '空格' };

  const CSS = `
  .tskb { display: flex; flex-direction: column; gap: 10px; padding: 14px; border-radius: 22px;
          background: #0c1224f2; border: 1px solid #ffffff1a; user-select: none; -webkit-user-select: none; }
  .tskb-row { display: flex; gap: 8px; justify-content: center; }
  .tskb-key { flex: 1 1 0; max-width: 96px; height: 60px; border: 0; border-radius: 12px; background: #ffffff14;
              color: #eef2ff; font: 500 24px/1 "Noto Sans CJK SC", sans-serif; display: grid; place-items: center;
              transition: transform .06s, background .06s; }
  .tskb-key:active { transform: scale(.94); background: #ffffff2e; }
  .tskb-key.fn { background: #ffffff0a; font-size: 18px; color: #a9b4d6; max-width: 130px; flex: 1.5 1 0; }
  .tskb-key.on { background: #6c8cff; color: #fff; }
  .tskb-key.lock { background: #5ee0ff; color: #0b1020; }
  .tskb-key.space { flex: 5 1 0; max-width: none; font-size: 18px; color: #a9b4d6; }
  .tskb-key.enter { flex: 2 1 0; max-width: 220px; background: linear-gradient(135deg, #6c8cff, #5ee0ff); color: #0b1020;
                    font-size: 20px; font-weight: 700; }
  .tskb-key.enter[disabled] { opacity: .35; }
  `;

  function create(parent, opts) {
    opts = opts || {};
    if (!document.getElementById('tskb-style')) {
      const style = document.createElement('style');
      style.id = 'tskb-style';
      style.textContent = CSS;
      document.head.appendChild(style);
    }
    const root = document.createElement('div');
    root.className = 'tskb';
    parent.appendChild(root);

    let layout = 'abc', shift = 0;  // shift: 0 off, 1 next letter, 2 locked
    let enterEnabled = true;

    function render() {
      root.textContent = '';
      for (const keys of LAYOUTS[layout]) {
        const row = document.createElement('div');
        row.className = 'tskb-row';
        for (const k of keys) {
          const b = document.createElement('button');
          b.type = 'button';
          b.className = 'tskb-key';
          if (k === '{space}') b.classList.add('space');
          else if (k === '{enter}') { b.classList.add('enter'); b.disabled = !enterEnabled; }
          else if (k.startsWith('{')) b.classList.add('fn');
          if (k === '{shift}' && shift) b.classList.add(shift === 2 ? 'lock' : 'on');
          b.textContent = k === '{enter}' ? (opts.enterLabel || '完成')
            : LABEL[k] || (shift && k.length === 1 ? k.toUpperCase() : k);
          // pointerdown, not click: no 300 ms delay and the field keeps its look
          b.addEventListener('pointerdown', e => { e.preventDefault(); press(k); });
          row.appendChild(b);
        }
        root.appendChild(row);
      }
    }

    let lastShift = 0;
    function press(k) {
      if (k === '{shift}') {
        const now = Date.now();
        shift = shift === 0 ? 1 : (shift === 1 && now - lastShift < 400 ? 2 : 0);
        lastShift = now;
      } else if (k === '{123}') layout = 'num';
      else if (k === '{sym}') layout = 'sym';
      else if (k === '{abc}') layout = 'abc';
      else if (k === '{bksp}') opts.onBackspace && opts.onBackspace();
      else if (k === '{enter}') { if (enterEnabled && opts.onEnter) opts.onEnter(); }
      else {
        const ch = k === '{space}' ? ' ' : (shift ? k.toUpperCase() : k);
        opts.onKey && opts.onKey(ch);
        if (shift === 1) shift = 0;
      }
      render();
    }

    render();
    return {
      el: root,
      setEnterEnabled(on) { enterEnabled = !!on; render(); },
      reset() { layout = 'abc'; shift = 0; render(); },
      destroy() { root.remove(); },
    };
  }

  window.ThinkSmartKeyboard = { create };
})();
