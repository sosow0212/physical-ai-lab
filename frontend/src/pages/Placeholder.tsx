interface PlaceholderProps {
  title: string;
  phase: string;
}

/** 아직 구현되지 않은 페이지의 안내 화면 (Phase 완료 시 실제 페이지로 교체) */
export function Placeholder({ title, phase }: PlaceholderProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <h1 className="text-2xl font-semibold text-slate-700">{title}</h1>
      <p className="rounded-full bg-amber-100 px-3 py-1 text-sm font-medium text-amber-700">
        {phase}에서 구현 예정
      </p>
      <p className="max-w-md text-sm text-slate-500">
        진행 상황은 <code className="rounded bg-slate-200 px-1">docs/PROGRESS.md</code>에서 확인할 수
        있어요.
      </p>
    </div>
  );
}
