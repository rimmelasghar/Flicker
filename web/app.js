// Flick phone app: UI state, pairing, picking and upload.

import { attachSwipe, startWristFlick } from "./gesture.js";
import { angleDiff, normalize, startCompass } from "./heading.js";

const TOKEN_KEY = "flick.token";
const TOKEN_HEADER = "X-Flick-Token";

const state = {
  token: null,
  // "checking" | "paired" | "unpaired" | "offline"
  pairing: "checking",
  host: "",
  // { file: File, url: string } for the photo on the card, or null.
  photo: null,
  // Further picked photos, sent one per flick after the card.
  queue: [],
  sending: false,
  // "off" | "on" | "denied" | "unsupported"
  compass: "off",
  // Latest heading in degrees, or null before the first reading.
  heading: null,
  // { heading, savedAt } saved when the user pointed at the laptop.
  calibration: null,
  calibrating: false,
  // Recent { t, heading } readings, to check direction from just before a
  // wrist flick (the flick itself swings the compass).
  headingLog: [],
  // Motion sensor: "off" | "on" | "denied" | "unsupported"
  motion: "off",
  // User setting: send by flicking the phone itself.
  wristEnabled: true,
};

const WRIST_KEY = "flick.wrist";
const HEADING_LOG_MS = 1500;
// Direction is judged from the heading this long before the jolt.
// The flick is reported ~350 ms after its peak, so look back past both.
const WRIST_LOOKBACK_MS = 900;

const CALIBRATION_KEY = "flick.calibration";
// ± degrees from the calibrated laptop heading that still count as
// pointing at it (design doc default).
const ANGLE_TOLERANCE = 35;

// How long to wait for a first reading before giving up on the compass.
const COMPASS_TIMEOUT_MS = 2000;
// Compass states in which Flick falls back to swipe-only sending.
const SWIPE_ONLY = new Set(["unsupported", "denied", "nodata"]);

// Why a flick may not send right now, or null when it may.
function directionProblem(heading = state.heading) {
  if (SWIPE_ONLY.has(state.compass)) return null;
  if (state.compass !== "on") return "Enable the compass first.";
  if (heading === null) return "Waiting for the compass…";
  if (!state.calibration) return "Calibrate first: point at the laptop and tap Calibrate.";
  const off = angleDiff(heading, state.calibration.heading);
  if (off > ANGLE_TOLERANCE) return `Point at the laptop (${Math.round(off)}° off).`;
  return null;
}

const $ = (id) => document.getElementById(id);

function storeGet(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function storeSet(key, value) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Private mode or storage blocked: the token lives for this page only.
  }
}

// The QR code opens https://<laptop>:8443/#t=<token>. The fragment never
// reaches the server; keep the token and remove it from the address bar.
function takeTokenFromLink() {
  const params = new URLSearchParams(location.hash.slice(1));
  const token = params.get("t");
  if (token) {
    storeSet(TOKEN_KEY, token);
    history.replaceState(null, "", location.pathname + location.search);
  }
  return token;
}

export async function api(path, options = {}) {
  const headers = new Headers(options.headers);
  headers.set(TOKEN_HEADER, state.token ?? "");
  return fetch(path, { ...options, headers, cache: "no-store" });
}

async function checkPairing() {
  if (!state.token) {
    state.pairing = "unpaired";
    return;
  }
  try {
    const res = await api("/api/ping");
    if (res.status === 401) {
      state.token = null;
      storeSet(TOKEN_KEY, null);
      state.pairing = "unpaired";
    } else if (res.ok) {
      state.host = (await res.json()).host;
      state.pairing = "paired";
    } else {
      state.pairing = "offline";
    }
  } catch {
    state.pairing = "offline";
  }
}

const PILL = {
  checking: ["Connecting…", ""],
  paired: ["Paired", "ok"],
  unpaired: ["Not paired", "err"],
  offline: ["Laptop unreachable", "err"],
};

