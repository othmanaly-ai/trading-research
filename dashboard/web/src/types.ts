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

export interface Meta {
  mode: string;
  source: string;
  banner: string;
  feed: string;
  cost_model: string;
  instruments: { id: string; label: string; feed: string }[];
  instances: { id: string; name: string; instrument: string; allocation: number }[];
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
