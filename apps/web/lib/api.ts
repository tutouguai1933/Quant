export type ApiEnvelope<T> = {
  data: T;
  error: { code: string; message: string } | null;
  meta: Record<string, unknown>;
};

type NavigationItem = {
  href: string;
  label: string;
};

type DashboardSummary = {
  scope: {
    market: string;
    exchange: string;
    executor: string;
    producer: string;
  };
  pipeline: Array<{ name: string; status: string }>;
  navigation: NavigationItem[];
};

export type SignalsPageModel = {
  columns: string[];
  items: Array<{ id: string; symbol: string; source: string; generatedAt: string; status: string }>;
};

type StrategiesPageModel = {
  items: Array<{ id: string; name: string; producerType: string; status: string }>;
};

export type StrategyWorkspaceCard = {
  strategy_id: number;
  key: string;
  display_name: string;
  description: string;
  symbols: string[];
  default_params: Record<string, unknown>;
  runtime_status: string;
  runtime_name: string;
  latest_signal: Record<string, unknown> | null;
  research_summary: ResearchSymbolSummary;
  research_cockpit: ResearchCockpitSummary;
  current_evaluation: Record<string, unknown>;
};

export type WorkspaceResearchOverview = {
  status: string;
  detail: string;
  model_version: string;
  signal_count: number;
};

export type StrategyWorkspaceModel = {
  overview: {
    strategy_count: number;
    whitelist_count: number;
    signal_count: number;
    order_count: number;
    running_count: number;
  };
  executor_runtime: {
    executor: string;
    backend: string;
    mode: string;
    connection_status: string;
  };
  research: WorkspaceResearchOverview;
  research_recommendation: ResearchRecommendation | null;
  whitelist: string[];
  strategies: StrategyWorkspaceCard[];
  recent_signals: Array<Record<string, unknown>>;
  recent_orders: Array<Record<string, unknown>>;
  account_state: WorkspaceAccountState;
};

type BalancesPageModel = {
  source: string;
  truthSource: string;
  items: Array<{
    id: string;
    asset: string;
    available: string;
    locked: string;
    tradeStatus: string;
    tradeHint: string;
    sellableQuantity: string;
    dustQuantity: string;
  }>;
};

type WorkspaceAccountBalance = {
  id: string;
  asset: string;
  available: string;
  locked: string;
  tradeStatus: string;
  tradeHint: string;
  sellableQuantity: string;
  dustQuantity: string;
};

type WorkspaceAccountOrder = {
  id: string;
  symbol: string;
  side: string;
  orderType: string;
  status: string;
};

type WorkspaceAccountPosition = {
  id: string;
  symbol: string;
  side: string;
  quantity: string;
};

export type WorkspaceAccountState = {
  source: string;
  truth_source: string;
  summary: {
    balance_count: number;
    tradable_balance_count: number;
    dust_count: number;
    order_count: number;
    position_count: number;
  };
  balances: WorkspaceAccountBalance[];
  orders: WorkspaceAccountOrder[];
  positions: WorkspaceAccountPosition[];
  latest_balance: WorkspaceAccountBalance | null;
  latest_order: WorkspaceAccountOrder | null;
  latest_position: WorkspaceAccountPosition | null;
};

type PositionsPageModel = {
  source: string;
  truthSource: string;
  items: Array<{ id: string; symbol: string; side: string; quantity: string; unrealizedPnl: string }>;
};

type OrdersPageModel = {
  source: string;
  truthSource: string;
  items: Array<{ id: string; symbol: string; side: string; orderType: string; status: string }>;
};

type RiskPageModel = {
  items: Array<{ id: string; level: string; ruleName: string; decision: string }>;
};

type TasksPageModel = {
  items: Array<{ id: string; taskType: string; source: string; status: string }>;
};

export type AutomationStatusModel = {
  mode: string;
  paused: boolean;
  pauseReason: string;
  manualTakeover: boolean;
  armedSymbol: string;
  runtimeMode: string;
  allowLiveExecution: boolean;
  alerts: Array<{ level: string; code: string; message: string; createdAt: string }>;
  lastCycle: Record<string, unknown>;
  reviewOverview: Record<string, unknown>;
  researchOverview: Record<string, unknown>;
  health: Record<string, unknown>;
  executionHealth: Record<string, unknown>;
};

export type MarketSnapshot = {
  symbol: string;
  last_price: string;
  change_percent: string;
  quote_volume: string;
  is_whitelisted: boolean;
  recommended_strategy: "trend_breakout" | "trend_pullback" | "none";
  trend_state: "uptrend" | "pullback" | "neutral";
  strategy_summary: Record<string, Record<string, unknown>>;
  research_brief: ResearchCockpitSummary;
};

export type MarketCandle = {
  open_time: number;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
  close_time: number;
};

export type ChartIndicatorMetric = {
  value: string | null;
  ready: boolean;
  sample_size: number;
  warnings: string[];
  last_candle_closed: boolean;
};

export type ChartIndicatorSummary = {
  ema_fast: ChartIndicatorMetric;
  ema_slow: ChartIndicatorMetric;
  atr: ChartIndicatorMetric;
  rsi: ChartIndicatorMetric;
  volume_sma: ChartIndicatorMetric;
};

export type ChartMarkerGroups = {
  signals: Array<Record<string, unknown>>;
  entries: Array<Record<string, unknown>>;
  stops: Array<Record<string, unknown>>;
};

export type ResearchSymbolSummary = {
  symbol: string;
  score: string;
  signal: string;
  model_version: string;
  explanation: string;
  generated_at: string;
};

export type ResearchCockpitSummary = {
  research_bias: string;
  recommended_strategy: "trend_breakout" | "trend_pullback" | "none";
  confidence: string;
  research_gate: Record<string, unknown>;
  primary_reason: string;
  research_explanation: string;
  model_version: string;
  generated_at: string;
  signal_count?: number;
  entry_hint?: string;
  stop_hint?: string;
  overlay_summary?: string;
};

export type MultiTimeframeSummaryItem = {
  interval: string;
  trend_state: "uptrend" | "pullback" | "neutral";
  research_bias: string;
  recommended_strategy: "trend_breakout" | "trend_pullback" | "none";
  confidence: string;
  primary_reason: string;
};

export type LatestResearchItem = {
  status: string;
  backend: string;
  qlib_available: boolean;
  detail: string;
  latest_training: Record<string, unknown> | null;
  latest_inference: Record<string, unknown> | null;
  symbols: Record<string, ResearchSymbolSummary>;
};

