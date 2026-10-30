'use strict';
document.documentElement.classList.add('js');
const korean = document.documentElement.lang === 'ko';
// Keep the current section and query when switching the same page's language.
// Plain links still work without JavaScript; locale-relative links retain choice.
for (const link of document.querySelectorAll('[data-language-link]')) {
  const target = new URL(link.href);
  const syncLocation = () => {
    target.search = location.search;
    target.hash = location.hash;
    link.href = target.href;
  };
  syncLocation();
  window.addEventListener('hashchange', syncLocation);
  link.addEventListener('click', syncLocation);
}
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
      button.textContent = korean ? '복사됨' : 'Copied';
      live.textContent = button.getAttribute('aria-label') + (korean ? ': 클립보드에 복사했습니다.' : ': copied to clipboard.');
    } catch {
      const range = document.createRange();
      range.selectNodeContents(code);
      const selection = window.getSelection();
      selection.removeAllRanges(); selection.addRange(range);
      live.textContent = korean ? '클립보드를 사용할 수 없습니다. 선택된 코드를 단축키로 복사하세요.' : 'Clipboard unavailable. Code selected; use your copy shortcut.';
      button.textContent = korean ? '선택됨' : 'Selected';
    }
    setTimeout(() => { button.textContent = korean ? '복사' : 'Copy'; }, 2200);
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
