import { send } from "../shared/api";
import type { PersonalityResult } from "../shared/types";

const CONSTELLATIONS = [
  "白羊座", "金牛座", "双子座", "巨蟹座",
  "狮子座", "处女座", "天秤座", "天蝎座",
  "射手座", "摩羯座", "水瓶座", "双鱼座",
];

export async function renderPersonalityQuiz(root: HTMLElement): Promise<void> {
  root.innerHTML = `
    <div class="vr-personality-quiz">
      <h2>Vibe-Radar 快速定位</h2>
      <p class="vr-quiz-sub">告诉我一点关于你的事，让 Vibe 马上懂你</p>

      <label class="vr-field-label">你的 MBTI <span class="vr-optional">（可选）</span></label>
      <input type="text" id="mbti-input" class="vr-input" placeholder="INTP" maxlength="4" />
      <a class="vr-ext-link" href="https://www.16personalities.com/ch/%E5%85%8D%E8%B4%B9%E4%BA%BA%E6%A0%BC%E6%B5%8B%E8%AF%95" target="_blank">不清楚？去 16personalities 测一下 →</a>

      <label class="vr-field-label">你的星座 <span class="vr-optional">（可选）</span></label>
      <select id="constellation-select" class="vr-input">
        <option value="">—— 不填 ——</option>
        ${CONSTELLATIONS.map((c) => `<option value="${c}">${c}</option>`).join("")}
      </select>

      <button class="vr-btn vr-btn-secondary" id="skip-btn">跳过，让 Vibe 自己学</button>
      <button class="vr-btn vr-btn-primary" id="submit-btn">确认提交</button>

      <div class="vr-quiz-msg" id="quiz-msg"></div>
    </div>
  `;

  const mbtiInput = root.querySelector("#mbti-input") as HTMLInputElement;
  const constellationSelect = root.querySelector("#constellation-select") as HTMLSelectElement;
  const skipBtn = root.querySelector("#skip-btn") as HTMLButtonElement;
  const submitBtn = root.querySelector("#submit-btn") as HTMLButtonElement;
  const msg = root.querySelector("#quiz-msg") as HTMLElement;

  async function submit(mbti: string | null, constellation: string | null): Promise<void> {
    submitBtn.disabled = true;
    skipBtn.disabled = true;
    msg.textContent = "Vibe 正在理解你…";
    try {
      const result = await send<PersonalityResult>({
        type: "PERSONALITY_SUBMIT",
        payload: { mbti, constellation },
      });
      chrome.storage.local.set({ personality_completed: true });
      if (result.status === "ok" && result.summary) {
        msg.innerHTML = `<strong>✓ 已完成</strong><br><br>${result.summary}<br><br>2 秒后进入主界面…`;
      } else {
        msg.textContent = "✓ 已完成，进入主界面…";
      }
      setTimeout(async () => {
        const mod = await import("./welcome");
        mod.renderWelcome(root);
      }, 2000);
    } catch (e: any) {
      msg.textContent = `提交失败: ${e?.message ?? "未知"}`;
      submitBtn.disabled = false;
      skipBtn.disabled = false;
    }
  }

  skipBtn.addEventListener("click", () => submit(null, null));
  submitBtn.addEventListener("click", () => {
    const mbti = mbtiInput.value.trim().toUpperCase();
    const constellation = constellationSelect.value;
    submit(mbti || null, constellation || null);
  });
}