export type LatestResearchResponse = {
  item: LatestResearchItem;
};

export type ResearchCandidateItem = {
  rank: number;
  symbol: string;
  strategy_template: string;
  score: string;
  backtest: { metrics: Record<string, string> };
  dry_run_gate: { status: string; reasons: string[] };
  allowed_to_dry_run: boolean;
  review_status: string;
  next_action: string;
  forced_for_validation: boolean;
  forced_reason: string;
};

export type ResearchCandidateSnapshot = {
  status: string;
  backend: string;
  model_version: string;
  generated_at: string;
  summary: {
    candidate_count: number;
    ready_count: number;
    blocked_count?: number;
    pass_rate_pct?: string;
    top_candidate_symbol?: string;
    top_candidate_score?: string;
  };
  candidates: ResearchCandidateItem[];
};

export type ResearchRecommendation = {
  symbol: string;
  score: string;
  allowed_to_dry_run: boolean;
  strategy_template: string;
  dry_run_gate: { status: string; reasons: string[] };
  next_action: string;
};

export type ResearchReportItem = {
  status: string;
  backend: string;
  overview: {
    model_version: string;
    generated_at: string;
    candidate_count: number;
    ready_count: number;
    blocked_count: number;
    pass_rate_pct: string;
    signal_count: number;
    top_candidate_symbol: string;
    top_candidate_score: string;
  };
  latest_training: Record<string, unknown>;
  latest_inference: Record<string, unknown>;
  candidates: ResearchCandidateItem[];
  experiments: {
    training: Record<string, unknown>;
    inference: Record<string, unknown>;
  };
};

export type ValidationReviewItem = {
  overview: Record<string, unknown>;
  steps: Array<Record<string, unknown>>;
  research_report: Record<string, unknown>;
  task_health: Record<string, unknown>;
  execution_health: Record<string, unknown>;
  automation?: Record<string, unknown>;
  recent_tasks: Array<Record<string, unknown>>;
  account_snapshot: Record<string, unknown>;
};

export type MarketChartData = {
  items: MarketCandle[];
  overlays: ChartIndicatorSummary;
  markers: ChartMarkerGroups;
  active_interval: string;
  supported_intervals: string[];
  multi_timeframe_summary: MultiTimeframeSummaryItem[];
  research_cockpit: ResearchCockpitSummary;
  strategy_context: {
    recommended_strategy: "trend_breakout" | "trend_pullback" | "none";
    trend_state: "uptrend" | "pullback" | "neutral";
    next_step: string;
    primary_reason: string;
    evaluations: Record<string, Record<string, unknown>>;
  };
  freqtrade_readiness: {
    executor: string;
    backend: string;
    runtime_mode: string;
    ready_for_real_freqtrade: boolean;
    reason: string;
    next_step: string;
  };
};

export type LoginPageModel = {
  notes: string[];
  defaultUsername: string;
  sessionMode: string;
  protectedPages: string[];
};

const DEFAULT_API_BASE_URL = "http://127.0.0.1:9011/api/v1";
const API_BASE_URL = (process.env.QUANT_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, "");
const WEB_PROXY_BASE_URL = "/api/control";
export const AUTH_STORAGE_KEY = "quant_admin_token";
const PROTECTED_ROUTE_PATHS = ["/strategies", "/tasks", "/risk"];

export function buildApiUrl(path: string): string {
  if (typeof window !== "undefined") {
    return `${WEB_PROXY_BASE_URL}${path}`;
  }
  return `${API_BASE_URL}${path}`;
}

export function buildAuthHeaders(token?: string): HeadersInit {
  return {
    Accept: "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export function isProtectedRoute(path: string): boolean {
  return PROTECTED_ROUTE_PATHS.includes(path);
}

export async function fetchJson<T>(path: string, token?: string): Promise<ApiEnvelope<T>> {
  const response = await fetch(buildApiUrl(path), {
    headers: buildAuthHeaders(token),
    cache: "no-store",
  });

  return response.json() as Promise<ApiEnvelope<T>>;
}

export async function loginAdmin(
  username: string,
  password: string,
): Promise<ApiEnvelope<{ item: { token: string; username: string; scope: string } }>> {
  const response = await fetch(buildApiUrl("/auth/login"), {
    method: "POST",
    headers: {
      ...buildAuthHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username, password }),
    cache: "no-store",
  });

  return response.json() as Promise<ApiEnvelope<{ item: { token: string; username: string; scope: string } }>>;
}

export async function getAdminSession(
  token: string,
): Promise<ApiEnvelope<{ item: { token: string; username: string; scope: string } }>> {
  return fetchJson<{ item: { token: string; username: string; scope: string } }>(`/auth/session?token=${token}`);
}

export async function logoutAdmin(
  token: string,
): Promise<ApiEnvelope<{ item: { token: string; status: string } }>> {
  const response = await fetch(buildApiUrl(`/auth/logout?token=${token}`), {
    method: "POST",
    headers: buildAuthHeaders(token),
    cache: "no-store",
  });

  return response.json() as Promise<ApiEnvelope<{ item: { token: string; status: string } }>>;
}

export async function listSignals(): Promise<
  ApiEnvelope<{ items: SignalsPageModel["items"] }>
> {
  const response = await fetchJson<{ items: Array<Record<string, unknown>> }>("/signals");
  if (response.error) {
    return response as ApiEnvelope<{ items: SignalsPageModel["items"] }>;
  }
  return {
    ...response,
    data: {
      items: response.data.items.map((item) => ({
        id: String(item.signal_id ?? item.id ?? ""),
        symbol: String(item.symbol ?? ""),
        source: String(item.source ?? ""),
        generatedAt: String(item.generated_at ?? item.generatedAt ?? ""),
        status: String(item.status ?? ""),
      })),
    },
  };
}

export async function listStrategies(
  token?: string,
): Promise<ApiEnvelope<{ items: StrategiesPageModel["items"] }>> {
  const response = await fetchJson<{ items: Array<Record<string, unknown>> }>("/strategies", token);
  if (response.error) {
    return response as ApiEnvelope<{ items: StrategiesPageModel["items"] }>;
  }
  return {
    ...response,
    data: {
      items: response.data.items.map((item) => ({
        id: String(item.id ?? ""),
        name: String(item.name ?? ""),
        producerType: String(item.producerType ?? item.producer_type ?? ""),
        status: String(item.status ?? ""),
      })),
    },
  };
}