function render() {
  const [label, tone] = PILL[state.pairing];
  const pill = $("pair-status");
  pill.textContent = label;
  pill.className = `pill ${tone}`;

  const unpaired = state.pairing === "unpaired";
  const calibrating = !unpaired && state.calibrating;
  const main = !unpaired && !calibrating;
  $("direction").hidden = unpaired;
  renderDirection();
  renderWrist();
  $("unpaired").hidden = !unpaired;
  $("calibrate").hidden = !calibrating;
  $("empty").hidden = !main || state.photo !== null;
  $("card").hidden = !main || state.photo === null;
  $("pick").hidden = !main;
}

const COMPASS_TEXT = {
  off: "Compass off",
  denied: "Compass not allowed: swipe-only, no direction check",
  unsupported: "No compass on this browser: swipe-only, no direction check",
  nodata: "No compass data: swipe-only, no direction check",
};

function renderDirection() {
  const on = state.compass === "on";
  const reading = state.heading === null ? null : Math.round(state.heading);
  let text = COMPASS_TEXT[state.compass];
  if (on && reading === null) text = "Waiting for compass…";
  else if (on && !state.calibration) text = "Not calibrated: tap Calibrate";
  else if (on) text = pointingText();
  const inRange = on && directionProblem() === null;
  $("dir-text").textContent = text;
  $("dir-dot").className = `dot ${inRange ? "ok" : ""}`;
  $("card").classList.toggle("in-range", inRange);
  $("compass-btn").hidden = on || state.compass === "unsupported" || state.compass === "nodata";
  $("calibrate-btn").hidden = !on || state.calibrating;
  $("calibrate-btn").textContent = state.calibration ? "Re-calibrate" : "Calibrate";
  $("cal-heading").textContent = reading === null ? "–" : `${reading}°`;
  $("cal-save").disabled = reading === null;
}

function pointingText() {
  const off = angleDiff(state.heading, state.calibration.heading);
  if (off <= ANGLE_TOLERANCE) return "Pointing at the laptop";
  // Positive: the laptop is clockwise from where the phone points.
  const turn = normalize(state.calibration.heading - state.heading) <= 180 ? "right" : "left";
  return `Turn ${turn} ${Math.round(off)}° to the laptop`;
}

function headingBefore(ms) {
  const cutoff = performance.now() - ms;
  const older = state.headingLog.filter((r) => r.t <= cutoff);
  return (older.at(-1) ?? state.headingLog[0])?.heading ?? state.heading;
}

function onHeading(degrees) {
  state.heading = degrees;
  const now = performance.now();
  state.headingLog.push({ t: now, heading: degrees });
  state.headingLog = state.headingLog.filter((r) => now - r.t <= HEADING_LOG_MS);
  if (state.compass === "nodata") {
    // Readings arrived late after all: turn the direction check back on.
    state.compass = "on";
    render();
    return;
  }
  renderDirection();
}

// auto: tried on page load without a tap. iPhone refuses that, which is
// not a real "denied", so the button stays available.
async function enableCompass({ auto = false } = {}) {
  const result = await startCompass(onHeading);
  if (auto && result === "denied") return;
  state.compass = result === "ok" ? "on" : result;
  // First time with a working compass: go straight to calibration.
  if (state.compass === "on" && !state.calibration && !auto) state.calibrating = true;
  render();
  if (state.compass === "on") {
    // Some browsers accept the listener but never deliver a heading
    // (laptops, no magnetometer): fall back to swipe-only.
    setTimeout(() => {
      if (state.compass === "on" && state.heading === null) {
        state.compass = "nodata";
        state.calibrating = false;
        render();
      }
    }, COMPASS_TIMEOUT_MS);
  }
}

async function enableMotion({ auto = false } = {}) {
  const result = await startWristFlick(onWristFlick);
  if (auto && result === "denied") return;
  state.motion = result === "ok" ? "on" : result;
  render();
}

