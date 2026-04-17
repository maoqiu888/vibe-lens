import { send } from "../shared/api";
import type { RadarResult } from "../shared/types";

function addSettingsGear(root: HTMLElement) {
  const gear = document.createElement("button");
  gear.className = "vr-gear-btn";
  gear.textContent = "⚙";
  gear.title = "大模型配置";
  gear.addEventListener("click", async () => {
    const mod = await import("./settings");
    await mod.renderSettings(root, () => main());
  });
  root.appendChild(gear);
}

async function main() {
  const root = document.getElementById("root")!;
  try {
    const data = await send<RadarResult>({ type: "GET_RADAR" });
    if (data.interaction_count > 0) {
      const mod = await import("./radar");
      await mod.renderRadar(root, data);
      addSettingsGear(root);
    } else if (data.has_personality) {
      const mod = await import("./welcome");
      mod.renderWelcome(root);
      addSettingsGear(root);
    } else {
      chrome.storage.local.remove("personality_completed");
      const mod = await import("./personality");
      await mod.renderPersonalityQuiz(root);
      addSettingsGear(root);
    }
  } catch (e: any) {
    root.innerHTML = `<div class="error">加载失败: ${e?.message ?? "未知"}</div>`;
    addSettingsGear(root);
  }
}

main();
