import { API_BASE } from "../shared/api";

interface ProviderInfo {
  base_url: string;
  models: string[];
}

interface LlmConfigData {
  provider: string;
  api_key_masked: string;
  model: string;
  base_url: string;
  providers: Record<string, ProviderInfo>;
}

export async function renderSettings(root: HTMLElement, onBack: () => void): Promise<void> {
  root.innerHTML = `
    <div class="vr-settings">
      <div class="vr-settings-header">
        <button class="vr-back-btn">← 返回</button>
        <h2>大模型配置</h2>
      </div>
      <div class="vr-settings-loading">加载中...</div>
    </div>
  `;

  root.querySelector(".vr-back-btn")!.addEventListener("click", onBack);

  let config: LlmConfigData;
  try {
    const r = await fetch(`${API_BASE}/settings/llm`);
    config = await r.json();
  } catch {
    root.querySelector(".vr-settings-loading")!.textContent = "无法连接后端";
    return;
  }

  const providers = config.providers;
  const providerNames: Record<string, string> = {
    deepseek: "DeepSeek",
    openai: "OpenAI (GPT)",
    anthropic: "Anthropic (Claude)",
    moonshot: "Moonshot (Kimi)",
    qwen: "通义千问 (Qwen)",
    zhipu: "智谱 (GLM)",
    custom: "自定义",
  };

  const form = document.createElement("div");
  form.className = "vr-settings-form";
  form.innerHTML = `
    <label class="vr-field-label">模型厂商</label>
    <select id="provider-select" class="vr-input">
      ${Object.keys(providers).map(k =>
        `<option value="${k}" ${k === config.provider ? "selected" : ""}>${providerNames[k] || k}</option>`
      ).join("")}
    </select>

    <label class="vr-field-label">API Key</label>
    <input type="password" id="api-key-input" class="vr-input" placeholder="${config.api_key_masked}" />
    <div class="vr-field-hint">当前: ${config.api_key_masked}</div>

    <label class="vr-field-label">模型</label>
    <select id="model-select" class="vr-input"></select>

    <label class="vr-field-label">Base URL</label>
    <input type="text" id="base-url-input" class="vr-input" value="${config.base_url}" />

    <button class="vr-btn vr-btn-primary" id="save-btn">保存配置</button>
    <div class="vr-settings-msg" id="settings-msg"></div>
  `;

  const loadingEl = root.querySelector(".vr-settings-loading")!;
  loadingEl.replaceWith(form);

  const providerSelect = form.querySelector("#provider-select") as HTMLSelectElement;
  const modelSelect = form.querySelector("#model-select") as HTMLSelectElement;
  const baseUrlInput = form.querySelector("#base-url-input") as HTMLInputElement;
  const apiKeyInput = form.querySelector("#api-key-input") as HTMLInputElement;
  const saveBtn = form.querySelector("#save-btn") as HTMLButtonElement;
  const msg = form.querySelector("#settings-msg") as HTMLElement;

  function updateModels(provider: string) {
    const info = providers[provider];
    modelSelect.innerHTML = info.models.length
      ? info.models.map(m => `<option value="${m}" ${m === config.model ? "selected" : ""}>${m}</option>`).join("")
      : `<option value="">请手动输入</option>`;
    if (info.base_url) baseUrlInput.value = info.base_url;
    if (provider === "custom") {
      modelSelect.outerHTML = `<input type="text" id="model-select" class="vr-input" placeholder="model-name" value="${config.model}" />`;
    }
  }

  updateModels(config.provider);
  providerSelect.addEventListener("change", () => updateModels(providerSelect.value));

  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    msg.textContent = "保存中...";
    const modelEl = form.querySelector("#model-select") as HTMLSelectElement | HTMLInputElement;
    try {
      const r = await fetch(`${API_BASE}/settings/llm`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: providerSelect.value,
          api_key: apiKeyInput.value || "",
          model: modelEl.value,
          base_url: baseUrlInput.value,
        }),
      });
      if (!r.ok) throw new Error(`${r.status}`);
      const result = await r.json();
      msg.textContent = "✓ 已保存";
      msg.style.color = "#2d8c2d";
      const hint = form.querySelector(".vr-field-hint") as HTMLElement;
      if (hint) hint.textContent = `当前: ${result.api_key_masked}`;
    } catch (e: any) {
      msg.textContent = `保存失败: ${e?.message ?? "未知"}`;
      msg.style.color = "#d63031";
    }
    saveBtn.disabled = false;
  });
}
