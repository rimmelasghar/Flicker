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

// Starts calling onHeading(degrees). Resolves to "ok", "denied" or
// "unsupported". iPhone Safari only grants access when this runs from a
// tap; recent Chrome also has requestPermission but grants it silently.
export async function startCompass(onHeading) {
  stopCompass();
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
