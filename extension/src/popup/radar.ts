import * as echarts from "echarts";

import type { RadarResult } from "../shared/types";

export async function renderRadar(root: HTMLElement, data: RadarResult): Promise<void> {
  root.innerHTML = `
    <h2>你的审美雷达</h2>
    <div id="radar"></div>
    <div class="vr-level-panel">
      <div class="vr-level-current">${data.level_emoji} Lv.${data.level} ${data.level_title}</div>
      <div class="vr-level-bar">
        <div class="vr-level-fill" style="width: ${levelFillPercent(data)}%"></div>
      </div>
      <div class="vr-level-counts">
        已喂入 <b>${data.interaction_count}</b> 个信号 · 下一级还差 <b>${Math.max(0, data.next_level_at - data.interaction_count)}</b> 次
      </div>
    </div>
    <div class="stats">
      已鉴定 <b>${data.total_analyze_count}</b> 次 · 已确权 <b>${data.total_action_count}</b> 次
    </div>
  `;
  const chartRoot = root.querySelector("#radar") as HTMLElement;

  const chart = echarts.init(chartRoot);
  chart.setOption({
    radar: {
      indicator: data.dimensions.map((d) => ({
        name: d.category_label,
        max: 100,
      })),
      radius: "65%",
      axisName: { color: "#c8c0ff", fontSize: 12 },
      splitArea: { show: true, areaStyle: { color: ["rgba(108,92,231,0.06)", "rgba(108,92,231,0.02)"] } },
      splitLine: { lineStyle: { color: "rgba(108,92,231,0.15)" } },
      axisLine: { lineStyle: { color: "rgba(108,92,231,0.2)" } },
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
}

function levelFillPercent(data: RadarResult): number {
  if (data.next_level_at <= 0) return 100;
  const prev = data.level * data.level;
  const span = data.next_level_at - prev;
  if (span <= 0) return 100;
  const progressed = data.interaction_count - prev;
  return Math.min(100, Math.max(0, Math.round((progressed / span) * 100)));
}
