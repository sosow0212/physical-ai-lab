import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  telemetryApi,
  type CircuitBreakerStatus,
  type CircuitState,
  type EarlyWarningAlert,
  type GeneratorStatus,
  type ScenarioType,
  type TelemetryEventData,
} from "../api/telemetry";

const SCENARIOS: { id: ScenarioType; label: string; desc: string; color: string } = {
  NORMAL: { id: "NORMAL", label: "🟢 100% 정상", desc: "기준치 내 안정적 가우시안 분포", color: "border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100" },
  ANOMALY_40: { id: "ANOMALY_40", label: "🟡 이상 40%", desc: "40% 확률로 온도 상승/압력 흔들림", color: "border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100" },
  ANOMALY_70: { id: "ANOMALY_70", label: "🟠 이상 70%", desc: "70% 확률로 심각한 이상 발생", color: "border-orange-300 bg-orange-50 text-orange-800 hover:bg-orange-100" },
  CRITICAL_SPIKE: { id: "CRITICAL_SPIKE", label: "🔴 과열 스파이크", desc: "즉각적인 서킷 브레이커 트립", color: "border-red-300 bg-red-50 text-red-800 hover:bg-red-100" },
  DRIFT: { id: "DRIFT", label: "📈 점진적 온도 상승", desc: "서서히 누적 과열 (조기 감지 테스트)", color: "border-purple-300 bg-purple-50 text-purple-800 hover:bg-purple-100" },
};

const STATE_BADGE: Record<CircuitState, { label: string; bg: string; text: string; ring: string }> = {
  NORMAL: { label: "정상 (NORMAL)", bg: "bg-emerald-500", text: "text-emerald-700 bg-emerald-50 border-emerald-200", ring: "" },
  WARNING: { label: "조기 경보 (WARNING)", bg: "bg-amber-500", text: "text-amber-700 bg-amber-50 border-amber-300", ring: "animate-pulse ring-2 ring-amber-400" },
  TRIP: { label: "차단됨 (TRIPPED)", bg: "bg-red-600", text: "text-red-700 bg-red-50 border-red-300", ring: "animate-pulse ring-4 ring-red-400" },
};

