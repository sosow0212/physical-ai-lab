import { useCallback, useEffect, useRef, useState } from "react";

import { askStream, chatApi, type ChatSource, type MessageItem, type SessionItem } from "../api/chat";

interface ChatMessageView extends MessageItem {
  streaming?: boolean;
}

export default function ChatPage() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageView[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadSessions = useCallback(async () => {
    setSessions(await chatApi.listSessions());
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (!activeId) return;
    void chatApi.messages(activeId).then(setMessages);
  }, [activeId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const newSession = async () => {
    const session = await chatApi.createSession();
    await loadSessions();
    setActiveId(session.id);
    setMessages([]);
  };

  const removeSession = async (id: string) => {
    if (!confirm("대화를 삭제할까요?")) return;
    await chatApi.deleteSession(id);
    if (activeId === id) {
      setActiveId(null);
      setMessages([]);
    }
    await loadSessions();
  };

  const send = async () => {
    const text = question.trim();
    if (!text || busy) return;
    let sessionId = activeId;
    if (!sessionId) {
      sessionId = (await chatApi.createSession()).id;
      setActiveId(sessionId);
      await loadSessions();
    }

    setQuestion("");
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { id: `local-${Date.now()}`, role: "user", content: text, sources: [], created_at: new Date().toISOString() },
      { id: "streaming", role: "assistant", content: "", sources: [], streaming: true, created_at: new Date().toISOString() },
    ]);

    const patch = (fn: (m: ChatMessageView) => ChatMessageView) =>
      setMessages((prev) => prev.map((m) => (m.streaming ? fn(m) : m)));

    try {
      for await (const event of askStream(sessionId, text)) {
        if (event.event === "sources") {
          patch((m) => ({ ...m, sources: event.data.sources as ChatSource[] }));
        } else if (event.event === "token") {
          patch((m) => ({ ...m, content: m.content + (event.data.delta as string) }));
        } else if (event.event === "graph") {
          patch((m) => ({ ...m, impact: event.data as MessageItem["impact"] }));
        } else if (event.event === "error") {
          patch((m) => ({ ...m, content: `⚠️ ${event.data.message}`, streaming: false }));
        }
      }
    } catch (e) {
      patch((m) => ({ ...m, content: `⚠️ ${e instanceof Error ? e.message : "오류"}` }));
    } finally {
      patch((m) => ({ ...m, streaming: false }));
      setBusy(false);
      void loadSessions();
    }
  };

  return (
    <div className="flex h-full">
      {/* 세션 사이드바 */}
      <aside className="w-64 shrink-0 border-r border-slate-200 bg-white">
        <button
          onClick={() => void newSession()}
          className="m-3 w-[calc(100%-1.5rem)] rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          + 새 대화
        </button>
        <div className="space-y-1 px-3">
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`group flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm ${
                activeId === s.id ? "bg-blue-50 font-medium text-blue-700" : "text-slate-600 hover:bg-slate-50"
              }`}
              onClick={() => setActiveId(s.id)}
            >
              <span className="truncate">{s.title}</span>
              <button
                className="ml-2 hidden text-xs text-red-500 group-hover:block"
                onClick={(e) => {
                  e.stopPropagation();
                  void removeSession(s.id);
                }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* 대화 영역 */}
      <section className="flex flex-1 flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto p-6">
          {!messages.length && (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
              <p className="text-lg font-medium text-slate-600">공정 매뉴얼에게 물어보세요</p>
              <p className="text-sm text-slate-400">
                예: "금형온도 상한과 초과 시 인터락은?" · "냉각수 압력이 낮으면?"
              </p>
            </div>
          )}
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-slate-200 bg-white p-4">
          <div className="flex gap-2">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void send()}
              placeholder={activeId ? "질문을 입력하세요..." : "새 대화를 만들고 질문을 입력하세요"}
              className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none"
              disabled={busy}
            />
            <button
              onClick={() => void send()}
              disabled={busy || !question.trim()}
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-slate-300"
            >
              {busy ? "답변 중..." : "전송"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessageView }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-2xl ${isUser ? "order-1" : ""}`}>
        <div
          className={`whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "rounded-br-sm bg-blue-600 text-white"
              : "rounded-bl-sm border border-slate-200 bg-white text-slate-800"
          }`}
        >
          {message.content || (message.streaming ? "..." : "")}
          {message.streaming && <span className="ml-0.5 animate-pulse">▍</span>}
        </div>
        {!isUser && !!message.sources.length && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {message.sources.map((s, i) => (
              <span
                key={`${s.doc_id}-${i}`}
                title={`유사도 ${s.score}`}
                className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
              >
                📄 {s.title} {s.page != null ? `p.${s.page}` : ""}
              </span>
            ))}
          </div>
        )}
        {!isUser && message.impact && (
          <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            🔗 영향범위: <b>{message.impact.root}</b> → {message.impact.nodes.join(" → ")}
          </div>
        )}
      </div>
    </div>
  );
}
