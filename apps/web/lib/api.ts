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
  configuration: Record<string, unknown>;
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
  pausedAt: string;
  manualTakeoverAt: string;
  lastFailureAt: string;
  armedSymbol: string;
  runtimeMode: string;
  allowLiveExecution: boolean;
  alerts: Array<{ id: number; level: string; code: string; message: string; createdAt: string }>;
  lastCycle: Record<string, unknown>;
  reviewOverview: Record<string, unknown>;
  researchOverview: Record<string, unknown>;
  health: Record<string, unknown>;
  executionHealth: Record<string, unknown>;
  dailySummary: Record<string, unknown>;
  runtimeWindow: Record<string, unknown>;
  schedulerPlan: Array<Record<string, unknown>>;
  failurePolicy: Record<string, unknown>;
  operations: Record<string, unknown>;
  automationConfig: Record<string, unknown>;
  executionPolicy: Record<string, unknown>;
  severitySummary: Record<string, unknown>;
  resumeChecklist: Array<Record<string, unknown>>;
};

export type WorkbenchControlOptions = {
  timeframes?: string[];
  models?: string[];
  research_templates?: string[];
  label_modes?: string[];
  window_modes?: string[];
  all_symbols?: string[];
  factor_categories?: Record<string, string[]>;
  all_factors?: Array<Record<string, unknown>>;
  [key: string]: unknown;
};

export type WorkbenchControlsModel = {
  config: Record<string, Record<string, unknown>>;
  options: WorkbenchControlOptions;
};

