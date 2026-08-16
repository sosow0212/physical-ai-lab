/** 실시간 텔레메트리 & 조기 경보 API */

import { get, post } from "./client";

export type ScenarioType = "NORMAL" | "ANOMALY_40" | "ANOMALY_70" | "CRITICAL_SPIKE" | "DRIFT";
export type CircuitState = "NORMAL" | "WARNING" | "TRIP";

export interface GeneratorStatus {
  is_running: boolean;
  hz: number;
  scenario: ScenarioType;
  total_emitted: number;
  started_at: string | null;
}


export interface CircuitBreakerStatus {
  equipment_id: string;
  equipment_name: string;
  sensor_id: string;
  metric_name: string;
  state: CircuitState;
  current_value: number;
  z_score: number;
  slope: number;
  unit: string;
  threshold_warning: number | null;
  threshold_trip: number | null;
  source: "graph" | "default" | "auto";
  recent_values: number[];
  updated_at: string;
}

export interface EarlyWarningAlert {
  alert_id: string;
  timestamp: string;
  severity: "WARNING" | "CRITICAL";
  equipment_id: string;
  equipment_name: string;
  sensor_id: string;
  metric_name: string;
  value: number;
  unit: string;
  reason: string;
  z_score: number;
  impact_path: string[];
  guide_summary?: string | null;
}

export interface TelemetryEventData {
  equipment_id: string;
  equipment_name: string;
  sensor_id: string;
  metric_name: string;
  value: number;
  unit: string;
  z_score: number;
  slope: number;
  state: CircuitState;
  timestamp: string;
}

export const telemetryApi = {
  start: (hz = 5, scenario: ScenarioType = "NORMAL") =>
    post<GeneratorStatus>(`/telemetry/generator/start?hz=${hz}&scenario=${scenario}`),
  stop: () => post<GeneratorStatus>("/telemetry/generator/stop"),
  setScenario: (scenario: ScenarioType, hz?: number) =>
    post<GeneratorStatus>("/telemetry/generator/scenario", { scenario, hz }),
  getStatus: () => get<GeneratorStatus>("/telemetry/generator/status"),
  getCircuitBreakers: () => get<CircuitBreakerStatus[]>("/telemetry/circuit-breakers"),
  resetCircuitBreaker: (equipment_id?: string) =>
    post<{ status: string; message: string }>(
      `/telemetry/circuit-breaker/reset${equipment_id ? `?equipment_id=${equipment_id}` : ""}`
    ),
  getAlerts: (limit = 30) => get<EarlyWarningAlert[]>(`/telemetry/alerts?limit=${limit}`),
  streamUrl: () => "/api/v1/telemetry/stream",
};
