// Progressive enhancement: every <select data-filter="x"> hides items whose data-x does not contain the value.
// Without JavaScript the full lists stay visible.
(function () {
  var selects = document.querySelectorAll("select[data-filter]");
  if (!selects.length) return;

  function apply() {
    var active = [];
    selects.forEach(function (select) {
      if (select.value) active.push([select.dataset.filter, select.value]);
    });
    document.querySelectorAll("[data-item]").forEach(function (item) {
      var visible = active.every(function (pair) {
        var tokens = (item.dataset[pair[0]] || "").split(" ");
        return tokens.indexOf(pair[1]) !== -1;
      });
      item.hidden = !visible;
    });
  }

  selects.forEach(function (select) {
    select.addEventListener("change", apply);
  });
})();
