// Upward swipe ("flick") detection on the photo card, using Pointer Events.

// A flick is a mostly vertical upward move that either travels far enough
// or is released fast enough (values from the design doc).
const MIN_DISTANCE_FRACTION = 0.25; // of the viewport height
const MIN_FAST_DISTANCE = 40; // px; a fast flick must still move this far
const MIN_VELOCITY = 0.8; // px per ms, upward
const VELOCITY_WINDOW = 100; // ms of recent samples used for velocity

export function isFlick({ dx, dy, vy, viewportHeight }) {
  if (dy >= 0 || Math.abs(dx) > Math.abs(dy)) return false;
  const far = -dy >= viewportHeight * MIN_DISTANCE_FRACTION;
  const fast = -vy >= MIN_VELOCITY && -dy >= MIN_FAST_DISTANCE;
  return far || fast;
}

function velocity(samples) {
  const last = samples.at(-1);
  const first = samples.find((s) => last.t - s.t <= VELOCITY_WINDOW) ?? samples[0];
  const dt = last.t - first.t;
  return dt > 0 ? (last.y - first.y) / dt : 0;
}

// Physical "wrist flick": one sharp forward snap of the whole phone
// towards the laptop. Shaking, putting the phone down and walking must
// not count, so a flick needs all of:
//   1. the phone held still just before (aiming),
//   2. a fast pitch (top edge tipping) with a sharp jolt,
//   3. no strong swing back afterwards (a shake reverses, a flick stops).
const WRIST_ROTATION = 300; // deg/s, peak pitch rate
const WRIST_ACCEL = 15; // m/s², peak acceleration without gravity
const WRIST_WINDOW = 250; // ms; both peaks must fall inside this window
const PITCH_SHARE = 1.5; // pitch must beat the other two axes by this factor
const QUIET_ROTATION = 80; // deg/s; "held still" means below this ...
const QUIET_ACCEL = 4; // ... and below this m/s²
const QUIET_MS = 300; // for this long before the flick starts
const SETTLE_MS = 350; // watch this long after the peak for a swing back
const REVERSAL = 0.6; // a swing back above this share of the peak = shake
const WRIST_COOLDOWN = 1500; // ms after a flick or a rejected shake
const HISTORY_MS = 1000;
const GRAVITY = 9.81;

const peak = (list, pick) => Math.max(0, ...list.map(pick));

// Returns push(sample) -> true when a wrist flick has just completed.
// Samples are { t, alpha, beta, gamma, rot, acc } (rotation in deg/s).
export function createWristDetector() {
  let history = [];
  let pending = null; // { t, sign, peak } while watching for a swing back
  let blockedUntil = -Infinity;

  const settle = (sample) => {
    const opposite = Math.sign(sample.beta) === -pending.sign;
    if (opposite && Math.abs(sample.beta) > REVERSAL * pending.peak) {
      pending = null; // swung back: a shake, not a flick
      blockedUntil = sample.t + WRIST_COOLDOWN;
      return false;
    }
    if (!opposite) pending.peak = Math.max(pending.peak, Math.abs(sample.beta));
    if (sample.t - pending.t < SETTLE_MS) return false;
    pending = null;
    blockedUntil = sample.t + WRIST_COOLDOWN;
    return true;
  };

  return (sample) => {
    history.push(sample);
    history = history.filter((h) => sample.t - h.t <= HISTORY_MS);
    if (pending) return settle(sample);
    if (sample.t < blockedUntil) return false;

    const recent = history.filter((h) => sample.t - h.t <= WRIST_WINDOW);
    const pitch = peak(recent, (h) => Math.abs(h.beta));
    const other = peak(recent, (h) => Math.max(Math.abs(h.alpha), Math.abs(h.gamma)));
    if (pitch < WRIST_ROTATION || peak(recent, (h) => h.acc) < WRIST_ACCEL) return false;
    if (pitch < PITCH_SHARE * other) return false;

    const moving = (h) => h.rot > QUIET_ROTATION || h.acc > QUIET_ACCEL;
    const onset = (recent.find(moving) ?? sample).t;
    const before = history.filter((h) => h.t < onset && onset - h.t <= QUIET_MS);
    const heldLongEnough = before.length > 0 && onset - before[0].t >= QUIET_MS * 0.8;
    if (!heldLongEnough || before.some(moving)) return false;

    const top = recent.reduce((a, b) => (Math.abs(b.beta) > Math.abs(a.beta) ? b : a));
    pending = { t: top.t, sign: Math.sign(top.beta), peak: pitch };
    return false;
  };
}

