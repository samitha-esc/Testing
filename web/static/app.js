"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let currentMode = "PLAY";
let mappingSources = { absolute: [], relative: [], trigger: [] };

// ---------------------------------------------------------------- state poll
async function pollState() {
  try {
    const r = await fetch("/state", { cache: "no-store" });
    const s = await r.json();
    renderState(s);
    setConn(true);
  } catch (e) {
    setConn(false);
  }
}

function setConn(ok) {
  const el = $("#conn-status");
  el.textContent = ok ? "● live" : "● offline";
  el.className = "pill " + (ok ? "pill-on" : "pill-off");
}

function renderState(s) {
  if (!s || !s.mode) return;

  // mode buttons
  if (s.mode !== currentMode) {
    currentMode = s.mode;
    $$(".mode-btn").forEach((b) =>
      b.classList.toggle("active", b.dataset.mode === currentMode));
    $("#active-mode").textContent = currentMode;
  }

  // fps + midi
  $("#fps").textContent = (s.fps != null ? s.fps.toFixed(0) : "–") + " fps";
  const midi = $("#midi-status");
  if (s.midi) { midi.textContent = "MIDI: " + s.midi; midi.className = "pill pill-on"; }
  else { midi.textContent = "MIDI: none"; midi.className = "pill pill-off"; }

  // hand state + markers
  $("#hand-state").textContent = s.hand || "—";
  const mk = s.markers || {};
  $$(".marker").forEach((el) => {
    const on = mk[el.dataset.m];
    el.querySelector("i").className = on ? "on" : "";
  });

  // OOB + calibrating
  $("#oob-alert").classList.toggle("hidden", !s.oob);
  $(".video-wrap").classList.toggle("oob", !!s.oob);
  $("#calibrating").classList.toggle("hidden", !s.calibrating);

  renderControls(s.controls || []);
}

function renderControls(controls) {
  const box = $("#controls");
  if (!controls.length) {
    box.innerHTML = '<div class="controls-empty">No controls mapped for this mode.</div>';
    return;
  }
  // Reuse DOM nodes by id to keep bar animation smooth.
  const seen = new Set();
  controls.forEach((c) => {
    seen.add(c.id);
    let el = document.getElementById("ctrl-" + c.id);
    if (!el) {
      el = document.createElement("div");
      el.id = "ctrl-" + c.id;
      el.className = "control";
      el.innerHTML =
        '<div class="control-head">' +
          '<span class="label"></span>' +
          '<span class="meta"></span>' +
          '<span class="val"></span>' +
        '</div><div class="bar"><div></div></div>';
      box.appendChild(el);
    }
    el.classList.toggle("active", !!c.active);
    el.querySelector(".label").textContent = c.label;
    el.querySelector(".meta").textContent = "CC " + c.cc + " · ch " + c.channel + " · " + c.type;
    el.querySelector(".val").textContent = c.value;
    el.querySelector(".bar > div").style.width = (c.value / 127 * 100) + "%";
  });
  // Remove stale control nodes (mode changed).
  $$("#controls .control").forEach((el) => {
    if (!seen.has(el.id.replace("ctrl-", ""))) el.remove();
  });
}

// ---------------------------------------------------------------- commands
async function post(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  return r.json();
}

$("#mode-switch").addEventListener("click", (e) => {
  const btn = e.target.closest(".mode-btn");
  if (btn) post("/mode", { mode: btn.dataset.mode });
});

$("#recalibrate-btn").addEventListener("click", () => {
  if (confirm("Recalibrate glove colors? Hold your hand open and still.")) {
    post("/recalibrate");
  }
});

// ---------------------------------------------------------------- mappings
async function loadMappings() {
  const r = await fetch("/mappings", { cache: "no-store" });
  const data = await r.json();
  mappingSources = data.sources;
  renderMappingEditor(data.config);
}

function optionList(values, selected) {
  return values.map((v) =>
    `<option value="${v}" ${v === selected ? "selected" : ""}>${v}</option>`).join("");
}

