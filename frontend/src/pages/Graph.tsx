import { useCallback, useEffect, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

import { graphApi, type GraphLink, type GraphNode, type ImpactResult } from "../api/graph";

const NODE_COLORS: Record<GraphNode["label"], string> = {
  Line: "#dc2626",
  Equipment: "#1d4ed8",
  Sensor: "#059669",
  Document: "#92400e",
};

export default function GraphPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<{ nodes: GraphNode[]; links: GraphLink[] } | null>(null);
  const [impact, setImpact] = useState<ImpactResult | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [size, setSize] = useState({ w: 800, h: 600 });

  useEffect(() => {
    void graphApi.overview().then(setData);
  }, []);

  useEffect(() => {
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0) setSize({ w: width, h: height });
    });
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const highlightIds = useCallback(() => {
    if (!impact || !selected) return new Set<string>();
    return new Set([impact.root, ...impact.items.map((i) => i.impacted)]);
  }, [impact, selected]);

  const runImpact = useCallback(
    async (id: string) => {
      setSelected(id);
      try {
        setImpact(await graphApi.impact(id));
      } catch {
        setImpact(null);
      }
    },
    [],
  );

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-slate-200 bg-white px-8 py-4">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">지식그래프</h1>
          <p className="text-xs text-slate-500">
            노드를 클릭하면 해당 설비의 하류 영향범위를 하이라이트합니다.
          </p>
        </div>
        <div className="flex gap-3 text-xs text-slate-600">
          {Object.entries(NODE_COLORS).map(([label, color]) => (
            <span key={label} className="flex items-center gap-1">
              <span className="size-2.5 rounded-full" style={{ background: color }} />
              {label}
            </span>
          ))}
        </div>
      </div>

      <div ref={containerRef} className="relative flex-1 bg-slate-50">
        {data && (
          <ForceGraph2D
            width={size.w}
            height={size.h}
            graphData={data}
            backgroundColor="#f8fafc"
            nodeLabel={(n) => `${(n as GraphNode).name} (${(n as GraphNode).id})`}
            nodeColor={(n) => {
              const node = n as GraphNode;
              const hl = highlightIds();
              if (hl.size && hl.has(node.id)) return "#f59e0b";
              return NODE_COLORS[node.label] ?? "#64748b";
            }}
            nodeVal={(n) => ((n as GraphNode).label === "Equipment" ? 6 : 4)}
            linkColor={(l) => {
              const link = l as GraphLink;
              if (impact && (link.source as unknown as GraphNode).id === impact.root) return "#f59e0b";
              return "#cbd5e1";
            }}
            linkLabel={(l) => {
              const link = l as GraphLink;
              return Object.entries(link.props ?? {})
                .map(([k, v]) => `${k}: ${v}`)
                .join("\n");
            }}
            onNodeClick={(n) => void runImpact((n as GraphNode).id)}
          />
        )}

        {impact && (
          <div className="absolute right-4 top-4 max-w-sm rounded-xl border border-amber-200 bg-white p-4 shadow-lg">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-800">
                🔗 {impact.root} 영향범위
              </h2>
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
            <ul className="space-y-1.5">
              {impact.items.map((item) => (
                <li key={item.impacted} className="text-xs text-slate-600">
                  <span className="font-medium text-slate-800">{item.impacted}</span>{" "}
                  {item.impacted_name}
                  <span className="ml-1 text-slate-400">
                    (깊이 {item.depth} · {item.rels.join("→")})
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
