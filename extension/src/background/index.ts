import { API_BASE } from "../shared/api";
import type { Msg, MsgResponse } from "../shared/types";

async function fetchJson<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    let code = "HTTP_ERROR";
    let message = `${r.status}`;
    try {
      const j = await r.json();
      if (j?.error) {
        code = j.error.code || code;
        message = j.error.message || message;
      }
    } catch {
      /* ignore */
    }
    const err = new Error(message);
    (err as any).code = code;
    throw err;
  }
  return r.json();
}

async function routeApi(msg: Msg): Promise<unknown> {
  switch (msg.type) {
    case "ANALYZE":
      return fetchJson("POST", "/vibe/analyze", {
        text: msg.payload.text,
        domain: msg.payload.domain,
        context: {
          page_title: msg.payload.pageTitle,
          page_url: msg.payload.pageUrl,
        },
        hesitation_ms: msg.payload.hesitationMs,
        exclude_items: msg.payload.excludeItems || [],
      });
    case "ACTION":
      return fetchJson("POST", "/vibe/action", {
        action: msg.payload.action,
        matched_tag_ids: msg.payload.matchedTagIds,
        text_hash: msg.payload.textHash,
        read_ms: msg.payload.readMs,
        item_name: msg.payload.itemName,
        domain: msg.payload.domain,
        match_score: msg.payload.matchScore,
        verdict: msg.payload.verdict,
      });
    case "GET_RADAR":
      return fetchJson("GET", "/profile/radar");
    case "RECOMMEND":
      return fetchJson("POST", "/vibe/recommend", {
        text: msg.payload.text,
        source_domain: msg.payload.sourceDomain,
        matched_tag_ids: msg.payload.matchedTagIds,
      });
    case "PERSONALITY_SUBMIT":
      return fetchJson("POST", "/personality/submit", {
        mbti: msg.payload.mbti,
        constellation: msg.payload.constellation,
      });
  }
}

// On extension startup, sync personality_completed flag with backend state
async function syncPersonalityFlag() {
  try {
    const data = await fetchJson<{ has_personality: boolean }>("GET", "/profile/radar");
    if (!data.has_personality) {
      chrome.storage.local.remove("personality_completed");
    } else {
      chrome.storage.local.set({ personality_completed: true });
    }
  } catch {
    // Backend not running — leave flag as-is
  }
}
syncPersonalityFlag();

chrome.runtime.onMessage.addListener(
  (msg: any, _sender, sendResponse: (r: MsgResponse<unknown>) => void) => {
    if (msg.type === "OPEN_PERSONALITY") {
      const url = chrome.runtime.getURL("popup/popup.html");
      chrome.tabs.create({ url });
      return false;
    }
    (async () => {
      try {
        const data = await routeApi(msg as Msg);
        sendResponse({ ok: true, data });
      } catch (e: any) {
        sendResponse({
          ok: false,
          error: {
            code: e?.code || "BACKEND_DOWN",
            message: e?.message || "unknown error",
          },
        });
      }
    })();
    return true; // keep message channel open for async
  }
);
