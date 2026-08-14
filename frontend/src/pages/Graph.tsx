import { useCallback, useEffect, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

import { graphApi, type GraphLink, type GraphNode, type ImpactResult } from "../api/graph";

const NODE_COLORS: Record<GraphNode["label"], string> = {
  Line: "#dc2626",
  Equipment: "#1d4ed8",
  Sensor: "#059669",
  Document: "#92400e",
};

const REL_KO: Record<GraphLink["type"], string> = {
  PART_OF: "소속",
  FEEDS: "공정흐름",
  AFFECTS: "영향",
  MONITORS: "감시",
  ATTACHED_TO: "부착",
  DESCRIBES: "문서설명",
};

const LABELS = ["Equipment", "Sensor", "Line"] as const;
const REL_TYPES = ["AFFECTS", "FEEDS", "PART_OF", "MONITORS", "ATTACHED_TO", "DESCRIBES"] as const;

interface GraphData {
  nodes: GraphNode[];
  links: (GraphLink & { __srcColor?: string })[];
}

export default function GraphPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<GraphData | null>(null);
  const [impact, setImpact] = useState<ImpactResult | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  const [showNodeForm, setShowNodeForm] = useState(false);
  const [showEdgeForm, setShowEdgeForm] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setData(await graphApi.overview());
    } catch {
      /* 무시 */
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0) setSize({ w: width, h: height });
    });
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const runImpact = useCallback(async (id: string) => {
    setSelected(id);
    try {
      setImpact(await graphApi.impact(id));
    } catch {
      setImpact(null);
    }
  }, []);

  const deleteNode = async (id: string) => {
    if (!confirm(`'${id}' 노드를 삭제할까요? 연결된 관계도 함께 삭제됩니다.`)) return;
    await graphApi.deleteNode(id);
    setImpact(null);
    setSelected(null);
    await refresh();
  };

  const highlight = useCallback(() => {
    if (!impact) return new Set<string>();
    return new Set([impact.root, ...impact.items.map((i) => i.impacted)]);
  }, [impact]);

  return (
    <div className="flex h-full flex-col">
      {/* 헤더 */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-8 py-4">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">지식그래프</h1>
          <p className="text-xs text-slate-500">
            노드 클릭 = 영향범위 하이라이트 · 더블클릭 = 노드 삭제 · 그래프는 재시드/수집(DESCRIBES)·직접 편집으로
            구성됩니다
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Legend />
          <button
            onClick={() => setShowNodeForm(true)}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-blue-700"
          >
            + 노드
          </button>
          <button
            onClick={() => setShowEdgeForm(true)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50"
          >
            + 관계
          </button>
        </div>
      </div>

      {/* 캔버스 */}
      <div ref={containerRef} className="relative flex-1 bg-slate-50">
        {data && (
          <ForceGraph2D
            width={size.w}
            height={size.h}
            graphData={data}
            backgroundColor="#f8fafc"
            nodeLabel={(n) => `${(n as GraphNode).name} (${(n as GraphNode).id})`}
            nodeCanvasObject={(n, ctx, globalScale) => {
              const node = n as GraphNode;
              const hl = highlight();
              const isHl = hl.size > 0 && hl.has(node.id);
              const r = node.label === "Equipment" ? 9 : node.label === "Line" ? 12 : 7;

              // 원
              ctx.beginPath();
              ctx.arc(node.x!, node.y!, r, 0, 2 * Math.PI);
              ctx.fillStyle = isHl ? "#f59e0b" : (NODE_COLORS[node.label] ?? "#64748b");
              ctx.fill();
              ctx.strokeStyle = selected === node.id ? "#0f172a" : "rgba(255,255,255,0.9)";
              ctx.lineWidth = selected === node.id ? 2.5 : 1.5;
              ctx.stroke();

              // 이름 라벨 (줌 레벨에 따라 크기 하한 보장)
              const fontSize = Math.max(11 / globalScale, 3.2);
              ctx.font = `${fontSize}px sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              ctx.fillStyle = "#0f172a";
              ctx.fillText(node.name ?? node.id, node.x!, node.y! + r + 2);
            }}
            linkColor={(l) => {
              const link = l as GraphLink;
              if (impact && (link.source as unknown as GraphNode).id === impact.root) return "#f59e0b";
              return "#94a3b8";
            }}
            linkWidth={(l) => ((l as GraphLink).type === "AFFECTS" ? 2 : 1)}
            linkCanvasObjectMode={() => "after"}
            linkCanvasObject={(l, ctx, globalScale) => {
              const link = l as GraphLink;
              const src = link.source as unknown as GraphNode;
              const tgt = link.target as unknown as GraphNode;
              if (!src.x || !tgt.x) return;
              const fontSize = Math.max(9 / globalScale, 2.6);
              ctx.font = `${fontSize}px sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "bottom";
              ctx.fillStyle = "#64748b";
              const mx = (src.x + tgt.x) / 2;
              const my = (src.y + tgt.y) / 2;
              ctx.fillText(REL_KO[link.type] ?? link.type, mx, my - 2);
            }}
            onNodeClick={(n: object) => void runImpact((n as GraphNode).id)}
            onNodeDblClick={(n: object) => void deleteNode((n as GraphNode).id)}
          />
        )}

        {/* 영향범위 패널 */}
        {impact && (
          <div className="absolute right-4 top-4 max-w-sm rounded-xl border border-amber-200 bg-white p-4 shadow-lg">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-800">🔗 {impact.root} 영향범위</h2>
              <div className="flex items-center gap-2">
                <button
                  className="text-xs text-red-500 hover:text-red-700"
                  onClick={() => void deleteNode(impact.root)}
                >
                  노드 삭제
                </button>
                <button
                  className="text-xs text-slate-400 hover:text-slate-600"
                  onClick={() => {
                    setImpact(null);
                    setSelected(null);
                  }}
                >
                  ✕
                </button>
              </div>
            </div>
            <ul className="space-y-1.5">
              {impact.items.map((item) => (
                <li key={item.impacted} className="text-xs text-slate-600">
                  <span className="font-medium text-slate-800">{item.impacted}</span> {item.impacted_name}
                  <span className="ml-1 text-slate-400">
                    (깊이 {item.depth} · {item.rels.map((r) => REL_KO[r as GraphLink["type"]] ?? r).join("→")})
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {showNodeForm && data && (
        <NodeFormModal
          onClose={() => setShowNodeForm(false)}
          onSaved={async () => {
            setShowNodeForm(false);
            await refresh();
          }}
        />
      )}
      {showEdgeForm && data && (
        <EdgeFormModal
          nodes={data.nodes}
          links={data.links}
          onClose={() => setShowEdgeForm(false)}
          onChanged={async () => {
            await refresh();
          }}
        />
      )}
    </div>
  );
}

function Legend() {
  return (
    <div className="hidden gap-2 text-xs text-slate-600 md:flex">
      {Object.entries(NODE_COLORS).map(([label, color]) => (
        <span key={label} className="flex items-center gap-1">
          <span className="size-2.5 rounded-full" style={{ background: color }} />
          {label}
        </span>
      ))}
    </div>
  );
}

function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
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

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none";

function NodeFormModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => Promise<void> }) {
  const [form, setForm] = useState({ id: "", label: "Equipment", name: "", when: "", severity: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!form.id || !form.name) {
      setError("ID와 이름은 필수입니다");
      return;
    }
    setBusy(true);
    try {
      const props: Record<string, string> = {};
      if (form.when) props.when = form.when;
      if (form.severity) props.severity = form.severity;
      await graphApi.upsertNode({ id: form.id, label: form.label, name: form.name, props });
      await onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ModalShell title="노드 추가/수정" onClose={onClose}>
      <div className="space-y-3">
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-600">ID * (예: EQ-500)</span>
          <input className={inputClass} value={form.id} onChange={(e) => setForm({ ...form, id: e.target.value })} />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-600">유형</span>
          <select
            className={inputClass}
            value={form.label}
            onChange={(e) => setForm({ ...form, label: e.target.value })}
          >
            {LABELS.map((l) => (
              <option key={l}>{l}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-600">이름 *</span>
          <input
            className={inputClass}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="예: 2차 칠러"
          />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-600">조건 (when)</span>
            <input className={inputClass} value={form.when} onChange={(e) => setForm({ ...form, when: e.target.value })} />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-600">심각도</span>
            <select className={inputClass} value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>
              <option value="">-</option>
              <option value="high">high</option>
              <option value="mid">mid</option>
              <option value="low">low</option>
            </select>
          </label>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          disabled={busy}
          onClick={() => void submit()}
          className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-slate-300"
        >
          {busy ? "저장 중..." : "저장 (같은 ID면 수정)"}
        </button>
      </div>
    </ModalShell>
  );
}

function EdgeFormModal({
  nodes,
  links,
  onClose,
  onChanged,
}: {
  nodes: GraphNode[];
  links: GraphLink[];
  onClose: () => void;
  onChanged: () => Promise<void>;
}) {
  const [form, setForm] = useState({ source: "", target: "", type: "AFFECTS", when: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectable = nodes.filter((n) => n.label !== "Document");

  const submit = async () => {
    if (!form.source || !form.target) {
      setError("출발/도착 노드를 선택하세요");
      return;
    }
    setBusy(true);
    try {
      await graphApi.upsertEdge({
        source: form.source,
        target: form.target,
        type: form.type,
        props: form.when ? { when: form.when } : {},
      });
      await onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setBusy(false);
    }
  };

  const removeEdge = async (link: GraphLink) => {
    const src = link.source as unknown as GraphNode;
    const tgt = link.target as unknown as GraphNode;
    await graphApi.deleteEdge(src.id, tgt.id, link.type);
    await onChanged();
  };

  return (
    <ModalShell title="관계 추가/삭제" onClose={onClose}>
      <div className="space-y-3">
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-600">출발 노드</span>
          <select className={inputClass} value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })}>
            <option value="">선택</option>
            {selectable.map((n) => (
              <option key={n.id} value={n.id}>
                {n.id} · {n.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-600">도착 노드</span>
          <select className={inputClass} value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })}>
            <option value="">선택</option>
            {selectable.map((n) => (
              <option key={n.id} value={n.id}>
                {n.id} · {n.name}
              </option>
            ))}
          </select>
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-600">관계 유형</span>
            <select className={inputClass} value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              {REL_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t} ({REL_KO[t]})
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-600">조건 (when)</span>
            <input className={inputClass} value={form.when} onChange={(e) => setForm({ ...form, when: e.target.value })} />
          </label>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          disabled={busy}
          onClick={() => void submit()}
          className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-slate-300"
        >
          {busy ? "저장 중..." : "관계 저장"}
        </button>

        <div className="max-h-48 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
          <p className="px-1 text-xs font-medium text-slate-500">기존 관계 (삭제하려면 ✕)</p>
          {links.map((l, i) => {
            const src = l.source as unknown as GraphNode;
            const tgt = l.target as unknown as GraphNode;
            if (!src?.id) return null;
            return (
              <div key={i} className="group flex items-center justify-between rounded px-2 py-1 text-xs hover:bg-slate-50">
                <span className="truncate text-slate-600">
                  {src.id} → <b className="text-blue-700">{REL_KO[l.type] ?? l.type}</b> → {tgt.id}
                </span>
                <button
                  className="hidden text-red-500 hover:text-red-700 group-hover:block"
                  onClick={() => void removeEdge(l)}
                >
                  ✕
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </ModalShell>
  );
}
