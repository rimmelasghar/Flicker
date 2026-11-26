// Flick phone app: UI state, pairing, picking and upload.

const TOKEN_KEY = "flick.token";
const TOKEN_HEADER = "X-Flick-Token";

const state = {
  token: null,
  // "checking" | "paired" | "unpaired" | "offline"
  pairing: "checking",
  host: "",
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
  $("empty").hidden = unpaired;
  $("pick").hidden = unpaired;
}

async function init() {
  state.token = takeTokenFromLink() ?? storeGet(TOKEN_KEY);
  render();
  await checkPairing();
  render();
}

init();
