/*
 * PrintPipe live slice status + download UI.
 *
 * Polls GET /runs/<id>/status.json on an interval, renders a small status chip
 * (idle / slicing... / sliced / failed), and once a usable bundle exists reveals
 * a Download button plus an optional print-time / filament summary line.
 *
 * Public API:
 *   window.PrintPipeStatus.init({ runId, mountId, downloadUrl });
 *
 *   runId       (string, required)  run id used to build /runs/<id>/status.json
 *   mountId     (string, required)  id of an element to render the chip into
 *   downloadUrl (string, optional)  explicit artifact URL for the Download button.
 *                                   When omitted, the first usable bundle / gcode
 *                                   artifact from status.json is used instead.
 *
 * No build step, no dependencies. Plain DOM + fetch.
 */
(function () {
  "use strict";

  var POLL_INTERVAL_MS = 1500;

  // status.progress.state values that mean "stop polling".
  var TERMINAL_STATES = {
    succeeded: true,
    failed: true,
    invalid_manifest: true,
    unreadable_manifest: true,
    invalid_report: true,
    unreadable_report: true
  };

  // Map a raw progress state to a coarse chip phase.
  function chipPhase(state) {
    if (state === "succeeded") {
      return "done";
    }
    if (state === "failed") {
      return "failed";
    }
    if (
      state === "invalid_manifest" ||
      state === "unreadable_manifest" ||
      state === "invalid_report" ||
      state === "unreadable_report"
    ) {
      return "failed";
    }
    if (state === "running" || state === "in_progress") {
      return "slicing";
    }
    // missing_manifest, missing_report, unknown -> not started yet.
    return "idle";
  }

  function chipLabel(phase, progress) {
    switch (phase) {
      case "done":
        return "sliced ✓";
      case "failed":
        return "failed";
      case "slicing":
        if (progress && typeof progress.percent === "number" && progress.percent > 0) {
          return "slicing… " + progress.percent + "%";
        }
        return "slicing…";
      default:
        return "idle";
    }
  }

  // Pull the canonical progress state out of a status payload, tolerating a few
  // shapes the status route might ship.
  function readState(status) {
    if (!status || typeof status !== "object") {
      return "unknown";
    }
    if (status.progress && typeof status.progress.state === "string") {
      return status.progress.state;
    }
    if (typeof status.state === "string") {
      return status.state;
    }
    return "unknown";
  }

  function readProgress(status) {
    if (status && status.progress && typeof status.progress === "object") {
      return status.progress;
    }
    return null;
  }

  // An artifact is downloadable when it is present and readable.
  function artifactUsable(artifact) {
    if (!artifact || typeof artifact !== "object") {
      return false;
    }
    if (artifact.present !== true) {
      return false;
    }
    return artifact.readable !== false;
  }

  function lowerStr(value) {
    return typeof value === "string" ? value.toLowerCase() : "";
  }

  // Build the public artifact download URL for a run-relative path,
  // matching the GET /runs/<id>/artifacts/<path> contract.
  function artifactUrlFor(runId, relativePath) {
    var segments = String(relativePath).split("/").map(function (segment) {
      return encodeURIComponent(segment);
    });
    return (
      "/runs/" + encodeURIComponent(runId) + "/artifacts/" + segments.join("/")
    );
  }

  // Choose the best downloadable artifact: prefer the sliced .3mf bundle,
  // then any gcode/bgcode, falling back to the first usable artifact.
  function pickDownload(runId, status) {
    if (!status || !Array.isArray(status.artifacts)) {
      return null;
    }
    var usable = status.artifacts.filter(artifactUsable);
    if (!usable.length) {
      return null;
    }

    function find(predicate) {
      for (var i = 0; i < usable.length; i += 1) {
        if (predicate(usable[i])) {
          return usable[i];
        }
      }
      return null;
    }

    var bundle =
      find(function (artifact) {
        return lowerStr(artifact.kind).indexOf("bundle") !== -1;
      }) ||
      find(function (artifact) {
        return lowerStr(artifact.path).slice(-4) === ".3mf";
      });

    var gcode = find(function (artifact) {
      var ext = lowerStr(artifact.path);
      return ext.slice(-6) === ".gcode" || ext.slice(-7) === ".bgcode";
    });

    var chosen = bundle || gcode || usable[0];
    if (!chosen || typeof chosen.path !== "string" || !chosen.path) {
      return null;
    }
    return {
      url: artifactUrlFor(runId, chosen.path),
      label: chosen.label || chosen.path.split("/").pop()
    };
  }

  // Find slice metrics (time / filament / cost) wherever the status route
  // chose to expose them. All fields are optional.
  function readMetrics(status) {
    if (!status || typeof status !== "object") {
      return null;
    }
    var sources = [status.metrics, status.slice, status.slice_result, status.slice_metrics];
    for (var i = 0; i < sources.length; i += 1) {
      var source = sources[i];
      if (source && typeof source === "object") {
        if (
          source.time_seconds != null ||
          source.filament_g != null ||
          source.cost != null
        ) {
          return source;
        }
        // Some shapes nest metrics one level deeper.
        if (source.metrics && typeof source.metrics === "object") {
          return source.metrics;
        }
      }
    }
    return null;
  }

  function formatDuration(totalSeconds) {
    var seconds = Math.max(0, Math.round(Number(totalSeconds)));
    var hours = Math.floor(seconds / 3600);
    var minutes = Math.floor((seconds % 3600) / 60);
    var parts = [];
    if (hours) {
      parts.push(hours + "h");
    }
    if (minutes || hours) {
      parts.push(minutes + "m");
    }
    parts.push((seconds % 60) + "s");
    return parts.join(" ");
  }

  function formatMetrics(metrics) {
    if (!metrics) {
      return "";
    }
    var parts = [];
    if (typeof metrics.time_seconds === "number" && metrics.time_seconds > 0) {
      parts.push("⏱ " + formatDuration(metrics.time_seconds));
    }
    if (typeof metrics.filament_g === "number" && metrics.filament_g > 0) {
      parts.push("⚙ " + metrics.filament_g.toFixed(2) + " g");
    }
    if (typeof metrics.cost === "number" && metrics.cost > 0) {
      parts.push("$" + metrics.cost.toFixed(2));
    }
    return parts.join("  ·  ");
  }

  // Build the DOM skeleton inside the mount element once.
  function buildView(mount) {
    mount.classList.add("pp-status");
    mount.innerHTML =
      '<span class="pp-status-chip" data-phase="idle">' +
      '<span class="pp-status-dot"></span>' +
      '<span class="pp-status-text">idle</span>' +
      "</span>" +
      '<a class="pp-status-download" hidden>Download</a>' +
      '<span class="pp-status-metrics" hidden></span>';
    return {
      chip: mount.querySelector(".pp-status-chip"),
      text: mount.querySelector(".pp-status-text"),
      download: mount.querySelector(".pp-status-download"),
      metrics: mount.querySelector(".pp-status-metrics")
    };
  }

  function render(view, runId, status, fallbackUrl) {
    var state = readState(status);
    var phase = chipPhase(state);
    var progress = readProgress(status);

    view.chip.setAttribute("data-phase", phase);
    view.text.textContent = chipLabel(phase, progress);

    var download = null;
    if (fallbackUrl) {
      download = { url: fallbackUrl, label: "Download" };
    } else if (phase === "done") {
      download = pickDownload(runId, status);
    }

    if (download) {
      view.download.href = download.url;
      view.download.textContent = "Download " + download.label;
      view.download.setAttribute("download", "");
      view.download.hidden = false;
    } else {
      view.download.hidden = true;
    }

    var metricsText = phase === "done" ? formatMetrics(readMetrics(status)) : "";
    if (metricsText) {
      view.metrics.textContent = metricsText;
      view.metrics.hidden = false;
    } else {
      view.metrics.hidden = true;
    }
  }

  function init(options) {
    options = options || {};
    var runId = options.runId;
    var mountId = options.mountId;
    var fallbackUrl = options.downloadUrl || null;

    if (!runId || !mountId) {
      return null;
    }
    var mount = document.getElementById(mountId);
    if (!mount) {
      return null;
    }

    var view = buildView(mount);
    var statusUrl = "/runs/" + encodeURIComponent(runId) + "/status.json";
    var timer = null;
    var stopped = false;

    function stop() {
      stopped = true;
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
    }

    function schedule() {
      if (stopped) {
        return;
      }
      timer = setTimeout(poll, POLL_INTERVAL_MS);
    }

    function poll() {
      if (stopped) {
        return;
      }
      fetch(statusUrl, { headers: { Accept: "application/json" } })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("status " + response.status);
          }
          return response.json();
        })
        .then(function (status) {
          if (stopped) {
            return;
          }
          render(view, runId, status, fallbackUrl);
          if (TERMINAL_STATES[readState(status)] === true) {
            stop();
          } else {
            schedule();
          }
        })
        .catch(function () {
          if (stopped) {
            return;
          }
          // Transient errors (mid-write, server busy): keep polling.
          schedule();
        });
    }

    poll();

    return { stop: stop, poll: poll };
  }

  window.PrintPipeStatus = { init: init };
})();
