// Dashboard charts (Chart.js, bundled in static/js/vendor so it works offline).
(function () {
  var dataEl = document.getElementById("chart-data");
  if (!dataEl || typeof Chart === "undefined") return;
  var data = JSON.parse(dataEl.textContent);
  var charts = [];

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function build() {
    charts.forEach(function (c) { c.destroy(); });
    charts = [];
    var text = css("--text"), muted = css("--muted"), border = css("--border");
    Chart.defaults.color = text;
    Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";

    var overall = document.getElementById("overallChart");
    if (overall) {
      charts.push(new Chart(overall, {
        type: "doughnut",
        data: {
          labels: data.overall.labels,
          datasets: [{ data: data.overall.values,
                       backgroundColor: [css("--success"), css("--warn"), border],
                       borderColor: css("--surface"), borderWidth: 2 }]
        },
        options: { maintainAspectRatio: false, cutout: "62%",
                   plugins: { legend: { position: "bottom" } } }
      }));
    }

    var domains = document.getElementById("domainChart");
    if (domains) {
      charts.push(new Chart(domains, {
        type: "bar",
        data: {
          labels: data.domains.labels,
          datasets: [{ label: "% completed", data: data.domains.values,
                       backgroundColor: css("--primary"), borderRadius: 6 }]
        },
        options: {
          indexAxis: "y", maintainAspectRatio: false,
          scales: {
            x: { min: 0, max: 100, ticks: { color: muted }, grid: { color: border } },
            y: { ticks: { color: text }, grid: { display: false } }
          },
          plugins: { legend: { display: false } }
        }
      }));
    }
  }

  build();
  document.addEventListener("ga:themechange", build);
})();
