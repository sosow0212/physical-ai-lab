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
};
