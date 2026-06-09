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

export interface OrderStats {
  total: number;
  completed: number;
  open: number;
  rejected: number;
  cancelled: number;
}

export interface OrderRecord {
  order_id: string;
  parent_order_id: string;
  symbol: string;
  broker_symbol: string;
  exchange_code: string;
  product_type: string;
  action: string;
  status: string;
  status_normalized: string;
  quantity: number | null;
  pending_quantity: number | null;
  filled_quantity: number | null;
  limit_price: number | null;
  trigger_price: number | null;
  average_price: number | null;
  order_type: string;
  validity: string;
  created_at: string;
  updated_at: string;
  message: string;
}

export interface OrdersResponse {
  status: string;
  exchange_code: string;
  from_date: string;
  to_date: string;
  stats: OrderStats;
  orders: OrderRecord[];
}

export interface CancelOrderResponse {
  status: string;
  exchange_code: string;
  order_id: string;
  result: Record<string, unknown> | string;
}

export interface CancelAllItemResult {
  order_id: string;
  symbol: string;
  status: string;
  result?: Record<string, unknown> | string;
  error?: string;
}

export interface CancelAllResponse {
  status: string;
  exchange_code: string;
  requested: number;
  cancelled_count: number;
  error_count: number;
  cancelled: CancelAllItemResult[];
  errors: CancelAllItemResult[];
}

export interface TradeStats {
  total: number;
  buy: number;
  sell: number;
}

export interface TradeRecord {
  trade_id: string;
  order_id: string;
  symbol: string;
  broker_symbol: string;
  exchange_code: string;
  product_type: string;
  action: string;
  quantity: number | null;
  price: number | null;
  trade_time: string;
}

export interface TradesResponse {
  status: string;
  exchange_code: string;
  from_date: string;
  to_date: string;
  stats: TradeStats;
  trades: TradeRecord[];
}

export interface PositionsStats {
  open_positions: number;
  long_positions: number;
  short_positions: number;
  total_pnl: number;
}

export interface PositionRecord {
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
  direction: string;
  quote_status: string;
  quote_error: string | null;
  pnl_percent: number | null;
  resolution_source: string | null;
  token: string | null;
}

export interface PositionsResponse {
  status: string;
  quote_status: string;
  close_actions_active: boolean;
  positions: PositionRecord[];
  totals: PositionsStats;
  error?: string;
}

export interface OptionExpiriesResponse {
  status: string;
  underlying: string;
  broker_symbol: string;
  exchange_code: string;
  expiries: string[];
}

export interface OptionChainLeg {
  ltp: number | null;
  bid: number | null;
  ask: number | null;
  oi: number | null;
  volume: number | null;
}

export interface OptionChainRow {
  strike_price: number;
  ce: OptionChainLeg | null;
  pe: OptionChainLeg | null;
}

export interface OptionChainResponse {
  status: string;
  underlying: string;
  broker_symbol: string;
  exchange_code: string;
  expiry: string;
  updated_at: string;
  underlying_ltp: number | null;
  previous_close: number | null;
  atm_strike: number;
  pcr: number | null;
  total_call_oi: number;
  total_put_oi: number;
  total_oi: number;
  rows: OptionChainRow[];
}

export interface OIRow {
  strike_price: number;
  ce_oi: number;
  pe_oi: number;
  total_oi: number;
  ce_ltp: number | null;
  pe_ltp: number | null;
}

export interface OITrackerResponse {
  status: string;
  underlying: string;
  exchange_code: string;
  expiry: string;
  underlying_ltp: number | null;
  atm_strike: number;
  pcr: number | null;
  total_call_oi: number;
  total_put_oi: number;
  max_ce_oi_strike: number | null;
  max_pe_oi_strike: number | null;
  updated_at: string;
  rows: OIRow[];
}

