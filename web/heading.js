// Compass heading (degrees clockwise from north) from device orientation.

let active = null;

function listen(type, handler) {
  window.addEventListener(type, handler);
  active = { type, handler };
}

export function stopCompass() {
  if (active) {
    window.removeEventListener(active.type, active.handler);
    active = null;
  }
}

// iPhone Safari only exposes orientation after the user allows it, and the
// prompt can only be opened from a tap.
export function needsPermission() {
  return typeof window.DeviceOrientationEvent?.requestPermission === "function";
}

// Starts calling onHeading(degrees). On iPhone, call this from a tap.
// Resolves to "ok", "denied" or "unsupported".
export async function startCompass(onHeading) {
  stopCompass();
  if (!window.isSecureContext || !window.DeviceOrientationEvent) return "unsupported";

  if (needsPermission()) {
    let answer = "denied";
    try {
      answer = await window.DeviceOrientationEvent.requestPermission();
    } catch {
      // Thrown when not called from a user gesture.
    }
    if (answer !== "granted") return "denied";
  }

  listen("deviceorientation", (event) => {
    // iOS: already a true-north-referenced compass heading.
    if (typeof event.webkitCompassHeading === "number") onHeading(event.webkitCompassHeading);
  });
  return "ok";
}