export type DataWorkspaceModel = {
  status: string;
  backend: string;
  config_alignment?: Record<string, unknown>;
  filters: {
    selected_symbol: string;
    selected_interval: string;
    limit: number;
    available_symbols: string[];
    available_intervals: string[];
  };
  sources: {
    research: string;
    market: string;
  };
  source_explanations: Array<{
    label: string;
    value: string;
    detail: string;
  }>;
  controls: {
    selected_symbols: string[];
    primary_symbol: string;
    timeframes: string[];
    sample_limit: number;
    lookback_days: number;
    window_mode: string;
    start_date: string;
    end_date: string;
    available_symbols: string[];
    available_timeframes: string[];
    available_window_modes: string[];
  };
  snapshot: {
    run_type: string;
    run_id: string;
    generated_at: string;
    snapshot_id: string;
    cache_signature: string;
    cache_status: string;
    cache_hit_count: number;
    cache_miss_count: number;
    active_data_state: string;
    data_states: Record<string, unknown>;
    dataset_snapshot_path: string;
  };
  snapshot_consistency: {
    training_snapshot_id: string;
    training_generated_at: string;
    training_cache_status: string;
    training_cache_hit_count: number;
    training_cache_miss_count: number;
    inference_snapshot_id: string;
    inference_generated_at: string;
    inference_cache_status: string;
    inference_cache_hit_count: number;
    inference_cache_miss_count: number;
    matches_training_snapshot: boolean;
    note: string;
  };
  quality: {
    raw_rows: number;
    cleaned_rows: number;
    feature_ready_rows: number;
    cleaned_drop_rows: number;
    feature_drop_rows: number;
    total_drop_rows: number;
    retention_ratio_pct: number;
    missing_rows: number | null;
    invalid_rows: number | null;
    detail: string;
    summary: string;
  };
  preview: {
    symbol: string;
    interval: string;
    effective_interval: string;
    source: string;
    total_rows: number;
    first_open_time: string;
    last_close_time: string;
    status: string;
    detail: string;
  };
  training_window: {
    holding_window: string;
    sample_window: Record<string, unknown>;
  };
  symbols: Array<{
    symbol: string;
    selected: boolean;
  }>;
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
  live_gate?: { status: string; reasons: string[] };
  allowed_to_live?: boolean;
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
  allowed_to_live?: boolean;
  strategy_template: string;
  dry_run_gate: { status: string; reasons: string[] };
  live_gate?: { status: string; reasons: string[] };
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

export type ResearchRuntimeStatusModel = {
  status: string;
  action: string;
  current_stage: string;
  progress_pct: number;
  started_at: string;
  finished_at: string;
  message: string;
  last_completed_action: string;
  last_finished_at: string;
  result_paths: string[];
  history: Record<string, unknown>;
  estimated_seconds: Record<string, number>;
  current_estimate_seconds: number;
};

export type FeatureWorkspaceModel = {
  status: string;
  backend: string;
  config_alignment?: Record<string, unknown>;
  overview: {
    feature_version: string;
    factor_count: number;
    primary_count: number;
    auxiliary_count: number;
    holding_window: string;
  };
  categories: Record<string, string[]>;
  roles: {
    primary: string[];
    auxiliary: string[];
  };
  controls: {
    feature_preset_key?: string;
    primary_factors: string[];
    auxiliary_factors: string[];
    trend_weight: string;
    momentum_weight: string;
    volume_weight: string;
    oscillator_weight: string;
    volatility_weight: string;
    strict_penalty_weight: string;
    signal_confidence_floor: string;
    missing_policy: string;
    outlier_policy: string;
    normalization_policy: string;
    timeframe_profiles: Record<string, Record<string, unknown>>;
    available_primary_factors: string[];
    available_auxiliary_factors: string[];
    available_missing_policies: string[];
    available_outlier_policies: string[];
    available_normalization_policies: string[];
    available_feature_presets?: string[];
    feature_preset_catalog?: Array<Record<string, unknown>>;
  };
  preprocessing: {
    missing_policy: string;
    outlier_policy: string;
    normalization_policy: string;
  };
  timeframe_profiles: Record<string, Record<string, unknown>>;
  factors: Array<{
    name: string;
    category: string;
    role: string;
    description: string;
  }>;
  selection_matrix?: Array<{
    name: string;
    category: string;
    protocol_role: string;
    current_role: string;
    description: string;
  }>;
};

export type ResearchWorkspaceModel = {
  status: string;
  backend: string;
  config_alignment?: Record<string, unknown>;
  overview: {
    holding_window: string;
    candidate_count: number;
    recommended_symbol: string;
    recommended_action: string;
  };
  strategy_templates: string[];
  labeling: {
    label_columns: string[];
    label_mode: string;
    definition: string;
  };
  sample_window: Record<string, Record<string, unknown>>;
  model: {
    model_version: string;
    backend: string;
  };
  controls: {
    research_preset_key?: string;
    research_template: string;
    model_key: string;
    label_mode: string;
    label_trigger_basis: string;
    holding_window_label: string;
    force_validation_top_candidate: boolean;
    min_holding_days: number;
    max_holding_days: number;
    label_target_pct: string;
    label_stop_pct: string;
    train_split_ratio: string;
    validation_split_ratio: string;
    test_split_ratio: string;
    signal_confidence_floor: string;
    trend_weight: string;
    momentum_weight: string;
    volume_weight: string;
    oscillator_weight: string;
    volatility_weight: string;
    strict_penalty_weight: string;
    available_models: string[];
    available_research_templates: string[];
    available_label_modes: string[];
    available_label_trigger_bases: string[];
    available_holding_windows: string[];
    available_research_presets?: string[];
    research_preset_catalog?: Array<Record<string, unknown>>;
  };
  parameters: Record<string, string>;
  selectors: {
    symbols: string[];
    timeframes: string[];
  };
  readiness: {
    train_ready: boolean;
    infer_ready: boolean;
    blocking_reasons: string[];
    infer_reason: string;
    next_step: string;
  };
  execution_preview: {
    data_scope: string;
    factor_mix: string;
    label_scope: string;
    dry_run_gate: string;
    live_gate: string;
    validation_policy: string;
  };
  label_rule_summary?: {
    preset_key: string;
    headline: string;
    detail: string;
    next_step: string;
  };
};

export type BacktestWorkspaceModel = {
  status: string;
  backend: string;
  overview: {
    holding_window: string;
    candidate_count: number;
    recommended_symbol: string;
  };
  assumptions: Record<string, string>;
  controls: {
    backtest_preset_key?: string;
    fee_bps: string;
    slippage_bps: string;
    cost_model: string;
    available_cost_models: string[];
    available_backtest_presets?: string[];
    backtest_preset_catalog?: Array<Record<string, unknown>>;
    enable_rule_gate: boolean;
    enable_validation_gate: boolean;
    enable_backtest_gate: boolean;
    enable_consistency_gate: boolean;
    enable_live_gate: boolean;
    dry_run_min_score: string;
    dry_run_min_positive_rate: string;
    dry_run_min_net_return_pct: string;
    dry_run_min_sharpe: string;
    dry_run_max_drawdown_pct: string;
    dry_run_max_loss_streak: string;
    dry_run_min_win_rate: string;
    dry_run_max_turnover: string;
    dry_run_min_sample_count: string;
    validation_min_sample_count: string;
    validation_min_avg_future_return_pct: string;
    consistency_max_validation_backtest_return_gap_pct: string;
    consistency_max_training_validation_positive_rate_gap: string;
    consistency_max_training_validation_return_gap_pct: string;
    rule_min_ema20_gap_pct: string;
    rule_min_ema55_gap_pct: string;
    rule_max_atr_pct: string;
    rule_min_volume_ratio: string;
    strict_rule_min_ema20_gap_pct: string;
    strict_rule_min_ema55_gap_pct: string;
    strict_rule_max_atr_pct: string;
    strict_rule_min_volume_ratio: string;
    live_min_score: string;
    live_min_positive_rate: string;
    live_min_net_return_pct: string;
    live_min_win_rate: string;
    live_max_turnover: string;
    live_min_sample_count: string;
  };
  training_backtest: {
    metrics: Record<string, string>;
  };
  leaderboard: Array<{
    symbol: string;
    strategy_template: string;
    backtest: Record<string, string>;
  }>;
};

export type EvaluationWorkspaceModel = {
  status: string;
  backend: string;
  config_alignment?: Record<string, unknown>;
  overview: {
    recommended_symbol: string;
    recommended_action: string;
    candidate_count: number;
  };
  controls: {
    threshold_preset_key?: string;
    dry_run_min_score: string;
    dry_run_min_positive_rate: string;
    dry_run_min_net_return_pct: string;
    dry_run_min_sharpe: string;
    dry_run_max_drawdown_pct: string;
    dry_run_max_loss_streak: string;
    dry_run_min_win_rate: string;
    dry_run_max_turnover: string;
    dry_run_min_sample_count: string;
    validation_min_sample_count: string;
    validation_min_avg_future_return_pct: string;
    consistency_max_validation_backtest_return_gap_pct: string;
    consistency_max_training_validation_positive_rate_gap: string;
    consistency_max_training_validation_return_gap_pct: string;
    rule_min_ema20_gap_pct: string;
    rule_min_ema55_gap_pct: string;
    rule_max_atr_pct: string;
    rule_min_volume_ratio: string;
    strict_rule_min_ema20_gap_pct: string;
    strict_rule_min_ema55_gap_pct: string;
    strict_rule_max_atr_pct: string;
    strict_rule_min_volume_ratio: string;
    enable_rule_gate: boolean;
    enable_validation_gate: boolean;
    enable_backtest_gate: boolean;
    enable_consistency_gate: boolean;
    enable_live_gate: boolean;
    live_min_score: string;
    live_min_positive_rate: string;
    live_min_net_return_pct: string;
    live_min_win_rate: string;
    live_max_turnover: string;
    live_min_sample_count: string;
    available_threshold_presets?: string[];
    threshold_preset_catalog?: Array<Record<string, unknown>>;
  };
  operations: {
    review_limit: string;
    comparison_run_limit: string;
    cycle_cooldown_minutes: string;
    max_daily_cycle_count: string;
  };
  evaluation: Record<string, unknown>;
  reviews: Record<string, unknown>;
  recent_review_tasks: Array<Record<string, unknown>>;
  leaderboard: Array<Record<string, unknown>>;
  best_experiment: Record<string, unknown>;
  best_stage_candidates: Record<string, unknown>;
  recommendation_explanation: Record<string, unknown>;
  elimination_explanation: Record<string, unknown>;
  recent_runs: Array<Record<string, unknown>>;
  recent_training_runs: Array<Record<string, unknown>>;
  recent_inference_runs: Array<Record<string, unknown>>;
  experiment_comparison: Array<Record<string, unknown>>;
  gate_matrix: Array<Record<string, unknown>>;
  run_deltas: Array<Record<string, unknown>>;
  delta_overview: Record<string, unknown>;
  comparison_summary: Record<string, unknown>;
  execution_alignment: Record<string, unknown>;
  alignment_details: Record<string, unknown>;
  alignment_story: Record<string, unknown>;
  alignment_metric_rows: Array<Record<string, unknown>>;
  alignment_gaps: Array<Record<string, unknown>>;
  alignment_actions: Array<Record<string, unknown>>;
  workflow_alignment_timeline: Array<Record<string, unknown>>;
  stage_decision_summary?: Record<string, unknown>;
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

const WEB_PROXY_BASE_URL = "/api/control";
const DEFAULT_API_BASE_URL = "http://127.0.0.1:9011/api/v1";
export const AUTH_STORAGE_KEY = "quant_admin_token";
const PROTECTED_ROUTE_PATHS = ["/strategies", "/tasks", "/risk"];

async function resolveControlPlaneBaseUrl(request?: Request): Promise<string> {
  if (typeof window !== "undefined") {
    return WEB_PROXY_BASE_URL;
  }

  const localDebugBaseUrl = deriveLocalApiBaseUrl(request);
  if (localDebugBaseUrl) {
    return localDebugBaseUrl;
  }

  try {
    const { headers } = await import("next/headers");
    const requestHeaders = await headers();
    const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "";
    const protocol = requestHeaders.get("x-forwarded-proto") ?? "http";
    if (host) {
      return `${protocol}://${host}${WEB_PROXY_BASE_URL}`;
    }
  } catch {
    // 服务端无法读取当前请求头时，回退到显式 API 基址。
  }

  return buildUpstreamApiUrl("/");
}

export async function resolveControlPlaneUrl(path: string, request?: Request): Promise<string> {
  const baseUrl = await resolveControlPlaneBaseUrl(request);
  return `${baseUrl}${path}`;
}

function deriveLocalApiBaseUrl(request?: Request): string | null {
  if (!request) {
    return null;
  }

  try {
    const currentUrl = new URL(request.url);
    const forwardedHost = request.headers.get("x-forwarded-host")?.trim() ?? "";
    const directHost = request.headers.get("host")?.trim() ?? "";
    const hostPort = (forwardedHost || directHost || currentUrl.host).trim();
    const [hostnamePart, portPart] = splitHostPort(hostPort);
    const hostname = hostnamePart || currentUrl.hostname;
    if (!isLoopbackHost(hostname)) {
      return null;
    }
    const webPort = Number(portPart || currentUrl.port || "0");
    if (!Number.isFinite(webPort) || webPort <= 1) {
      return null;
    }
    return `${currentUrl.protocol}//${hostname}:${webPort - 1}/api/v1`;
  } catch {
    return null;
  }
}

function splitHostPort(hostPort: string): [string, string] {
  if (!hostPort) {
    return ["", ""];
  }
  if (hostPort.startsWith("[")) {
    const closingIndex = hostPort.indexOf("]");
    if (closingIndex === -1) {
      return [hostPort, ""];
    }
    const hostname = hostPort.slice(0, closingIndex + 1);
    const port = hostPort.slice(closingIndex + 2);
    return [hostname, port];
  }
  const separatorIndex = hostPort.lastIndexOf(":");
  if (separatorIndex === -1) {
    return [hostPort, ""];
  }
  return [hostPort.slice(0, separatorIndex), hostPort.slice(separatorIndex + 1)];
}

function isLoopbackHost(hostname: string): boolean {
  return hostname === "127.0.0.1" || hostname === "::1" || hostname === "[::1]";
}

/* 构建服务端直连控制面 API 地址。 */
export function buildUpstreamApiUrl(path: string, request?: Request): string {
  const configuredBaseUrl = (deriveLocalApiBaseUrl(request) ?? process.env.QUANT_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(
    /\/$/,
    "",
  );
  return `${configuredBaseUrl}${path}`;
}

/* 构建当前主机下的控制代理地址。 */
export function buildProxyUrl(request: Request, path: string): string {
  return new URL(`${WEB_PROXY_BASE_URL}${path}`, request.url).toString();
}

export function buildApiUrl(path: string): string {
  if (typeof window !== "undefined") {
    return `${WEB_PROXY_BASE_URL}${path}`;
  }
  return buildUpstreamApiUrl(path);
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
  const response = await fetch(await resolveControlPlaneUrl(path), {
    headers: buildAuthHeaders(token),
    cache: "no-store",
  });

  return response.json() as Promise<ApiEnvelope<T>>;
}

export async function loginAdmin(
  username: string,
  password: string,
  request?: Request,
): Promise<ApiEnvelope<{ item: { token: string; username: string; scope: string } }>> {
  const response = await fetch(await resolveControlPlaneUrl("/auth/login", request), {
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
  request?: Request,
): Promise<ApiEnvelope<{ item: { token: string; status: string } }>> {
  const response = await fetch(await resolveControlPlaneUrl(`/auth/logout?token=${token}`, request), {
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
      configuration: isPlainObject(data.configuration) ? data.configuration : {},
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

export async function getResearchRuntimeStatus(): Promise<ApiEnvelope<{ item: ResearchRuntimeStatusModel }>> {
  const response = await fetchJson<{ item: Record<string, unknown> }>("/signals/research/runtime");
  if (response.error) {
    return {
      ...response,
      data: {
        item: getResearchRuntimeStatusFallback(),
      },
    };
  }
  return {
    ...response,
    data: {
      item: normalizeResearchRuntimeStatus(response.data.item),
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
        pausedAt: String(state.paused_at ?? ""),
        manualTakeoverAt: String(state.manual_takeover_at ?? ""),
        lastFailureAt: String(state.last_failure_at ?? ""),
        armedSymbol: String(state.armed_symbol ?? ""),
        runtimeMode: String(state.runtime_mode ?? "demo"),
        allowLiveExecution: Boolean(state.allow_live_execution),
        alerts: Array.isArray(state.alerts)
          ? state.alerts.map((entry) => {
              const row = isPlainObject(entry) ? entry : {};
              return {
                id: Number(row.id ?? 0),
                level: String(row.level ?? ""),
                code: String(row.code ?? ""),
                message: String(row.message ?? ""),
                createdAt: String(row.created_at ?? ""),
              };
            })
          : [],
        lastCycle: isPlainObject(state.last_cycle) ? state.last_cycle : {},
        reviewOverview: isPlainObject(item.review_overview) ? item.review_overview : {},
        researchOverview: isPlainObject(item.research_overview) ? item.research_overview : {},
        health,
        executionHealth: isPlainObject(item.execution_health) ? item.execution_health : {},
        dailySummary: isPlainObject(item.daily_summary) ? item.daily_summary : {},
        runtimeWindow: isPlainObject(item.runtime_window) ? item.runtime_window : {},
        schedulerPlan: Array.isArray(item.scheduler_plan) ? item.scheduler_plan.filter((entry) => isPlainObject(entry)) as Array<Record<string, unknown>> : [],
        failurePolicy: isPlainObject(item.failure_policy) ? item.failure_policy : {},
        operations: isPlainObject(item.operations) ? item.operations : {},
        automationConfig: isPlainObject(item.automation_config) ? item.automation_config : {},
        executionPolicy: isPlainObject(item.execution_policy) ? item.execution_policy : {},
        severitySummary: isPlainObject(item.severity_summary) ? item.severity_summary : {},
        resumeChecklist: Array.isArray(item.resume_checklist) ? item.resume_checklist.filter((entry) => isPlainObject(entry)) as Array<Record<string, unknown>> : [],
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

export async function getDataWorkspace(
  symbol?: string,
  interval?: string,
  limit?: number,
): Promise<ApiEnvelope<{ item: DataWorkspaceModel }>> {
  const query = new URLSearchParams();
  if (symbol) {
    query.set("symbol", symbol);
  }
  if (interval) {
    query.set("interval", interval);
  }
  if (typeof limit === "number" && Number.isFinite(limit)) {
    query.set("limit", String(limit));
  }
  const path = query.size > 0 ? `/data/workspace?${query.toString()}` : "/data/workspace";
  let response: ApiEnvelope<{ item: Record<string, unknown> }>;
  try {
    response = await fetchJson<{ item: Record<string, unknown> }>(path);
  } catch (error) {
    return {
      data: {
        item: getDataWorkspaceFallback(symbol, interval, limit),
      },
      error: {
        code: "workspace_fetch_failed",
        message: error instanceof Error ? error.message : "数据工作台暂时不可用",
      },
      meta: {
        source: "data-workspace",
      },
    };
  }
  if (response.error) {
    return {
      ...response,
      data: {
        item: getDataWorkspaceFallback(symbol, interval, limit),
      },
    };
  }

  return {
    ...response,
    data: {
      item: normalizeDataWorkspaceModel(response.data.item),
    },
  };
}

export async function getFeatureWorkspace(): Promise<ApiEnvelope<{ item: FeatureWorkspaceModel }>> {
  let response: ApiEnvelope<{ item: Record<string, unknown> }>;
  try {
    response = await fetchJson<{ item: Record<string, unknown> }>("/features/workspace");
  } catch (error) {
    return {
      data: {
        item: getFeatureWorkspaceFallback(),
      },
      error: {
        code: "feature_workspace_fetch_failed",
        message: error instanceof Error ? error.message : "特征工作台暂时不可用",
      },
      meta: {
        source: "feature-workspace",
      },
    };
  }

  if (response.error) {
    return {
      ...response,
      data: {
        item: getFeatureWorkspaceFallback(),
      },
    };
  }

  return {
    ...response,
    data: {
      item: normalizeFeatureWorkspaceModel(response.data.item),
    },
  };
}

export async function getResearchWorkspace(): Promise<ApiEnvelope<{ item: ResearchWorkspaceModel }>> {
  let response: ApiEnvelope<{ item: Record<string, unknown> }>;
  try {
    response = await fetchJson<{ item: Record<string, unknown> }>("/research/workspace");
  } catch (error) {
    return {
      data: {
        item: getResearchWorkspaceFallback(),
      },
      error: {
        code: "research_workspace_fetch_failed",
        message: error instanceof Error ? error.message : "策略研究工作台暂时不可用",
      },
      meta: {
        source: "research-workspace",
      },
    };
  }

  if (response.error) {
    return {
      ...response,
      data: {
        item: getResearchWorkspaceFallback(),
      },
    };
  }

  return {
    ...response,
    data: {
      item: normalizeResearchWorkspaceModel(response.data.item),
    },
  };
}

export async function getBacktestWorkspace(): Promise<ApiEnvelope<{ item: BacktestWorkspaceModel }>> {
  let response: ApiEnvelope<{ item: Record<string, unknown> }>;
  try {
    response = await fetchJson<{ item: Record<string, unknown> }>("/backtest/workspace");
  } catch (error) {
    return {
      data: {
        item: getBacktestWorkspaceFallback(),
      },
      error: {
        code: "backtest_workspace_fetch_failed",
        message: error instanceof Error ? error.message : "回测工作台暂时不可用",
      },
      meta: {
        source: "backtest-workspace",
      },
    };
  }

  if (response.error) {
    return {
      ...response,
      data: {
        item: getBacktestWorkspaceFallback(),
      },
    };
  }

  return {
    ...response,
    data: {
      item: normalizeBacktestWorkspaceModel(response.data.item),
    },
  };
}

export async function getEvaluationWorkspace(): Promise<ApiEnvelope<{ item: EvaluationWorkspaceModel }>> {
  let response: ApiEnvelope<{ item: Record<string, unknown> }>;
  try {
    response = await fetchJson<{ item: Record<string, unknown> }>("/evaluation/workspace");
  } catch (error) {
    return {
      data: {
        item: getEvaluationWorkspaceFallback(),
      },
      error: {
        code: "evaluation_workspace_fetch_failed",
        message: error instanceof Error ? error.message : "评估与实验中心暂时不可用",
      },
      meta: {
        source: "evaluation-workspace",
      },
    };
  }

  if (response.error) {
    return {
      ...response,
      data: {
        item: getEvaluationWorkspaceFallback(),
      },
    };
  }

  return {
    ...response,
    data: {
      item: normalizeEvaluationWorkspaceModel(response.data.item),
    },
  };
}

export function getDataWorkspaceFallback(symbol?: string, interval?: string, limit?: number): DataWorkspaceModel {
  return {
    status: "unavailable",
    backend: "qlib-fallback",
    config_alignment: {},
    filters: {
      selected_symbol: String(symbol ?? "").trim() || "BTCUSDT",
      selected_interval: String(interval ?? "").trim() || "4h",
      limit: typeof limit === "number" && Number.isFinite(limit) ? limit : 200,
      available_symbols: [],
      available_intervals: ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
    },
    controls: {
      selected_symbols: [String(symbol ?? "").trim() || "BTCUSDT"],
      primary_symbol: String(symbol ?? "").trim() || "BTCUSDT",
      timeframes: [String(interval ?? "").trim() || "4h", "1h"],
      sample_limit: typeof limit === "number" && Number.isFinite(limit) ? limit : 200,
      lookback_days: 30,
      window_mode: "rolling",
      start_date: "",
      end_date: "",
      available_symbols: [],
      available_timeframes: ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
      available_window_modes: ["rolling", "fixed"],
    },
    sources: {
      research: "qlib-fallback",
      market: "binance",
    },
    source_explanations: [],
    snapshot: {
      run_type: "training",
      run_id: "",
      generated_at: "",
      snapshot_id: "",
      cache_signature: "",
      cache_status: "",
      cache_hit_count: 0,
      cache_miss_count: 0,
      active_data_state: "",
      data_states: {},
      dataset_snapshot_path: "",
    },
    snapshot_consistency: {
      training_snapshot_id: "",
      training_generated_at: "",
      training_cache_status: "",
      training_cache_hit_count: 0,
      training_cache_miss_count: 0,
      inference_snapshot_id: "",
      inference_generated_at: "",
      inference_cache_status: "",
      inference_cache_hit_count: 0,
      inference_cache_miss_count: 0,
      matches_training_snapshot: false,
      note: "当前还没有可用快照一致性说明。",
    },
    quality: {
      raw_rows: 0,
      cleaned_rows: 0,
      feature_ready_rows: 0,
      cleaned_drop_rows: 0,
      feature_drop_rows: 0,
      total_drop_rows: 0,
      retention_ratio_pct: 0,
      missing_rows: null,
      invalid_rows: null,
      detail: "当前还没有可用质量摘要。",
      summary: "当前还没有可用质量摘要。",
    },
    preview: {
      symbol: String(symbol ?? "").trim() || "BTCUSDT",
      interval: String(interval ?? "").trim() || "4h",
      effective_interval: String(interval ?? "").trim() || "4h",
      source: "binance",
      total_rows: 0,
      first_open_time: "",
      last_close_time: "",
      status: "unavailable",
      detail: "数据工作台当前没有拿到可用响应。",
    },
    training_window: {
      holding_window: "",
      sample_window: {},
    },
    symbols: [],
  };
}

export function getFeatureWorkspaceFallback(): FeatureWorkspaceModel {
  return {
    status: "unavailable",
    backend: "qlib-fallback",
    config_alignment: {},
    overview: {
      feature_version: "",
      factor_count: 0,
      primary_count: 0,
      auxiliary_count: 0,
      holding_window: "",
    },
    categories: {},
    roles: {
      primary: [],
      auxiliary: [],
    },
    controls: {
      primary_factors: [],
      auxiliary_factors: [],
      trend_weight: "1.3",
      momentum_weight: "1",
      volume_weight: "1.1",
      oscillator_weight: "0.7",
      volatility_weight: "0.8",
      strict_penalty_weight: "0.6",
      signal_confidence_floor: "0.55",
      missing_policy: "neutral_fill",
      outlier_policy: "clip",
      normalization_policy: "fixed_4dp",
      timeframe_profiles: {},
      available_primary_factors: [],
      available_auxiliary_factors: [],
      available_missing_policies: ["neutral_fill", "strict_drop"],
      available_outlier_policies: ["clip", "raw"],
      available_normalization_policies: ["fixed_4dp", "zscore_by_symbol"],
    },
    preprocessing: {
      missing_policy: "",
      outlier_policy: "",
      normalization_policy: "",
    },
    timeframe_profiles: {},
    factors: [],
    selection_matrix: [],
  };
}

export function getResearchWorkspaceFallback(): ResearchWorkspaceModel {
  return {
    status: "unavailable",
    backend: "qlib-fallback",
    config_alignment: {},
    overview: {
      holding_window: "",
      candidate_count: 0,
      recommended_symbol: "",
      recommended_action: "",
    },
    strategy_templates: [],
    labeling: {
      label_columns: [],
      label_mode: "earliest_hit",
      definition: "",
    },
    sample_window: {},
    model: {
      model_version: "",
      backend: "qlib-fallback",
    },
    controls: {
      research_template: "single_asset_timing",
      model_key: "heuristic_v1",
      label_mode: "earliest_hit",
      label_trigger_basis: "close",
      holding_window_label: "1-3d",
      force_validation_top_candidate: false,
      min_holding_days: 1,
      max_holding_days: 3,
      label_target_pct: "1",
      label_stop_pct: "-1",
      train_split_ratio: "0.6",
      validation_split_ratio: "0.2",
      test_split_ratio: "0.2",
      signal_confidence_floor: "0.55",
      trend_weight: "1.3",
      momentum_weight: "1",
      volume_weight: "1.1",
      oscillator_weight: "0.7",
      volatility_weight: "0.9",
      strict_penalty_weight: "1",
      available_models: ["heuristic_v1", "trend_bias_v2", "balanced_v3"],
      available_research_templates: ["single_asset_timing", "single_asset_timing_strict"],
      available_label_modes: ["earliest_hit", "close_only", "window_majority"],
      available_label_trigger_bases: ["close", "high_low"],
      available_holding_windows: ["1-3d", "2-4d", "3-5d"],
    },
    parameters: {},
    selectors: {
      symbols: [],
      timeframes: [],
    },
    readiness: {
      train_ready: false,
      infer_ready: false,
      blocking_reasons: ["当前工作台暂时不可用"],
      infer_reason: "当前还没有训练结果，暂时无法推理。",
      next_step: "先恢复研究接口，再重新运行训练。",
    },
    execution_preview: {
      data_scope: "",
      factor_mix: "",
      label_scope: "",
      dry_run_gate: "",
      live_gate: "",
      validation_policy: "",
    },
    label_rule_summary: {
      preset_key: "balanced_window",
      headline: "",
      detail: "",
      next_step: "",
    },
  };
}

export function getBacktestWorkspaceFallback(): BacktestWorkspaceModel {
  return {
    status: "unavailable",
    backend: "qlib-fallback",
    overview: {
      holding_window: "",
      candidate_count: 0,
      recommended_symbol: "",
    },
    assumptions: {},
    controls: {
      fee_bps: "10",
      slippage_bps: "5",
      cost_model: "round_trip_basis_points",
      available_cost_models: ["round_trip_basis_points", "single_side_basis_points", "zero_cost_baseline"],
      enable_rule_gate: true,
      enable_validation_gate: true,
      enable_backtest_gate: true,
      enable_consistency_gate: true,
      enable_live_gate: true,
      dry_run_min_score: "0.55",
      dry_run_min_positive_rate: "0.45",
      dry_run_min_net_return_pct: "0",
      dry_run_min_sharpe: "0.5",
      dry_run_max_drawdown_pct: "15",
      dry_run_max_loss_streak: "3",
      dry_run_min_win_rate: "0.5",
      dry_run_max_turnover: "0.6",
      dry_run_min_sample_count: "20",
      validation_min_sample_count: "12",
      validation_min_avg_future_return_pct: "-0.1",
      consistency_max_validation_backtest_return_gap_pct: "1.5",
      consistency_max_training_validation_positive_rate_gap: "0.2",
      consistency_max_training_validation_return_gap_pct: "1.5",
      rule_min_ema20_gap_pct: "0",
      rule_min_ema55_gap_pct: "0",
      rule_max_atr_pct: "5",
      rule_min_volume_ratio: "1",
      strict_rule_min_ema20_gap_pct: "1.2",
      strict_rule_min_ema55_gap_pct: "1.8",
      strict_rule_max_atr_pct: "4.5",
      strict_rule_min_volume_ratio: "1.05",
      live_min_score: "0.65",
      live_min_positive_rate: "0.50",
      live_min_net_return_pct: "0.20",
      live_min_win_rate: "0.55",
      live_max_turnover: "0.45",
      live_min_sample_count: "24",
    },
    training_backtest: {
      metrics: {},
    },
    leaderboard: [],
  };
}

export function getEvaluationWorkspaceFallback(): EvaluationWorkspaceModel {
  return {
    status: "unavailable",
    backend: "qlib-fallback",
    overview: {
      recommended_symbol: "",
      recommended_action: "",
      candidate_count: 0,
    },
    controls: {
      dry_run_min_score: "0.55",
      dry_run_min_positive_rate: "0.45",
      dry_run_min_net_return_pct: "0",
      dry_run_min_sharpe: "0.5",
      dry_run_max_drawdown_pct: "15",
      dry_run_max_loss_streak: "3",
      dry_run_min_win_rate: "0.5",
      dry_run_max_turnover: "0.6",
      dry_run_min_sample_count: "20",
      validation_min_sample_count: "12",
      validation_min_avg_future_return_pct: "-0.1",
      consistency_max_validation_backtest_return_gap_pct: "1.5",
      consistency_max_training_validation_positive_rate_gap: "0.2",
      consistency_max_training_validation_return_gap_pct: "1.5",
      rule_min_ema20_gap_pct: "0",
      rule_min_ema55_gap_pct: "0",
      rule_max_atr_pct: "5",
      rule_min_volume_ratio: "1",
      strict_rule_min_ema20_gap_pct: "1.2",
      strict_rule_min_ema55_gap_pct: "1.8",
      strict_rule_max_atr_pct: "4.5",
      strict_rule_min_volume_ratio: "1.05",
      enable_rule_gate: true,
      enable_validation_gate: true,
      enable_backtest_gate: true,
      enable_consistency_gate: true,
      enable_live_gate: true,
      live_min_score: "0.65",
      live_min_positive_rate: "0.50",
      live_min_net_return_pct: "0.20",
      live_min_win_rate: "0.55",
      live_max_turnover: "0.45",
      live_min_sample_count: "24",
    },
    operations: {
      review_limit: "10",
      comparison_run_limit: "5",
      cycle_cooldown_minutes: "15",
      max_daily_cycle_count: "8",
    },
    evaluation: {},
    reviews: {},
    recent_review_tasks: [],
    leaderboard: [],
    best_experiment: {},
    best_stage_candidates: {},
    recommendation_explanation: {},
    elimination_explanation: {},
    recent_runs: [],
    recent_training_runs: [],
    recent_inference_runs: [],
    experiment_comparison: [],
    gate_matrix: [],
    workflow_alignment_timeline: [],
    run_deltas: [],
    delta_overview: {},
    comparison_summary: {},
    execution_alignment: {},
    stage_decision_summary: {},
    alignment_details: {},
    alignment_story: {},
    alignment_metric_rows: [],
    alignment_gaps: [],
    alignment_actions: [],
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

function normalizeDataWorkspaceModel(item: unknown): DataWorkspaceModel {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  const filters = isPlainObject(row.filters) ? row.filters : {};
  const sources = isPlainObject(row.sources) ? row.sources : {};
  const controls = isPlainObject(row.controls) ? row.controls : {};
  const snapshot = isPlainObject(row.snapshot) ? row.snapshot : {};
  const preview = isPlainObject(row.preview) ? row.preview : {};
  const trainingWindow = isPlainObject(row.training_window) ? row.training_window : {};
  const sampleWindow = isPlainObject(trainingWindow.sample_window) ? trainingWindow.sample_window : {};
  const symbols = Array.isArray(row.symbols) ? row.symbols : [];
  return {
    status: String(row.status ?? "unavailable"),
    backend: String(row.backend ?? "qlib-fallback"),
    config_alignment: isPlainObject(row.config_alignment) ? row.config_alignment : {},
    filters: {
      selected_symbol: String(filters.selected_symbol ?? ""),
      selected_interval: String(filters.selected_interval ?? "4h"),
      limit: Number(filters.limit ?? 0),
      available_symbols: normalizeStringArray(filters.available_symbols, []),
      available_intervals: normalizeStringArray(filters.available_intervals, ["1h", "4h", "1d"]),
    },
    controls: {
      selected_symbols: normalizeStringArray(controls.selected_symbols, []),
      primary_symbol: String(controls.primary_symbol ?? ""),
      timeframes: normalizeStringArray(controls.timeframes, []),
      sample_limit: Number(controls.sample_limit ?? 120),
      lookback_days: Number(controls.lookback_days ?? 30),
      window_mode: String(controls.window_mode ?? "rolling"),
      start_date: String(controls.start_date ?? ""),
      end_date: String(controls.end_date ?? ""),
      available_symbols: normalizeStringArray(controls.available_symbols, []),
      available_timeframes: normalizeStringArray(controls.available_timeframes, []),
      available_window_modes: normalizeStringArray(controls.available_window_modes, ["rolling", "fixed"]),
    },
    sources: {
      research: String(sources.research ?? "qlib-fallback"),
      market: String(sources.market ?? "binance"),
    },
    source_explanations: normalizeObjectArray(row.source_explanations).map((value) => ({
      label: String(value.label ?? ""),
      value: String(value.value ?? ""),
      detail: String(value.detail ?? ""),
    })),
    snapshot: {
      run_type: String(snapshot.run_type ?? "training"),
      run_id: String(snapshot.run_id ?? ""),
      generated_at: String(snapshot.generated_at ?? ""),
      snapshot_id: String(snapshot.snapshot_id ?? ""),
      cache_signature: String(snapshot.cache_signature ?? ""),
      cache_status: String(snapshot.cache_status ?? ""),
      cache_hit_count: Number(snapshot.cache_hit_count ?? 0),
      cache_miss_count: Number(snapshot.cache_miss_count ?? 0),
      active_data_state: String(snapshot.active_data_state ?? ""),
      data_states: isPlainObject(snapshot.data_states) ? snapshot.data_states : {},
      dataset_snapshot_path: String(snapshot.dataset_snapshot_path ?? ""),
    },
    snapshot_consistency: normalizeDataWorkspaceSnapshotConsistency(row.snapshot_consistency),
    quality: normalizeDataWorkspaceQuality(row.quality),
    preview: {
      symbol: String(preview.symbol ?? ""),
      interval: String(preview.interval ?? "4h"),
      effective_interval: String(preview.effective_interval ?? preview.interval ?? "4h"),
      source: String(preview.source ?? "binance"),
      total_rows: Number(preview.total_rows ?? 0),
      first_open_time: String(preview.first_open_time ?? ""),
      last_close_time: String(preview.last_close_time ?? ""),
      status: String(preview.status ?? "ready"),
      detail: String(preview.detail ?? ""),
    },
    training_window: {
      holding_window: String(trainingWindow.holding_window ?? ""),
      sample_window: sampleWindow,
    },
    symbols: symbols
      .map((value) => {
        const symbolRow = isPlainObject(value) ? value : {};
        return {
          symbol: String(symbolRow.symbol ?? ""),
          selected: Boolean(symbolRow.selected),
        };
      })
      .filter((value) => value.symbol.length > 0),
  };
}

function normalizeDataWorkspaceSnapshotConsistency(value: unknown): DataWorkspaceModel["snapshot_consistency"] {
  const row: Record<string, unknown> = isPlainObject(value) ? value : {};
  return {
    training_snapshot_id: String(row.training_snapshot_id ?? ""),
    training_generated_at: String(row.training_generated_at ?? ""),
    training_cache_status: String(row.training_cache_status ?? ""),
    training_cache_hit_count: Number(row.training_cache_hit_count ?? 0),
    training_cache_miss_count: Number(row.training_cache_miss_count ?? 0),
    inference_snapshot_id: String(row.inference_snapshot_id ?? ""),
    inference_generated_at: String(row.inference_generated_at ?? ""),
    inference_cache_status: String(row.inference_cache_status ?? ""),
    inference_cache_hit_count: Number(row.inference_cache_hit_count ?? 0),
    inference_cache_miss_count: Number(row.inference_cache_miss_count ?? 0),
    matches_training_snapshot: Boolean(row.matches_training_snapshot),
    note: String(row.note ?? "当前还没有可用快照一致性说明。"),
  };
}

function normalizeDataWorkspaceQuality(value: unknown): DataWorkspaceModel["quality"] {
  const row: Record<string, unknown> = isPlainObject(value) ? value : {};
  return {
    raw_rows: Number(row.raw_rows ?? 0),
    cleaned_rows: Number(row.cleaned_rows ?? 0),
    feature_ready_rows: Number(row.feature_ready_rows ?? 0),
    cleaned_drop_rows: Number(row.cleaned_drop_rows ?? 0),
    feature_drop_rows: Number(row.feature_drop_rows ?? 0),
    total_drop_rows: Number(row.total_drop_rows ?? 0),
    retention_ratio_pct: Number(row.retention_ratio_pct ?? 0),
    missing_rows: row.missing_rows === null || row.missing_rows === undefined ? null : Number(row.missing_rows ?? 0),
    invalid_rows: row.invalid_rows === null || row.invalid_rows === undefined ? null : Number(row.invalid_rows ?? 0),
    detail: String(row.detail ?? "当前还没有可用质量摘要。"),
    summary: String(row.summary ?? "当前还没有可用质量摘要。"),
  };
}

function normalizeFeatureWorkspaceModel(item: unknown): FeatureWorkspaceModel {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  const overview = isPlainObject(row.overview) ? row.overview : {};
  const controls = isPlainObject(row.controls) ? row.controls : {};
  const roles = isPlainObject(row.roles) ? row.roles : {};
  const preprocessing = isPlainObject(row.preprocessing) ? row.preprocessing : {};
  const categories = isPlainObject(row.categories) ? row.categories : {};
  const timeframeProfiles = isPlainObject(row.timeframe_profiles) ? row.timeframe_profiles : {};
  const factors = Array.isArray(row.factors) ? row.factors : [];
  const selectionMatrix = Array.isArray(row.selection_matrix) ? row.selection_matrix : [];

  return {
    status: String(row.status ?? "unavailable"),
    backend: String(row.backend ?? "qlib-fallback"),
    config_alignment: isPlainObject(row.config_alignment) ? row.config_alignment : {},
    overview: {
      feature_version: String(overview.feature_version ?? ""),
      factor_count: Number(overview.factor_count ?? 0),
      primary_count: Number(overview.primary_count ?? 0),
      auxiliary_count: Number(overview.auxiliary_count ?? 0),
      holding_window: String(overview.holding_window ?? ""),
    },
    categories: Object.fromEntries(
      Object.entries(categories).map(([name, values]) => [String(name), normalizeStringArray(values, [])]),
    ),
    roles: {
      primary: normalizeStringArray(roles.primary, []),
      auxiliary: normalizeStringArray(roles.auxiliary, []),
    },
    controls: {
      primary_factors: normalizeStringArray(controls.primary_factors, []),
      auxiliary_factors: normalizeStringArray(controls.auxiliary_factors, []),
      trend_weight: String(controls.trend_weight ?? "1.3"),
      momentum_weight: String(controls.momentum_weight ?? "1"),
      volume_weight: String(controls.volume_weight ?? "1.1"),
      oscillator_weight: String(controls.oscillator_weight ?? "0.7"),
      volatility_weight: String(controls.volatility_weight ?? "0.8"),
      strict_penalty_weight: String(controls.strict_penalty_weight ?? "0.6"),
      signal_confidence_floor: String(controls.signal_confidence_floor ?? "0.55"),
      missing_policy: String(controls.missing_policy ?? "neutral_fill"),
      outlier_policy: String(controls.outlier_policy ?? ""),
      normalization_policy: String(controls.normalization_policy ?? ""),
      timeframe_profiles: Object.fromEntries(
        Object.entries(isPlainObject(controls.timeframe_profiles) ? controls.timeframe_profiles : {}).map(([name, values]) => [
          String(name),
          isPlainObject(values) ? values : {},
        ]),
      ),
      available_primary_factors: normalizeStringArray(controls.available_primary_factors, []),
      available_auxiliary_factors: normalizeStringArray(controls.available_auxiliary_factors, []),
      available_missing_policies: normalizeStringArray(controls.available_missing_policies, ["neutral_fill", "strict_drop"]),
      available_outlier_policies: normalizeStringArray(controls.available_outlier_policies, []),
      available_normalization_policies: normalizeStringArray(controls.available_normalization_policies, []),
    },
    preprocessing: {
      missing_policy: String(preprocessing.missing_policy ?? ""),
      outlier_policy: String(preprocessing.outlier_policy ?? ""),
      normalization_policy: String(preprocessing.normalization_policy ?? ""),
    },
    timeframe_profiles: Object.fromEntries(
      Object.entries(timeframeProfiles).map(([name, values]) => [String(name), isPlainObject(values) ? values : {}]),
    ),
    factors: factors
      .map((value) => {
        const factor = isPlainObject(value) ? value : {};
        return {
          name: String(factor.name ?? ""),
          category: String(factor.category ?? ""),
          role: String(factor.role ?? ""),
          description: String(factor.description ?? ""),
        };
      })
      .filter((value) => value.name.length > 0),
    selection_matrix: selectionMatrix
      .map((value) => {
        const item = isPlainObject(value) ? value : {};
        return {
          name: String(item.name ?? ""),
          category: String(item.category ?? ""),
          protocol_role: String(item.protocol_role ?? ""),
          current_role: String(item.current_role ?? ""),
          description: String(item.description ?? ""),
        };
      })
      .filter((value) => value.name.length > 0),
  };
}

function normalizeResearchWorkspaceModel(item: unknown): ResearchWorkspaceModel {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  const overview = isPlainObject(row.overview) ? row.overview : {};
  const controls = isPlainObject(row.controls) ? row.controls : {};
  const labeling = isPlainObject(row.labeling) ? row.labeling : {};
  const model = isPlainObject(row.model) ? row.model : {};
  const selectors = isPlainObject(row.selectors) ? row.selectors : {};
  const sampleWindow = isPlainObject(row.sample_window) ? row.sample_window : {};
  const parameters = isPlainObject(row.parameters) ? row.parameters : {};
  const readiness = isPlainObject(row.readiness) ? row.readiness : {};
  const executionPreview = isPlainObject(row.execution_preview) ? row.execution_preview : {};
  const labelRuleSummary = isPlainObject(row.label_rule_summary) ? row.label_rule_summary : {};

  return {
    status: String(row.status ?? "unavailable"),
    backend: String(row.backend ?? "qlib-fallback"),
    config_alignment: isPlainObject(row.config_alignment) ? row.config_alignment : {},
    overview: {
      holding_window: String(overview.holding_window ?? ""),
      candidate_count: Number(overview.candidate_count ?? 0),
      recommended_symbol: String(overview.recommended_symbol ?? ""),
      recommended_action: String(overview.recommended_action ?? ""),
    },
    strategy_templates: normalizeStringArray(row.strategy_templates, []),
    labeling: {
      label_columns: normalizeStringArray(labeling.label_columns, []),
      label_mode: String(labeling.label_mode ?? ""),
      definition: String(labeling.definition ?? ""),
    },
    sample_window: Object.fromEntries(
      Object.entries(sampleWindow).map(([name, value]) => [String(name), isPlainObject(value) ? value : {}]),
    ),
    model: {
      model_version: String(model.model_version ?? ""),
      backend: String(model.backend ?? "qlib-fallback"),
    },
    controls: {
      research_template: String(controls.research_template ?? ""),
      model_key: String(controls.model_key ?? ""),
      label_mode: String(controls.label_mode ?? ""),
      label_trigger_basis: String(controls.label_trigger_basis ?? "close"),
      holding_window_label: String(controls.holding_window_label ?? ""),
      force_validation_top_candidate: Boolean(controls.force_validation_top_candidate),
      min_holding_days: Number(controls.min_holding_days ?? 1),
      max_holding_days: Number(controls.max_holding_days ?? 3),
      label_target_pct: String(controls.label_target_pct ?? ""),
      label_stop_pct: String(controls.label_stop_pct ?? ""),
      train_split_ratio: String(controls.train_split_ratio ?? "0.6"),
      validation_split_ratio: String(controls.validation_split_ratio ?? "0.2"),
      test_split_ratio: String(controls.test_split_ratio ?? "0.2"),
      signal_confidence_floor: String(controls.signal_confidence_floor ?? "0.55"),
      trend_weight: String(controls.trend_weight ?? "1.3"),
      momentum_weight: String(controls.momentum_weight ?? "1"),
      volume_weight: String(controls.volume_weight ?? "1.1"),
      oscillator_weight: String(controls.oscillator_weight ?? "0.7"),
      volatility_weight: String(controls.volatility_weight ?? "0.9"),
      strict_penalty_weight: String(controls.strict_penalty_weight ?? "1"),
      available_models: normalizeStringArray(controls.available_models, []),
      available_research_templates: normalizeStringArray(controls.available_research_templates, []),
      available_label_modes: normalizeStringArray(controls.available_label_modes, []),
      available_label_trigger_bases: normalizeStringArray(controls.available_label_trigger_bases, []),
      available_holding_windows: normalizeStringArray(controls.available_holding_windows, []),
    },
    parameters: Object.fromEntries(
      Object.entries(parameters).map(([name, value]) => [String(name), String(value ?? "")]),
    ),
    selectors: {
      symbols: normalizeStringArray(selectors.symbols, []),
      timeframes: normalizeStringArray(selectors.timeframes, []),
    },
    readiness: {
      train_ready: Boolean(readiness.train_ready),
      infer_ready: Boolean(readiness.infer_ready),
      blocking_reasons: normalizeStringArray(readiness.blocking_reasons, []),
      infer_reason: String(readiness.infer_reason ?? ""),
      next_step: String(readiness.next_step ?? ""),
    },
    execution_preview: {
      data_scope: String(executionPreview.data_scope ?? ""),
      factor_mix: String(executionPreview.factor_mix ?? ""),
      label_scope: String(executionPreview.label_scope ?? ""),
      dry_run_gate: String(executionPreview.dry_run_gate ?? ""),
      live_gate: String(executionPreview.live_gate ?? ""),
      validation_policy: String(executionPreview.validation_policy ?? ""),
    },
    label_rule_summary: {
      preset_key: String(labelRuleSummary.preset_key ?? "balanced_window"),
      headline: String(labelRuleSummary.headline ?? ""),
      detail: String(labelRuleSummary.detail ?? ""),
      next_step: String(labelRuleSummary.next_step ?? ""),
    },
  };
}

function normalizeBacktestWorkspaceModel(item: unknown): BacktestWorkspaceModel {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  const overview = isPlainObject(row.overview) ? row.overview : {};
  const controls = isPlainObject(row.controls) ? row.controls : {};
  const assumptions = isPlainObject(row.assumptions) ? row.assumptions : {};
  const trainingBacktest = isPlainObject(row.training_backtest) ? row.training_backtest : {};
  const metrics = isPlainObject(trainingBacktest.metrics) ? trainingBacktest.metrics : {};
  const leaderboard = Array.isArray(row.leaderboard) ? row.leaderboard : [];

  return {
    status: String(row.status ?? "unavailable"),
    backend: String(row.backend ?? "qlib-fallback"),
    overview: {
      holding_window: String(overview.holding_window ?? ""),
      candidate_count: Number(overview.candidate_count ?? 0),
      recommended_symbol: String(overview.recommended_symbol ?? ""),
    },
    assumptions: Object.fromEntries(
      Object.entries(assumptions).map(([name, value]) => [String(name), String(value ?? "")]),
    ),
    controls: {
      fee_bps: String(controls.fee_bps ?? ""),
      slippage_bps: String(controls.slippage_bps ?? ""),
      cost_model: String(controls.cost_model ?? "round_trip_basis_points"),
      available_cost_models: normalizeStringArray(controls.available_cost_models, []),
      enable_rule_gate: Boolean(controls.enable_rule_gate),
      enable_validation_gate: Boolean(controls.enable_validation_gate),
      enable_backtest_gate: Boolean(controls.enable_backtest_gate),
      enable_consistency_gate: Boolean(controls.enable_consistency_gate),
      enable_live_gate: Boolean(controls.enable_live_gate),
      dry_run_min_score: String(controls.dry_run_min_score ?? "0.55"),
      dry_run_min_positive_rate: String(controls.dry_run_min_positive_rate ?? "0.45"),
      dry_run_min_net_return_pct: String(controls.dry_run_min_net_return_pct ?? "0"),
      dry_run_min_sharpe: String(controls.dry_run_min_sharpe ?? "0.5"),
      dry_run_max_drawdown_pct: String(controls.dry_run_max_drawdown_pct ?? "15"),
      dry_run_max_loss_streak: String(controls.dry_run_max_loss_streak ?? "3"),
      dry_run_min_win_rate: String(controls.dry_run_min_win_rate ?? "0.5"),
      dry_run_max_turnover: String(controls.dry_run_max_turnover ?? "0.6"),
      dry_run_min_sample_count: String(controls.dry_run_min_sample_count ?? "20"),
      validation_min_sample_count: String(controls.validation_min_sample_count ?? "12"),
      validation_min_avg_future_return_pct: String(controls.validation_min_avg_future_return_pct ?? "-0.1"),
      consistency_max_validation_backtest_return_gap_pct: String(controls.consistency_max_validation_backtest_return_gap_pct ?? "1.5"),
      consistency_max_training_validation_positive_rate_gap: String(controls.consistency_max_training_validation_positive_rate_gap ?? "0.2"),
      consistency_max_training_validation_return_gap_pct: String(controls.consistency_max_training_validation_return_gap_pct ?? "1.5"),
      rule_min_ema20_gap_pct: String(controls.rule_min_ema20_gap_pct ?? "0"),
      rule_min_ema55_gap_pct: String(controls.rule_min_ema55_gap_pct ?? "0"),
      rule_max_atr_pct: String(controls.rule_max_atr_pct ?? "5"),
      rule_min_volume_ratio: String(controls.rule_min_volume_ratio ?? "1"),
      strict_rule_min_ema20_gap_pct: String(controls.strict_rule_min_ema20_gap_pct ?? "1.2"),
      strict_rule_min_ema55_gap_pct: String(controls.strict_rule_min_ema55_gap_pct ?? "1.8"),
      strict_rule_max_atr_pct: String(controls.strict_rule_max_atr_pct ?? "4.5"),
      strict_rule_min_volume_ratio: String(controls.strict_rule_min_volume_ratio ?? "1.05"),
      live_min_score: String(controls.live_min_score ?? "0.65"),
      live_min_positive_rate: String(controls.live_min_positive_rate ?? "0.50"),
      live_min_net_return_pct: String(controls.live_min_net_return_pct ?? "0.20"),
      live_min_win_rate: String(controls.live_min_win_rate ?? "0.55"),
      live_max_turnover: String(controls.live_max_turnover ?? "0.45"),
      live_min_sample_count: String(controls.live_min_sample_count ?? "24"),
    },
    training_backtest: {
      metrics: Object.fromEntries(
        Object.entries(metrics).map(([name, value]) => [String(name), String(value ?? "")]),
      ),
    },
    leaderboard: leaderboard
      .map((value) => {
        const item = isPlainObject(value) ? value : {};
        const backtest = isPlainObject(item.backtest) ? item.backtest : {};
        return {
          symbol: String(item.symbol ?? ""),
          strategy_template: String(item.strategy_template ?? ""),
          backtest: Object.fromEntries(
            Object.entries(backtest).map(([name, metric]) => [String(name), String(metric ?? "")]),
          ),
        };
      })
      .filter((item) => item.symbol.length > 0),
  };
}

function normalizeEvaluationWorkspaceModel(item: unknown): EvaluationWorkspaceModel {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  const overview = isPlainObject(row.overview) ? row.overview : {};
  const controls = isPlainObject(row.controls) ? row.controls : {};
  const operations = isPlainObject(row.operations) ? row.operations : {};

  return {
    status: String(row.status ?? "unavailable"),
    backend: String(row.backend ?? "qlib-fallback"),
    config_alignment: isPlainObject(row.config_alignment) ? row.config_alignment : {},
    overview: {
      recommended_symbol: String(overview.recommended_symbol ?? ""),
      recommended_action: String(overview.recommended_action ?? ""),
      candidate_count: Number(overview.candidate_count ?? 0),
    },
    controls: {
      dry_run_min_score: String(controls.dry_run_min_score ?? ""),
      dry_run_min_positive_rate: String(controls.dry_run_min_positive_rate ?? ""),
      dry_run_min_net_return_pct: String(controls.dry_run_min_net_return_pct ?? ""),
      dry_run_min_sharpe: String(controls.dry_run_min_sharpe ?? ""),
      dry_run_max_drawdown_pct: String(controls.dry_run_max_drawdown_pct ?? ""),
      dry_run_max_loss_streak: String(controls.dry_run_max_loss_streak ?? ""),
      dry_run_min_win_rate: String(controls.dry_run_min_win_rate ?? "0.5"),
      dry_run_max_turnover: String(controls.dry_run_max_turnover ?? "0.6"),
      dry_run_min_sample_count: String(controls.dry_run_min_sample_count ?? "20"),
      validation_min_sample_count: String(controls.validation_min_sample_count ?? "12"),
      validation_min_avg_future_return_pct: String(controls.validation_min_avg_future_return_pct ?? "-0.1"),
      consistency_max_validation_backtest_return_gap_pct: String(controls.consistency_max_validation_backtest_return_gap_pct ?? "1.5"),
      consistency_max_training_validation_positive_rate_gap: String(controls.consistency_max_training_validation_positive_rate_gap ?? "0.2"),
      consistency_max_training_validation_return_gap_pct: String(controls.consistency_max_training_validation_return_gap_pct ?? "1.5"),
      rule_min_ema20_gap_pct: String(controls.rule_min_ema20_gap_pct ?? "0"),
      rule_min_ema55_gap_pct: String(controls.rule_min_ema55_gap_pct ?? "0"),
      rule_max_atr_pct: String(controls.rule_max_atr_pct ?? "5"),
      rule_min_volume_ratio: String(controls.rule_min_volume_ratio ?? "1"),
      strict_rule_min_ema20_gap_pct: String(controls.strict_rule_min_ema20_gap_pct ?? "1.2"),
      strict_rule_min_ema55_gap_pct: String(controls.strict_rule_min_ema55_gap_pct ?? "1.8"),
      strict_rule_max_atr_pct: String(controls.strict_rule_max_atr_pct ?? "4.5"),
      strict_rule_min_volume_ratio: String(controls.strict_rule_min_volume_ratio ?? "1.05"),
      enable_rule_gate: Boolean(controls.enable_rule_gate),
      enable_validation_gate: Boolean(controls.enable_validation_gate),
      enable_backtest_gate: Boolean(controls.enable_backtest_gate),
      enable_consistency_gate: Boolean(controls.enable_consistency_gate),
      enable_live_gate: Boolean(controls.enable_live_gate),
      live_min_score: String(controls.live_min_score ?? ""),
      live_min_positive_rate: String(controls.live_min_positive_rate ?? ""),
      live_min_net_return_pct: String(controls.live_min_net_return_pct ?? ""),
      live_min_win_rate: String(controls.live_min_win_rate ?? "0.55"),
      live_max_turnover: String(controls.live_max_turnover ?? "0.45"),
      live_min_sample_count: String(controls.live_min_sample_count ?? "24"),
    },
    operations: {
      review_limit: String(operations.review_limit ?? "10"),
      comparison_run_limit: String(operations.comparison_run_limit ?? "5"),
      cycle_cooldown_minutes: String(operations.cycle_cooldown_minutes ?? "15"),
      max_daily_cycle_count: String(operations.max_daily_cycle_count ?? "8"),
    },
    evaluation: isPlainObject(row.evaluation) ? row.evaluation : {},
    reviews: isPlainObject(row.reviews) ? row.reviews : {},
    recent_review_tasks: Array.isArray(row.recent_review_tasks) ? row.recent_review_tasks.filter(isPlainObject) : [],
    leaderboard: Array.isArray(row.leaderboard) ? row.leaderboard.filter(isPlainObject) : [],
    best_experiment: isPlainObject(row.best_experiment) ? row.best_experiment : {},
    best_stage_candidates: isPlainObject(row.best_stage_candidates) ? row.best_stage_candidates : {},
    recommendation_explanation: isPlainObject(row.recommendation_explanation) ? row.recommendation_explanation : {},
    elimination_explanation: isPlainObject(row.elimination_explanation) ? row.elimination_explanation : {},
    recent_runs: Array.isArray(row.recent_runs) ? row.recent_runs.filter(isPlainObject) : [],
    recent_training_runs: Array.isArray(row.recent_training_runs) ? row.recent_training_runs.filter(isPlainObject) : [],
    recent_inference_runs: Array.isArray(row.recent_inference_runs) ? row.recent_inference_runs.filter(isPlainObject) : [],
    experiment_comparison: Array.isArray(row.experiment_comparison) ? row.experiment_comparison.filter(isPlainObject) : [],
    gate_matrix: Array.isArray(row.gate_matrix) ? row.gate_matrix.filter(isPlainObject) : [],
    workflow_alignment_timeline: Array.isArray(row.workflow_alignment_timeline) ? row.workflow_alignment_timeline.filter(isPlainObject) : [],
    run_deltas: Array.isArray(row.run_deltas) ? row.run_deltas.filter(isPlainObject) : [],
    delta_overview: isPlainObject(row.delta_overview) ? row.delta_overview : {},
    comparison_summary: isPlainObject(row.comparison_summary) ? row.comparison_summary : {},
    execution_alignment: isPlainObject(row.execution_alignment) ? row.execution_alignment : {},
    stage_decision_summary: isPlainObject(row.stage_decision_summary) ? row.stage_decision_summary : {},
    alignment_details: isPlainObject(row.alignment_details) ? row.alignment_details : {},
    alignment_story: isPlainObject(row.alignment_story) ? row.alignment_story : {},
    alignment_metric_rows: Array.isArray(row.alignment_metric_rows) ? row.alignment_metric_rows.filter(isPlainObject) : [],
    alignment_gaps: Array.isArray(row.alignment_gaps) ? row.alignment_gaps.filter(isPlainObject) : [],
    alignment_actions: Array.isArray(row.alignment_actions) ? row.alignment_actions.filter(isPlainObject) : [],
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
  const liveGateRow: Record<string, unknown> = isPlainObject(row.live_gate) ? row.live_gate : {};
  return {
    symbol,
    score: String(row.score ?? ""),
    allowed_to_dry_run: Boolean(row.allowed_to_dry_run),
    allowed_to_live: Boolean(row.allowed_to_live),
    strategy_template: String(row.strategy_template ?? ""),
    dry_run_gate: {
      status: String(gateRow.status ?? "unavailable"),
      reasons: normalizeStringArray(gateRow.reasons, []),
    },
    live_gate: {
      status: String(liveGateRow.status ?? "unavailable"),
      reasons: normalizeStringArray(liveGateRow.reasons, []),
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
  const liveGateRow: Record<string, unknown> = isPlainObject(row.live_gate) ? row.live_gate : {};
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
    live_gate: {
      status: String(liveGateRow.status ?? "unavailable"),
      reasons: normalizeStringArray(liveGateRow.reasons, []),
    },
    allowed_to_live: Boolean(row.allowed_to_live),
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

function normalizeResearchRuntimeStatus(item: unknown): ResearchRuntimeStatusModel {
  const row: Record<string, unknown> = isPlainObject(item) ? item : {};
  const estimatedRow: Record<string, unknown> = isPlainObject(row.estimated_seconds) ? row.estimated_seconds : {};
  return {
    status: String(row.status ?? "idle"),
    action: String(row.action ?? ""),
    current_stage: String(row.current_stage ?? "idle"),
    progress_pct: Number(row.progress_pct ?? 0),
    started_at: String(row.started_at ?? ""),
    finished_at: String(row.finished_at ?? ""),
    message: String(row.message ?? "当前没有研究任务在运行。"),
    last_completed_action: String(row.last_completed_action ?? ""),
    last_finished_at: String(row.last_finished_at ?? ""),
    result_paths: normalizeStringArray(row.result_paths, ["/research", "/evaluation", "/signals"]),
    history: isPlainObject(row.history) ? row.history : {},
    estimated_seconds: {
      training: Number(estimatedRow.training ?? 25),
      inference: Number(estimatedRow.inference ?? 12),
      pipeline: Number(estimatedRow.pipeline ?? 40),
    },
    current_estimate_seconds: Number(row.current_estimate_seconds ?? 0),
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
    configuration: {},
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

export function getResearchRuntimeStatusFallback(): ResearchRuntimeStatusModel {
  return normalizeResearchRuntimeStatus({
    status: "idle",
    action: "",
    current_stage: "idle",
    progress_pct: 0,
    started_at: "",
    finished_at: "",
    message: "当前没有研究任务在运行。",
    last_completed_action: "",
    last_finished_at: "",
    result_paths: ["/research", "/evaluation", "/signals"],
    history: {},
    estimated_seconds: {
      training: 25,
      inference: 12,
      pipeline: 40,
    },
    current_estimate_seconds: 0,
  });
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
      pausedAt: "",
      manualTakeoverAt: "",
      lastFailureAt: "",
      armedSymbol: "",
      runtimeMode: "demo",
      allowLiveExecution: false,
      alerts: [],
      lastCycle: {},
      reviewOverview: {},
      researchOverview: {},
      health: {
        active_blockers: [],
        operator_actions: [],
        takeover_summary: {},
        alert_summary: { groups: [] },
      },
      executionHealth: {},
      dailySummary: {},
      runtimeWindow: {},
      schedulerPlan: [],
      failurePolicy: {},
      severitySummary: {},
      resumeChecklist: [],
      automationConfig: {
        long_run_seconds: "300",
        alert_cleanup_minutes: "15",
      },
      executionPolicy: {
        live_allowed_symbols: [],
        live_max_stake_usdt: "6",
        live_max_open_trades: "1",
      },
      operations: {
        pause_after_consecutive_failures: "2",
        stale_sync_failure_threshold: "1",
        auto_pause_on_error: true,
        review_limit: "10",
        comparison_run_limit: "5",
        cycle_cooldown_minutes: "15",
        max_daily_cycle_count: "8",
      },
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
