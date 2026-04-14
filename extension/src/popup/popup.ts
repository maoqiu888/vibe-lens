import { renderColdStart } from "./coldStart";

async function main() {
  const root = document.getElementById("root")!;
  const { profile_initialized } = await chrome.storage.local.get("profile_initialized");

  if (!profile_initialized) {
    await renderColdStart(root, () => main());
  } else {
    const mod = await import("./radar");
    await mod.renderRadar(root);
  }
}

main();