export default function EarlyWarningPage() {
  const navigate = useNavigate();

  const [generator, setGenerator] = useState<GeneratorStatus | null>(null);
  const [circuitBreakers, setCircuitBreakers] = useState<Record<string, CircuitBreakerStatus>>({});
  const [alerts, setAlerts] = useState<EarlyWarningAlert[]>([]);
  const [recentHistory, setRecentHistory] = useState<Record<string, number[]>>({});
  const [hz, setHz] = useState<number>(5);
  const [showCurlModal, setShowCurlModal] = useState<boolean>(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);

  // 초기 상태 로드
  useEffect(() => {
    void telemetryApi.getStatus().then((st) => {
      setGenerator(st);
      setHz(st.hz);
    });
    void telemetryApi.getCircuitBreakers().then((list) => {
      const map: Record<string, CircuitBreakerStatus> = {};
      const hist: Record<string, number[]> = {};
      list.forEach((cb) => {
        map[cb.equipment_id] = cb;
        hist[cb.equipment_id] = cb.recent_values || [];
      });
      setCircuitBreakers(map);
      setRecentHistory(hist);
    });
    void telemetryApi.getAlerts(20).then(setAlerts);
  }, []);

  // SSE 실시간 스트림 연결
  useEffect(() => {
    const es = new EventSource(telemetryApi.streamUrl());
    eventSourceRef.current = es;

    es.addEventListener("init", (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.circuit_breakers) {
          const map: Record<string, CircuitBreakerStatus> = {};
          data.circuit_breakers.forEach((cb: CircuitBreakerStatus) => {
            map[cb.equipment_id] = cb;
          });
          setCircuitBreakers(map);
        }
      } catch {
        /* 무시 */
      }
    });

    es.addEventListener("telemetry", (e) => {
      try {
        const data: TelemetryEventData = JSON.parse(e.data);
        setCircuitBreakers((prev) => {
          const current = prev[data.equipment_id];
          if (!current) return prev;
          return {
            ...prev,
            [data.equipment_id]: {
              ...current,
              current_value: data.value,
              z_score: data.z_score,
              slope: data.slope,
              state: data.state,
              updated_at: data.timestamp,
            },
          };
        });

        setRecentHistory((prev) => {
          const list = prev[data.equipment_id] || [];
          return {
            ...prev,
            [data.equipment_id]: [...list.slice(-25), data.value],
          };
        });

        setGenerator((prev) => (prev ? { ...prev, total_emitted: prev.total_emitted + 1 } : null));
      } catch {
        /* 무시 */
      }
    });

    es.addEventListener("alert", (e) => {
      try {
        const newAlert: EarlyWarningAlert = JSON.parse(e.data);
        setAlerts((prev) => [newAlert, ...prev.slice(0, 30)]);
      } catch {
        /* 무시 */
      }
    });

    es.addEventListener("circuit_reset", () => {
      void telemetryApi.getCircuitBreakers().then((list) => {
        const map: Record<string, CircuitBreakerStatus> = {};
        list.forEach((cb) => (map[cb.equipment_id] = cb));
        setCircuitBreakers(map);
      });
    });

    // 신규 설비 자동 등록 / 레지스트리 변경 이벤트 → 브레이커 목록 갱신
    const refreshBreakers = () => {
      void telemetryApi.getCircuitBreakers().then((list) => {
        const map: Record<string, CircuitBreakerStatus> = {};
        list.forEach((cb) => (map[cb.equipment_id] = cb));
        setCircuitBreakers(map);
      });
    };
    es.addEventListener("monitor_registered", refreshBreakers);
    es.addEventListener("registry_changed", refreshBreakers);

    return () => {
      es.close();
    };
  }, []);

  const handleToggleGenerator = async () => {
    if (generator?.is_running) {
      const st = await telemetryApi.stop();
      setGenerator(st);
      setActionMsg("제너레이터가 정지되었습니다.");
    } else {
      const st = await telemetryApi.start(hz, generator?.scenario || "NORMAL");
      setGenerator(st);
      setActionMsg(`제너레이터가 가동되었습니다 (${hz} Hz).`);
    }
    setTimeout(() => setActionMsg(null), 3000);
  };

  const handleScenarioChange = async (scenario: ScenarioType) => {
    const st = await telemetryApi.setScenario(scenario, hz);
    setGenerator(st);
    setActionMsg(`시나리오가 '${SCENARIOS[scenario].label}'(으)로 변경되었습니다.`);
    setTimeout(() => setActionMsg(null), 3000);
  };

  const handleReset = async (equipmentId?: string) => {
    await telemetryApi.resetCircuitBreaker(equipmentId);
    setActionMsg(equipmentId ? `${equipmentId} 서킷 브레이커가 리셋되었습니다.` : "전체 서킷 브레이커가 리셋되었습니다.");
    setTimeout(() => setActionMsg(null), 3000);
  };

  const cbList = Object.values(circuitBreakers);
  const trippedCount = cbList.filter((c) => c.state === "TRIP").length;
  const warningCount = cbList.filter((c) => c.state === "WARNING").length;

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-slate-100">
      {/* 상단 헤더 */}
      <div className="border-b border-slate-200 bg-white px-8 py-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold text-slate-800">조기 경보 시스템 (Early Warning)</h1>
              <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700">
                Kafka · 슬라이딩 윈도우 · 서킷브레이커
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              실시간 모의 센서 텔레메트리를 분석하여 임계치 초과 전 이상 징후를 선제 감지하고, GraphRAG와 RAG 조치 매뉴얼을 연계합니다.
            </p>
          </div>

          {/* 지표 요약 & 리셋 버튼 */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs">
              <span className="text-slate-500">발송 건수:</span>
              <span className="font-mono font-bold text-slate-800">
                {generator?.total_emitted?.toLocaleString() || 0}
              </span>
            </div>

            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs">
              <span className="text-slate-500">이상 설비:</span>
              <span className={`font-bold ${trippedCount > 0 ? "text-red-600 font-extrabold" : warningCount > 0 ? "text-amber-600" : "text-emerald-600"}`}>
                {trippedCount > 0 ? `트립 ${trippedCount}대` : warningCount > 0 ? `주의 ${warningCount}대` : "모두 정상"}
              </span>
            </div>

            <button
              onClick={() => void handleReset()}
              className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 hover:text-blue-600 transition"
              title="모든 서킷 브레이커를 정상으로 복귀"
            >
              🔄 전체 리셋
            </button>
          </div>
        </div>

        {/* 액션 피드백 배너 */}
        {actionMsg && (
          <div className="mt-3 rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 transition">
            {actionMsg}
          </div>
        )}
      </div>

      <div className="space-y-6 p-8">
        {/* 1. 모의 데이터 제너레이터 컨트롤러 바 */}
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-4">
            <div className="flex items-center gap-3">
              <span className="text-lg">⚙️</span>
              <div>
                <h2 className="text-sm font-bold text-slate-800">모의 공정 데이터 Generator</h2>
                <p className="text-xs text-slate-500">
                  초당 텔레메트리 발송 속도 및 모의 이상 시나리오를 실시간 주입합니다.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* 속도 슬라이더 */}
              <div className="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-1.5 text-xs text-slate-600 border border-slate-200">
                <span className="font-medium">속도:</span>
                <input
                  type="range"
                  min="1"
                  max="20"
                  value={hz}
                  onChange={(e) => {
                    const newHz = Number(e.target.value);
                    setHz(newHz);
                    if (generator?.is_running) {
                      void telemetryApi.setScenario(generator.scenario, newHz);
                    }
                  }}
                  className="h-1.5 w-20 accent-blue-600 cursor-pointer"
                />
                <span className="font-bold text-blue-700 w-8">{hz} Hz</span>
              </div>

              {/* 가동 토글 버튼 */}
              <button
                onClick={() => void handleToggleGenerator()}
                className={`rounded-xl px-4 py-2 text-xs font-bold shadow-sm transition ${
                  generator?.is_running
                    ? "bg-red-600 text-white hover:bg-red-700"
                    : "bg-blue-600 text-white hover:bg-blue-700"
                }`}
              >
                {generator?.is_running ? "⏸️ 제너레이터 정지" : "▶️ 제너레이터 시작"}
              </button>

              <button
                onClick={() => setShowCurlModal(true)}
                className="rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
              >
                📋 curl 명령 보기
              </button>
            </div>
          </div>

          {/* 시나리오 버튼 바 */}
          <div className="mt-4">
            <p className="mb-2 text-xs font-semibold text-slate-600">주입 시나리오 선택:</p>
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
              {(Object.keys(SCENARIOS) as ScenarioType[]).map((key) => {
                const sc = SCENARIOS[key];
                const isSelected = generator?.scenario === key;
                return (
                  <button
                    key={key}
                    onClick={() => void handleScenarioChange(key)}
                    className={`flex flex-col text-left rounded-xl border p-3 transition shadow-sm ${
                      isSelected
                        ? "border-blue-600 bg-blue-50/90 ring-2 ring-blue-500 shadow-md"
                        : sc.color
                    }`}
                  >
                    <span className="text-xs font-bold leading-none">{sc.label}</span>
                    <span className="mt-1 text-[11px] text-slate-600 line-clamp-2 leading-tight">
                      {sc.desc}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </section>

        {/* 2. 공정별 서킷 브레이커 그리드 */}
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-800 flex items-center gap-2">
              <span>⚡ 공정별 서킷 브레이커 (Circuit Breakers)</span>
              <span className="text-xs font-normal text-slate-500">
                {cbList.length}대 설비 실시간 감시 (그래프 연동 · 자동 등록 포함)
              </span>
            </h2>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {cbList.map((cb) => {
              const badge = STATE_BADGE[cb.state];
              const history = recentHistory[cb.equipment_id] || [];

              return (
                <div
                  key={cb.equipment_id}
                  className={`relative flex flex-col justify-between rounded-2xl border bg-white p-4 shadow-sm transition hover:shadow-md ${badge.ring} ${
                    cb.state === "TRIP"
                      ? "border-red-400 bg-red-50/30"
                      : cb.state === "WARNING"
                      ? "border-amber-300 bg-amber-50/20"
                      : "border-slate-200"
                  }`}
                >
                  <div>
                    {/* 카드 헤더 */}
                    <div className="flex items-start justify-between">
                      <div>
                        <span className="text-xs font-bold text-slate-800">{cb.equipment_name}</span>
                        <span className="ml-1 text-[11px] text-slate-400 font-mono">({cb.equipment_id})</span>
                      </div>
                      <span className={`size-2.5 rounded-full ${badge.bg}`} />
                    </div>

                    {/* 센서명 & 상태 뱃지 & 등록 소스 */}
                    <div className="mt-2 flex items-center justify-between gap-1">
                      <span className="text-[11px] text-slate-500 truncate">
                        {cb.sensor_id} · {cb.metric_name}
                      </span>
                      <div className="flex shrink-0 items-center gap-1">
                        {cb.source === "auto" && (
                          <span
                            title="그래프에 없는 설비가 자동 등록됨 (통계 전용 감시) — 그래프에서 임계치를 설정하세요"
                            className="rounded bg-indigo-50 px-1 py-0.5 text-[9px] font-semibold text-indigo-600"
                          >
                            AUTO
                          </span>
                        )}
                        <span className={`rounded-md border px-1.5 py-0.5 text-[10px] font-bold ${badge.text}`}>
                          {cb.state}
                        </span>
                      </div>
                    </div>

                    {/* 실시간 수치 게이지 */}
                    <div className="mt-3 text-center">
                      <div className="text-2xl font-black font-mono tracking-tight text-slate-900">
                        {cb.current_value.toFixed(cb.unit === "MPa" ? 3 : 1)}
                        <span className="ml-1 text-xs font-semibold text-slate-500">{cb.unit}</span>
                      </div>

                      {/* 임계치 기준 안내 (자동 등록 설비는 통계 전용) */}
                      <div className="mt-1 flex justify-center gap-2 text-[10px] text-slate-500 font-medium">
                        {cb.threshold_warning != null && cb.threshold_trip != null ? (
                          <>
                            <span>주의: {cb.threshold_warning}{cb.unit}</span>
                            <span>·</span>
                            <span className="text-red-600 font-semibold">트립: {cb.threshold_trip}{cb.unit}</span>
                          </>
                        ) : (
                          <span className="text-indigo-500">통계 전용 (임계치 미등록)</span>
                        )}
                      </div>
                    </div>

                    {/* 슬라이딩 윈도우 지표 (Z-score & 기울기) */}
                    <div className="mt-3 grid grid-cols-2 gap-1 rounded-lg bg-slate-50 p-2 text-[11px]">
                      <div>
                        <span className="text-slate-400">Z-Score:</span>
                        <span className={`ml-1 font-bold ${cb.z_score >= 3.0 ? "text-red-600" : cb.z_score >= 2.0 ? "text-amber-600" : "text-slate-700"}`}>
                          {cb.z_score.toFixed(1)}σ
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400">변화율:</span>
                        <span className="ml-1 font-bold text-slate-700">
                          {cb.slope > 0 ? `+${cb.slope.toFixed(2)}` : cb.slope.toFixed(2)}
                        </span>
                      </div>
                    </div>

                    {/* 간이 스파크라인 */}
                    <div className="mt-3 h-8 w-full">
                      <Sparkline values={history} unit={cb.unit} isTrip={cb.state === "TRIP"} />
                    </div>
                  </div>

                  {/* 개별 리셋 버튼 */}
                  {cb.state !== "NORMAL" && (
                    <button
                      onClick={() => void handleReset(cb.equipment_id)}
                      className="mt-3 w-full rounded-lg bg-white border border-slate-300 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-sm"
                    >
                      🔄 차단 해제 (리셋)
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* 3. 조기 경보 및 GraphRAG/RAG 연계 피드 */}
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <span className="text-lg">🚨</span>
              <h2 className="text-sm font-bold text-slate-800">조기 이상 경보 및 GraphRAG 조치 피드</h2>
              <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-bold text-red-600">
                실시간 발생 {alerts.length}건
              </span>
            </div>
          </div>

          {!alerts.length ? (
            <div className="py-12 text-center text-slate-400 text-sm">
              <p className="text-2xl mb-1">🛡️</p>
              현재 감지된 조기 경보가 없습니다. 공정이 안정적으로 가동 중입니다.
            </div>
          ) : (
            <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
              {alerts.map((al) => {
                const isCrit = al.severity === "TRIP" || al.severity === "CRITICAL";

                return (
                  <div
                    key={al.alert_id}
                    className={`rounded-xl border p-4 transition ${
                      isCrit
                        ? "border-red-200 bg-red-50/40 hover:bg-red-50/70"
                        : "border-amber-200 bg-amber-50/40 hover:bg-amber-50/70"
                    }`}
                  >
                    {/* 경보 상단 메타 */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`rounded-md px-2 py-0.5 text-xs font-bold text-white ${
                            isCrit ? "bg-red-600" : "bg-amber-600"
                          }`}
                        >
                          {al.severity}
                        </span>
                        <span className="font-bold text-slate-900 text-sm">
                          {al.equipment_name} ({al.equipment_id}) — {al.reason}
                        </span>
                      </div>
                      <span className="text-xs text-slate-400 font-mono">
                        {new Date(al.timestamp).toLocaleTimeString()}
                      </span>
                    </div>

                    {/* 실측 수치 & 통계 */}
                    <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-600">
                      <span>센서: <b>{al.sensor_id}</b> ({al.metric_name})</span>
                      <span>측정값: <b className="text-red-700">{al.value}{al.unit}</b></span>
                      <span>Z-Score: <b>{al.z_score}σ</b></span>
                    </div>

                    {/* GraphRAG 하류 영향도 경로 체인 */}
                    {al.impact_path && al.impact_path.length > 1 && (
                      <div className="mt-3 rounded-lg bg-white/80 p-2.5 border border-slate-200/80 text-xs">
                        <p className="font-semibold text-slate-700 mb-1.5 flex items-center gap-1">
                          <span>🔗 GraphRAG 하류 파급 영향 경로:</span>
                        </p>
                        <div className="flex flex-wrap items-center gap-1.5">
                          {al.impact_path.map((node, i) => (
                            <span key={i} className="flex items-center gap-1">
                              <span className={`rounded px-1.5 py-0.5 font-medium ${i === 0 ? "bg-red-100 text-red-800 font-bold" : "bg-slate-100 text-slate-700"}`}>
                                {node}
                              </span>
                              {i < al.impact_path.length - 1 && <span className="text-slate-400">→</span>}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* RAG 매뉴얼 긴급 조치 가이드 */}
                    {al.guide_summary && (
                      <div className="mt-2 rounded-lg bg-blue-50/70 p-2.5 border border-blue-200/60 text-xs text-blue-900">
                        <p className="font-bold text-blue-800 mb-1">📄 RAG 매뉴얼 긴급 조치 가이드:</p>
                        <p className="leading-relaxed font-mono whitespace-pre-wrap text-[11px] text-blue-950">
                          {al.guide_summary}
                        </p>
                      </div>
                    )}

                    {/* 챗봇 연계 버튼 */}
                    <div className="mt-3 flex justify-end">
                      <button
                        onClick={() =>
                          navigate(
                            `/chat?ask=${encodeURIComponent(
                              `[긴급] ${al.equipment_name}(${al.equipment_id}) ${al.sensor_id} 센서에서 "${al.reason}" 경보가 발생했어. 영향범위와 매뉴얼 기반 긴급 조치 절차를 알려줘.`,
                            )}`,
                          )
                        }
                        className="inline-flex items-center gap-1.5 rounded-lg bg-white border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:text-blue-600 shadow-sm"
                      >
                        💬 챗봇에서 긴급 조치 가이드 질의하기 →
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {/* curl 가이드 모달 */}
      {showCurlModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={() => setShowCurlModal(false)}>
          <div className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <h3 className="text-base font-bold text-slate-800">📋 텔레메트리 시뮬레이션 curl 명령어 모음</h3>
              <button onClick={() => setShowCurlModal(false)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <div className="mt-4 space-y-3 text-xs">
              <div>
                <p className="font-semibold text-slate-700 mb-1">1. 이상 40% 시나리오 주입:</p>
                <pre className="rounded-lg bg-slate-900 p-3 text-emerald-400 font-mono overflow-x-auto">
{`curl -X POST http://localhost:8000/api/v1/telemetry/generator/scenario \\
  -H "Content-Type: application/json" \\
  -d '{"scenario": "ANOMALY_40", "hz": 10}'`}
                </pre>
              </div>

              <div>
                <p className="font-semibold text-slate-700 mb-1">2. 이상 70% 고위험 시나리오 주입:</p>
                <pre className="rounded-lg bg-slate-900 p-3 text-emerald-400 font-mono overflow-x-auto">
{`curl -X POST http://localhost:8000/api/v1/telemetry/generator/scenario \\
  -H "Content-Type: application/json" \\
  -d '{"scenario": "ANOMALY_70", "hz": 10}'`}
                </pre>
              </div>

              <div>
                <p className="font-semibold text-slate-700 mb-1">3. 급격한 과열 스파이크 (트립 테스트):</p>
                <pre className="rounded-lg bg-slate-900 p-3 text-emerald-400 font-mono overflow-x-auto">
{`curl -X POST http://localhost:8000/api/v1/telemetry/generator/scenario \\
  -H "Content-Type: application/json" \\
  -d '{"scenario": "CRITICAL_SPIKE"}'`}
                </pre>
              </div>

              <div>
                <p className="font-semibold text-slate-700 mb-1">4. 서킷 브레이커 전체 리셋:</p>
                <pre className="rounded-lg bg-slate-900 p-3 text-emerald-400 font-mono overflow-x-auto">
{`curl -X POST http://localhost:8000/api/v1/telemetry/circuit-breaker/reset`}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** 경량 실시간 스파크라인 컴포넌트 */
function Sparkline({ values, unit, isTrip }: { values: number[]; unit: string; isTrip: boolean }) {
  if (!values.length) return <div className="h-full w-full bg-slate-50 rounded" />;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const width = 200;
  const height = 30;

  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1 || 1)) * width;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg className="h-full w-full overflow-visible" viewBox={`0 0 ${width} ${height}`}>
      <polyline
        fill="none"
        stroke={isTrip ? "#dc2626" : "#2563eb"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
}
