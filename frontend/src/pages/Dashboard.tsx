import { useCallback, useEffect, useState } from "react";

import { statsApi, type StatsPayload } from "../api/stats";

export default function DashboardPage() {
  const [stats, setStats] = useState<StatsPayload | null>(null);

  const refresh = useCallback(async () => {
    try {
      setStats(await statsApi.get());
    } catch {
      /* 폴링 실패는 무시 */
    }
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => void refresh(), 10000);
    return () => clearInterval(t);
  }, [refresh]);

  if (!stats) {
    return <div className="p-8 text-sm text-slate-400">통계를 불러오는 중...</div>;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">대시보드</h1>
        <p className="mt-1 text-sm text-slate-500">LINE-1 파일럿 라인 지식 시스템 현황 (10초 간격 갱신)</p>
      </div>

      {/* 지표 카드 */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card
          label="매뉴얼"
          value={`${stats.documents.done}/${stats.documents.total}`}
          sub={`${stats.documents.chunks}청크 · 실패 ${stats.documents.failed}`}
          accent="text-blue-600"
        />
        <Card
          label="설계도면"
          value={`${stats.drawings.done}/${stats.drawings.total}`}
          sub="수집 완료 / 전체"
          accent="text-violet-600"
        />
        <Card
          label="지식그래프"
          value={String(stats.graph.nodes)}
          sub={`관계 ${stats.graph.links}건`}
          accent="text-amber-600"
        />
        <Card
          label="채팅 세션"
          value={String(stats.chat.sessions)}
          sub={`수집 작업 대기 ${stats.jobs.active} · DEAD ${stats.jobs.dead}`}
          accent="text-emerald-600"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* 최근 질문 */}
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">최근 질문</h2>
          <ul className="space-y-2">
            {stats.chat.recent_questions.map((q) => (
              <li key={q.id} className="truncate rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
                💬 {q.content}
              </li>
            ))}
            {!stats.chat.recent_questions.length && <Empty text="아직 질문이 없습니다" />}
          </ul>
        </section>

        {/* 최근 수집 작업 */}
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">최근 수집 작업</h2>
          <ul className="space-y-2">
            {stats.jobs.recent.map((j) => (
              <li key={j.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span className="text-slate-700">
                  {j.type === "manual" ? "📄" : "📐"} {j.type}/{j.action}
                </span>
                <JobStatusBadge status={j.status} />
              </li>
            ))}
            {!stats.jobs.recent.length && <Empty text="작업 이력이 없습니다" />}
          </ul>
        </section>
      </div>
    </div>
  );
}

function Card({ label, value, sub, accent }: { label: string; value: string; sub: string; accent: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accent}`}>{value}</p>
      <p className="mt-1 text-xs text-slate-500">{sub}</p>
    </div>
  );
}

function JobStatusBadge({ status }: { status: string }) {
  const style: Record<string, string> = {
    DONE: "bg-emerald-100 text-emerald-700",
    RUNNING: "bg-blue-100 text-blue-700",
    PENDING: "bg-slate-100 text-slate-600",
    FAILED: "bg-amber-100 text-amber-700",
    DEAD: "bg-red-100 text-red-700",
  };
  return <span className={`rounded-full px-2 py-0.5 text-xs ${style[status] ?? style.PENDING}`}>{status}</span>;
}

function Empty({ text }: { text: string }) {
  return <li className="rounded-lg border border-dashed border-slate-200 px-3 py-6 text-center text-xs text-slate-400">{text}</li>;
}
