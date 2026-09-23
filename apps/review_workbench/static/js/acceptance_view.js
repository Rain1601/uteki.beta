/* Progressive enhancement: all panels remain readable without JavaScript. */
(() => {
  const links = [...document.querySelectorAll('[data-av-step]')];
  const panels = [...document.querySelectorAll('.av-panel')];
  function select() {
    const id = location.hash.slice(1);
    const selected = panels.find(panel => panel.id === id) || panels[0];
    if (!selected) return;
    panels.forEach(panel => { panel.hidden = panel !== selected; });
    links.forEach(link => {
      if (link.dataset.avStep === selected.id) link.setAttribute('aria-current', 'step');
      else link.removeAttribute('aria-current');
    });
  }
  links.forEach(link => link.addEventListener('click', event => {
    event.preventDefault();
    history.pushState(null, '', link.getAttribute('href'));
    select();
    // Keep the step rail available when switching from the end of a long panel.
    const start = document.getElementById('walkthrough');
    if (start.getBoundingClientRect().top < 150) start.scrollIntoView();
  }));
  window.addEventListener('hashchange', select);
  window.addEventListener('popstate', select);
  select();
})();