export async function getStrategyWorkspace(
  token?: string,
): Promise<ApiEnvelope<StrategyWorkspaceModel>> {
  const response = await fetchJson<Record<string, unknown>>("/strategies/workspace", token);
  if (response.error) {
    return response as ApiEnvelope<StrategyWorkspaceModel>;
  }

  const data: Record<string, unknown> = isPlainObject(response.data) ? response.data : {};
  return {
    ...response,
    data: {
      overview: normalizeStrategyWorkspaceOverview(data.overview),
      executor_runtime: normalizeExecutorRuntime(data.executor_runtime),
      research: normalizeWorkspaceResearchOverview(data.research),
      research_recommendation: normalizeResearchRecommendation(data.research_recommendation),
      whitelist: normalizeStringArray(data.whitelist, []),
      strategies: normalizeStrategyCards(data.strategies),
      recent_signals: normalizeObjectArray(data.recent_signals),
      recent_orders: normalizeObjectArray(data.recent_orders),
      account_state: normalizeWorkspaceAccountState(data.account_state),
    },
  };
}

export async function getLatestResearch(): Promise<ApiEnvelope<LatestResearchResponse>> {
  const response = await fetchJson<{ item: Record<string, unknown> }>("/signals/research/latest");
  if (response.error) {
    return response as ApiEnvelope<LatestResearchResponse>;
  }

  return {
    ...response,
    data: {
      item: normalizeLatestResearchItem(response.data.item),
    },
  };
}

export async function getResearchCandidates(): Promise<ApiEnvelope<{ items: ResearchCandidateItem[]; summary: ResearchCandidateSnapshot["summary"] }>> {
  const response = await fetchJson<Record<string, unknown>>("/signals/research/candidates");
  if (response.error) {
    return response as ApiEnvelope<{ items: ResearchCandidateItem[]; summary: ResearchCandidateSnapshot["summary"] }>;
  }
  const data: Record<string, unknown> = isPlainObject(response.data) ? response.data : {};
  return {
    ...response,
    data: {
      items: normalizeResearchCandidateArray(data.items),
      summary: normalizeResearchCandidateSummary(data.summary),
    },
  };
}

export async function getResearchCandidate(symbol: string): Promise<ApiEnvelope<{ item: ResearchCandidateItem | null }>> {
  const response = await fetchJson<Record<string, unknown>>(`/signals/research/candidates/${encodeURIComponent(symbol)}`);
  if (response.error) {
    return response as ApiEnvelope<{ item: ResearchCandidateItem | null }>;
  }
  const data: Record<string, unknown> = isPlainObject(response.data) ? response.data : {};
  return {
    ...response,
    data: {
      item: normalizeResearchCandidateItem(data.item),
    },
  };
}

export async function getResearchReport(): Promise<ApiEnvelope<{ item: ResearchReportItem }>> {
  const response = await fetchJson<{ item: Record<string, unknown> }>("/signals/research/report");
  if (response.error) {
    return response as ApiEnvelope<{ item: ResearchReportItem }>;
  }
  return {
    ...response,
    data: {
      item: normalizeResearchReportItem(response.data.item),
    },
  };
}

export async function listBalances(): Promise<
  ApiEnvelope<BalancesPageModel>
> {
  const response = await fetchJson<{ items: Array<Record<string, unknown>> }>("/balances");
  if (response.error) {
    return response as ApiEnvelope<BalancesPageModel>;
  }
  return {
    ...response,
    data: {
      source: String(response.meta.source ?? "unknown"),
      truthSource: String(response.meta.truth_source ?? "unknown"),
      items: response.data.items.map((item) => ({
        id: String(item.id ?? item.asset ?? ""),
        asset: String(item.asset ?? ""),
        available: String(item.available ?? ""),
        locked: String(item.locked ?? ""),
        tradeStatus: String(item.tradeStatus ?? "unknown"),
        tradeHint: String(item.tradeHint ?? ""),
        sellableQuantity: String(item.sellableQuantity ?? "0"),
        dustQuantity: String(item.dustQuantity ?? "0"),
      })),
    },
  };
}

export async function listPositions(): Promise<
  ApiEnvelope<PositionsPageModel>
> {
  const response = await fetchJson<{ items: Array<Record<string, unknown>> }>("/positions");
  if (response.error) {
    return response as ApiEnvelope<PositionsPageModel>;
  }
  return {
    ...response,
    data: {
      source: String(response.meta.source ?? "unknown"),
      truthSource: String(response.meta.truth_source ?? "unknown"),
      items: response.data.items.map((item) => ({
        id: String(item.id ?? ""),
        symbol: String(item.symbol ?? ""),
        side: String(item.side ?? ""),
        quantity: String(item.quantity ?? ""),
        unrealizedPnl: String(item.unrealizedPnl ?? item.unrealized_pnl ?? ""),
      })),
    },
  };
}

export async function listOrders(): Promise<
  ApiEnvelope<OrdersPageModel>
> {
  const response = await fetchJson<{ items: Array<Record<string, unknown>> }>("/orders");
  if (response.error) {
    return response as ApiEnvelope<OrdersPageModel>;
  }
  return {
    ...response,
    data: {
      source: String(response.meta.source ?? "unknown"),
      truthSource: String(response.meta.truth_source ?? "unknown"),
      items: response.data.items.map((item) => ({
        id: String(item.id ?? ""),
        symbol: String(item.symbol ?? ""),
        side: String(item.side ?? ""),
        orderType: String(item.orderType ?? item.order_type ?? ""),
        status: String(item.status ?? ""),
      })),
    },
  };
}

export async function listRiskEvents(
  token?: string,
): Promise<ApiEnvelope<{ items: RiskPageModel["items"] }>> {
  const response = await fetchJson<{ items: Array<Record<string, unknown>> }>("/risk-events", token);
  if (response.error) {
    return response as ApiEnvelope<{ items: RiskPageModel["items"] }>;
  }
  return {
    ...response,
    data: {
      items: response.data.items.map((item) => ({
        id: String(item.id ?? ""),
        level: String(item.level ?? ""),
        ruleName: String(item.rule_name ?? item.ruleName ?? ""),
        decision: String(item.decision ?? ""),
      })),
    },
  };
}

