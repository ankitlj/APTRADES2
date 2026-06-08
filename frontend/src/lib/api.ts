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

export interface QuoteResolvedInstrument {
  display_symbol: string;
  broker_symbol: string;
  exchange_code: string;
  product_type: string;
  token: string | null;
  contract_code: string;
  expiry_date: string | null;
  right: string;
  strike_price: string;
  lot_size: number | null;
  tick_size: string | null;
  source: string | null;
  resolution_source: string;
}

export interface QuoteResult {
  status: string;
  symbol: string;
  resolved?: QuoteResolvedInstrument;
  quote?: Record<string, unknown>;
  exchange_code?: string;
  product_type?: string | null;
  error?: string;
}

export interface BatchQuoteRequestItem {
  symbol: string;
  exchange: string;
  product_type?: string;
  expiry_date?: string;
  right?: string;
  strike_price?: string;
}

export interface QuoteResponse extends QuoteResult {}

export interface BatchQuoteResponse {
  status: string;
  results: QuoteResult[];
}

export interface MasterContractAlias {
  display_symbol: string;
  broker_symbol: string;
}

export interface MasterContractRun {
  status: string;
  source_name: string;
  source_checksum: string | null;
  row_count: number;
  alias_count: number;
  warning_count: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface MasterContractStatusResponse {
  status: string;
  database_configured: boolean;
  csv_path: string | null;
  csv_available: boolean;
  security_master_url: string;
  instrument_count?: number;
  alias_count?: number;
  latest_run?: MasterContractRun | null;
  verified_aliases?: MasterContractAlias[];
}

export interface DashboardMetric {
  key: string;
  label: string;
  value: number | string | null;
  change?: number | null;
  previous_close?: number | null;
  expiry_date?: string | null;
  meta: string;
  tone: string;
  status?: string;
}

export interface DashboardTickerItem {
  symbol: string;
  broker_symbol?: string | null;
  ltp: number | null;
  change_percent: number | null;
  status: string;
}

export interface DashboardPosition {
  symbol: string;
  broker_symbol: string;
  exchange_code: string;
  product_type: string;
  quantity: number;
  average_price: number | null;
  ltp: number | null;
  pnl: number | null;
  expiry_date: string | null;
  right: string | null;
  strike_price: string | null;
  segment: string | null;
}

export interface DashboardSummaryResponse {
  status: string;
  updated_at: string;
  metrics: DashboardMetric[];
  ticker: DashboardTickerItem[];
  positions_status: string;
  positions_error?: string | null;
  positions: DashboardPosition[];
}

export interface DashboardAlert {
  level: string;
  title: string;
  message: string;
}

export interface DashboardAlertsResponse {
  status: string;
  alerts: DashboardAlert[];
}

export interface DashboardChartResolved {
  display_symbol: string;
  broker_symbol: string;
  exchange_code: string;
  product_type: string;
  token: string | null;
  contract_code: string;
  expiry_date: string | null;
}

export interface DashboardChartPoint {
  time: string | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface DashboardChartResponse {
  status: string;
  symbol: string;
  resolved: DashboardChartResolved;
  interval: string;
  points: DashboardChartPoint[];
  error?: string;
}

const API_BASE_URL = import.meta.env.DEV ? "" : (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:5000");

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { error?: string; message?: string; status?: string };
      message = payload.error ?? payload.message ?? message;
    } catch {
      // Preserve generic HTTP status text when the response is not JSON.
    }
    throw new Error(message);
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

export function getMasterContractStatus() {
  return requestJson<MasterContractStatusResponse>("/api/master-contract/status");
}

export function getQuote(item: BatchQuoteRequestItem) {
  const params = new URLSearchParams({
    symbol: item.symbol,
    exchange: item.exchange,
  });
  if (item.product_type) {
    params.set("product_type", item.product_type);
  }
  if (item.expiry_date) {
    params.set("expiry_date", item.expiry_date);
  }
  if (item.right) {
    params.set("right", item.right);
  }
  if (item.strike_price) {
    params.set("strike_price", item.strike_price);
  }
  return requestJson<QuoteResponse>(`/api/quotes?${params.toString()}`);
}

export function getBatchQuotes(symbols: BatchQuoteRequestItem[]) {
  return requestJson<BatchQuoteResponse>("/api/quotes/batch", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ symbols }),
  });
}

export function getDashboardSummary() {
  return requestJson<DashboardSummaryResponse>("/api/dashboard/summary");
}

export function getDashboardAlerts() {
  return requestJson<DashboardAlertsResponse>("/api/dashboard/alerts");
}

export function getDashboardChart(symbol = "NIFTY") {
  return requestJson<DashboardChartResponse>(`/api/dashboard/chart?symbol=${encodeURIComponent(symbol)}`);
}
