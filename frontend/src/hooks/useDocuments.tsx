import { useCallback, useEffect, useRef, useState } from "react";

import { documentsApi, type DocumentItem } from "../api/documents";

const STATUS_STYLE: Record<DocumentItem["status"], string> = {
  PENDING: "bg-slate-100 text-slate-600",
  PROCESSING: "bg-blue-100 text-blue-700 animate-pulse",
  DONE: "bg-emerald-100 text-emerald-700",
  FAILED: "bg-red-100 text-red-700",
};

/** 처리 중 문서가 있으면 자동 새로고침 (폴링) */
export function useDocuments() {
  const [items, setItems] = useState<DocumentItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const page = await documentsApi.list();
      setItems(page.items);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "목록 조회 실패");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const busy = items.some((d) => d.status === "PENDING" || d.status === "PROCESSING");
    if (busy && !timer.current) {
      timer.current = setInterval(() => void refresh(), 2500);
    }
    if (!busy && timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
    return () => {
      if (timer.current) {
        clearInterval(timer.current);
        timer.current = null;
      }
    };
  }, [items, refresh]);

  return { items, error, refresh };
}

export function StatusBadge({ status }: { status: DocumentItem["status"] }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[status]}`}>
      {status}
    </span>
  );
}