export async function listTasks(
  token?: string,
): Promise<ApiEnvelope<{ items: TasksPageModel["items"] }>> {
  const response = await fetchJson<{ items: Array<Record<string, unknown>> }>("/tasks", token);
  if (response.error) {
    return response as ApiEnvelope<{ items: TasksPageModel["items"] }>;
  }
  return {
    ...response,
    data: {
      items: response.data.items.map((item) => ({
        id: String(item.id ?? ""),
        taskType: String(item.task_type ?? item.taskType ?? ""),
        source: String(item.source ?? ""),
        status: String(item.status ?? ""),
      })),
    },
  };
}

export async function getAutomationStatus(
  token?: string,
): Promise<ApiEnvelope<{ item: AutomationStatusModel }>> {
  const response = await fetchJson<{ item: Record<string, unknown> }>("/tasks/automation", token);
  if (response.error) {
    return response as ApiEnvelope<{ item: AutomationStatusModel }>;
  }
  const item = isPlainObject(response.data.item) ? response.data.item : {};
  const state = isPlainObject(item.state) ? item.state : {};
  const health = isPlainObject(item.health) ? item.health : {};
  return {
    ...response,
    data: {
      item: {
        mode: String(state.mode ?? "manual"),
        paused: Boolean(state.paused),
        pauseReason: String(state.paused_reason ?? ""),
        manualTakeover: Boolean(state.manual_takeover),
        armedSymbol: String(state.armed_symbol ?? ""),
        runtimeMode: String(state.runtime_mode ?? "demo"),
        allowLiveExecution: Boolean(state.allow_live_execution),
        alerts: Array.isArray(state.alerts)
          ? state.alerts.map((entry) => {
              const row = isPlainObject(entry) ? entry : {};
              return {
                level: String(row.level ?? ""),
                code: String(row.code ?? ""),
                message: String(row.message ?? ""),
                createdAt: String(row.created_at ?? ""),
              };
            })
          : [],
        lastCycle: isPlainObject(state.last_cycle) ? state.last_cycle : {},
        reviewOverview: isPlainObject(item.review_overview) ? item.review_overview : {},
        researchOverview: isPlainObject(item.review_overview) ? item.review_overview : {},
        health,
        executionHealth: isPlainObject(item.execution_health) ? item.execution_health : {},
      },
    },
  };
}

export async function getValidationReview(
  token?: string,
): Promise<ApiEnvelope<{ item: ValidationReviewItem }>> {
  const response = await fetchJson<{ item: Record<string, unknown> }>("/tasks/validation-review", token);
  if (response.error) {
    return response as ApiEnvelope<{ item: ValidationReviewItem }>;
  }
  return {
    ...response,
    data: {
      item: isPlainObject(response.data.item) ? (response.data.item as ValidationReviewItem) : {
        overview: {},
        steps: [],
        research_report: {},
        task_health: {},
        execution_health: {},
        recent_tasks: [],
        account_snapshot: {},
      },
    },
  };
}

export async function listMarketSnapshots(): Promise<
  ApiEnvelope<{ items: MarketSnapshot[] }>
> {
  const response = await fetchJson<{ items: Array<Record<string, unknown>> }>("/market");
  if (response.error) {
    return response as ApiEnvelope<{ items: MarketSnapshot[] }>;
  }

  const data: Record<string, unknown> = isPlainObject(response.data) ? response.data : {};
  const items: unknown[] = Array.isArray(data.items) ? data.items : [];
  return {
    ...response,
    data: {
      ...data,
      items: items.map((item) => normalizeMarketSnapshot(item)),
    },
  };
}

export async function getMarketChart(symbol: string, interval?: string): Promise<
  ApiEnvelope<MarketChartData>
> {
  const normalizedInterval = String(interval ?? "").trim();
  const chartPath = normalizedInterval.length > 0
    ? `/market/${encodeURIComponent(symbol)}/chart?interval=${encodeURIComponent(normalizedInterval)}`
    : `/market/${encodeURIComponent(symbol)}/chart`;
  const response = await fetchJson<MarketChartData>(chartPath);
  if (response.error) {
    return response as ApiEnvelope<MarketChartData>;
  }

  const data: Record<string, unknown> = isPlainObject(response.data) ? response.data : {};
  const items: unknown[] = Array.isArray(data.items) ? data.items : [];
  return {
    ...response,
    data: {
      ...data,
      items: items.map((item) => normalizeMarketCandle(item)),
      overlays: normalizeChartIndicatorSummary(data.overlays),
      markers: normalizeChartMarkerGroups(data.markers),
      active_interval: String(data.active_interval ?? "4h"),
      supported_intervals: normalizeStringArray(data.supported_intervals, []),
      multi_timeframe_summary: normalizeMultiTimeframeSummary(data.multi_timeframe_summary),
      research_cockpit: normalizeResearchCockpitSummary(data.research_cockpit),
      strategy_context: normalizeMarketStrategyContext(data.strategy_context),
      freqtrade_readiness: normalizeFreqtradeReadiness(data.freqtrade_readiness),
    },
  };
}

export function getDashboardSummary(): DashboardSummary {
  return {
    scope: {
      market: "crypto",
      exchange: "Binance",
      executor: "Freqtrade",
      producer: "Qlib minimal pipeline or mock producer",
    },
    pipeline: [
      { name: "Signal", status: "contract ready" },
      { name: "Risk", status: "pending implementation" },
      { name: "Execution", status: "pending adapter" },
      { name: "Monitoring", status: "skeleton ready" },
    ],
    navigation: [
      { href: "/signals", label: "Signals" },
      { href: "/market", label: "Market" },
      { href: "/strategies", label: "Strategies" },
      { href: "/balances", label: "Balances" },
      { href: "/positions", label: "Positions" },
      { href: "/orders", label: "Orders" },
      { href: "/risk", label: "Risk" },
      { href: "/tasks", label: "Tasks" },
      { href: "/login", label: "Login" },
    ],
  };
}

function normalizeMarketSnapshot(item: unknown): MarketSnapshot {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  const preferredStrategy = normalizeMarketStrategy(row.recommended_strategy);
  const trendState = normalizeTrendState(row.trend_state);
  return {
    symbol: String(row.symbol ?? ""),
    last_price: String(row.last_price ?? row.lastPrice ?? ""),
    change_percent: String(row.change_percent ?? row.changePercent ?? row.priceChangePercent ?? ""),
    quote_volume: String(row.quote_volume ?? row.quoteVolume ?? ""),
    is_whitelisted: Boolean(row.is_whitelisted),
    recommended_strategy: preferredStrategy,
    trend_state: trendState,
    strategy_summary: normalizeStrategySummary(row.strategy_summary),
    research_brief: normalizeResearchCockpitSummary(row.research_brief),
  };
}

