// Shapes produced by trading/events.py and trading/dashboard/ledger.py.
// The interface only displays these; it never computes P&L or risk itself.

export type EventType =
  | "session_open" | "feed_status" | "bar" | "signal" | "risk_status"
  | "decision" | "fill" | "position_closed" | "session_close";

export interface TradingEvent {
  schema: number;
  event_id: string;
  ts_utc: string;
  source: string;
  mode: string;
  type: EventType;
  strategy_id: string | null;
  instrument: string | null;
  payload: Record<string, unknown>;
}

export interface SpecInfo {
  strategy: string;
  title: string;
  spec_path: string;
  spec_version: string;
  spec_sha256: string;
  variant_id: string;
  params: Record<string, unknown>;
  target_defined: boolean;
}

export interface Instance {
  id: string;
  name: string;
  instrument: string;
  allocation: number;
  params: Record<string, unknown>;
  risk_limits: Record<string, number | boolean>;
  spec: SpecInfo;
}

export interface Research {
  modes: Record<string, { available: boolean; reason: string }>;
  historical_periods: { period: string; start: string; end: string; expected_sessions: number; sessions_with_verified_data: number }[];
  historical_data: null | {
    source: string; symbol: string; requested_feed: string; actual_feed: string; adjustment: string;
    interval: string; calendar: string; start: string; end: string; retrieved_utc: string;
    transformations: string[]; limitations: string[];
    requests: { minute_requested: string[]; minute_received: string[] | null; minute_pages: number; pagination_complete: boolean };
    summary: { expected_sessions: number; usable_sessions: number };
  };
  experiment_lock: {
    present: boolean; status: string; experiment_id?: string; created_utc?: string; hypothesis?: string;
    risk_limits_are_placeholders?: boolean;
    data_status_at_lock?: { sessions_stored_by_period: Record<string, number>; inspection_replays_touching_period: Record<string, number> };
  };
  responsibilities: { id: string; name: string; implementation: string; module: string | null; status: string; notes: string; veto?: boolean }[];
  skills_note: string;
  scanner_news: { available: boolean; reason: string };
  product_spec: string;
  order_submission?: { enabled: boolean; trading_mode: string; note: string };
}

export interface Evaluation {
  mode: string;
  strategy_id: string;
  as_of_utc: string | null;
  sample: { trades: number; unique_sessions_traded: number; sessions_evaluated: number; expected_sessions: number; coverage: number; skips: Record<string, number> };
  pnl: { net: number; gross: number; modeled_costs: number; net_return_on_allocation: number; cost_sensitivity: Record<string, number> };
  risk: { max_drawdown: number; time_in_market: number; avg_notional_to_allocation: number };
  outcomes: { target_first: number | null; stop_first: number; neither: number; ambiguous: number | null; unfillable: number; target_defined: boolean };
  trades: { wins: number; losses: number; avg_gain: number | null; avg_loss: number | null; avg_holding_minutes: number | null };
  limitations: string[];
  result_hash: string;
}

export interface Meta {
  mode: string;
  source: string;
  banner: string;
  feed: string;
  cost_model: string;
  instruments: { id: string; label: string; feed: string }[];
  instances: Instance[];
  sessions: { date: string; open_utc: string; close_utc: string; early_close: boolean }[];
  event_count: number;
  order_submission: string;
}

export interface Position {
  direction: number;
  shares: number;
  entry_fill: number;
  entry_utc: string;
  stop_price: number | null;
  mark_price: number;
  mark_utc: string;
}

export interface StrategyView {
  id: string;
  name: string;
  instrument: string;
  instrument_label: string;
  status: string;
  status_detail: string;
  feed_status: string | null;
  position: Position | null;
  allocation: number;
  realized_pnl: number;
  unrealized_pnl: number;
  net_pnl: number;
  equity: number;
  trades: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  profit_factor: number | null;
  max_drawdown: number;
  risk_status: string;
  risk_reason: string;
  version: number;
}

export interface Account {
  start_equity: number;
  equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  gross_exposure: number;
  exposure_pct: number;
  open_positions: number;
  risk_status: string;
  risk_notes: string[];
}

export interface InstrumentView {
  id: string;
  label: string;
  feed: string;
  feed_status: string;
  last_bar_end_utc: string | null;
  last_price: number | null;
  stale_since_utc: string | null;
}

export interface SessionRow {
  date: string;
  early_close: boolean;
  status: string;
  per_strategy: Record<string, { realized_pnl: number; trades: number; skips: number; skip_reasons: string[] }>;
  end_equity: number | null;
}

export interface Snapshot {
  mode: string;
  source: string;
  as_of_utc: string | null;
  current_session: string | null;
  applied: number;
  duplicates_ignored: number;
  rejected: number;
  account: Account;
  strategies: StrategyView[];
  leaderboard: { rank: number; id: string }[];
  instruments: InstrumentView[];
  sessions: SessionRow[];
}

export interface ReplayStatus {
  mode: string;
  playing: boolean;
  speed: number;
  replay_clock_utc: string | null;
  cursor: number;
  total: number;
  finished: boolean;
  generation: number;
}

export interface Bar { t: string; o: number; h: number; l: number; c: number; v: number }

export interface StrategyRecords {
  strategy: StrategyView;
  session: string | null;
  bars: Bar[];
  signals: Array<Record<string, unknown> & { ts_utc: string; event_id: string }>;
  decisions: Array<Record<string, unknown> & { ts_utc: string; event_id: string }>;
  fills: Array<Record<string, unknown> & { ts_utc: string; event_id: string }>;
  trades: Array<Record<string, unknown> & { ts_utc: string; event_id: string }>;
  risk: Array<Record<string, unknown> & { ts_utc: string; event_id: string }>;
}

export type Connection = "connecting" | "connected" | "reconnecting" | "disconnected";
