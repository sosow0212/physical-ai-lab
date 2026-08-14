import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { askStream, chatApi, type ChatSource, type MessageItem, type SessionItem } from "../api/chat";
import { SourceViewer, sourceViewerProps } from "../components/SourceViewer";

interface ChatMessageView extends MessageItem {
  streaming?: boolean;
}

interface ViewerState {
  title: string;
  url: string;
  kind: "pdf" | "image";
}

const SUGGESTIONS = [
  "금형온도 상한과 초과 시 인터락은?",
  "1번 라인 온도가 올라가는데 영향범위를 알려줘",
  "냉각수 배관 계통도에서 압력계 위치는?",
  "컨베이어 정지 시 대응 절차 알려줘",
];

export default function ChatPage() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageView[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [viewer, setViewer] = useState<ViewerState | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadSessions = useCallback(async () => {
    try {
      setSessions(await chatApi.listSessions());
    } catch {
      /* 목록 실패 무시 */
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (!activeId) return;
    void chatApi
      .messages(activeId)
      .then(setMessages)
      .catch(() => setMessages([]));
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

  const send = async (text?: string) => {
    const q = (text ?? question).trim();
    if (!q || busy) return;
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
      {
        id: `local-${Date.now()}`,
        role: "user",
        content: q,
        sources: [],
        created_at: new Date().toISOString(),
      },
      {
        id: "streaming",
        role: "assistant",
        content: "",
        sources: [],
        streaming: true,
        created_at: new Date().toISOString(),
      },
    ]);

    const patch = (fn: (m: ChatMessageView) => ChatMessageView) =>
      setMessages((prev) => prev.map((m) => (m.streaming ? fn(m) : m)));

    try {
      for await (const event of askStream(sessionId, q)) {
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
      <aside className="flex w-64 shrink-0 flex-col border-r border-slate-200 bg-white">
        <button
          onClick={() => void newSession()}
          className="m-3 w-[calc(100%-1.5rem)] rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700"
        >
          + 새 대화
        </button>
        <div className="flex-1 space-y-1 overflow-y-auto px-3 pb-3">
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`group flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm transition ${
                activeId === s.id
                  ? "bg-blue-50 font-medium text-blue-700"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
              onClick={() => setActiveId(s.id)}
            >
              <span className="truncate">{s.title}</span>
              <button
                className="ml-2 hidden shrink-0 text-xs text-red-500 hover:text-red-700 group-hover:block"
                onClick={(e) => {
                  e.stopPropagation();
                  void removeSession(s.id);
                }}
              >
                ✕
              </button>
            </div>
          ))}
          {!sessions.length && (
            <p className="px-3 py-6 text-center text-xs text-slate-400">대화가 없습니다</p>
          )}
        </div>
      </aside>

      {/* 대화 영역 */}
      <section className="flex flex-1 flex-col bg-slate-50">
        <div className="flex-1 space-y-5 overflow-y-auto p-6">
          {!messages.length && (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
              <div className="flex size-14 items-center justify-center rounded-2xl bg-blue-600 text-2xl shadow-lg shadow-blue-200">
                🏭
              </div>
              <div>
                <p className="text-lg font-semibold text-slate-700">공정 매뉴얼에게 물어보세요</p>
                <p className="mt-1 text-sm text-slate-400">
                  매뉴얼·설계도면·설비 그래프를 근거로 답변합니다
                </p>
              </div>
              <div className="flex max-w-2xl flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => void send(s)}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 shadow-sm transition hover:border-blue-300 hover:text-blue-700"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} onOpenSource={(s) => setViewer(sourceViewerProps(s))} />
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-slate-200 bg-white p-4">
          <div className="flex gap-2">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void send()}
              placeholder={activeId ? "질문을 입력하세요..." : "질문 입력 시 새 대화가 시작됩니다"}
              className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none"
              disabled={busy}
            />
            <button
              onClick={() => void send()}
              disabled={busy || !question.trim()}
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:bg-slate-300"
            >
              {busy ? "답변 중..." : "전송"}
            </button>
          </div>
        </div>
      </section>

      {viewer && <SourceViewer {...viewer} onClose={() => setViewer(null)} />}
    </div>
  );
}

function MessageBubble({
  message,
  onOpenSource,
}: {
  message: ChatMessageView;
  onOpenSource: (s: ChatSource) => void;
}) {
  const isUser = message.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-sm">
          🏭
        </div>
      )}
      <div className="max-w-2xl">
        <div
          className={
            isUser
              ? "whitespace-pre-wrap rounded-2xl rounded-br-sm bg-blue-600 px-4 py-3 text-sm leading-relaxed text-white shadow-sm"
              : "chat-prose rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 text-slate-800 shadow-sm"
          }
        >
          {isUser ? (
            message.content
          ) : (
            <MarkdownContent content={message.content} streaming={message.streaming} />
          )}
        </div>

        {!isUser && !!message.sources.length && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="py-0.5 text-xs text-slate-400">출처:</span>
            {message.sources.map((s, i) => (
              <button
                key={`${s.doc_id}-${i}`}
                title={`유사도 ${s.score} — 클릭하면 원본을 엽니다`}
                onClick={() => onOpenSource(s)}
                className={
                  s.type === "drawing"
                    ? "rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-xs text-violet-700 transition hover:bg-violet-100"
                    : "rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs text-blue-700 transition hover:bg-blue-100"
                }
              >
                {s.type === "drawing" ? "📐" : "📄"} {s.title}
                {s.type === "manual" && s.page != null ? ` p.${s.page}` : ""}
              </button>
            ))}
          </div>
        )}
        {!isUser && message.impact && (
          <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            🔗 영향범위: <b>{message.impact.root}</b> → {message.impact.nodes.join(" → ")}
          </div>
        )}
      </div>
      {isUser && (
        <div className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-sm text-white">
          🧑
        </div>
      )}
    </div>
  );
}

function MarkdownContent({ content, streaming }: { content: string; streaming?: boolean }) {
  if (!content && streaming) {
    return (
      <div className="flex items-center gap-1.5 py-1 text-slate-400">
        <span className="size-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:0ms]" />
        <span className="size-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:150ms]" />
        <span className="size-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:300ms]" />
      </div>
    );
  }
  return (
    <>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      {streaming && <span className="ml-0.5 inline-block animate-pulse text-blue-600">▍</span>}
    </>
  );
}