function normalizeMarketStrategy(value: unknown): "trend_breakout" | "trend_pullback" | "none" {
  if (value === "trend_breakout" || value === "trend_pullback") {
    return value;
  }
  return "none";
}

function normalizeTrendState(value: unknown): "uptrend" | "pullback" | "neutral" {
  if (value === "uptrend" || value === "pullback") {
    return value;
  }
  return "neutral";
}

function normalizeMarketCandle(item: unknown): MarketCandle {
  if (Array.isArray(item)) {
    return {
      open_time: Number(item[0] ?? 0),
      open: String(item[1] ?? ""),
      high: String(item[2] ?? ""),
      low: String(item[3] ?? ""),
      close: String(item[4] ?? ""),
      volume: String(item[5] ?? ""),
      close_time: Number(item[6] ?? 0),
    };
  }

  if (item && typeof item === "object") {
    const row = item as Record<string, unknown>;
    return {
      open_time: Number(row.open_time ?? row.openTime ?? 0),
      open: String(row.open ?? ""),
      high: String(row.high ?? ""),
      low: String(row.low ?? ""),
      close: String(row.close ?? ""),
      volume: String(row.volume ?? ""),
      close_time: Number(row.close_time ?? row.closeTime ?? 0),
    };
  }

  return {
    open_time: 0,
    open: "",
    high: "",
    low: "",
    close: "",
    volume: "",
    close_time: 0,
  };
}

function normalizeChartIndicatorSummary(item: unknown): ChartIndicatorSummary {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  return {
    ema_fast: normalizeChartIndicatorMetric(row.ema_fast),
    ema_slow: normalizeChartIndicatorMetric(row.ema_slow),
    atr: normalizeChartIndicatorMetric(row.atr),
    rsi: normalizeChartIndicatorMetric(row.rsi),
    volume_sma: normalizeChartIndicatorMetric(row.volume_sma),
  };
}

function normalizeChartIndicatorMetric(item: unknown): ChartIndicatorMetric {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  return {
    value: row.value === null || row.value === undefined ? null : String(row.value),
    ready: Boolean(row.ready),
    sample_size: Number(row.sample_size ?? 0),
    warnings: normalizeStringArray(row.warnings, []),
    last_candle_closed: Boolean(row.last_candle_closed),
  };
}

function normalizeChartMarkerGroups(item: unknown): ChartMarkerGroups {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  return {
    signals: normalizeObjectArray(row.signals),
    entries: normalizeObjectArray(row.entries),
    stops: normalizeObjectArray(row.stops),
  };
}

function normalizeStrategySummary(value: unknown): Record<string, Record<string, unknown>> {
  if (!isPlainObject(value)) {
    return {};
  }
  const result: Record<string, Record<string, unknown>> = {};
  for (const [key, item] of Object.entries(value)) {
    if (isPlainObject(item)) {
      result[key] = item;
    }
  }
  return result;
}

function normalizeMarketStrategyContext(item: unknown): MarketChartData["strategy_context"] {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  return {
    recommended_strategy: normalizeMarketStrategy(row.recommended_strategy),
    trend_state: normalizeTrendState(row.trend_state),
    next_step: String(row.next_step ?? ""),
    primary_reason: String(row.primary_reason ?? ""),
    evaluations: normalizeStrategySummary(row.evaluations),
  };
}

function normalizeFreqtradeReadiness(item: unknown): MarketChartData["freqtrade_readiness"] {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  return {
    executor: String(row.executor ?? "freqtrade"),
    backend: String(row.backend ?? "memory"),
    runtime_mode: String(row.runtime_mode ?? row.runtimeMode ?? "demo"),
    ready_for_real_freqtrade: Boolean(row.ready_for_real_freqtrade),
    reason: String(row.reason ?? "unknown"),
    next_step: String(row.next_step ?? ""),
  };
}

function normalizeObjectArray(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter(isPlainObject);
}

function normalizeExecutorRuntime(
  item: unknown,
): StrategyWorkspaceModel["executor_runtime"] {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  return {
    executor: String(row.executor ?? "freqtrade"),
    backend: String(row.backend ?? "memory"),
    mode: String(row.mode ?? "demo"),
    connection_status: String(row.connection_status ?? row.connectionStatus ?? "unknown"),
  };
}

function normalizeWorkspaceResearchOverview(item: unknown): WorkspaceResearchOverview {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  return {
    status: String(row.status ?? "unavailable"),
    detail: String(row.detail ?? "n/a"),
    model_version: String(row.model_version ?? row.modelVersion ?? ""),
    signal_count: Number(row.signal_count ?? row.signalCount ?? 0),
  };
}

function normalizeStrategyWorkspaceOverview(
  item: unknown,
): StrategyWorkspaceModel["overview"] {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  return {
    strategy_count: Number(row.strategy_count ?? 0),
    whitelist_count: Number(row.whitelist_count ?? 0),
    signal_count: Number(row.signal_count ?? 0),
    order_count: Number(row.order_count ?? 0),
    running_count: Number(row.running_count ?? 0),
  };
}

function normalizeResearchRecommendation(item: unknown): ResearchRecommendation | null {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  const symbol = String(row.symbol ?? "").trim().toUpperCase();
  if (!symbol) {
    return null;
  }
  const gateRow: Record<string, unknown> = isPlainObject(row.dry_run_gate) ? row.dry_run_gate : {};
  return {
    symbol,
    score: String(row.score ?? ""),
    allowed_to_dry_run: Boolean(row.allowed_to_dry_run),
    strategy_template: String(row.strategy_template ?? ""),
    dry_run_gate: {
      status: String(gateRow.status ?? "unavailable"),
      reasons: normalizeStringArray(gateRow.reasons, []),
    },
    next_action: String(row.next_action ?? ""),
  };
}

