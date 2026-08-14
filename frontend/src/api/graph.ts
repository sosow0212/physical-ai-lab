/** 지식그래프 API */

import { get } from "./client";

export interface GraphNode {
  id: string;
  name: string;
  label: "Line" | "Equipment" | "Sensor" | "Document";
}

export interface GraphLink {
  source: string;
  target: string;
  type: "PART_OF" | "FEEDS" | "AFFECTS" | "MONITORS" | "ATTACHED_TO" | "DESCRIBES";
  props?: Record<string, unknown>;
}

export interface ImpactItem {
  via: string;
  impacted: string;
  impacted_label: string;
  impacted_name: string;
  rels: string[];
  depth: number;
}

export interface ImpactResult {
  root: string;
  items: ImpactItem[];
}

export const graphApi = {
  overview: () => get<{ nodes: GraphNode[]; links: GraphLink[] }>("/graph/overview"),
  impact: (equipment: string) =>
    get<ImpactResult>(`/graph/impact?equipment=${encodeURIComponent(equipment)}`),
  upsertNode: (body: { id: string; label: string; name: string; props?: Record<string, string> }) =>
    post<GraphNode>("/graph/nodes", body),
  deleteNode: (id: string) => del(`/graph/nodes/${encodeURIComponent(id)}`),
  upsertEdge: (body: { source: string; target: string; type: string; props?: Record<string, string> }) =>
    post<GraphLink>("/graph/edges", body),
  deleteEdge: (source: string, target: string, type: string) =>
    del(`/graph/edges?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}&type=${type}`),
};
