import { useCallback, useEffect, useState } from "react";

import { documentsApi, type JobItem } from "../api/documents";

const FILTERS = ["ALL", "PENDING", "RUNNING", "DONE", "FAILED", "DEAD"] as const;

export default function PipelinePage() {
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("ALL");

  const refresh = useCallback(async () => {
    const page = await documentsApi.jobs();
    setJobs(page.items);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // 진행 중 작업이 있으면 폴링
  useEffect(() => {
    const busy = jobs.some((j) => j.status === "PENDING" || j.status === "RUNNING");
    if (!busy) return;
    const t = setInterval(() => void refresh(), 3000);
    return () => clearInterval(t);
  }, [jobs, refresh]);

  const visible = filter === "ALL" ? jobs : jobs.filter((j) => j.status === filter);

  return (
    <div className="mx-auto max-w-5xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">수집 작업</h1>
          <p className="mt-1 text-sm text-slate-500">
            Kafka 소비 → 파싱/청킹/임베딩 → 적재 파이프라인의 작업 이력 (재시도 3회 소진 시 DEAD → DLQ)
          </p>
        </div>
        <button
          onClick={() => void refresh()}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
        >
          새로고침
        </button>
      </div>

      <div className="mb-4 flex gap-2">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              filter === f ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {f}
            {f !== "ALL" && (
              <span className="ml-1 opacity-70">{jobs.filter((j) => j.status === f).length}</span>
            )}
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">작업</th>
              <th className="px-4 py-3">타입</th>
              <th className="px-4 py-3">상태</th>
              <th className="px-4 py-3">시도</th>
              <th className="px-4 py-3">에러</th>
              <th className="px-4 py-3">생성</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {visible.map((job) => (
              <tr key={job.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{job.id.slice(-8)}</td>
                <td className="px-4 py-3">
                  {job.type === "manual" ? "📄" : "📐"} {job.type}/{job.action}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={job.status} />
                </td>
                <td className="px-4 py-3 text-slate-600">{job.attempts}</td>
                <td className="max-w-xs truncate px-4 py-3 text-xs text-red-600" title={job.last_error ?? ""}>
                  {job.last_error ?? "-"}
                </td>
                <td className="px-4 py-3 text-xs text-slate-500">
                  {new Date(job.created_at).toLocaleString("ko-KR")}
                </td>
              </tr>
            ))}
            {!visible.length && (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-sm text-slate-400">
                  해당 상태의 작업이 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: JobItem["status"] }) {
  const style: Record<JobItem["status"], string> = {
    PENDING: "bg-slate-100 text-slate-600",
    RUNNING: "bg-blue-100 text-blue-700 animate-pulse",
    DONE: "bg-emerald-100 text-emerald-700",
    FAILED: "bg-amber-100 text-amber-700",
    DEAD: "bg-red-100 text-red-700",
  };
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${style[status]}`}>{status}</span>;
}
