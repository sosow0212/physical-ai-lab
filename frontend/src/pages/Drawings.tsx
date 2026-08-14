import { useCallback, useEffect, useRef, useState } from "react";

import { drawingsApi, type DrawingForm, type DrawingItem } from "../api/drawings";

const STATUS_STYLE: Record<DrawingItem["status"], string> = {
  PENDING: "bg-slate-100 text-slate-600",
  PROCESSING: "bg-blue-100 text-blue-700 animate-pulse",
  DONE: "bg-emerald-100 text-emerald-700",
  FAILED: "bg-red-100 text-red-700",
};

const EMPTY_FORM: DrawingForm = { title: "", drawing_no: "", equipment: "", line: "LINE-1", description: "" };

export default function DrawingsPage() {
  const [items, setItems] = useState<DrawingItem[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<DrawingItem | null>(null);
  const [viewer, setViewer] = useState<DrawingItem | null>(null);

  const refresh = useCallback(async () => {
    setItems(await drawingsApi.list());
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // 처리 중 도면이 있으면 폴링
  useEffect(() => {
    const busy = items.some((d) => d.status === "PENDING" || d.status === "PROCESSING");
    if (!busy) return;
    const t = setInterval(() => void refresh(), 2500);
    return () => clearInterval(t);
  }, [items, refresh]);

  return (
    <div className="mx-auto max-w-6xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">도면 관리</h1>
          <p className="mt-1 text-sm text-slate-500">
            도면은 메타데이터와 함께 임베딩되어 챗봇 답변의 출처로 첨부됩니다.
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          + 도면 등록
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {items.map((d) => (
          <div key={d.id} className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            <button
              className="block w-full cursor-zoom-in border-b border-slate-100 bg-slate-50"
              onClick={() => setViewer(d)}
            >
              <img
                src={drawingsApi.fileUrl(d.id)}
                alt={d.title}
                className="h-40 w-full object-contain"
              />
            </button>
            <div className="p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-slate-800">{d.title}</p>
                  <p className="text-xs text-slate-500">
                    {d.drawing_no} · Rev {d.revision}
                  </p>
                </div>
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${STATUS_STYLE[d.status]}`}>
                  {d.status}
                </span>
              </div>
              {(d.equipment || d.line) && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {d.equipment && (
                    <span className="rounded bg-blue-50 px-1.5 py-0.5 text-xs text-blue-700">{d.equipment}</span>
                  )}
                  {d.line && (
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{d.line}</span>
                  )}
                </div>
              )}
              <p className="mt-2 line-clamp-2 text-xs text-slate-500">{d.description}</p>
              <div className="mt-3 flex gap-2 text-xs">
                <button className="text-blue-600 hover:underline" onClick={() => setEditing(d)}>
                  수정
                </button>
                <RevisionButton drawing={d} onDone={refresh} />
                <button
                  className="text-red-600 hover:underline"
                  onClick={async () => {
                    if (!confirm("도면을 삭제할까요?")) return;
                    await drawingsApi.remove(d.id);
                    await refresh();
                  }}
                >
                  삭제
                </button>
              </div>
            </div>
          </div>
        ))}
        {!items.length && (
          <p className="col-span-full rounded-xl border border-dashed border-slate-300 p-12 text-center text-sm text-slate-400">
            등록된 도면이 없습니다.
          </p>
        )}
      </div>

      {showForm && (
        <DrawingFormModal
          onClose={() => setShowForm(false)}
          onSaved={async () => {
            setShowForm(false);
            await refresh();
          }}
        />
      )}
      {editing && (
        <EditModal
          drawing={editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await refresh();
          }}
        />
      )}
      {viewer && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-8"
          onClick={() => setViewer(null)}
        >
          <div className="max-h-full max-w-5xl overflow-auto" onClick={(e) => e.stopPropagation()}>
            <img src={drawingsApi.fileUrl(viewer.id)} alt={viewer.title} className="rounded-lg bg-white" />
            <p className="mt-2 text-center text-sm text-white">
              {viewer.drawing_no} · Rev {viewer.revision} — {viewer.title}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function RevisionButton({ drawing, onDone }: { drawing: DrawingItem; onDone: () => Promise<void> }) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <button className="text-blue-600 hover:underline" onClick={() => inputRef.current?.click()}>
        리비전 업로드
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg"
        hidden
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (file) {
            await drawingsApi.addRevision(drawing.id, file);
            await onDone();
          }
          if (inputRef.current) inputRef.current.value = "";
        }}
      />
    </>
  );
}

function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-800">{title}</h2>
          <button className="text-slate-400 hover:text-slate-600" onClick={onClose}>
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-slate-600">{label}</span>
      {children}
    </label>
  );
}

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none";

function DrawingFormModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => Promise<void> }) {
  const [form, setForm] = useState<DrawingForm>(EMPTY_FORM);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!file || !form.title || !form.drawing_no) {
      setError("파일·제목·도면번호는 필수입니다");
      return;
    }
    setBusy(true);
    try {
      await drawingsApi.create(file, form);
      await onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "등록 실패");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ModalShell title="도면 등록" onClose={onClose}>
      <div className="space-y-3">
        <Field label="이미지 파일 (PNG/JPG)">
          <input type="file" accept="image/png,image/jpeg" className={inputClass} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </Field>
        <Field label="제목 *">
          <input className={inputClass} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        </Field>
        <Field label="도면번호 *">
          <input placeholder="예: DW-LINE1-002" className={inputClass} value={form.drawing_no} onChange={(e) => setForm({ ...form, drawing_no: e.target.value })} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="설비">
            <input placeholder="예: TCU-100" className={inputClass} value={form.equipment} onChange={(e) => setForm({ ...form, equipment: e.target.value })} />
          </Field>
          <Field label="라인">
            <input className={inputClass} value={form.line} onChange={(e) => setForm({ ...form, line: e.target.value })} />
          </Field>
        </div>
        <Field label="설명 (검색에 사용됨)">
          <textarea rows={3} className={inputClass} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </Field>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          disabled={busy}
          onClick={() => void submit()}
          className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-slate-300"
        >
          {busy ? "등록 중..." : "등록"}
        </button>
      </div>
    </ModalShell>
  );
}

function EditModal({
  drawing,
  onClose,
  onSaved,
}: {
  drawing: DrawingItem;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [form, setForm] = useState({
    title: drawing.title,
    equipment: drawing.equipment ?? "",
    line: drawing.line ?? "",
    description: drawing.description ?? "",
  });
  const [busy, setBusy] = useState(false);

  return (
    <ModalShell title={`${drawing.drawing_no} 수정`} onClose={onClose}>
      <div className="space-y-3">
        <Field label="제목">
          <input className={inputClass} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="설비">
            <input className={inputClass} value={form.equipment} onChange={(e) => setForm({ ...form, equipment: e.target.value })} />
          </Field>
          <Field label="라인">
            <input className={inputClass} value={form.line} onChange={(e) => setForm({ ...form, line: e.target.value })} />
          </Field>
        </div>
        <Field label="설명">
          <textarea rows={3} className={inputClass} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </Field>
        <p className="text-xs text-slate-400">텍스트 변경 시 임베딩 재생성을 위해 자동 재수집됩니다.</p>
        <button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            await drawingsApi.update(drawing.id, form);
            await onSaved();
          }}
          className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-slate-300"
        >
          {busy ? "저장 중..." : "저장"}
        </button>
      </div>
    </ModalShell>
  );
}
