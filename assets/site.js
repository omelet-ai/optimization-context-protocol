'use strict';
document.documentElement.classList.add('js');
const menu = document.querySelector('.menu-toggle');
const nav = document.querySelector('#primary-nav');
menu.addEventListener('click', () => {
  const open = menu.getAttribute('aria-expanded') !== 'true';
  menu.setAttribute('aria-expanded', String(open));
  nav.classList.toggle('is-open', open);
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && menu.getAttribute('aria-expanded') === 'true') {
    menu.setAttribute('aria-expanded', 'false');
    nav.classList.remove('is-open');
    menu.focus();
  }
});
for (const button of document.querySelectorAll('[data-copy]')) {
  button.addEventListener('click', async () => {
    const code = document.getElementById(button.dataset.copy);
    const live = document.getElementById('copy-status');
    try {
      await navigator.clipboard.writeText(code.textContent);
      button.textContent = 'Copied';
      live.textContent = button.getAttribute('aria-label') + ': copied to clipboard.';
    } catch {
      const range = document.createRange();
      range.selectNodeContents(code);
      const selection = window.getSelection();
      selection.removeAllRanges(); selection.addRange(range);
      live.textContent = 'Clipboard unavailable. Code selected; use your copy shortcut.';
      button.textContent = 'Selected';
    }
    setTimeout(() => { button.textContent = 'Copy'; }, 2200);
  });
}
const explorer = document.querySelector('[data-example]');
if (explorer) {
  const scenarios = JSON.parse(document.getElementById('example-data').textContent);
  let scenario = 'routing';
  let view = 'input';
  const panel = document.getElementById('example-panel');
  const tabs = [...document.querySelectorAll('[role=tab]')];
  function render() {
    const data = scenarios[scenario];
    panel.textContent = JSON.stringify(data[view], null, 2);
    panel.setAttribute('aria-labelledby', 'tab-' + view);
    document.getElementById('example-summary').textContent = data.summary;
    document.getElementById('route-picture').hidden = scenario !== 'routing';
    document.getElementById('rejection-picture').hidden = scenario !== 'rejected';
    for (const button of document.querySelectorAll('[data-scenario]')) button.setAttribute('aria-pressed', String(button.dataset.scenario === scenario));
    for (const tab of tabs) {
      const active = tab.dataset.view === view;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
    }
  }
  for (const button of document.querySelectorAll('[data-scenario]')) button.addEventListener('click', () => {scenario = button.dataset.scenario; render();});
  for (const tab of tabs) {
    tab.addEventListener('click', () => {view = tab.dataset.view; render();});
    tab.addEventListener('keydown', event => {
      const index = tabs.indexOf(tab);
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next !== undefined) {event.preventDefault(); view = tabs[next].dataset.view; render(); tabs[next].focus();}
    });
  }
  render();
}
