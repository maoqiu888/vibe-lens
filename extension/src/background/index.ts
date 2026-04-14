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
    case "COLD_START_GET_CARDS":
      return fetchJson("GET", "/cold-start/cards");
    case "COLD_START_SUBMIT":
      return fetchJson("POST", "/cold-start/submit", {
        selected_tag_ids: msg.payload.selectedTagIds,
      });
    case "ANALYZE":
      return fetchJson("POST", "/vibe/analyze", {
        text: msg.payload.text,
        domain: msg.payload.domain,
        context: {
          page_title: msg.payload.pageTitle,
          page_url: msg.payload.pageUrl,
        },
      });
    case "ACTION":
      return fetchJson("POST", "/vibe/action", {
        action: msg.payload.action,
        matched_tag_ids: msg.payload.matchedTagIds,
        text_hash: msg.payload.textHash,
      });
    case "GET_RADAR":
      return fetchJson("GET", "/profile/radar");
    case "RECOMMEND":
      return fetchJson("POST", "/vibe/recommend", {
        text: msg.payload.text,
        source_domain: msg.payload.sourceDomain,
        matched_tag_ids: msg.payload.matchedTagIds,
      });
  }
}

chrome.runtime.onMessage.addListener(
  (msg: Msg, _sender, sendResponse: (r: MsgResponse<unknown>) => void) => {
    (async () => {
      try {
        const data = await routeApi(msg);
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
