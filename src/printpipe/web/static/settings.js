/*
 * PrintPipe slicer-settings panel.
 *
 * Fetches the resolved slicer settings for a material, renders editable
 * controls, and POSTs the changed values as a JSON override map to
 * /runs/<run_id>/reslice. No build step, no framework: plain ES module
 * loaded as a classic <script> and exposed on window.PrintPipeSettings.
 *
 * Public API:
 *   window.PrintPipeSettings.init({ material, runId, mountId })
 */
(function () {
  "use strict";

  // Bambu process settings are stored as single-element string lists
  // (e.g. ["0.2"]). These helpers normalise between that wire format and
  // the plain values the form controls work with.
  function firstValue(raw, fallback) {
    if (Array.isArray(raw)) {
      return raw.length ? String(raw[0]) : fallback;
    }
    if (raw === undefined || raw === null) {
      return fallback;
    }
    return String(raw);
  }

  function asConfigValue(value) {
    // Mirror the Bambu config shape so overrides merge cleanly server-side.
    return [String(value)];
  }

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        if (key === "class") {
          node.className = attrs[key];
        } else if (key === "text") {
          node.textContent = attrs[key];
        } else if (key === "html") {
          node.innerHTML = attrs[key];
        } else if (key.startsWith("on") && typeof attrs[key] === "function") {
          node.addEventListener(key.slice(2).toLowerCase(), attrs[key]);
        } else {
          node.setAttribute(key, attrs[key]);
        }
      });
    }
    (children || []).forEach(function (child) {
      if (child === null || child === undefined) {
        return;
      }
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    });
    return node;
  }

  const LAYER_HEIGHTS = ["0.12", "0.16", "0.20", "0.28"];
  const SUPPORT_TYPES = [
    { value: "normal(auto)", label: "Normal (auto)" },
    { value: "tree(auto)", label: "Tree (auto)" },
  ];

  function fieldRow(labelText, control, hint) {
    return el("label", { class: "ppset-field" }, [
      el("span", { class: "ppset-label", text: labelText }),
      control,
      hint ? el("span", { class: "ppset-hint", text: hint }) : null,
    ]);
  }

  function buildSelect(options, current) {
    const select = el("select", { class: "ppset-select" });
    options.forEach(function (opt) {
      const value = typeof opt === "string" ? opt : opt.value;
      const label = typeof opt === "string" ? opt : opt.label;
      const optionNode = el("option", { value: value, text: label });
      if (value === current) {
        optionNode.selected = true;
      }
      select.appendChild(optionNode);
    });
    return select;
  }

  function nearestLayerHeight(value) {
    // Snap arbitrary resolved heights (e.g. "0.2") to the closest preset.
    const target = parseFloat(value);
    if (!isFinite(target)) {
      return "0.20";
    }
    let best = LAYER_HEIGHTS[0];
    let bestDelta = Infinity;
    LAYER_HEIGHTS.forEach(function (candidate) {
      const delta = Math.abs(parseFloat(candidate) - target);
      if (delta < bestDelta) {
        bestDelta = delta;
        best = candidate;
      }
    });
    return best;
  }

  function normaliseSupportType(value) {
    const lowered = String(value || "").toLowerCase();
    if (lowered.indexOf("tree") !== -1) {
      return "tree(auto)";
    }
    return "normal(auto)";
  }

  function isSupportEnabled(value) {
    const lowered = firstValue(value, "0").toLowerCase();
    return lowered === "1" || lowered === "true" || lowered === "yes";
  }

  function renderPanel(root, process, state) {
    root.innerHTML = "";

    const layerCurrent = nearestLayerHeight(firstValue(process.layer_height, "0.20"));
    const layerSelect = buildSelect(LAYER_HEIGHTS, layerCurrent);

    const wallInput = el("input", {
      class: "ppset-number",
      type: "number",
      min: "1",
      max: "6",
      step: "1",
      value: firstValue(process.wall_loops, "3"),
    });

    const infillValue = firstValue(process.sparse_infill_density, "15").replace("%", "");
    const infillRange = el("input", {
      class: "ppset-range",
      type: "range",
      min: "0",
      max: "100",
      step: "1",
      value: infillValue,
    });
    const infillReadout = el("output", { class: "ppset-readout", text: infillValue + "%" });
    infillRange.addEventListener("input", function () {
      infillReadout.textContent = infillRange.value + "%";
    });

    const supportToggle = el("input", {
      class: "ppset-toggle-input",
      type: "checkbox",
    });
    supportToggle.checked = isSupportEnabled(process.enable_support);

    const supportSelect = buildSelect(
      SUPPORT_TYPES,
      normaliseSupportType(firstValue(process.support_type, "normal(auto)"))
    );

    const speedInput = el("input", {
      class: "ppset-number",
      type: "number",
      min: "1",
      max: "500",
      step: "1",
      value: firstValue(process.outer_wall_speed, "120"),
    });

    function syncSupportType() {
      supportSelect.disabled = !supportToggle.checked;
    }
    supportToggle.addEventListener("change", syncSupportType);
    syncSupportType();

    const grid = el("div", { class: "ppset-grid" }, [
      fieldRow("Layer height", layerSelect, "mm — finer = smoother, slower"),
      fieldRow("Wall loops", wallInput, "1–6 perimeters"),
      el("div", { class: "ppset-field ppset-field-wide" }, [
        el("span", { class: "ppset-label", text: "Infill density" }),
        el("div", { class: "ppset-range-row" }, [infillRange, infillReadout]),
        el("span", { class: "ppset-hint", text: "Sparse infill — 0–100%" }),
      ]),
      el("label", { class: "ppset-field ppset-toggle-field" }, [
        el("span", { class: "ppset-label", text: "Supports" }),
        el("span", { class: "ppset-toggle" }, [
          supportToggle,
          el("span", { class: "ppset-toggle-track", "aria-hidden": "true" }),
        ]),
      ]),
      fieldRow("Support type", supportSelect, "Active only when supports are on"),
      fieldRow("Outer wall speed", speedInput, "mm/s"),
    ]);

    const sliceButton = el("button", {
      class: "ppset-slice",
      type: "button",
      text: "Slice",
    });

    const status = el("p", { class: "ppset-status", "aria-live": "polite" });
    const applied = el("div", { class: "ppset-applied" });

    function collectOverrides() {
      return {
        layer_height: asConfigValue(layerSelect.value),
        wall_loops: asConfigValue(wallInput.value),
        sparse_infill_density: asConfigValue(infillRange.value + "%"),
        enable_support: asConfigValue(supportToggle.checked ? "1" : "0"),
        support_type: asConfigValue(supportSelect.value),
        outer_wall_speed: asConfigValue(speedInput.value),
      };
    }

    sliceButton.addEventListener("click", function () {
      submitReslice(state.runId, collectOverrides(), state.csrfToken || "", {
        button: sliceButton,
        status: status,
        applied: applied,
      });
    });

    const card = el("section", { class: "ppset-card" }, [
      el("header", { class: "ppset-head" }, [
        el("h2", { class: "ppset-title", text: "Slicer Settings" }),
        el("span", { class: "ppset-material", text: state.material }),
      ]),
      grid,
      el("div", { class: "ppset-actions" }, [sliceButton, status]),
      applied,
    ]);

    root.appendChild(card);
  }

  function renderApplied(container, payload) {
    container.innerHTML = "";
    const process = (payload && (payload.applied || payload.process)) || {};
    const keys = Object.keys(process);
    if (!keys.length) {
      return;
    }
    const rows = keys.sort().map(function (key) {
      return el("div", { class: "ppset-applied-row" }, [
        el("span", { class: "ppset-applied-key", text: key }),
        el("span", { class: "ppset-applied-value", text: firstValue(process[key], "—") }),
      ]);
    });
    container.appendChild(
      el("div", { class: "ppset-applied-box" }, [
        el("h3", { class: "ppset-applied-title", text: "Applied to re-slice" }),
        el("div", { class: "ppset-applied-grid" }, rows),
      ])
    );
  }

  function setStatus(node, text, tone) {
    node.textContent = text;
    node.className = "ppset-status" + (tone ? " ppset-status-" + tone : "");
  }

  function submitReslice(runId, overrides, csrfToken, ui) {
    ui.button.disabled = true;
    setStatus(ui.status, "Slicing…", "busy");
    ui.applied.innerHTML = "";

    const headers = { "Content-Type": "application/json" };
    if (csrfToken) {
      headers["X-PrintPipe-CSRF"] = csrfToken;
    }

    fetch("/runs/" + encodeURIComponent(runId) + "/reslice", {
      method: "POST",
      headers: headers,
      body: JSON.stringify({ process_overrides: overrides }),
    })
      .then(function (response) {
        return response
          .json()
          .catch(function () {
            return {};
          })
          .then(function (payload) {
            return { ok: response.ok, status: response.status, payload: payload };
          });
      })
      .then(function (result) {
        ui.button.disabled = false;
        if (!result.ok) {
          const message =
            (result.payload && (result.payload.error || result.payload.message)) ||
            "Re-slice failed (HTTP " + result.status + ")";
          setStatus(ui.status, message, "error");
          return;
        }
        setStatus(ui.status, "Re-slice complete.", "ok");
        renderApplied(ui.applied, result.payload);
      })
      .catch(function (err) {
        ui.button.disabled = false;
        setStatus(ui.status, "Network error: " + err.message, "error");
      });
  }

  function init(config) {
    const options = config || {};
    const material = options.material || "Generic PLA";
    const runId = options.runId;
    const csrfToken = options.csrfToken || "";
    const mountId = options.mountId || "ppset-mount";
    const root = document.getElementById(mountId);

    if (!root) {
      console.warn("PrintPipeSettings: mount #" + mountId + " not found");
      return;
    }
    if (!runId) {
      root.innerHTML = '<p class="ppset-status ppset-status-error">Missing run id.</p>';
      return;
    }

    root.innerHTML = '<p class="ppset-status ppset-status-busy">Loading slicer settings…</p>';

    fetch("/api/settings?material=" + encodeURIComponent(material))
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }
        return response.json();
      })
      .then(function (payload) {
        const process = (payload && payload.process) || {};
        renderPanel(root, process, { material: material, runId: runId, csrfToken: csrfToken });
      })
      .catch(function (err) {
        root.innerHTML =
          '<p class="ppset-status ppset-status-error">Could not load settings: ' +
          err.message +
          "</p>";
      });
  }

  window.PrintPipeSettings = { init: init };
})();
