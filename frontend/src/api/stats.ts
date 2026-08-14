/** 통계 API */

import { get } from "./client";

export interface StatsPayload {
  documents: { total: number; done: number; failed: number; chunks: number };
  drawings: { total: number; done: number };
  jobs: {
    active: number;
    dead: number;
    recent: { id: string; type: string; action: string; status: string; created_at: string }[];
  };
  graph: { nodes: number; links: number };
  chat: {
    sessions: number;
    recent_questions: { id: string; content: string; created_at: string }[];
  };
}

export const statsApi = {
  get: () => get<StatsPayload>("/stats"),
};