function normalizeWorkspaceAccountState(item: unknown): WorkspaceAccountState {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  const summaryRow: Record<string, unknown> = isPlainObject(row.summary) ? row.summary : {};
  return {
    source: String(row.source ?? "unknown"),
    truth_source: String(row.truth_source ?? row.truthSource ?? "unknown"),
    summary: {
      balance_count: Number(summaryRow.balance_count ?? 0),
      tradable_balance_count: Number(summaryRow.tradable_balance_count ?? 0),
      dust_count: Number(summaryRow.dust_count ?? 0),
      order_count: Number(summaryRow.order_count ?? 0),
      position_count: Number(summaryRow.position_count ?? 0),
    },
    balances: normalizeWorkspaceAccountBalances(row.balances),
    orders: normalizeWorkspaceAccountOrders(row.orders),
    positions: normalizeWorkspaceAccountPositions(row.positions),
    latest_balance: normalizeWorkspaceAccountBalance(row.latest_balance),
    latest_order: normalizeWorkspaceAccountOrder(row.latest_order),
    latest_position: normalizeWorkspaceAccountPosition(row.latest_position),
  };
}

function normalizeWorkspaceAccountBalances(value: unknown): WorkspaceAccountBalance[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => normalizeWorkspaceAccountBalance(item)).filter((item): item is WorkspaceAccountBalance => item !== null);
}

function normalizeWorkspaceAccountOrders(value: unknown): WorkspaceAccountOrder[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => normalizeWorkspaceAccountOrder(item)).filter((item): item is WorkspaceAccountOrder => item !== null);
}

function normalizeWorkspaceAccountPositions(value: unknown): WorkspaceAccountPosition[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => normalizeWorkspaceAccountPosition(item)).filter((item): item is WorkspaceAccountPosition => item !== null);
}

function normalizeWorkspaceAccountBalance(item: unknown): WorkspaceAccountBalance | null {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  const asset = String(row.asset ?? "");
  const id = String(row.id ?? row.asset ?? "").trim();
  if (!asset && !id) {
    return null;
  }
  return {
    id,
    asset,
    available: String(row.available ?? ""),
    locked: String(row.locked ?? ""),
    tradeStatus: String(row.tradeStatus ?? row.trade_status ?? "unknown"),
    tradeHint: String(row.tradeHint ?? row.trade_hint ?? ""),
    sellableQuantity: String(row.sellableQuantity ?? row.sellable_quantity ?? "0"),
    dustQuantity: String(row.dustQuantity ?? row.dust_quantity ?? "0"),
  };
}

function normalizeWorkspaceAccountOrder(item: unknown): WorkspaceAccountOrder | null {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  const id = String(row.id ?? "").trim();
  const symbol = String(row.symbol ?? "").trim();
  if (!id && !symbol) {
    return null;
  }
  return {
    id,
    symbol,
    side: String(row.side ?? ""),
    orderType: String(row.orderType ?? row.order_type ?? ""),
    status: String(row.status ?? ""),
  };
}

function normalizeWorkspaceAccountPosition(item: unknown): WorkspaceAccountPosition | null {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  const id = String(row.id ?? "").trim();
  const symbol = String(row.symbol ?? "").trim();
  if (!id && !symbol) {
    return null;
  }
  return {
    id,
    symbol,
    side: String(row.side ?? ""),
    quantity: String(row.quantity ?? ""),
  };
}

function normalizeStrategyCards(value: unknown): StrategyWorkspaceCard[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map((item) => {
    const row: Record<string, unknown> = isPlainObject(item) ? item : {};
    const symbols = normalizeStringArray(row.symbols, []);
    return {
      strategy_id: Number(row.strategy_id ?? 0),
      key: String(row.key ?? ""),
      display_name: String(row.display_name ?? row.displayName ?? ""),
      description: String(row.description ?? ""),
      symbols,
      default_params: isPlainObject(row.default_params) ? row.default_params : {},
      runtime_status: String(row.runtime_status ?? row.runtimeStatus ?? ""),
      runtime_name: String(row.runtime_name ?? row.runtimeName ?? ""),
      latest_signal: isPlainObject(row.latest_signal) ? row.latest_signal : null,
      research_summary: normalizeResearchSymbolSummary(row.research_summary, symbols[0] ?? ""),
      research_cockpit: normalizeResearchCockpitSummary(row.research_cockpit),
      current_evaluation: isPlainObject(row.current_evaluation) ? row.current_evaluation : {},
    };
  });
}

function normalizeResearchCockpitSummary(item: unknown): ResearchCockpitSummary {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  return {
    research_bias: String(row.research_bias ?? "unavailable"),
    recommended_strategy: normalizeMarketStrategy(row.recommended_strategy),
    confidence: String(row.confidence ?? "low"),
    research_gate: isPlainObject(row.research_gate) ? row.research_gate : {},
    primary_reason: String(row.primary_reason ?? ""),
    research_explanation: String(row.research_explanation ?? ""),
    model_version: String(row.model_version ?? row.modelVersion ?? ""),
    generated_at: String(row.generated_at ?? row.generatedAt ?? ""),
    signal_count: row.signal_count === undefined ? undefined : Number(row.signal_count ?? 0),
    entry_hint: row.entry_hint === undefined ? undefined : String(row.entry_hint ?? ""),
    stop_hint: row.stop_hint === undefined ? undefined : String(row.stop_hint ?? ""),
    overlay_summary: row.overlay_summary === undefined ? undefined : String(row.overlay_summary ?? ""),
  };
}

function normalizeMultiTimeframeSummary(value: unknown): MultiTimeframeSummaryItem[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map((item) => {
    const row: Record<string, unknown> = isPlainObject(item) ? item : {};
    return {
      interval: String(row.interval ?? ""),
      trend_state: normalizeTrendState(row.trend_state),
      research_bias: String(row.research_bias ?? "unavailable"),
      recommended_strategy: normalizeMarketStrategy(row.recommended_strategy),
      confidence: String(row.confidence ?? "low"),
      primary_reason: String(row.primary_reason ?? ""),
    };
  });
}

function normalizeLatestResearchItem(item: unknown): LatestResearchItem {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  return {
    status: String(row.status ?? "unavailable"),
    backend: String(row.backend ?? "qlib-fallback"),
    qlib_available: Boolean(row.qlib_available),
    detail: String(row.detail ?? "n/a"),
    latest_training: isPlainObject(row.latest_training) ? row.latest_training : null,
    latest_inference: isPlainObject(row.latest_inference) ? row.latest_inference : null,
    symbols: normalizeResearchSymbolMap(row.symbols),
  };
}

function normalizeResearchCandidateArray(value: unknown): ResearchCandidateItem[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => normalizeResearchCandidateItem(item)).filter((item): item is ResearchCandidateItem => item !== null);
}

