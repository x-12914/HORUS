// DEFENSE-LOG — light client behaviour: live clock + clickable rows.
(function () {
  // Zulu-style live clock in the sidebar.
  const clock = document.getElementById("clock");
  function tick() {
    if (!clock) return;
    const d = new Date();
    const p = (n) => String(n).padStart(2, "0");
    clock.textContent = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())} LOC`;
  }
  tick();
  setInterval(tick, 1000);

  // Make whole table rows clickable when they carry a data-href.
  document.querySelectorAll("tr.row-link[data-href]").forEach((row) => {
    row.addEventListener("click", (e) => {
      if (e.target.closest("a,button,form,input,select")) return;
      window.location.href = row.dataset.href;
    });
  });

  // Guard destructive actions.
  document.querySelectorAll("form[data-confirm]").forEach((f) => {
    f.addEventListener("submit", (e) => {
      if (!window.confirm(f.dataset.confirm)) e.preventDefault();
    });
  });
})();
