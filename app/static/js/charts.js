/* AttendAI - Chart.js setup.
   All values come from data-* attributes rendered by Jinja from the
   database, so nothing here is hard-coded sample data. */

window.AttendAI = window.AttendAI || {};

(function (app) {
  "use strict";

  var COLORS = {
    brand: "#2e4bc6",
    success: "#21916a",
    warning: "#d98b17",
    danger: "#d6455a",
    muted: "#97a0b5"
  };

  function read(el, key) {
    var raw = el.getAttribute("data-" + key);
    try { return JSON.parse(raw); } catch (error) { return []; }
  }

  function trendChart() {
    var el = document.getElementById("trendChart");
    if (!el) { return; }
    new Chart(el, {
      type: "line",
      data: {
        labels: read(el, "labels"),
        datasets: [
          { label: "Present", data: read(el, "present"), borderColor: COLORS.success,
            backgroundColor: "rgba(33,145,106,.12)", tension: .35, fill: true },
          { label: "Late", data: read(el, "late"), borderColor: COLORS.warning, tension: .35 },
          { label: "Absent", data: read(el, "absent"), borderColor: COLORS.danger, tension: .35 }
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
      }
    });
  }

  function subjectChart() {
    var el = document.getElementById("subjectChart");
    if (!el) { return; }
    var values = read(el, "values");
    new Chart(el, {
      type: "bar",
      data: {
        labels: read(el, "labels"),
        datasets: [{
          label: "Attendance %",
          data: values,
          backgroundColor: values.map(function (value) {
            return value < 75 ? COLORS.danger : COLORS.brand;
          }),
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, max: 100 } }
      }
    });
  }

  function statusChart() {
    var el = document.getElementById("statusChart");
    if (!el) { return; }
    new Chart(el, {
      type: "doughnut",
      data: {
        labels: read(el, "labels"),
        datasets: [{
          data: read(el, "values"),
          backgroundColor: [COLORS.success, COLORS.warning, COLORS.danger, COLORS.muted]
        }]
      },
      options: { responsive: true, plugins: { legend: { position: "bottom" } } }
    });
  }

  app.charts = {
    dashboard: function () { trendChart(); subjectChart(); },
    analytics: function () { trendChart(); subjectChart(); statusChart(); },
    studentSplit: function () {
      var el = document.getElementById("studentSplit");
      if (!el) { return; }
      new Chart(el, {
        type: "doughnut",
        data: {
          labels: ["Present", "Late", "Absent", "Review"],
          datasets: [{
            data: [
              Number(el.dataset.present || 0),
              Number(el.dataset.late || 0),
              Number(el.dataset.absent || 0),
              Number(el.dataset.review || 0)
            ],
            backgroundColor: [COLORS.success, COLORS.warning, COLORS.danger, COLORS.muted]
          }]
        },
        options: { responsive: true, plugins: { legend: { position: "bottom" } } }
      });
    }
  };
}(window.AttendAI));
