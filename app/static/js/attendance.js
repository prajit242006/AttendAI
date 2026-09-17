/* AttendAI - live attendance page.
   A frame is sent to /api/attendance/recognize every few seconds; the reply
   drives the recognition card, the liveness challenge and the live table. */

window.AttendAI = window.AttendAI || {};

(function (app) {
  "use strict";

  app.liveAttendance = {
    init: function (options) {
      var video = document.getElementById("cameraFeed");
      var canvas = document.getElementById("captureCanvas");
      var statusEl = document.getElementById("cameraStatus");
      if (!video || !canvas) { return; }

      var camera = new app.Camera(video, canvas, statusEl);
      var scanning = options.active;
      var busy = false;

      var nameEl = document.getElementById("recogName");
      var regEl = document.getElementById("recogReg");
      var messageEl = document.getElementById("recogMessage");
      var metaEl = document.getElementById("recogMeta");
      var cardEl = document.getElementById("recognitionCard");
      var flagFace = document.getElementById("flagFace");
      var flagLive = document.getElementById("flagLive");
      var flagMark = document.getElementById("flagMark");
      var challengeBox = document.getElementById("challengeBox");
      var challengeText = document.getElementById("challengeText");
      var toggleBtn = document.getElementById("scanToggle");
      var clockEl = document.getElementById("clock");
      var checksEl = document.getElementById("totalChecks");

      /* ---- clock ---- */
      function tickClock() {
        if (clockEl) { clockEl.textContent = new Date().toLocaleTimeString(); }
      }
      tickClock();
      setInterval(tickClock, 1000);

      /* ---- recognition card ---- */
      function setFlag(el, state) {
        el.className = "flag" + (state === true ? " on" : state === false ? " off" : "");
      }

      function render(data) {
        var student = data.student || {};
        var tone = "";
        var face = null, live = null, mark = null;

        switch (data.state) {
          case "NO_FACE":
            nameEl.textContent = "No face detected";
            regEl.innerHTML = "&nbsp;";
            face = false;
            break;
          case "MULTIPLE_FACES":
            nameEl.textContent = "Multiple faces";
            regEl.innerHTML = "&nbsp;";
            tone = "state-warn";
            face = false;
            break;
          case "UNKNOWN":
            nameEl.textContent = "UNKNOWN PERSON";
            regEl.innerHTML = "&nbsp;";
            tone = "state-bad";
            face = true; live = null; mark = false;
            break;
          case "NOT_ENROLLED":
            nameEl.textContent = student.name || "Not enrolled";
            regEl.textContent = student.register_number || "";
            tone = "state-warn";
            face = true; mark = false;
            break;
          case "LIVENESS_PENDING":
            nameEl.textContent = student.name || "";
            regEl.textContent = "Register No: " + (student.register_number || "");
            tone = "state-warn";
            face = true;
            break;
          case "LIVENESS_FAILED":
            nameEl.textContent = student.name || "";
            regEl.textContent = "Register No: " + (student.register_number || "");
            tone = "state-bad";
            face = true; live = false; mark = false;
            break;
          case "MARKED":
            nameEl.textContent = (student.name || "").toUpperCase();
            regEl.textContent = "Register No: " + (student.register_number || "");
            tone = "state-ok";
            face = true; live = true; mark = true;
            break;
          case "ALREADY_MARKED":
            nameEl.textContent = (student.name || "").toUpperCase();
            regEl.textContent = "Register No: " + (student.register_number || "");
            tone = "state-ok";
            face = true; live = true; mark = true;
            break;
          default:
            nameEl.textContent = data.message || "Waiting…";
            regEl.innerHTML = "&nbsp;";
        }

        cardEl.className = "recognition-card " + tone;
        messageEl.textContent = data.message || "";
        setFlag(flagFace, face);
        setFlag(flagLive, live);
        setFlag(flagMark, mark);

        metaEl.textContent = data.confidence !== undefined && data.confidence !== null
          ? "Confidence " + data.confidence + "%  (LBPH distance " + data.distance + ")"
          : "\u00A0";

        if (data.state === "LIVENESS_PENDING" && data.challenge) {
          challengeText.textContent = data.challenge;
          challengeBox.classList.remove("d-none");
        } else {
          challengeBox.classList.add("d-none");
        }
      }

      /* ---- live table ---- */
      function refreshTable() {
        app.getJSON(options.recordsUrl).then(function (data) {
          if (!data || !data.success) { return; }
          if (checksEl) { checksEl.textContent = data.total_checks; }
          var body = document.getElementById("liveTableBody");
          if (!body) { return; }
          if (!data.rows.length) { return; }

          body.innerHTML = data.rows.map(function (row) {
            var tone = row.status === "PRESENT" ? "success"
              : row.status === "LATE" ? "warning"
              : row.status === "ABSENT" ? "danger" : "secondary";
            return "<tr>" +
              '<td><span class="reg-chip">' + row.register_number + "</span></td>" +
              "<td>" + row.name + "</td>" +
              "<td>" + row.first_detection + "</td>" +
              "<td>" + (row.liveness === "VERIFIED"
                ? '<span class="badge bg-success">VERIFIED</span>' : "—") + "</td>" +
              "<td>" + row.presence + "% <small class='text-muted'>(" +
                row.presence_count + "/" + row.total_checks + ")</small></td>" +
              '<td><span class="badge bg-' + tone + '">' + row.status + "</span></td>" +
              "</tr>";
          }).join("");
        });
      }

      /* ---- scanning loop ---- */
      function scan() {
        if (!scanning || busy) { return; }
        var frame = camera.grab(0.8);
        if (!frame) { return; }
        busy = true;

        app.postJSON(options.recognizeUrl, {
          session_id: options.sessionId,
          image: frame
        }).then(function (data) {
          busy = false;
          if (!data.success) {
            camera.setStatus(data.message || "Recognition failed.", "error");
            render({ state: data.state || "ERROR", message: data.message });
            if (data.state === "SESSION_ENDED" || data.state === "INVALID_SESSION") {
              scanning = false;
            }
            return;
          }
          camera.setStatus("Scanning…", "ok");
          render(data);
          if (data.state === "MARKED") {
            app.toast(data.student.name + " marked " + data.record.status, "success");
          }
          if (data.ticked || data.state === "MARKED" || data.state === "ALREADY_MARKED") {
            refreshTable();
          }
        });
      }

      if (toggleBtn) {
        toggleBtn.addEventListener("click", function () {
          scanning = !scanning;
          toggleBtn.innerHTML = scanning
            ? '<i class="bi bi-pause-circle"></i> Pause scanning'
            : '<i class="bi bi-play-circle"></i> Resume scanning';
          camera.setStatus(scanning ? "Scanning…" : "Scanning paused.", scanning ? "ok" : "warn");
        });
      }

      if (options.active) {
        camera.start().then(function () {
          setInterval(scan, options.intervalMs || 2500);
          setInterval(refreshTable, 8000);
        }).catch(function () { scanning = false; });
      } else {
        camera.setStatus("This session has ended. The camera stays off.", "warn");
      }

      window.addEventListener("beforeunload", function () { camera.stop(); });
    }
  };
}(window.AttendAI));
