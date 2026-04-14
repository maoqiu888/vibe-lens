import * as echarts from "echarts";

import { send } from "../shared/api";
import type { RadarResult } from "../shared/types";

export async function renderRadar(root: HTMLElement) {
  root.innerHTML = `
    <h2>你的审美雷达</h2>
    <div id="radar"></div>
    <div class="stats" id="stats"></div>
  `;
  const chartRoot = root.querySelector("#radar") as HTMLElement;
  const statsRoot = root.querySelector("#stats") as HTMLElement;

  let data: RadarResult;
  try {
    data = await send<RadarResult>({ type: "GET_RADAR" });
  } catch (e: any) {
    chartRoot.innerHTML = `<div class="error">加载失败: ${e?.message ?? "未知"}</div>`;
    return;
  }

  const chart = echarts.init(chartRoot);
  chart.setOption({
    radar: {
      indicator: data.dimensions.map((d) => ({
        name: d.category_label,
        max: 100,
      })),
      radius: "65%",
      axisName: { color: "#555", fontSize: 12 },
      splitArea: { show: true, areaStyle: { color: ["#f8f7ff", "#fff"] } },
    },
    series: [
      {
        type: "radar",
        data: [
          {
            value: data.dimensions.map((d) => d.score),
            name: "当前画像",
            areaStyle: { color: "rgba(108, 92, 231, 0.3)" },
            lineStyle: { color: "#6c5ce7" },
            itemStyle: { color: "#6c5ce7" },
          },
        ],
      },
    ],
  });

  statsRoot.innerHTML = `
    已鉴定 <b>${data.total_analyze_count}</b> 次 ·
    已确权 <b>${data.total_action_count}</b> 次
  `;
}
