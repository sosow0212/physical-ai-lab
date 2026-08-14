import { useEffect, useState } from "react";
import { documentsApi, type DocumentChunk } from "../api/documents";

interface ChunkViewerModalProps {
  documentId: string;
  title: string;
  onClose: () => void;
}

export function ChunkViewerModal({ documentId, title, onClose }: ChunkViewerModalProps) {
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selectedPage, setSelectedPage] = useState<number | "all">("all");
  const [copiedSeq, setCopiedSeq] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    documentsApi
      .getChunks(documentId)
      .then((res) => {
        if (active) {
          setChunks(res.chunks);
        }
      })
      .catch((e) => {
        if (active) {
          setError(e instanceof Error ? e.message : "청크 목록을 불러오지 못했습니다.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [documentId]);

  // 사용 가능한 페이지 목록
  const pages = Array.from(new Set(chunks.map((c) => c.page))).sort((a, b) => a - b);

  // 필터링된 청크 목록
  const filteredChunks = chunks.filter((c) => {
    if (selectedPage !== "all" && c.page !== selectedPage) return false;
    if (!search.trim()) return true;
    const query = search.toLowerCase();
    return (
      c.text.toLowerCase().includes(query) ||
      c.heading.toLowerCase().includes(query) ||
      String(c.seq + 1).includes(query)
    );
  });

  const handleCopy = async (seq: number, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSeq(seq);
      setTimeout(() => setCopiedSeq(null), 2000);
    } catch {
      /* 무시 */
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/70 p-4 sm:p-6"
      onClick={onClose}
    >
      <div
        className="flex h-full max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 상단 헤더 */}
        <div className="border-b border-slate-200 bg-white px-6 py-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 overflow-hidden">
              <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 font-bold">
                🧩
              </div>
              <div className="overflow-hidden">
                <h2 className="truncate text-base font-semibold text-slate-800">
                  {title} <span className="font-normal text-slate-500">— 분할 청크 뷰어</span>
                </h2>
                <p className="text-xs text-slate-500">
                  RAG 파이프라인에서 벡터DB(Milvus)에 적재된 청크와 메타데이터를 학습/검증용으로 확인합니다.
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              aria-label="닫기"
            >
              ✕
            </button>
          </div>

          {/* 검색 및 필터 툴바 */}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <div className="relative min-w-[220px] flex-1">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="청크 내용, 헤딩, 번호 검색..."
                className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-1.5 pl-8 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none"
              />
              <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-400">
                🔍
              </span>
              {search && (
                <button
                  onClick={() => setSearch("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-600"
                >
                  ✕
                </button>
              )}
            </div>

            {/* 페이지 필터 */}
            {pages.length > 1 && (
              <div className="flex items-center gap-1.5 text-xs text-slate-600">
                <span className="font-medium text-slate-500">페이지:</span>
                <select
                  value={selectedPage}
                  onChange={(e) =>
                    setSelectedPage(e.target.value === "all" ? "all" : Number(e.target.value))
                  }
                  className="rounded-lg border border-slate-300 bg-slate-50 px-2 py-1.5 text-xs font-medium text-slate-700 focus:border-blue-500 focus:bg-white focus:outline-none"
                >
                  <option value="all">전체 ({pages.length}p)</option>
                  {pages.map((p) => (
                    <option key={p} value={p}>
                      p.{p}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* 청크 요약 배지 */}
            <div className="flex items-center gap-2">
              <span className="rounded-md bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
                총 {chunks.length}개 청크 {search || selectedPage !== "all" ? `(필터됨: ${filteredChunks.length}개)` : ""}
              </span>
            </div>
          </div>
        </div>

        {/* 본문 청크 목록 영역 */}
        <div className="flex-1 overflow-y-auto bg-slate-50 p-6">
          {loading && (
            <div className="flex h-64 flex-col items-center justify-center gap-3 text-slate-400">
              <div className="size-8 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
              <p className="text-sm font-medium">Milvus에서 청크를 조회하고 있습니다...</p>
            </div>
          )}

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-red-700">
              <p className="font-medium">{error}</p>
              <p className="mt-1 text-xs text-red-500">
                문서가 아직 처리 중이거나 적재되지 않았을 수 있습니다.
              </p>
            </div>
          )}

          {!loading && !error && filteredChunks.length === 0 && (
            <div className="flex h-64 flex-col items-center justify-center gap-2 text-center text-slate-400">
              <span className="text-3xl">📭</span>
              <p className="text-sm font-medium text-slate-600">
                {search || selectedPage !== "all"
                  ? "검색 조건과 일치하는 청크가 없습니다."
                  : "적재된 청크가 없습니다."}
              </p>
              {(search || selectedPage !== "all") && (
                <button
                  onClick={() => {
                    setSearch("");
                    setSelectedPage("all");
                  }}
                  className="mt-2 text-xs font-medium text-blue-600 hover:underline"
                >
                  필터 초기화
                </button>
              )}
            </div>
          )}

          {!loading && !error && filteredChunks.length > 0 && (
            <div className="space-y-4">
              {filteredChunks.map((chunk) => {
                const isCopied = copiedSeq === chunk.seq;
                const tokenEstimate = Math.round(chunk.char_count / 3);

                return (
                  <div
                    key={chunk.seq}
                    className="group rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-blue-300 hover:shadow-md"
                  >
                    {/* 청크 카드 헤더 */}
                    <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-700">
                          청크 #{chunk.seq + 1}
                        </span>
                        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                          📄 p.{chunk.page}
                        </span>
                        <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                          📏 {chunk.char_count}자 (약 {tokenEstimate} 토큰)
                        </span>
                      </div>

                      <button
                        onClick={() => void handleCopy(chunk.seq, chunk.text)}
                        className={`rounded-lg border px-2.5 py-1 text-xs font-medium transition ${
                          isCopied
                            ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                            : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                        }`}
                      >
                        {isCopied ? "✓ 복사됨" : "📋 텍스트 복사"}
                      </button>
                    </div>

                    {/* 헤딩 계층 경로 브레드크럼 */}
                    {chunk.heading && (
                      <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-blue-800 bg-blue-50/70 rounded-md px-2.5 py-1">
                        <span className="text-blue-500">🏷️ 헤딩:</span>
                        <span className="truncate">{chunk.heading}</span>
                      </div>
                    )}

                    {/* 청크 텍스트 본문 */}
                    <div className="rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-800 whitespace-pre-wrap font-mono selection:bg-blue-100">
                      {chunk.text}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* 하단 푸터 */}
        <div className="flex items-center justify-between border-t border-slate-200 bg-white px-6 py-3 text-xs text-slate-500">
          <span>
            💡 헤딩 프리픽스(<code>[문서명 &gt; 헤딩]</code>)는 검색 품질 향상을 위해 본문 앞에 자동 주입됩니다.
          </span>
          <button
            onClick={onClose}
            className="rounded-lg bg-slate-100 px-4 py-1.5 font-medium text-slate-700 hover:bg-slate-200"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
