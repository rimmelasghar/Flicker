// Upward swipe ("flick") detection on the photo card, using Pointer Events.

// A flick is a mostly vertical upward move that either travels far enough
// or is released fast enough.
const MIN_DISTANCE_FRACTION = 0.22; // of the viewport height
const MIN_FAST_DISTANCE = 40; // px; a fast flick must still move this far
const MIN_VELOCITY = 0.5; // px per ms, upward
const VELOCITY_WINDOW = 80; // ms of recent samples used for velocity

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

// Calls onDrag(dx, dy) while the finger moves, then either onFlick(dx, dy)
// or onCancel() when it lifts. Returns a function that detaches the handlers.
export function attachSwipe(el, { onDrag, onFlick, onCancel }) {
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
    if (isFlick(swipe)) onFlick(swipe.dx, swipe.dy);
    else onCancel();
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
