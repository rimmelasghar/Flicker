// Laptop page: pairing QR code, save-location picker, unpair.

const state = {
  browsing: "", // folder shown in the picker, relative to the inbox
  selected: "", // folder photos are saved to
  rootLabel: "",
};

const $ = (id) => document.getElementById(id);

const FOLDER_ICON =
  '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h4.6l2 2h8.4A1.5 1.5 0 0 1 21 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z"/></svg>';
const CHEVRON = '<svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>';

async function call(path, options = {}) {
  const res = await fetch(path, {
    cache: "no-store",
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ?? `Request failed (${res.status})`);
  return body;
}

let toastTimer;
function toast(text, tone = "") {
  const el = $("toast");
  el.textContent = text;
  el.className = `toast ${tone}`;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 2600);
}

function setServer(ok, text) {
  $("server-status").className = `status ${ok ? "ok" : "err"}`;
  $("server-text").textContent = text;
}

// --- pairing -------------------------------------------------------------

async function loadPairing() {
  try {
    const info = await call("/api/pair");
    $("qr").innerHTML = info.qr_svg;
    $("phone-url").value = info.phone_url;
    $("version").textContent = `Flick ${info.version}`;
    setServer(true, `Running on ${info.host}`);
  } catch {
    setServer(false, "Server not reachable");
  }
}

async function copyUrl() {
  try {
    await navigator.clipboard.writeText($("phone-url").value);
    toast("Address copied");
  } catch {
    $("phone-url").select();
  }
}

async function rotate() {
  if (!confirm("Unpair every phone? Each one must scan the new code.")) return;
  try {
    await call("/api/token/rotate", { method: "POST" });
    await loadPairing();
    toast("All phones unpaired. New code ready.");
  } catch (error) {
    toast(error.message, "err");
  }
}

// --- save location -------------------------------------------------------

function joinPath(parent, name) {
  return parent ? `${parent}/${name}` : name;
}

function renderCrumbs() {
  const nav = $("crumbs");
  nav.replaceChildren();
  const parts = state.browsing ? state.browsing.split("/") : [];
  const rootName = state.rootLabel.split(/[\\/]/).filter(Boolean).at(-1) ?? "Inbox";
  const stops = [{ name: rootName, path: "" }];
  parts.forEach((name, i) => stops.push({ name, path: parts.slice(0, i + 1).join("/") }));
  stops.forEach((stop, i) => {
    if (i) {
      const sep = document.createElement("span");
      sep.className = "sep";
      sep.textContent = "/";
      nav.append(sep);
    }
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = stop.name;
    if (i === stops.length - 1) button.setAttribute("aria-current", "page");
    button.addEventListener("click", () => browse(stop.path));
    nav.append(button);
  });
}

function renderFolders(folders) {
  const list = $("folder-list");
  list.replaceChildren();
  if (!folders.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No sub-folders. Save here, or create one.";
    list.append(empty);
    return;
  }
  for (const name of folders) {
    const path = joinPath(state.browsing, name);
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.innerHTML = `${FOLDER_ICON}<span class="name"></span>${
      path === state.selected ? '<span class="tag">Current</span>' : ""
    }${CHEVRON}`;
    button.querySelector(".name").textContent = name;
    button.addEventListener("click", () => browse(path));
    item.append(button);
    list.append(item);
  }
}

const CHECK = '<svg class="icon-sm" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';

function renderChooseButton() {
  const here = state.browsing === state.selected;
  const btn = $("choose-btn");
  btn.disabled = here;
  btn.classList.toggle("btn-done", here);
  btn.innerHTML = here ? `${CHECK} Saving here` : "Save photos here";
}

async function browse(path) {
  try {
    const body = await call(`/api/folders?path=${encodeURIComponent(path)}`);
    state.browsing = body.path;
    state.selected = body.selected;
    // display is "<INBOX_DIR>/<path>"; keep just the INBOX_DIR part.
    state.rootLabel = body.path ? body.display.slice(0, -(body.path.length + 1)) : body.display;
    renderCrumbs();
    renderFolders(body.folders);
    renderChooseButton();
  } catch (error) {
    toast(error.message, "err");
  }
}

async function loadCurrent() {
  try {
    const body = await call("/api/save-folder");
    state.selected = body.path;
    $("current-folder").textContent = body.display;
  } catch (error) {
    $("current-folder").textContent = "Unknown";
    toast(error.message, "err");
  }
}

async function choose() {
  try {
    const body = await call("/api/save-folder", {
      method: "PUT",
      body: JSON.stringify({ path: state.browsing }),
    });
    state.selected = body.path;
    $("current-folder").textContent = body.display;
    renderChooseButton();
    await browse(state.browsing);
    toast("Photos will be saved here");
  } catch (error) {
    toast(error.message, "err");
  }
}

function toggleNewFolder(show) {
  $("new-folder").hidden = !show;
  $("new-folder-btn").hidden = show;
  if (show) $("new-folder-name").focus();
  else $("new-folder-name").value = "";
}

async function createFolder(event) {
  event.preventDefault();
  const name = $("new-folder-name").value.trim();
  if (!name) return;
  try {
    const body = await call("/api/folders", {
      method: "POST",
      body: JSON.stringify({ parent: state.browsing, name }),
    });
    toggleNewFolder(false);
    await browse(body.path);
    toast(`Created “${name}”`);
  } catch (error) {
    toast(error.message, "err");
  }
}

// --- start ---------------------------------------------------------------

$("copy-url").addEventListener("click", copyUrl);
$("rotate").addEventListener("click", rotate);
$("choose-btn").addEventListener("click", choose);
$("new-folder-btn").addEventListener("click", () => toggleNewFolder(true));
$("new-folder-cancel").addEventListener("click", () => toggleNewFolder(false));
$("new-folder").addEventListener("submit", createFolder);

loadPairing();
await loadCurrent();
browse(state.selected);
