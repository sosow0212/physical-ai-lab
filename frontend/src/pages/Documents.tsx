import { useRef, useState } from "react";

import { documentsApi } from "../api/documents";
import { StatusBadge, useDocuments } from "../hooks/useDocuments";

export default function DocumentsPage() {
  const { items, error, refresh } = useDocuments();
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const handleUpload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    setMessage(null);
    try {
      const result = await documentsApi.upload(Array.from(files));
      setMessage(`${result.documents.length}개 문서 업로드 → 수집 대기`);
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "업로드 실패");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const handleReingest = async (id: string) => {
    await documentsApi.reingest(id);
    await refresh();
  };

  const handleDelete = async (id: string) => {
    if (!confirm("이 문서를 삭제할까요? (Milvus 청크도 함께 정리됩니다)")) return;
    await documentsApi.remove(id);
    await refresh();
  };

  return (
    <div className="mx-auto max-w-5xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">매뉴얼 관리</h1>
          <p className="mt-1 text-sm text-slate-500">
            PDF를 업로드하면 파싱 → 청킹 → 임베딩 → 벡터DB 적재가 자동으로 진행됩니다.
          </p>
        </div>
        <label className="cursor-pointer rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
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
        <p className="mb-4 rounded-lg bg-blue-50 px-4 py-2 text-sm text-blue-700">{message}</p>
      )}
      {error && (
        <p className="mb-4 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">{error}</p>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">제목</th>
              <th className="px-4 py-3">상태</th>
              <th className="px-4 py-3">페이지/청크</th>
              <th className="px-4 py-3">설비 태그</th>
              <th className="px-4 py-3 text-right">작업</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((doc) => (
              <tr key={doc.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-800">{doc.title}</p>
                  {doc.error && <p className="mt-0.5 text-xs text-red-600">{doc.error}</p>}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={doc.status} />
                </td>
                <td className="px-4 py-3 text-slate-600">
                  {doc.page_count ?? "-"}p / {doc.chunk_count ?? "-"}청크
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {doc.equipment_refs.slice(0, 4).map((code) => (
                      <span key={code} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                        {code}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => void handleReingest(doc.id)}
                    className="mr-2 text-xs text-blue-600 hover:underline"
                  >
                    재수집
                  </button>
                  <button
                    onClick={() => void handleDelete(doc.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    삭제
                  </button>
                </td>
              </tr>
            ))}
            {!items.length && (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-sm text-slate-400">
                  업로드된 매뉴얼이 없습니다. 샘플은 <code>make bootstrap</code> 또는 상단 버튼으로 넣어보세요.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