export interface OIProfileResponse {
  status: string;
  underlying: string;
  exchange_code: string;
  expiry: string;
  underlying_ltp: number | null;
  atm_strike: number;
  pcr: number | null;
  total_call_oi: number;
  total_put_oi: number;
  updated_at: string;
  rows: OIRow[];
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

export function getOrders(params?: { exchange?: string; status?: string }) {
  const search = new URLSearchParams();
  if (params?.exchange) {
    search.set("exchange", params.exchange);
  }
  if (params?.status) {
    search.set("status", params.status);
  }
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return requestJson<OrdersResponse>(`/api/orders${suffix}`);
}

export function cancelOrder(orderId: string, exchangeCode: string) {
  return requestJson<CancelOrderResponse>("/api/orders/cancel", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ order_id: orderId, exchange_code: exchangeCode }),
  });
}

export function cancelAllOrders(exchangeCode: string) {
  return requestJson<CancelAllResponse>("/api/orders/cancel-all", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ exchange_code: exchangeCode }),
  });
}

export function getTrades(params?: { exchange?: string; action?: string; product_type?: string }) {
  const search = new URLSearchParams();
  if (params?.exchange) {
    search.set("exchange", params.exchange);
  }
  if (params?.action) {
    search.set("action", params.action);
  }
  if (params?.product_type) {
    search.set("product_type", params.product_type);
  }
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return requestJson<TradesResponse>(`/api/trades${suffix}`);
}

export function getPositions() {
  return requestJson<PositionsResponse>("/api/positions");
}

export function getOptionExpiries(params: { underlying: string; exchange?: string }) {
  const search = new URLSearchParams({ underlying: params.underlying });
  if (params.exchange) {
    search.set("exchange", params.exchange);
  }
  return requestJson<OptionExpiriesResponse>(`/api/options/expiries?${search.toString()}`);
}

export function getOptionChain(params: { underlying: string; expiry: string; exchange?: string; strike_count?: number }) {
  const search = new URLSearchParams({
    underlying: params.underlying,
    expiry: params.expiry,
  });
  if (params.exchange) {
    search.set("exchange", params.exchange);
  }
  if (params.strike_count) {
    search.set("strike_count", String(params.strike_count));
  }
  return requestJson<OptionChainResponse>(`/api/option-chain?${search.toString()}`);
}

export function getOITracker(params: { underlying: string; expiry: string; exchange?: string }) {
  const search = new URLSearchParams({ underlying: params.underlying, expiry: params.expiry });
  if (params.exchange) {
    search.set("exchange", params.exchange);
  }
  return requestJson<OITrackerResponse>(`/api/oi/tracker?${search.toString()}`);
}

export function getOIProfile(params: { underlying: string; expiry: string; exchange?: string }) {
  const search = new URLSearchParams({ underlying: params.underlying, expiry: params.expiry });
  if (params.exchange) {
    search.set("exchange", params.exchange);
  }
  return requestJson<OIProfileResponse>(`/api/oi/profile?${search.toString()}`);
}

export interface StrategyLeg {
  action: string;
  right: string;
  strike: number;
  quantity: number;
  premium: number;
}

export interface StrategyRecord {
  id: number;
  name: string;
  underlying: string;
  exchange_code: string;
  expiry: string;
  legs: StrategyLeg[];
  net_premium: number;
  created_at: string;
}

export interface StrategyListResponse {
  status: string;
  strategies: StrategyRecord[];
}

export interface StrategyCreateRequest {
  name: string;
  underlying: string;
  exchange_code?: string;
  expiry: string;
  legs: StrategyLeg[];
}

export interface StrategyCreateResponse {
  status: string;
  strategy: StrategyRecord;
}

export interface PayoffPoint {
  spot: number;
  pnl: number;
}

export interface PayoffResponse {
  status: string;
  net_premium: number;
  max_profit: number;
  max_loss: number;
  breakevens: number[];
  curve: PayoffPoint[];
}

export function getStrategies() {
  return requestJson<StrategyListResponse>("/api/strategies");
}

export function createStrategy(body: StrategyCreateRequest) {
  return requestJson<StrategyCreateResponse>("/api/strategies", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function deleteStrategy(strategyId: number) {
  return requestJson<{ status: string; deleted_id: number }>(`/api/strategies/${strategyId}`, {
    method: "DELETE",
  });
}

export function getStrategyPayoff(legs: StrategyLeg[]) {
  return requestJson<PayoffResponse>("/api/strategies/payoff", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ legs }),
  });
}
