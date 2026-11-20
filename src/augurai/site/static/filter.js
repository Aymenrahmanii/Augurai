// Progressive enhancement. Without JavaScript every list stays complete and readable.
//  - input[data-filter-text]  : live text search over each [data-item]'s data-text
//  - select[data-filter="x"]  : keep items whose data-x contains the chosen value
//  - select[data-sort="name"] : reorder the [data-sortable="name"] container ("key:asc|desc")
//  - [data-count="noun"]      : "N of M noun" for the visible items
//  - #theme-toggle            : light/dark, remembered in localStorage
(function () {
  var root = document.documentElement;
  var items = Array.prototype.slice.call(document.querySelectorAll("[data-item]"));
  var search = document.querySelector("input[data-filter-text]");
  var selects = document.querySelectorAll("select[data-filter]");
  var counter = document.querySelector("[data-count]");

  function apply() {
    var query = search ? search.value.trim().toLowerCase() : "";
    var active = [];
    selects.forEach(function (s) { if (s.value) active.push([s.dataset.filter, s.value]); });
    var shown = 0;
    items.forEach(function (item) {
      var ok = (!query || (item.dataset.text || "").indexOf(query) !== -1) &&
        active.every(function (pair) { return (item.dataset[pair[0]] || "").split(" ").indexOf(pair[1]) !== -1; });
      item.hidden = !ok;
      if (ok) shown += 1;
    });
    if (counter) counter.textContent = shown + " of " + items.length + " " + (counter.dataset.count || "");
  }

  function sortBy(select) {
    var box = document.querySelector('[data-sortable="' + select.dataset.sort + '"]');
    if (!box) return;
    var parts = select.value.split(":");
    var key = "sort" + parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
    var dir = parts[1] === "asc" ? 1 : -1;
    var rows = Array.prototype.slice.call(box.children);
    rows.sort(function (a, b) {
      var x = parseFloat(a.dataset[key]), y = parseFloat(b.dataset[key]);
      var xn = isNaN(x), yn = isNaN(y);
      if (xn || yn) return xn === yn ? 0 : (xn ? 1 : -1); // rows without a value always go last
      return (x - y) * dir;
    });
    rows.forEach(function (row) { box.appendChild(row); });
  }

  if (search) search.addEventListener("input", apply);
  selects.forEach(function (s) { s.addEventListener("change", apply); });
  document.querySelectorAll("select[data-sort]").forEach(function (s) {
    s.addEventListener("change", function () { sortBy(s); });
    sortBy(s);
  });
  apply();

  var toggle = document.getElementById("theme-toggle");
  if (toggle) toggle.addEventListener("click", function () {
    var dark = root.dataset.theme ? root.dataset.theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    var next = dark ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem("augurai-theme", next); } catch (e) { /* private mode: still works for this visit */ }
  });
})();
