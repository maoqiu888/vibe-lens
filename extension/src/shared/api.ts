import type { Msg, MsgResponse } from "./types";

export function send<T>(msg: Msg): Promise<T> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (resp: MsgResponse<T>) => {
      if (chrome.runtime.lastError) {
        return reject(new Error(`BACKEND_DOWN: ${chrome.runtime.lastError.message}`));
      }
      if (!resp) {
        return reject(new Error("BACKEND_DOWN: no response"));
      }
      if (resp.ok) resolve(resp.data);
      else reject(new Error(`${resp.error.code}: ${resp.error.message}`));
    });
  });
}

export const API_BASE = "http://localhost:8000/api/v1";
