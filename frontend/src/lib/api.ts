export interface HealthResponse {
  status: string;
  service: string;
  timestamp: string;
}

export interface ReadinessResponse {
  status: string;
  timestamp: string;
  checks: Record<string, string>;
}

export interface DeploymentStatusResponse {
  status: string;
  environment: string;
  frontend_origin: string | null;
  timestamp: string;
  checks: Record<string, string>;
}

export interface BreezeAuthResponse {
  status: string;
  configured: boolean;
  missing?: string[];
  user_id?: string;
  user_name?: string;
  session_token_received?: boolean;
  segments_allowed?: Record<string, string>;
  exchange_status?: Record<string, string>;
  error?: string;
}

export interface BreezeTestSymbolResult {
  symbol: string;
  broker_symbol: string;
  status: string;
  exchange: string;
  product_type: string;
  quote?: Record<string, unknown> | Array<Record<string, unknown>>;
  error?: string;
}

export interface BreezeTestResponse {
  status: string;
  configured: boolean;
  error?: string;
  symbols: BreezeTestSymbolResult[];
}

const API_BASE_URL = import.meta.env.DEV ? "" : (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:5000");

async function requestJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export function getHealth() {
  return requestJson<HealthResponse>("/api/health");
}

export function getReadiness() {
  return requestJson<ReadinessResponse>("/api/health/readiness");
}

export function getDeploymentStatus() {
  return requestJson<DeploymentStatusResponse>("/api/health/deployment");
}

export function getBreezeAuth() {
  return requestJson<BreezeAuthResponse>("/api/debug/breeze-auth");
}

export function getBreezeTest() {
  return requestJson<BreezeTestResponse>("/api/debug/breeze-test");
}