function renderWrist() {
  const btn = $("wrist-btn");
  btn.hidden = state.pairing === "unpaired" || state.motion !== "on";
  btn.textContent = `Flick the phone to send: ${state.wristEnabled ? "on" : "off"}`;
}

function toggleWrist() {
  state.wristEnabled = !state.wristEnabled;
  storeSet(WRIST_KEY, state.wristEnabled ? "on" : "off");
  renderWrist();
}

// The whole phone was flicked. Only sends with a working compass that
// pointed at the laptop just before, so putting the phone down cannot send.
function onWristFlick() {
  if (!state.wristEnabled || !state.photo || state.sending || state.calibrating) return;
  if (state.pairing === "unpaired" || document.hidden) return;
  const problem =
    state.compass === "on"
      ? directionProblem(headingBefore(WRIST_LOOKBACK_MS))
      : "Flicking the phone needs the compass. Swipe the photo up instead.";
  if (problem) {
    setStatus(problem, "err");
    return;
  }
  onFlick(0);
}

function loadCalibration() {
  try {
    const saved = JSON.parse(storeGet(CALIBRATION_KEY));
    return Number.isFinite(saved?.heading) ? saved : null;
  } catch {
    return null;
  }
}

function setCalibrating(on) {
  state.calibrating = on;
  render();
}

function saveCalibration() {
  if (state.heading === null) return;
  state.calibration = { heading: state.heading, savedAt: new Date().toISOString() };
  storeSet(CALIBRATION_KEY, JSON.stringify(state.calibration));
  setStatus("Laptop direction saved.", "ok");
  setCalibrating(false);
}

function setPhoto(file) {
  if (state.photo) URL.revokeObjectURL(state.photo.url);
  state.photo = file ? { file, url: URL.createObjectURL(file) } : null;
  if (state.photo) $("card-img").src = state.photo.url;
  else $("card-img").removeAttribute("src");
  renderStack();
  render();
}

// Photos waiting under the top card.
function renderStack() {
  const waiting = state.queue.length;
  $("card").classList.toggle("stacked", waiting > 0);
  $("stack-count").hidden = waiting === 0;
  $("stack-count").textContent = `+${waiting}`;
}

// Show the next waiting photo on the card (or none).
function showNext() {
  setPhoto(state.queue.shift() ?? null);
}

function onPick(event) {
  const files = [...event.target.files];
  // Reset so picking the same photo again still fires "change".
  event.target.value = "";
  if (files.length) {
    state.queue.push(...files);
    if (!state.photo) showNext();
    else renderStack();
    const wrist = state.wristEnabled && state.motion === "on" && state.compass === "on";
    setStatus(
      wrist ? "Point at the laptop, then swipe up or flick the phone." : "Point at the laptop and swipe up.",
    );
  }
}

function moveCard(dx, dy) {
  const card = $("card");
  card.style.transition = "none";
  // Follow the finger upwards; resist downward and sideways drags.
  const y = dy < 0 ? dy : dy * 0.25;
  card.style.transform = `translate(${dx * 0.3}px, ${y}px) rotate(${dx * 0.03}deg)`;
}

function resetCard() {
  const card = $("card");
  card.style.transition = "transform 200ms ease-out";
  card.style.transform = "";
}

const FLY_MS = 220;

// Animate the card up and off the screen; resolves when it is gone.
function flyAway(dx) {
  const card = $("card");
  const distance = window.innerHeight + card.offsetHeight;
  card.style.transition = `transform ${FLY_MS}ms cubic-bezier(.3,.6,.4,1), opacity ${FLY_MS}ms`;
  card.style.transform = `translate(${dx * 0.5}px, ${-distance}px) rotate(${dx * 0.05}deg)`;
  card.style.opacity = "0";
  return new Promise((resolve) => setTimeout(resolve, FLY_MS));
}

function clearCard() {
  const card = $("card");
  card.style.transition = "none";
  card.style.transform = "";
  card.style.opacity = "";
}

const UPLOAD_ERRORS = {
  401: "Not paired any more. Scan the QR code again.",
  413: "Photo is too large.",
  415: "Not a supported image type.",
  429: "Too many photos at once. Wait a moment.",
  507: "Laptop disk is full.",
};