function motionSample(event) {
  const r = event.rotationRate;
  if (!r || (r.alpha == null && r.beta == null && r.gamma == null)) return null;
  const alpha = r.alpha ?? 0;
  const beta = r.beta ?? 0;
  const gamma = r.gamma ?? 0;
  const a = event.acceleration;
  const g = event.accelerationIncludingGravity;
  let acc;
  if (a && a.x != null) acc = Math.hypot(a.x, a.y ?? 0, a.z ?? 0);
  else if (g && g.x != null) acc = Math.abs(Math.hypot(g.x, g.y ?? 0, g.z ?? 0) - GRAVITY);
  else return null;
  return { t: event.timeStamp, alpha, beta, gamma, rot: Math.hypot(alpha, beta, gamma), acc };
}

let motionHandler = null;

export function stopWristFlick() {
  if (motionHandler) {
    window.removeEventListener("devicemotion", motionHandler);
    motionHandler = null;
  }
}

// Calls onWristFlick() for each detected flick of the phone. Resolves to
// "ok", "denied" or "unsupported". On iPhone, call this from a tap (it
// shares the Motion & Orientation permission with the compass).
export async function startWristFlick(onWristFlick) {
  stopWristFlick();
  const DME = window.DeviceMotionEvent;
  if (!window.isSecureContext || !DME) return "unsupported";
  if (typeof DME.requestPermission === "function") {
    let answer = "denied";
    try {
      answer = await DME.requestPermission();
    } catch {
      // Thrown when not called from a user gesture.
    }
    if (answer !== "granted") return "denied";
  }
  const detect = createWristDetector();
  motionHandler = (event) => {
    const sample = motionSample(event);
    if (sample && detect(sample)) onWristFlick();
  };
  window.addEventListener("devicemotion", motionHandler);
  return "ok";
}

// Calls onDrag(dx, dy) while the finger moves, then when it lifts either
// onFlick(dx, dy), onBlocked() for a flick that allow() refused (e.g. the
// phone is not pointing at the laptop), or onCancel().
// Returns a function that detaches the handlers.
export function attachSwipe(el, { onDrag, onFlick, onCancel, allow = () => true, onBlocked }) {
  let start = null;
  let samples = [];

  const down = (e) => {
    if (start || (e.pointerType === "mouse" && e.button !== 0)) return;
    start = { id: e.pointerId, x: e.clientX, y: e.clientY };
    samples = [{ y: e.clientY, t: e.timeStamp }];
    el.setPointerCapture(e.pointerId);
  };

  const move = (e) => {
    if (!start || e.pointerId !== start.id) return;
    samples.push({ y: e.clientY, t: e.timeStamp });
    if (samples.length > 20) samples.shift();
    onDrag(e.clientX - start.x, e.clientY - start.y);
  };

  const up = (e) => {
    if (!start || e.pointerId !== start.id) return;
    samples.push({ y: e.clientY, t: e.timeStamp });
    const swipe = {
      dx: e.clientX - start.x,
      dy: e.clientY - start.y,
      vy: velocity(samples),
      viewportHeight: window.innerHeight,
    };
    start = null;
    if (!isFlick(swipe)) onCancel();
    else if (allow()) onFlick(swipe.dx, swipe.dy);
    else (onBlocked ?? onCancel)();
  };

  const cancel = (e) => {
    if (!start || e.pointerId !== start.id) return;
    start = null;
    onCancel();
  };

  el.addEventListener("pointerdown", down);
  el.addEventListener("pointermove", move);
  el.addEventListener("pointerup", up);
  el.addEventListener("pointercancel", cancel);
  return () => {
    el.removeEventListener("pointerdown", down);
    el.removeEventListener("pointermove", move);
    el.removeEventListener("pointerup", up);
    el.removeEventListener("pointercancel", cancel);
  };
}
