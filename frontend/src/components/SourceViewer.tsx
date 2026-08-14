/** 원본 뷰어 — 매뉴얼 PDF(페이지 앵커) / 도면 이미지 공용 라이트박스 */

import type { ChatSource } from "../api/chat";

interface ViewerProps {
  title: string;
  url: string; // PDF (#page=N 지원) 또는 이미지
  kind: "pdf" | "image";
  onClose: () => void;
}

export function SourceViewer({ title, url, kind, onClose }: ViewerProps) {
  // 다운로드 전용 URL 생성 (download=true 쿼리 추가, #page=N 앵커는 다운로드 시 불필요)
  const baseUrl = url.split("#")[0];
  const downloadUrl = baseUrl.includes("?")
    ? `${baseUrl}&download=true`
    : `${baseUrl}?download=true`;

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-black/75 p-4 sm:p-8"
      onClick={onClose}
    >
      <div
        className="mx-auto flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 bg-white">
          <div className="flex items-center gap-2 overflow-hidden">
            <span className="text-base">{kind === "pdf" ? "📄" : "📐"}</span>
            <p className="truncate text-sm font-semibold text-slate-800">{title}</p>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={downloadUrl}
              download
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100 hover:text-blue-700"
              title="파일 다운로드"
            >
              📥 다운로드
            </a>
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100 hover:text-blue-700"
              title="새 탭에서 열기"
            >
              ↗ 새 탭
            </a>
            <button
              className="rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              onClick={onClose}
              aria-label="닫기"
            >
              ✕ 닫기
            </button>
          </div>
        </div>
        <div className="relative flex-1 bg-slate-100 overflow-hidden">
          {kind === "pdf" ? (
            <object
              data={url}
              type="application/pdf"
              className="h-full w-full"
            >
              <iframe src={url} title={title} className="h-full w-full border-0" />
              <div className="flex h-full flex-col items-center justify-center p-8 text-center text-slate-500">
                <p className="text-sm">브라우저 내장 PDF 뷰어로 문서를 직접 표시할 수 없습니다.</p>
                <div className="mt-3 flex gap-3">
                  <a
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-medium text-white hover:bg-blue-700"
                  >
                    새 탭에서 보기
                  </a>
                  <a
                    href={downloadUrl}
                    download
                    className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    다운로드
                  </a>
                </div>
              </div>
            </object>
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
    return { title: s.title, url: `/api/v1/drawings/${s.doc_id}/file`, kind: "image" };
  }
  const pageAnchor = s.page ? `#page=${s.page}` : "";
  return {
    title: `${s.title}${s.page ? ` (p.${s.page})` : ""}`,
    url: `/api/v1/documents/${s.doc_id}/file${pageAnchor}`,
    kind: "pdf",
  };
}

