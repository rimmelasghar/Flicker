// Flick phone app: UI state, pairing, picking and upload.

const state = {
  view: "empty",
};

const $ = (id) => document.getElementById(id);

function render() {
  $("unpaired").hidden = state.view !== "unpaired";
  $("empty").hidden = state.view !== "empty";
  $("pick").hidden = state.view === "unpaired";
}

render();