function normalizeResearchCandidateItem(item: unknown): ResearchCandidateItem | null {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  const symbol = String(row.symbol ?? "").trim().toUpperCase();
  if (!symbol) {
    return null;
  }
  const backtestRow: Record<string, unknown> = isPlainObject(row.backtest) ? row.backtest : {};
  const metricsRow: Record<string, unknown> = isPlainObject(backtestRow.metrics) ? backtestRow.metrics : {};
  const gateRow: Record<string, unknown> = isPlainObject(row.dry_run_gate) ? row.dry_run_gate : {};
  return {
    rank: Number(row.rank ?? 0),
    symbol,
    strategy_template: String(row.strategy_template ?? ""),
    score: String(row.score ?? ""),
    backtest: {
      metrics: Object.fromEntries(Object.entries(metricsRow).map(([key, value]) => [key, String(value ?? "")])),
    },
    dry_run_gate: {
      status: String(gateRow.status ?? "unavailable"),
      reasons: normalizeStringArray(gateRow.reasons, []),
    },
    allowed_to_dry_run: Boolean(row.allowed_to_dry_run),
    review_status: String(row.review_status ?? ""),
    next_action: String(row.next_action ?? ""),
    forced_for_validation: Boolean(row.forced_for_validation),
    forced_reason: String(row.forced_reason ?? ""),
  };
}

function normalizeResearchCandidateSummary(value: unknown): ResearchCandidateSnapshot["summary"] {
  const row: Record<string, unknown> = isPlainObject(value) ? value : {};
  return {
    candidate_count: Number(row.candidate_count ?? 0),
    ready_count: Number(row.ready_count ?? 0),
    blocked_count: Number(row.blocked_count ?? 0),
    pass_rate_pct: String(row.pass_rate_pct ?? "0.00"),
    top_candidate_symbol: String(row.top_candidate_symbol ?? ""),
    top_candidate_score: String(row.top_candidate_score ?? ""),
  };
}

function normalizeResearchReportItem(item: unknown): ResearchReportItem {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  const overviewRow: Record<string, unknown> = isPlainObject(row.overview) ? row.overview : {};
  const experimentsRow: Record<string, unknown> = isPlainObject(row.experiments) ? row.experiments : {};
  return {
    status: String(row.status ?? "unavailable"),
    backend: String(row.backend ?? "qlib-fallback"),
    overview: {
      model_version: String(overviewRow.model_version ?? ""),
      generated_at: String(overviewRow.generated_at ?? ""),
      candidate_count: Number(overviewRow.candidate_count ?? 0),
      ready_count: Number(overviewRow.ready_count ?? 0),
      blocked_count: Number(overviewRow.blocked_count ?? 0),
      pass_rate_pct: String(overviewRow.pass_rate_pct ?? "0.00"),
      signal_count: Number(overviewRow.signal_count ?? 0),
      top_candidate_symbol: String(overviewRow.top_candidate_symbol ?? ""),
      top_candidate_score: String(overviewRow.top_candidate_score ?? ""),
    },
    latest_training: isPlainObject(row.latest_training) ? row.latest_training : {},
    latest_inference: isPlainObject(row.latest_inference) ? row.latest_inference : {},
    candidates: normalizeResearchCandidateArray(row.candidates),
    experiments: {
      training: isPlainObject(experimentsRow.training) ? experimentsRow.training : {},
      inference: isPlainObject(experimentsRow.inference) ? experimentsRow.inference : {},
    },
  };
}

function normalizeResearchSymbolMap(value: unknown): Record<string, ResearchSymbolSummary> {
  if (!isPlainObject(value)) {
    return {};
  }

  const result: Record<string, ResearchSymbolSummary> = {};
  for (const [symbol, item] of Object.entries(value)) {
    const normalizedSymbol = String(symbol ?? "").trim().toUpperCase();
    if (!normalizedSymbol) {
      continue;
    }
    result[normalizedSymbol] = normalizeResearchSymbolSummary(item, normalizedSymbol);
  }
  return result;
}

function normalizeResearchSymbolSummary(item: unknown, fallbackSymbol: string): ResearchSymbolSummary {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  return {
    symbol: String(row.symbol ?? fallbackSymbol),
    score: String(row.score ?? ""),
    signal: String(row.signal ?? ""),
    model_version: String(row.model_version ?? row.modelVersion ?? ""),
    explanation: String(row.explanation ?? row.summary ?? ""),
    generated_at: String(row.generated_at ?? row.generatedAt ?? ""),
  };
}

export function getSignalsPageFallback(): SignalsPageModel {
  return {
    columns: ["symbol", "source", "generated_at", "status"],
    items: [
      {
        id: "signal-1",
        symbol: "BTC/USDT",
        source: "qlib",
        generatedAt: "2026-04-01T06:00:00Z",
        status: "received",
      },
    ],
  };
}

export function getStrategiesPageModel(): StrategiesPageModel {
  return {
    items: [
      {
        id: "strategy-1",
        name: "BTC Trend",
        producerType: "qlib",
        status: "stopped",
      },
    ],
  };
}

