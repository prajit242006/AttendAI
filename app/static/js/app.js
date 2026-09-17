/* AttendAI - shared front-end helpers.
   Everything hangs off one global object so the page scripts stay tidy. */

window.AttendAI = window.AttendAI || {};

(function (app) {
  "use strict";

  /* CSRF token for fetch() calls. Flask-WTF accepts the X-CSRFToken header. */
  app.csrfToken = function () {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  };

  /* POST JSON and always return a parsed object, even on an error status. */
  app.postJSON = function (url, payload) {
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": app.csrfToken()
      },
      body: JSON.stringify(payload)
    }).then(function (response) {
      return response.json().catch(function () {
        return { success: false, message: "The server sent an unexpected reply." };
      });
    }).catch(function () {
      return { success: false, message: "Cannot reach the server. Is python run.py still running?" };
    });
  };

  app.getJSON = function (url) {
    return fetch(url, { headers: { Accept: "application/json" } })
      .then(function (response) { return response.json(); })
      .catch(function () { return { success: false }; });
  };

  /* Bootstrap toast. */
  app.toast = function (message, tone) {
    var host = document.getElementById("toastHost");
    if (!host) { return; }
    var wrapper = document.createElement("div");
    wrapper.className = "toast align-items-center text-bg-" + (tone || "dark") + " border-0";
    wrapper.setAttribute("role", "status");
    wrapper.innerHTML =
      '<div class="d-flex"><div class="toast-body">' + message + "</div>" +
      '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>';
    host.appendChild(wrapper);
    var toast = new bootstrap.Toast(wrapper, { delay: 4000 });
    toast.show();
    wrapper.addEventListener("hidden.bs.toast", function () { wrapper.remove(); });
  };

  /* Mobile sidebar. */
  document.addEventListener("DOMContentLoaded", function () {
    var toggle = document.getElementById("sidebarToggle");
    var sidebar = document.getElementById("sidebar");
    var scrim = document.getElementById("sidebarScrim");
    if (!toggle || !sidebar || !scrim) { return; }

    function close() { sidebar.classList.remove("open"); scrim.classList.remove("show"); }
    toggle.addEventListener("click", function () {
      sidebar.classList.toggle("open");
      scrim.classList.toggle("show");
    });
    scrim.addEventListener("click", close);
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") { close(); }
    });
  });
}(window.AttendAI));
