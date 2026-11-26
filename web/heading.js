// Compass heading (degrees clockwise from north) from device orientation.

const SMOOTH_MS = 300; // readings averaged over this recent window

let active = null;

const toRad = (deg) => (deg * Math.PI) / 180;
const toDeg = (rad) => (rad * 180) / Math.PI;
export const normalize = (deg) => ((deg % 360) + 360) % 360;

// Mean of angles on a circle: 359 and 1 average to 0, not 180.
export function circularMean(angles) {
  let x = 0;
  let y = 0;
  for (const a of angles) {
    x += Math.cos(toRad(a));
    y += Math.sin(toRad(a));
  }
  return normalize(toDeg(Math.atan2(y, x)));
}

// Readings follow the top edge of the device. When the screen is rotated,
// the user points with the top of the screen instead, which is this many
// degrees clockwise from the device top. (landscape with the device top
// to the left = 90: device heading 270 + 90 = facing 0.)
export function screenAngle() {
  const angle = window.screen?.orientation?.angle ?? window.orientation ?? 0;
  return normalize(Number(angle) || 0);
}

// Returns a function that takes a raw reading and gives the smoothed heading.
export function createSmoother(windowMs = SMOOTH_MS) {
  let samples = [];
  return (heading, now = performance.now()) => {
    samples.push({ heading, t: now });
    samples = samples.filter((s) => now - s.t <= windowMs);
    return circularMean(samples.map((s) => s.heading));
  };
}

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

// Starts calling onHeading(smoothed degrees). Resolves to "ok", "denied" or
// "unsupported". iPhone Safari only grants access when this runs from a
// tap; recent Chrome also has requestPermission but grants it silently.
export async function startCompass(onReading) {
  stopCompass();
  const smooth = createSmoother();
  const onHeading = (raw) => onReading(smooth(normalize(raw + screenAngle())));
  if (!window.isSecureContext || !window.DeviceOrientationEvent) return "unsupported";

  if (typeof window.DeviceOrientationEvent.requestPermission === "function") {
    let answer = "denied";
    try {
      answer = await window.DeviceOrientationEvent.requestPermission();
    } catch {
      // Thrown when not called from a user gesture.
    }
    if (answer !== "granted") return "denied";
  }

  // Android Chrome: plain deviceorientation is relative to an arbitrary
  // start direction; the absolute event is referenced to north.
  if ("ondeviceorientationabsolute" in window) {
    listen("deviceorientationabsolute", (event) => {
      const heading = fromAlpha(event);
      if (heading !== null) onHeading(heading);
    });
    return "ok";
  }

  listen("deviceorientation", (event) => {
    // iOS: already a north-referenced compass heading.
    if (typeof event.webkitCompassHeading === "number") {
      onHeading(event.webkitCompassHeading);
      return;
    }
    // Other browsers (e.g. Firefox) mark north-referenced readings absolute.
    const heading = event.absolute ? fromAlpha(event) : null;
    if (heading !== null) onHeading(heading);
  });
  return "ok";
}

// alpha grows counter-clockwise; compass headings grow clockwise.
function fromAlpha(event) {
  return typeof event.alpha === "number" ? (360 - event.alpha) % 360 : null;
}