export function getStrategyWorkspaceFallback(): StrategyWorkspaceModel {
  return {
    overview: {
      strategy_count: 2,
      whitelist_count: 4,
      signal_count: 1,
      order_count: 1,
      running_count: 0,
    },
    executor_runtime: {
      executor: "freqtrade",
      backend: "memory",
      mode: "demo",
      connection_status: "not_configured",
    },
    research: {
      status: "unavailable",
      detail: "api_unavailable",
      model_version: "",
      signal_count: 0,
    },
    research_recommendation: null,
    whitelist: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"],
    strategies: [
      {
        strategy_id: 1,
        key: "trend_breakout",
        display_name: "趋势突破",
        description: "顺着趋势等待关键区间突破后入场。",
        symbols: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"],
        default_params: { timeframe: "1h", lookback_bars: 20, breakout_buffer_pct: 0.5 },
        runtime_status: "stopped",
        runtime_name: "趋势突破",
        latest_signal: null,
        research_summary: {
          symbol: "BTCUSDT",
          score: "",
          signal: "",
          model_version: "",
          explanation: "暂无研究结果",
          generated_at: "",
        },
        research_cockpit: normalizeResearchCockpitSummary({
          research_bias: "unavailable",
          recommended_strategy: "trend_breakout",
          confidence: "low",
          research_gate: { status: "unavailable" },
          primary_reason: "api_unavailable",
          research_explanation: "该币种暂无研究结论",
          model_version: "",
          generated_at: "",
        }),
        current_evaluation: { decision: "evaluation_unavailable", reason: "api_unavailable" },
      },
      {
        strategy_id: 2,
        key: "trend_pullback",
        display_name: "趋势回调",
        description: "在趋势中等待回调完成后顺势入场。",
        symbols: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"],
        default_params: { timeframe: "1h", lookback_bars: 20, pullback_depth_pct: 1.0 },
        runtime_status: "stopped",
        runtime_name: "趋势回调",
        latest_signal: null,
        research_summary: {
          symbol: "BTCUSDT",
          score: "",
          signal: "",
          model_version: "",
          explanation: "暂无研究结果",
          generated_at: "",
        },
        research_cockpit: normalizeResearchCockpitSummary({
          research_bias: "unavailable",
          recommended_strategy: "trend_pullback",
          confidence: "low",
          research_gate: { status: "unavailable" },
          primary_reason: "api_unavailable",
          research_explanation: "该币种暂无研究结论",
          model_version: "",
          generated_at: "",
        }),
        current_evaluation: { decision: "evaluation_unavailable", reason: "api_unavailable" },
      },
    ],
    recent_signals: [],
    recent_orders: [],
    account_state: {
      source: "freqtrade-sync",
      truth_source: "freqtrade",
      summary: {
        balance_count: 0,
        tradable_balance_count: 0,
        dust_count: 0,
        order_count: 0,
        position_count: 0,
      },
      balances: [],
      orders: [],
      positions: [],
      latest_balance: null,
      latest_order: null,
      latest_position: null,
    },
  };
}

export function getLatestResearchFallback(): LatestResearchResponse {
  return {
    item: normalizeLatestResearchItem({
      status: "unavailable",
      backend: "qlib-fallback",
      qlib_available: false,
      detail: "research_unavailable",
      latest_training: null,
      latest_inference: null,
      symbols: {},
    }),
  };
}

export function getResearchCandidatesFallback(): { items: ResearchCandidateItem[]; summary: ResearchCandidateSnapshot["summary"] } {
  const snapshot: ResearchCandidateSnapshot = {
    status: "unavailable",
    backend: "qlib-fallback",
    model_version: "",
    generated_at: "",
    summary: {
      candidate_count: 0,
      ready_count: 0,
    },
    candidates: [],
  };
  return {
    items: snapshot.candidates,
    summary: snapshot.summary,
  };
}

export function getResearchReportFallback(): { item: ResearchReportItem } {
  return {
    item: normalizeResearchReportItem({
      status: "unavailable",
      backend: "qlib-fallback",
      overview: {
        model_version: "",
        generated_at: "",
        candidate_count: 0,
        ready_count: 0,
        blocked_count: 0,
        pass_rate_pct: "0.00",
        signal_count: 0,
        top_candidate_symbol: "",
        top_candidate_score: "",
      },
      latest_training: {},
      latest_inference: {},
      candidates: [],
      experiments: {
        training: { status: "unavailable" },
        inference: { status: "unavailable" },
      },
    }),
  };
}

export function getPositionsPageModel(): PositionsPageModel {
  return {
    source: "freqtrade-sync",
    truthSource: "freqtrade",
    items: [
      {
        id: "position-1",
        symbol: "BTC/USDT",
        side: "long",
        quantity: "0.0100000000",
        unrealizedPnl: "0.0000000000",
      },
    ],
  };
}

export function getBalancesPageModel(): BalancesPageModel {
  return {
    source: "api-skeleton",
    truthSource: "binance",
    items: [
      {
        id: "balance-usdt",
        asset: "USDT",
        available: "10000.0000000000",
        locked: "0.0000000000",
        tradeStatus: "tradable",
        tradeHint: "这是基础计价资产，可以直接用于下单",
        sellableQuantity: "10000",
        dustQuantity: "0",
      },
    ],
  };
}

export function getOrdersPageModel(): OrdersPageModel {
  return {
    source: "freqtrade-sync",
    truthSource: "freqtrade",
    items: [
      {
        id: "order-1",
        symbol: "BTC/USDT",
        side: "buy",
        orderType: "market",
        status: "new",
      },
    ],
  };
}

export function getRiskPageModel(): RiskPageModel {
  return {
    items: [
      {
        id: "risk-1",
        level: "medium",
        ruleName: "not-implemented-yet",
        decision: "warn",
      },
    ],
  };
}

export function getTasksPageModel(): TasksPageModel {
  return {
    items: [
      {
        id: "task-1",
        taskType: "train",
        source: "openclaw",
        status: "queued",
      },
    ],
  };
}

export function getAutomationStatusFallback(): { item: AutomationStatusModel } {
  return {
    item: {
      mode: "manual",
      paused: false,
      pauseReason: "",
      manualTakeover: false,
      armedSymbol: "",
      runtimeMode: "demo",
      allowLiveExecution: false,
      alerts: [],
      lastCycle: {},
      reviewOverview: {},
      researchOverview: {},
      health: {},
      executionHealth: {},
    },
  };
}

export async function getLoginPageModel(): Promise<LoginPageModel> {
  try {
    const response = await fetchJson<{ item: Record<string, unknown> }>("/auth/model");
    if (!response.error) {
      const item = response.data.item;
      return {
        defaultUsername: String(item.default_username ?? "admin"),
        sessionMode: String(item.session_mode ?? "单管理员 + 本地会话令牌"),
        protectedPages: normalizeStringArray(item.protected_pages, ["Strategies", "Tasks", "Risk"]),
        notes: normalizeStringArray(item.notes, [
          "仅保留单管理员入口",
          "登录后通过会话令牌访问控制平面",
          "当前阶段不扩展多用户与角色权限",
        ]),
      };
    }
  } catch {
    // API 暂时不可用时保留本地兜底模型。
  }

  return {
    defaultUsername: "",
    sessionMode: "登录模型暂时不可用，请确认控制平面 API 已启动",
    protectedPages: ["Strategies", "Tasks", "Risk"],
    notes: [
      "当前无法从控制平面读取登录配置",
      "请先确认 API 已启动，再刷新登录页",
      "当前阶段不扩展多用户与角色权限",
    ],
  };
}

function normalizeStringArray(value: unknown, fallback: string[]): string[] {
  if (!Array.isArray(value)) {
    return fallback;
  }

  const items = value.map((item) => String(item ?? "").trim()).filter(Boolean);
  return items.length ? items : fallback;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
