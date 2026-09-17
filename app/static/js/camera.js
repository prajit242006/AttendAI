/* AttendAI - webcam access and face registration.
   The browser owns the camera; frames are sent to Flask as base64 JPEG
   and OpenCV does the detection and recognition on the server. */

window.AttendAI = window.AttendAI || {};

(function (app) {
  "use strict";

  /* ---------------------------------------------------------------
     Small wrapper around getUserMedia + a hidden canvas.
     --------------------------------------------------------------- */
  function Camera(videoEl, canvasEl, statusEl) {
    this.video = videoEl;
    this.canvas = canvasEl;
    this.status = statusEl;
    this.stream = null;
  }

  Camera.prototype.setStatus = function (text, tone) {
    if (!this.status) { return; }
    this.status.textContent = text;
    this.status.className = "camera-status" + (tone ? " " + tone : "");
  };

  Camera.prototype.start = function () {
    var self = this;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      self.setStatus("This browser cannot open a camera. Use Chrome or Edge.", "error");
      return Promise.reject(new Error("getUserMedia unsupported"));
    }
    return navigator.mediaDevices
      .getUserMedia({ video: { width: 640, height: 480, facingMode: "user" }, audio: false })
      .then(function (stream) {
        self.stream = stream;
        self.video.srcObject = stream;
        self.setStatus("Camera ready.", "ok");
        return stream;
      })
      .catch(function (error) {
        var message = "Camera error: " + error.name;
        if (error.name === "NotAllowedError") {
          message = "Camera permission denied. Allow camera access in the address bar and reload.";
        } else if (error.name === "NotFoundError") {
          message = "No camera found. Plug in a webcam and reload.";
        } else if (error.name === "NotReadableError") {
          message = "The camera is already in use by another program. Close it and reload.";
        }
        self.setStatus(message, "error");
        throw error;
      });
  };

  Camera.prototype.stop = function () {
    if (this.stream) {
      this.stream.getTracks().forEach(function (track) { track.stop(); });
      this.stream = null;
    }
  };

  /* Grab the current video frame as a base64 JPEG string. */
  Camera.prototype.grab = function (quality) {
    var width = this.video.videoWidth;
    var height = this.video.videoHeight;
    if (!width || !height) { return null; }
    this.canvas.width = width;
    this.canvas.height = height;
    this.canvas.getContext("2d").drawImage(this.video, 0, 0, width, height);
    return this.canvas.toDataURL("image/jpeg", quality || 0.85);
  };

  app.Camera = Camera;

  /* ---------------------------------------------------------------
     Face registration page
     --------------------------------------------------------------- */
  app.faceRegistration = {
    init: function (options) {
      var video = document.getElementById("cameraFeed");
      var canvas = document.getElementById("captureCanvas");
      var statusEl = document.getElementById("cameraStatus");
      if (!video || !canvas) { return; }

      var camera = new Camera(video, canvas, statusEl);
      var samples = [];

      var captureBtn = document.getElementById("captureBtn");
      var retakeBtn = document.getElementById("retakeBtn");
      var saveBtn = document.getElementById("saveFaceBtn");
      var countEl = document.getElementById("captureCount");
      var progressEl = document.getElementById("captureProgress");
      var strip = document.getElementById("thumbStrip");

      camera.start().catch(function () { /* the status box already explains it */ });

      function refresh() {
        countEl.textContent = samples.length;
        var percent = Math.min(100, Math.round((samples.length / options.target) * 100));
        progressEl.style.width = percent + "%";
        saveBtn.disabled = samples.length < options.minimum;
      }

      captureBtn.addEventListener("click", function () {
        var frame = camera.grab();
        if (!frame) {
          camera.setStatus("The camera is still starting. Try again in a second.", "warn");
          return;
        }
        captureBtn.disabled = true;
        camera.setStatus("Checking the frame…");

        app.postJSON(options.previewUrl, { image: frame }).then(function (data) {
          captureBtn.disabled = false;
          if (!data.success) {
            camera.setStatus(data.message || "The frame could not be read.", "error");
            return;
          }
          if (data.status !== "OK") {
            camera.setStatus(data.message, "warn");
            return;
          }
          samples.push(frame);
          var thumb = document.createElement("img");
          thumb.src = frame;
          thumb.alt = "Face sample " + samples.length;
          strip.appendChild(thumb);
          camera.setStatus("Sample " + samples.length + " captured. Change the angle slightly.", "ok");
          refresh();
        });
      });

      retakeBtn.addEventListener("click", function () {
        samples = [];
        strip.innerHTML = "";
        camera.setStatus("Samples cleared. Start capturing again.", "warn");
        refresh();
      });

      saveBtn.addEventListener("click", function () {
        saveBtn.disabled = true;
        camera.setStatus("Saving the face profile and training the model…");

        app.postJSON(options.saveUrl, {
          student_id: options.studentId,
          images: samples
        }).then(function (data) {
          if (!data.success) {
            camera.setStatus(data.message, "error");
            app.toast(data.message, "danger");
            saveBtn.disabled = false;
            return;
          }
          camera.setStatus("FACE REGISTERED SUCCESSFULLY — " + data.stored + " samples stored.", "ok");
          app.toast("FACE REGISTERED SUCCESSFULLY for " + options.registerNumber, "success");
          if (data.warning) { app.toast(data.warning, "warning"); }
          setTimeout(function () { window.location.reload(); }, 1600);
        });
      });

      window.addEventListener("beforeunload", function () { camera.stop(); });
      refresh();
    }
  };
}(window.AttendAI));
