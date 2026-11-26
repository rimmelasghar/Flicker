// Flick phone app: UI state, pairing, picking and upload.

import { attachSwipe } from "./gesture.js";

const TOKEN_KEY = "flick.token";
const TOKEN_HEADER = "X-Flick-Token";

const state = {
  token: null,
  // "checking" | "paired" | "unpaired" | "offline"
  pairing: "checking",
  host: "",
  // { file: File, url: string } for the photo on the card, or null.
  photo: null,
  sending: false,
};

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
  $("unpaired").hidden = !unpaired;
  $("empty").hidden = unpaired || state.photo !== null;
  $("card").hidden = unpaired || state.photo === null;
  $("pick").hidden = unpaired;
}

function setPhoto(file) {
  if (state.photo) URL.revokeObjectURL(state.photo.url);
  state.photo = file ? { file, url: URL.createObjectURL(file) } : null;
  if (state.photo) $("card-img").src = state.photo.url;
  else $("card-img").removeAttribute("src");
  render();
}

function onPick(event) {
  const [file] = event.target.files;
  // Reset so picking the same photo again still fires "change".
  event.target.value = "";
  if (file) {
    setPhoto(file);
    setStatus("Point at the laptop and swipe up.");
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

const FLY_MS = 280;

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

async function onFlick(dx) {
  if (state.sending || !state.photo) return;
  state.sending = true;
  const { file } = state.photo;
  setStatus("Sending…");
  const sending = upload(file);
  await flyAway(dx);
  clearCard();
  setPhoto(null);
  try {
    const result = await sending;
    setStatus(`Sent: ${result.saved}`, "ok");
    navigator.vibrate?.(30);
  } catch (error) {
    // Put the photo back so the user can flick it again.
    setPhoto(file);
    if (error.status === 401) {
      state.token = null;
      storeSet(TOKEN_KEY, null);
      state.pairing = "unpaired";
      render();
    }
    const offline = error instanceof TypeError || error.name === "TimeoutError";
    setStatus(offline ? "Laptop unreachable. Same Wi-Fi?" : error.message, "err");
  } finally {
    state.sending = false;
  }
}

async function init() {
  $("file-input").addEventListener("change", onPick);
  attachSwipe($("card"), { onDrag: moveCard, onFlick, onCancel: resetCard });
  state.token = takeTokenFromLink() ?? storeGet(TOKEN_KEY);
  render();
  await checkPairing();
  render();
}

init();