function setStatus(text, tone = "") {
  const el = $("status");
  el.textContent = text;
  el.className = `status ${tone}`;
  showErrorActions(null);
}

// After a failed upload: "retry" when trying again can help (network,
// busy, disk full), "skip" when this photo can never be sent (too large,
// wrong type), null to hide both.
function showErrorActions(kind) {
  $("error-actions").hidden = kind === null;
  $("retry-btn").hidden = kind !== "retry";
  $("skip-btn").hidden = kind === null;
}

function retry() {
  // An explicit tap: send the top photo again without another flick.
  onFlick(0);
}

function skip() {
  setStatus("Skipped.");
  showNext();
}

async function upload(file) {
  const body = new FormData();
  body.append("file", file, file.name);
  const timeout = AbortSignal.timeout?.(120_000);
  const res = await api("/api/upload", { method: "POST", body, signal: timeout });
  if (!res.ok) {
    const error = new Error(UPLOAD_ERRORS[res.status] ?? `Upload failed (${res.status}).`);
    error.status = res.status;
    throw error;
  }
  return res.json();
}

// A real flick while not pointing at the laptop: spring back and say why.
function onBlocked() {
  resetCard();
  setStatus(directionProblem() ?? "Try again.", "err");
  navigator.vibrate?.([20, 60, 20]);
}

async function onFlick(dx) {
  if (state.sending || !state.photo) return;
  state.sending = true;
  const { file } = state.photo;
  setStatus("Sending…");
  const sending = upload(file);
  // The result is awaited after the animation; mark it handled now so an
  // early failure is not reported as an unhandled rejection meanwhile.
  sending.catch(() => {});
  await flyAway(dx);
  clearCard();
  showNext();
  try {
    const result = await sending;
    const left = state.queue.length + (state.photo ? 1 : 0);
    setStatus(`Sent: ${result.saved}${left ? ` (${left} to go)` : ""}`, "ok");
    navigator.vibrate?.(30);
  } catch (error) {
    // Put the photo back on top of the stack so it can be flicked again.
    if (state.photo) state.queue.unshift(state.photo.file);
    setPhoto(file);
    if (error.status === 401) {
      state.token = null;
      storeSet(TOKEN_KEY, null);
      state.pairing = "unpaired";
      render();
    }
    const offline = error instanceof TypeError || error.name === "TimeoutError";
    setStatus(offline ? "Laptop unreachable. Same Wi-Fi?" : error.message, "err");
    if (error.status === 413 || error.status === 415) showErrorActions("skip");
    else if (error.status !== 401) showErrorActions("retry");
  } finally {
    state.sending = false;
  }
}

async function init() {
  $("file-input").addEventListener("change", onPick);
  $("retry-btn").addEventListener("click", retry);
  $("skip-btn").addEventListener("click", skip);
  // One tap asks for both sensors: on iPhone each requestPermission call
  // must start inside the tap, before any await.
  $("compass-btn").addEventListener("click", () => {
    enableMotion();
    enableCompass();
  });
  $("wrist-btn").addEventListener("click", toggleWrist);
  state.wristEnabled = storeGet(WRIST_KEY) !== "off";
  enableMotion({ auto: true });
  $("calibrate-btn").addEventListener("click", () => setCalibrating(true));
  $("cal-save").addEventListener("click", saveCalibration);
  $("cal-cancel").addEventListener("click", () => setCalibrating(false));
  state.calibration = loadCalibration();
  // Android grants orientation without a tap, so try straight away.
  enableCompass({ auto: true });
  attachSwipe($("card"), {
    onDrag: moveCard,
    onFlick,
    onCancel: resetCard,
    allow: () => directionProblem() === null,
    onBlocked,
  });
  state.token = takeTokenFromLink() ?? storeGet(TOKEN_KEY);
  render();
  await checkPairing();
  render();
}

init();
