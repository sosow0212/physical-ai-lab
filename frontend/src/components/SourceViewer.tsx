/** 원본 뷰어 — 매뉴얼 PDF(페이지 앵커) / 도면 이미지 공용 라이트박스 */

import type { ChatSource } from "../api/chat";

interface ViewerProps {
  title: string;
  url: string; // PDF (#page=N 지원) 또는 이미지
  kind: "pdf" | "image";
  onClose: () => void;
}

export function SourceViewer({ title, url, kind, onClose }: ViewerProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-black/75 p-4 sm:p-8"
      onClick={onClose}
    >
      <div
        className="mx-auto flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <p className="truncate text-sm font-medium text-slate-800">{title}</p>
          <button
            className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            onClick={onClose}
            aria-label="닫기"
          >
            ✕ 닫기
          </button>
        </div>
        <div className="flex-1 bg-slate-100">
          {kind === "pdf" ? (
            <iframe src={url} title={title} className="h-full w-full" />
          ) : (
            <div className="flex h-full items-center justify-center overflow-auto p-4">
              <img src={url} alt={title} className="max-h-full max-w-full object-contain" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** 채팅 출처 → 뷰어 속성 변환 */
export function sourceViewerProps(s: ChatSource): { title: string; url: string; kind: "pdf" | "image" } {
  if (s.type === "drawing") {
    // 동적 import 순환 방지를 위해 직접 경로 사용
    return { title: `📐 ${s.title}`, url: `/api/v1/drawings/${s.doc_id}/file`, kind: "image" };
  }
  const pageAnchor = s.page ? `#page=${s.page}` : "";
  return { title: `📄 ${s.title}${s.page ? ` (p.${s.page})` : ""}`, url: `/api/v1/documents/${s.doc_id}/file${pageAnchor}`, kind: "pdf" };
}
