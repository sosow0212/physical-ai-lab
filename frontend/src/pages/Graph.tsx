import { useCallback, useEffect, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

import { documentsApi } from "../api/documents";
import { graphApi, type GraphLink, type GraphNode, type ImpactResult } from "../api/graph";
import { SourceViewer } from "../components/SourceViewer";

const NODE_COLORS: Record<GraphNode["label"], string> = {
  Line: "#dc2626", // red
  Equipment: "#1d4ed8", // blue
  Sensor: "#059669", // emerald
  Document: "#92400e", // amber/brown
};

const NODE_LABELS_KO: Record<GraphNode["label"], string> = {
  Line: "생산라인",
  Equipment: "설비",
  Sensor: "센서",
  Document: "매뉴얼 문서",
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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<any>(null);

  const [data, setData] = useState<GraphData | null>(null);
  const [impact, setImpact] = useState<ImpactResult | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  const [spacing, setSpacing] = useState(130);
  const [showNodeForm, setShowNodeForm] = useState(false);
  const [showEdgeForm, setShowEdgeForm] = useState(false);
  const [viewingDoc, setViewingDoc] = useState<{ id: string; title: string } | null>(null);
  const [copiedId, setCopiedId] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await graphApi.overview();
      setData(res);
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

  // 노드 간격/물리력 조절 반영
  useEffect(() => {
    if (fgRef.current && data) {
      const charge = fgRef.current.d3Force("charge");
      if (charge) {
        charge.strength(-spacing * 3.8);
      }
      const link = fgRef.current.d3Force("link");
      if (link) {
        link.distance(spacing);
      }
      fgRef.current.d3ReheatSimulation();
    }
  }, [spacing, data]);

  const runImpact = useCallback(async (node: GraphNode) => {
    setSelectedNode(node);
    if (node.label === "Document") {
      setImpact(null);
      return;
    }
    try {
      const res = await graphApi.impact(node.id);
      setImpact(res);
    } catch {
      setImpact(null);
    }
  }, []);

  const handleZoomIn = () => {
    if (fgRef.current) {
      const current = fgRef.current.zoom();
      fgRef.current.zoom(current * 1.35, 300);
    }
  };

  const handleZoomOut = () => {
    if (fgRef.current) {
      const current = fgRef.current.zoom();
      fgRef.current.zoom(current / 1.35, 300);
    }
  };

  const handleZoomToFit = () => {
    if (fgRef.current) {
      fgRef.current.zoomToFit(400, 50);
    }
  };

  const deleteNode = async (id: string) => {
    if (!confirm(`'${id}' 노드를 삭제할까요? 연결된 관계도 함께 삭제됩니다.`)) return;
    await graphApi.deleteNode(id);
    setImpact(null);
    setSelectedNode(null);
    await refresh();
  };

  const highlight = useCallback(() => {
    if (!impact) return new Set<string>();
    return new Set([impact.root, ...impact.items.map((i) => i.impacted)]);
  }, [impact]);

  const copyNodeId = (id: string) => {
    void navigator.clipboard.writeText(id);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 1500);
  };

  // 선택된 노드의 연결 관계 계산
  const selectedRelations = selectedNode && data
    ? {
        incoming: data.links.filter((l) => {
          const tgtId = typeof l.target === "object" ? (l.target as GraphNode).id : l.target;
          return tgtId === selectedNode.id;
        }),
        outgoing: data.links.filter((l) => {
          const srcId = typeof l.source === "object" ? (l.source as GraphNode).id : l.source;
          return srcId === selectedNode.id;
        }),
      }
    : null;

  return (
    <div className="flex h-full flex-col">
      {/* 헤더 */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-8 py-3.5 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold text-slate-800">지식그래프 (GraphRAG)</h1>
            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700">
              Neo4j
            </span>
          </div>
          <p className="mt-0.5 text-xs text-slate-500">
            노드 클릭 = 상세 정보 및 영향범위 분석 · 드래그 = 노드 이동 · 도구로 확대/축소 및 간격 조절
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Legend />
          <button
            onClick={() => setShowNodeForm(true)}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-blue-700 transition"
          >
            + 노드
          </button>
          <button
            onClick={() => setShowEdgeForm(true)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 transition"
          >
            + 관계
          </button>
        </div>
      </div>

      {/* 캔버스 영역 */}
      <div ref={containerRef} className="relative flex-1 bg-slate-50 overflow-hidden">
        {data && (
          <ForceGraph2D
            ref={fgRef}
            width={size.w}
            height={size.h}
            graphData={data}
            backgroundColor="#f8fafc"
            d3VelocityDecay={0.3}
            cooldownTicks={120}
            nodeLabel={(n) => {
              const node = n as GraphNode;
              const typeKo = NODE_LABELS_KO[node.label] || node.label;
              const displayName = node.title || node.name || node.id;
              return `<div style="background:#0f172a;color:#fff;padding:6px 10px;border-radius:8px;font-size:11px;line-height:1.4;">
                <div style="color:#94a3b8;font-size:10px;">[${typeKo}]</div>
                <div style="font-weight:600;">${displayName}</div>
                <div style="color:#64748b;font-size:9px;">ID: ${node.id}</div>
              </div>`;
            }}
            nodeCanvasObject={(n, ctx, globalScale) => {
              const node = n as GraphNode;
              const hl = highlight();
              const isHl = hl.size > 0 && hl.has(node.id);
              const isSelected = selectedNode?.id === node.id;
              const r = node.label === "Equipment" ? 10 : node.label === "Line" ? 13 : node.label === "Document" ? 9 : 8;

              // 하이라이트/선택 외곽 링
              if (isSelected || isHl) {
                ctx.beginPath();
                ctx.arc(node.x!, node.y!, r + 3.5, 0, 2 * Math.PI);
                ctx.fillStyle = isSelected ? "rgba(15, 23, 42, 0.2)" : "rgba(245, 158, 11, 0.25)";
                ctx.fill();
              }

              // 노드 원형
              ctx.beginPath();
              ctx.arc(node.x!, node.y!, r, 0, 2 * Math.PI);
              ctx.fillStyle = isHl ? "#f59e0b" : (NODE_COLORS[node.label] ?? "#64748b");
              ctx.fill();
              ctx.strokeStyle = isSelected ? "#0f172a" : "rgba(255,255,255,0.95)";
              ctx.lineWidth = isSelected ? 2.5 : 1.5;
              ctx.stroke();

              // 노드 라벨 텍스트
              let labelText = node.name;
              if (node.label === "Document") {
                const docTitle = node.title || node.name || "매뉴얼";
                labelText = `📄 ${docTitle.length > 14 ? docTitle.slice(0, 13) + "…" : docTitle}`;
              } else if (node.label === "Line") {
                labelText = `🏭 ${node.name}`;
              } else {
                labelText = `${node.name} (${node.id})`;
              }

              const fontSize = Math.max(11.5 / globalScale, 3.5);
              ctx.font = `${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "top";

              // 텍스트 가독성을 위한 흰색 외곽선
              ctx.strokeStyle = "rgba(255,255,255,0.85)";
              ctx.lineWidth = 3 / globalScale;
              ctx.strokeText(labelText, node.x!, node.y! + r + 3);

              ctx.fillStyle = isSelected ? "#0f172a" : "#1e293b";
              ctx.fillText(labelText, node.x!, node.y! + r + 3);
            }}
            linkColor={(l) => {
              const link = l as GraphLink;
              const src = typeof link.source === "object" ? (link.source as GraphNode).id : link.source;
              if (impact && src === impact.root) return "#f59e0b";
              if (link.type === "DESCRIBES") return "#d97706";
              if (link.type === "AFFECTS") return "#ef4444";
              if (link.type === "FEEDS") return "#3b82f6";
              return "#94a3b8";
            }}
            linkWidth={(l) => {
              const link = l as GraphLink;
              if (link.type === "AFFECTS") return 2.2;
              if (link.type === "DESCRIBES") return 1.8;
              return 1.2;
            }}
            linkCanvasObjectMode={() => "after"}
            linkCanvasObject={(l, ctx, globalScale) => {
              const link = l as GraphLink;
              const src = link.source as unknown as GraphNode;
              const tgt = link.target as unknown as GraphNode;
              if (!src.x || !tgt.x || !src.y || !tgt.y) return;
              const fontSize = Math.max(8.5 / globalScale, 2.5);
              ctx.font = `${fontSize}px sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "bottom";
              ctx.fillStyle = link.type === "AFFECTS" ? "#b91c1c" : link.type === "DESCRIBES" ? "#b45309" : "#64748b";
              const mx = (src.x + tgt.x) / 2;
              const my = (src.y + tgt.y) / 2;
              ctx.fillText(REL_KO[link.type] ?? link.type, mx, my - 2);
            }}
            onNodeClick={(n: object) => void runImpact(n as GraphNode)}
            onNodeDblClick={(n: object) => void deleteNode((n as GraphNode).id)}
          />
        )}

        {/* 좌측 상단 플로팅 컨트롤 바 (줌 + 간격 조절) */}
        <div className="absolute left-4 top-4 z-10 flex flex-col gap-2 rounded-xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur">
          <div className="flex items-center gap-1">
            <button
              onClick={handleZoomIn}
              className="flex size-7 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-xs font-bold text-slate-700 hover:bg-slate-100"
              title="확대 (Zoom In)"
            >
              +
            </button>
            <button
              onClick={handleZoomOut}
              className="flex size-7 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-xs font-bold text-slate-700 hover:bg-slate-100"
              title="축소 (Zoom Out)"
            >
              -
            </button>
            <button
              onClick={handleZoomToFit}
              className="flex h-7 items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
              title="화면에 맞게 전체 보기"
            >
              🎯 맞춤
            </button>
          </div>

          <div className="border-t border-slate-100 pt-2">
            <div className="flex items-center justify-between text-[11px] font-medium text-slate-600">
              <span>↔️ 노드 간격</span>
              <span className="text-blue-600">{spacing}px</span>
            </div>
            <input
              type="range"
              min="60"
              max="260"
              step="10"
              value={spacing}
              onChange={(e) => setSpacing(Number(e.target.value))}
              className="mt-1 h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-blue-600"
            />
          </div>
        </div>

        {/* 우측 노드 상세 & 영향범위 패널 */}
        {selectedNode && (
          <div className="absolute right-4 top-4 z-10 max-h-[85vh] w-80 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-5 shadow-xl transition">
            <div className="mb-3 flex items-start justify-between">
              <div>
                <span
                  className="rounded-full px-2.5 py-0.5 text-xs font-semibold text-white shadow-sm"
                  style={{ background: NODE_COLORS[selectedNode.label] ?? "#64748b" }}
                >
                  {NODE_LABELS_KO[selectedNode.label] ?? selectedNode.label}
                </span>
                <h2 className="mt-1.5 text-base font-bold text-slate-800 leading-snug">
                  {selectedNode.title || selectedNode.name}
                </h2>
              </div>
              <button
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                onClick={() => {
                  setSelectedNode(null);
                  setImpact(null);
                }}
              >
                ✕
              </button>
            </div>

            {/* 식별자 (ID) */}
            <div className="mb-3 flex items-center justify-between rounded-lg bg-slate-50 px-2.5 py-1.5 text-xs text-slate-600 border border-slate-100">
              <span className="font-mono text-slate-500 truncate" title={selectedNode.id}>
                ID: {selectedNode.id}
              </span>
              <button
                onClick={() => copyNodeId(selectedNode.id)}
                className="ml-2 shrink-0 font-medium text-blue-600 hover:underline"
              >
                {copiedId ? "✓ 복사됨" : "복사"}
              </button>
            </div>

            {/* Document 노드인 경우 원본 열람 버튼 제공 */}
            {selectedNode.label === "Document" && (
              <div className="mb-4">
                <button
                  onClick={() =>
                    setViewingDoc({
                      id: selectedNode.id,
                      title: selectedNode.title || selectedNode.name,
                    })
                  }
                  className="w-full flex items-center justify-center gap-1.5 rounded-xl bg-amber-600 py-2 text-xs font-semibold text-white shadow-sm hover:bg-amber-700 transition"
                >
                  📄 원본 매뉴얼 PDF 열람
                </button>
              </div>
            )}

            {/* 노드 속성 */}
            {selectedNode.props && Object.keys(selectedNode.props).length > 0 && (
              <div className="mb-3 space-y-1 rounded-lg border border-slate-100 bg-slate-50/50 p-2.5 text-xs">
                <p className="font-semibold text-slate-700">속성 (Properties)</p>
                {Object.entries(selectedNode.props)
                  .filter(([k]) => !["id", "name", "title", "mongo_id"].includes(k))
                  .map(([k, v]) => (
                    <div key={k} className="flex justify-between text-slate-600">
                      <span className="text-slate-400">{k}:</span>
                      <span className="font-medium text-slate-700">{String(v)}</span>
                    </div>
                  ))}
              </div>
            )}

            {/* 연결 관계 (Incoming / Outgoing) */}
            {selectedRelations && (
              <div className="mb-3 text-xs">
                <p className="mb-1 font-semibold text-slate-700">연결 관계</p>
                <div className="max-h-32 space-y-1 overflow-y-auto rounded-lg border border-slate-100 p-2 bg-slate-50/40">
                  {selectedRelations.outgoing.map((l, i) => {
                    const tgtId = typeof l.target === "object" ? (l.target as GraphNode).id : l.target;
                    const tgtNode = data?.nodes.find((n) => n.id === tgtId);
                    return (
                      <div key={i} className="truncate text-slate-600">
                        <span className="text-blue-600 font-medium">{REL_KO[l.type] ?? l.type}</span> →{" "}
                        <span className="font-semibold text-slate-800">{tgtNode?.name || tgtId}</span>
                      </div>
                    );
                  })}
                  {selectedRelations.incoming.map((l, i) => {
                    const srcId = typeof l.source === "object" ? (l.source as GraphNode).id : l.source;
                    const srcNode = data?.nodes.find((n) => n.id === srcId);
                    return (
                      <div key={i} className="truncate text-slate-600">
                        <span className="font-semibold text-slate-800">{srcNode?.name || srcId}</span> →{" "}
                        <span className="text-blue-600 font-medium">{REL_KO[l.type] ?? l.type}</span>
                      </div>
                    );
                  })}
                  {!selectedRelations.outgoing.length && !selectedRelations.incoming.length && (
                    <p className="text-slate-400 text-[11px]">연결된 관계가 없습니다.</p>
                  )}
                </div>
              </div>
            )}

            {/* 영향범위 (Equipment / Sensor) */}
            {impact && (
              <div className="border-t border-slate-200 pt-3">
                <h3 className="mb-2 text-xs font-bold text-amber-900 flex items-center gap-1">
                  <span>🔗 하류 영향범위 ({impact.items.length}개 대상)</span>
                </h3>
                {impact.items.length === 0 ? (
                  <p className="text-xs text-slate-400">하류 영향 설비가 없습니다.</p>
                ) : (
                  <ul className="space-y-1.5 max-h-40 overflow-y-auto">
                    {impact.items.map((item) => (
                      <li key={item.impacted} className="rounded-lg bg-amber-50/70 p-2 text-xs text-slate-700 border border-amber-100">
                        <div className="font-semibold text-amber-950">
                          {item.impacted_name} <span className="text-slate-500 font-normal">({item.impacted})</span>
                        </div>
                        <div className="mt-0.5 text-[11px] text-amber-800">
                          깊이 {item.depth} · {item.rels.map((r) => REL_KO[r as GraphLink["type"]] ?? r).join(" → ")}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <div className="mt-4 border-t border-slate-100 pt-3 flex justify-between">
              <button
                onClick={() => void deleteNode(selectedNode.id)}
                className="text-xs font-medium text-red-500 hover:text-red-700"
              >
                노드 삭제
              </button>
            </div>
          </div>
        )}
      </div>

      {/* PDF 원본 뷰어 */}
      {viewingDoc && (
        <SourceViewer
          title={`📄 ${viewingDoc.title}`}
          url={documentsApi.fileUrl(viewingDoc.id)}
          kind="pdf"
          onClose={() => setViewingDoc(null)}
        />
      )}

      {/* 노드 생성/수정 모달 */}
      {showNodeForm && (
        <NodeFormModal
          onClose={() => setShowNodeForm(false)}
          onSaved={async () => {
            setShowNodeForm(false);
            await refresh();
          }}
        />
      )}

      {/* 관계 생성/삭제 모달 */}
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
    <div className="hidden gap-3 text-xs text-slate-600 md:flex items-center">
      {Object.entries(NODE_COLORS).map(([label, color]) => (
        <span key={label} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full" style={{ background: color }} />
          <span className="font-medium">{NODE_LABELS_KO[label as GraphNode["label"]] ?? label}</span>
        </span>
      ))}
    </div>
  );
}

function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
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
              <option key={l} value={l}>
                {NODE_LABELS_KO[l]} ({l})
              </option>
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
    const src = typeof link.source === "object" ? (link.source as GraphNode).id : link.source;
    const tgt = typeof link.target === "object" ? (link.target as GraphNode).id : link.target;
    await graphApi.deleteEdge(src, tgt, link.type);
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
            const srcId = typeof l.source === "object" ? (l.source as GraphNode).id : l.source;
            const tgtId = typeof l.target === "object" ? (l.target as GraphNode).id : l.target;
            if (!srcId) return null;
            return (
              <div key={i} className="group flex items-center justify-between rounded px-2 py-1 text-xs hover:bg-slate-50">
                <span className="truncate text-slate-600">
                  {srcId} → <b className="text-blue-700">{REL_KO[l.type] ?? l.type}</b> → {tgtId}
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
