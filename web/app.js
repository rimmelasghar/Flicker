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
  if (file) setPhoto(file);
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

function onFlick() {
  resetCard();
  setPhoto(null);
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
