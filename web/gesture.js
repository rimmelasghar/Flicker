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

// Physical "wrist flick": flicking the whole phone towards the laptop.
// Needs a fast turn of the phone and a sharp jolt close together, which
// putting the phone down or walking does not produce.
const WRIST_ROTATION = 300; // deg/s, peak rotation rate
const WRIST_ACCEL = 15; // m/s², peak acceleration without gravity
const WRIST_WINDOW = 250; // ms; both peaks must fall inside this window
const WRIST_COOLDOWN = 1500; // ms between two wrist flicks
const GRAVITY = 9.81;

export function isWristFlick(samples) {
  const rot = Math.max(0, ...samples.map((s) => s.rot));
  const acc = Math.max(0, ...samples.map((s) => s.acc));
  return rot >= WRIST_ROTATION && acc >= WRIST_ACCEL;
}

function motionSample(event) {
  const r = event.rotationRate;
  if (!r || (r.alpha == null && r.beta == null && r.gamma == null)) return null;
  const rot = Math.hypot(r.alpha ?? 0, r.beta ?? 0, r.gamma ?? 0);
  const a = event.acceleration;
  const g = event.accelerationIncludingGravity;
  let acc;
  if (a && a.x != null) acc = Math.hypot(a.x, a.y ?? 0, a.z ?? 0);
  else if (g && g.x != null) acc = Math.abs(Math.hypot(g.x, g.y ?? 0, g.z ?? 0) - GRAVITY);
  else return null;
  return { rot, acc, t: event.timeStamp };
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
  let samples = [];
  let last = -Infinity;
  motionHandler = (event) => {
    const sample = motionSample(event);
    if (!sample) return;
    samples.push(sample);
    samples = samples.filter((s) => sample.t - s.t <= WRIST_WINDOW);
    if (sample.t - last > WRIST_COOLDOWN && isWristFlick(samples)) {
      last = sample.t;
      samples = [];
      onWristFlick();
    }
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
