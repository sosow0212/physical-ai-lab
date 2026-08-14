import { useRef, useState } from "react";

import { documentsApi } from "../api/documents";
import { ChunkViewerModal } from "../components/ChunkViewerModal";
import { SourceViewer } from "../components/SourceViewer";
import { StatusBadge, useDocuments } from "../hooks/useDocuments";

export default function DocumentsPage() {
  const { items, error, refresh } = useDocuments();
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [viewingId, setViewingId] = useState<string | null>(null);
  const [chunkDoc, setChunkDoc] = useState<{ id: string; title: string } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const handleUpload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    setMessage(null);
    setUploadError(null);
    try {
      const result = await documentsApi.upload(Array.from(files));
      setMessage(`✓ ${result.documents.length}개 문서가 업로드되었습니다. 파이프라인 수집이 시작됩니다.`);
      await refresh();
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "업로드 중 오류가 발생했습니다.");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const handleReingest = async (id: string) => {
    try {
      await documentsApi.reingest(id);
      setMessage("문서 재수집이 요청되었습니다.");
      await refresh();
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "재수집 요청 실패");
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("이 문서를 삭제할까요? (Milvus 청크도 함께 정리됩니다)")) return;
    await documentsApi.remove(id);
    await refresh();
  };

  return (
    <div className="mx-auto max-w-6xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">매뉴얼 관리</h1>
          <p className="mt-1 text-sm text-slate-500">
            PDF를 업로드하면 파싱 → 청킹 → 임베딩 → 벡터DB 적재가 자동으로 진행됩니다.
          </p>
        </div>
        <label className="cursor-pointer rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 transition">
          {uploading ? "업로드 중..." : "+ PDF 업로드"}
          <input
            ref={fileInput}
            type="file"
            accept="application/pdf"
            multiple
            hidden
            onChange={(e) => void handleUpload(e.target.files)}
          />
        </label>
      </div>

      {message && (
        <div className="mb-4 flex items-center justify-between rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">
          <span>{message}</span>
          <button onClick={() => setMessage(null)} className="text-xs font-semibold text-blue-500 hover:text-blue-700">
            ✕
          </button>
        </div>
      )}

      {uploadError && (
        <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 shadow-sm">
          <span className="text-base">⚠️</span>
          <div className="flex-1">
            <p className="font-semibold">업로드 실패</p>
            <p className="mt-0.5 text-xs text-red-600 leading-relaxed">{uploadError}</p>
          </div>
          <button onClick={() => setUploadError(null)} className="text-xs font-semibold text-red-400 hover:text-red-600">
            ✕
          </button>
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">문서명</th>
              <th className="px-4 py-3">상태</th>
              <th className="px-4 py-3">페이지 / 청크</th>
              <th className="px-4 py-3">설비 태그</th>
              <th className="px-4 py-3 text-right">작업</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((doc) => (
              <tr key={doc.id} className="hover:bg-slate-50/70 transition">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <button
                      className="text-left font-medium text-slate-800 hover:text-blue-600 hover:underline"
                      title="클릭하면 원본 PDF를 미리보기로 엽니다"
                      onClick={() => setViewingId(doc.id)}
                    >
                      {doc.title}
                    </button>
                    <a
                      href={documentsApi.fileUrl(doc.id, true)}
                      download
                      className="text-slate-400 hover:text-slate-700"
                      title="PDF 직접 다운로드"
                    >
                      📥
                    </a>
                  </div>
                  {doc.error && (
                    <div className="mt-1 flex items-center gap-1 text-xs text-red-600 bg-red-50 px-2 py-0.5 rounded border border-red-100">
                      <span>⚠️ {doc.error}</span>
                    </div>
                  )}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={doc.status} />
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-600">{doc.page_count ?? "-"}p</span>
                    <span className="text-slate-300">/</span>
                    {doc.chunk_count !== null && doc.chunk_count > 0 ? (
                      <button
                        onClick={() => setChunkDoc({ id: doc.id, title: doc.title })}
                        className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700 hover:bg-blue-100 hover:text-blue-800 transition"
                        title="청크 분할 내역 및 본문 보기"
                      >
                        🧩 {doc.chunk_count}청크 보기
                      </button>
                    ) : (
                      <span className="text-slate-400 text-xs">-</span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {doc.equipment_refs.slice(0, 4).map((code) => (
                      <span key={code} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                        {code}
                      </span>
                    ))}
                    {doc.equipment_refs.length > 4 && (
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-400">
                        +{doc.equipment_refs.length - 4}
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => setViewingId(doc.id)}
                      className="text-xs font-medium text-slate-600 hover:text-blue-600"
                    >
                      미리보기
                    </button>
                    <button
                      onClick={() => void handleReingest(doc.id)}
                      className="text-xs font-medium text-blue-600 hover:underline"
                    >
                      재수집
                    </button>
                    <button
                      onClick={() => void handleDelete(doc.id)}
                      className="text-xs font-medium text-red-600 hover:underline"
                    >
                      삭제
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!items.length && (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-sm text-slate-400">
                  업로드된 매뉴얼이 없습니다. 상단 버튼으로 PDF를 업로드해보세요.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* PDF 미리보기 모달 */}
      {viewingId && items.find((d) => d.id === viewingId) && (
        <SourceViewer
          title={`📄 ${items.find((d) => d.id === viewingId)!.title}`}
          url={documentsApi.fileUrl(viewingId)}
          kind="pdf"
          onClose={() => setViewingId(null)}
        />
      )}

      {/* 청크 뷰어 모달 */}
      {chunkDoc && (
        <ChunkViewerModal
          documentId={chunkDoc.id}
          title={chunkDoc.title}
          onClose={() => setChunkDoc(null)}
        />
      )}
    </div>
  );
}

