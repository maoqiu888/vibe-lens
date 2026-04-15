import { send } from "../shared/api";
import type { RadarResult } from "../shared/types";
import { renderWelcome } from "./welcome";

async function main() {
  const root = document.getElementById("root")!;
  try {
    const data = await send<RadarResult>({ type: "GET_RADAR" });
    if (data.interaction_count === 0) {
      renderWelcome(root);
    } else {
      const mod = await import("./radar");
      await mod.renderRadar(root, data);
    }
  } catch (e: any) {
    root.innerHTML = `<div class="error">加载失败: ${e?.message ?? "未知"}</div>`;
  }
}

main();
