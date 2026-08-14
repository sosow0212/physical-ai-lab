/** 채팅 API — 세션/히스토리 + SSE 스트리밍 파서 */

import { API_BASE, del, get, post } from "./client";
import { drawingsApi } from "./drawings";

export interface ChatSource {
  type: "manual" | "drawing";
  doc_id: string;
  title: string;
  page: number | null;
  score: number;
}

/** 도면 출처 → 원본 이미지 URL */
export const sourceFileUrl = (s: ChatSource) => drawingsApi.fileUrl(s.doc_id);

export interface SessionItem {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface MessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: ChatSource[];
  impact?: { root: string; nodes: string[] } | null;
  created_at: string;
}

export interface StreamEvent {
  event: "sources" | "graph" | "token" | "done" | "error";
  data: Record<string, unknown>;
}

export const chatApi = {
  createSession: () => post<SessionItem>("/chat/sessions"),
  listSessions: () => get<SessionItem[]>("/chat/sessions"),
  deleteSession: (id: string) => del(`/chat/sessions/${id}`),
  messages: (sessionId: string) => get<MessageItem[]>(`/chat/sessions/${sessionId}/messages`),
};

/** SSE 질의 — 이벤트를 비동기 이터레이터로 yield */
export async function* askStream(sessionId: string, question: string): AsyncGenerator<StreamEvent> {
  const resp = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!resp.ok || !resp.body) throw new Error(`스트리밍 요청 실패 (${resp.status})`);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const parsed = parseSseBlock(raw);
      if (parsed) yield parsed;
    }
  }
}

function parseSseBlock(raw: string): StreamEvent | null {
  let event = "message";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  try {
    return { event: event as StreamEvent["event"], data: JSON.parse(data) };
  } catch {
    return null;
  }
}