function renderMappingEditor(config) {
  const root = $("#mapping-editor");
  root.innerHTML = "";
  ["PLAY", "EXPRESSION", "DJ"].forEach((mode) => {
    const bindings = config[mode] || [];
    const wrap = document.createElement("div");
    wrap.className = "map-mode";
    let rows = bindings.map((b, i) => mappingRow(mode, b, i)).join("");
    wrap.innerHTML =
      `<h3>${mode}</h3>` +
      '<table class="map-table"><thead><tr>' +
        '<th>Label</th><th>Type</th><th>Gesture</th><th>CC</th><th>Ch</th>' +
      '</tr></thead><tbody data-mode="' + mode + '">' + rows + '</tbody></table>';
    root.appendChild(wrap);
  });
}

function mappingRow(mode, b, i) {
  const type = b.type || "absolute";
  let gestureCell;
  if (type === "trigger") {
    gestureCell =
      'on:<select data-f="on_gesture">' + optionList(mappingSources.trigger, b.on_gesture) + '</select>' +
      ' off:<select data-f="off_gesture">' + optionList(mappingSources.trigger, b.off_gesture) + '</select>';
  } else {
    const src = type === "relative" ? mappingSources.relative : mappingSources.absolute;
    gestureCell = '<select data-f="source">' + optionList(src, b.source) + '</select>';
  }
  return `<tr data-id="${b.id}">
    <td><input data-f="label" value="${b.label || ""}"></td>
    <td><select data-f="type">
      ${optionList(["absolute", "relative", "trigger"], type)}
    </select></td>
    <td>${gestureCell}</td>
    <td><input type="number" data-f="cc" min="0" max="127" value="${b.cc}"></td>
    <td><input type="number" data-f="channel" min="1" max="16" value="${b.channel || 1}"></td>
  </tr>`;
}

// Re-render a row when its type changes (gesture options differ).
$("#mapping-editor").addEventListener("change", (e) => {
  if (e.target.dataset.f === "type") {
    const tr = e.target.closest("tr");
    const mode = tr.closest("tbody").dataset.mode;
    const b = readRow(tr);
    b.type = e.target.value;
    // pick a sensible default source for the new type
    if (b.type === "relative") b.source = mappingSources.relative[0];
    else if (b.type === "absolute") b.source = mappingSources.absolute[0];
    tr.outerHTML = mappingRow(mode, b, 0);
  }
});

function readRow(tr) {
  const b = { id: tr.dataset.id };
  tr.querySelectorAll("[data-f]").forEach((el) => {
    let v = el.value;
    if (el.dataset.f === "cc" || el.dataset.f === "channel") v = parseInt(v, 10);
    b[el.dataset.f] = v;
  });
  return b;
}

function collectMappings() {
  const config = { PLAY: [], EXPRESSION: [], DJ: [] };
  $$("#mapping-editor tbody").forEach((tbody) => {
    const mode = tbody.dataset.mode;
    tbody.querySelectorAll("tr").forEach((tr) => {
      const b = readRow(tr);
      if (b.type === "trigger") { b.on_value = 127; b.off_value = 0; }
      config[mode].push(b);
    });
  });
  return config;
}

$("#mapping-save").addEventListener("click", async () => {
  const status = $("#mapping-status");
  try {
    const res = await post("/mappings", collectMappings());
    if (res.ok) {
      status.textContent = "✓ Saved & applied on the Pi.";
      status.className = "mapping-status ok";
      renderMappingEditor(res.config);
    } else {
      status.textContent = "✗ " + (res.error || "save failed");
      status.className = "mapping-status err";
    }
  } catch (e) {
    status.textContent = "✗ " + e.message;
    status.className = "mapping-status err";
  }
});

$("#mapping-reload").addEventListener("click", loadMappings);

// ---------------------------------------------------------------- boot
loadMappings();
setInterval(pollState, 50);   // 20 Hz
pollState();
