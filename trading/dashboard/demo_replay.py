"""Build the DEMO REPLAY event log from synthetic fixtures and the real engine.

Each configured instance runs through trading.backtest.run_backtest on made-up
bars. Every resulting bar, signal, decision, simulated fill, closed position,
risk block and data gap becomes an Event. Nothing here is a backtest of real
data or a broker result.
"""

import json
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from trading.backtest import BacktestResult, DayData, run_backtest
from trading.costs import BASE
from trading.events import MODE_DEMO_REPLAY, Event
from trading.fixtures.synthetic import make_days
from trading.outcomes import classify_trade
from trading.risk import RiskLimits
from trading.sessions import Session, sessions_between
from trading.strategies.intraday_momentum import MINUTE, Params, signal
from trading.strategies.registry import spec_info

SOURCE = "demo_replay"
FEED = "synthetic"
STALE_AFTER = pd.Timedelta(minutes=2)
DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "dashboard" / "demo_config.json"


class ConfigError(ValueError):
    pass


@dataclass
class DemoReplay:
    meta: dict
    events: list[Event]
    backtests: dict[str, BacktestResult]


def _iso(ts) -> str:
    return pd.Timestamp(ts).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    instruments = {i["id"] for i in config.get("instruments", [])}
    ids = [i["id"] for i in config.get("instances", [])]
    if len(ids) != len(set(ids)):
        raise ConfigError("instance ids must be unique")
    for inst in config.get("instances", []):
        if inst["instrument"] not in instruments:
            raise ConfigError(f"instance {inst['id']} uses unknown instrument {inst['instrument']}")
        unknown = set(inst.get("params", {})) - set(Params().as_dict())
        if unknown:
            raise ConfigError(f"instance {inst['id']} has unknown params {sorted(unknown)}")
    if config["replay"]["sessions"] < 1:
        raise ConfigError("replay.sessions must be at least 1")
    return config


def _sessions(replay_cfg: dict) -> tuple[list[Session], list[Session]]:
    first = date.fromisoformat(replay_cfg["first_session"])
    pool = sessions_between(first - timedelta(days=120), first + timedelta(days=60))
    idx = next(k for k, s in enumerate(pool) if s.date >= first)
    n, warm = replay_cfg["sessions"], replay_cfg["warmup_sessions"]
    if idx < warm or idx + n >= len(pool):
        raise ConfigError("not enough calendar sessions around first_session")
    return pool[idx - warm: idx + n + 1], pool[idx: idx + n]


def _apply_outage(days: dict, replay: list[Session], outage: dict) -> None:
    session = replay[outage["session"]]
    day = days[session.date]
    start = pd.Timestamp(session.open_utc) + outage["start_minute"] * MINUTE
    end = start + outage["minutes"] * MINUTE
    keep = (day.bars.index < start) | (day.bars.index >= end)
    days[session.date] = DayData(session, day.bars[keep].reset_index(drop=True),
                                 day.official_close)


def _instrument_events(inst: dict, days: dict, replay: list[Session], ctx: "Context") -> list[Event]:
    ev = []
    for s in replay:
        day = days.get(s.date)
        if day is None:
            ev.append(Event(_iso(s.open_utc), ctx.source, ctx.mode, "feed_status", None, inst["id"],
                            {"status": "stale", "feed": ctx.feed, "reason": "no usable data for this session"}))
            continue
        ev.append(Event(_iso(s.open_utc), ctx.source, ctx.mode, "feed_status", None, inst["id"],
                        {"status": "live", "feed": ctx.feed, "session_date": str(s.date)}))
        prev_end = None
        for t, bar in day.bars.iterrows():
            end = t + MINUTE
            if prev_end is not None and t - prev_end >= MINUTE:
                gap = int((t - prev_end) / MINUTE)
                if prev_end + STALE_AFTER < end:
                    ev.append(Event(_iso(prev_end + STALE_AFTER), ctx.source, ctx.mode,
                                    "feed_status", None, inst["id"],
                                    {"status": "stale", "feed": ctx.feed, "last_bar_end_utc": _iso(prev_end)}))
                ev.append(Event(_iso(end), ctx.source, ctx.mode, "feed_status", None, inst["id"],
                                {"status": "live", "feed": ctx.feed, "recovered_after_missing_minutes": gap}))
            ev.append(Event(_iso(end), ctx.source, ctx.mode, "bar", None, inst["id"], {
                "t": _iso(t), "o": round(float(bar["open"]), 4), "h": round(float(bar["high"]), 4),
                "l": round(float(bar["low"]), 4), "c": round(float(bar["close"]), 4),
                "v": int(bar["volume"]), "feed": ctx.feed, "interval": "1Min"}))
            prev_end = end
    return ev


def _strategy_events(inst: dict, params: Params, days: dict, engine_sessions: list[Session],
                     result: BacktestResult, ctx: "Context") -> list[Event]:
    sid, ins = inst["id"], inst["instrument"]

    def mk(ts, typ, payload):
        return Event(_iso(ts), ctx.source, ctx.mode, typ, sid, ins, payload)

    ev = [mk(result.days[0].session.open_utc, "risk_status",
             {"status": "ok", "reason": "no limit reached"})] if result.days else []
    index = {s.date: k for k, s in enumerate(engine_sessions)}
    for d in result.days:
        s = d.session
        open_t, close_t = pd.Timestamp(s.open_utc), pd.Timestamp(s.close_utc)
        signal_t = open_t + params.signal_minutes * MINUTE
        decision_t = close_t - params.entry_offset_min * MINUTE
        day = days.get(s.date)
        prev = days.get(engine_sessions[index[s.date] - 1].date)
        if day is not None:
            known = day.bars[day.bars.index + MINUTE <= signal_t]
            direction, r1, reason = signal(params, prev.official_close if prev else None, known, open_t)
            ev.append(mk(signal_t, "signal", {
                "direction": direction, "r1": r1, "skip_reason": reason,
                "measured_from": params.signal_from}))
        t = d.trade
        if t is None:
            if d.skip_reason.startswith("risk:"):
                status = "halted" if "kill switch" in d.skip_reason else "blocked"
                ev.append(mk(decision_t, "risk_status", {"status": status, "reason": d.skip_reason}))
            ev.append(mk(decision_t, "decision", {"action": "skip", "reason": d.skip_reason}))
            continue
        ev.append(mk(decision_t, "decision", {
            "action": "enter", "direction": t.direction, "shares": t.shares,
            "binding_cap": t.binding_cap, "sigma30": t.sigma30, "risk_check": "passed"}))
        ev.append(mk(t.entry_time, "fill", {
            "leg": "entry", "side": "buy" if t.direction > 0 else "sell short",
            "shares": t.shares, "reference_price": t.entry_price, "fill_price": t.entry_fill,
            "stop_price": t.stop_price, "simulated": True}))
        ev.append(mk(t.exit_time, "fill", {
            "leg": "exit", "side": "sell" if t.direction > 0 else "buy to cover",
            "shares": t.shares, "reference_price": t.exit_price, "fill_price": t.exit_fill,
            "reason": t.exit_reason, "simulated": True}))
        ev.append(mk(t.exit_time, "position_closed", {
            "direction": t.direction, "shares": t.shares, "entry_time_utc": _iso(t.entry_time),
            "entry_fill": t.entry_fill, "exit_fill": t.exit_fill, "gross_pnl": t.gross_pnl,
            "net_pnl": t.net_pnl, "exit_reason": t.exit_reason, "flags": t.flags,
            "stop_price": t.stop_price, "target_price": None,
            "outcome": classify_trade(day.bars, t.entry_time, t.exit_time, t.direction,
                                      t.stop_price, None),
            "holding_minutes": t.minutes_held, "session_date": str(s.date),
            "cost_model": BASE.name, "simulated": True}))
    return ev


@dataclass(frozen=True)
class Context:
    source: str
    mode: str
    feed: str
    banner: str


DEMO_CONTEXT = Context(SOURCE, MODE_DEMO_REPLAY, FEED,
                       "DEMO REPLAY: synthetic data, simulated outcomes. Not market data, "
                       "not a backtest of real prices, not broker results.")


def build_replay(ctx: Context, instruments: list[dict], instrument_days: dict, instances: list[dict],
                 engine_sessions: list[Session], replay: list[Session], extra_meta: dict | None = None) -> DemoReplay:
    """Run every instance through the engine and turn the results into one event log.
    Shared by DEMO (synthetic days) and HISTORICAL REPLAY (stored Alpaca days)."""
    used = {i["instrument"] for i in instances}
    events = []
    for inst in instruments:
        if inst["id"] in used:
            events += _instrument_events(inst, instrument_days[inst["id"]], replay, ctx)
    for s in replay:
        events.append(Event(_iso(s.open_utc), ctx.source, ctx.mode, "session_open", None, None,
                            {"session_date": str(s.date), "open_utc": _iso(s.open_utc),
                             "close_utc": _iso(s.close_utc), "early_close": s.early_close}))
        events.append(Event(_iso(s.close_utc), ctx.source, ctx.mode, "session_close", None, None,
                            {"session_date": str(s.date)}))

    backtests, instances_meta = {}, []
    for inst in instances:
        params = replace(Params(), **inst.get("params", {}))
        limits = replace(RiskLimits(), **inst.get("risk", {}))
        days = instrument_days[inst["instrument"]]
        result = run_backtest(days, engine_sessions, replay[0].date, replay[-1].date, params,
                              BASE, limits, float(inst["allocation"]))
        backtests[inst["id"]] = result
        events += _strategy_events(inst, params, days, engine_sessions, result, ctx)
        instances_meta.append({"id": inst["id"], "name": inst["name"], "instrument": inst["instrument"],
                               "allocation": float(inst["allocation"]), "params": params.as_dict(),
                               "risk_limits": limits.__dict__,
                               "spec": spec_info(inst.get("strategy", "intraday_momentum"), params)})

    events.sort(key=Event.sort_key)
    meta = {
        "mode": ctx.mode,
        "source": ctx.source,
        "banner": ctx.banner,
        "feed": ctx.feed,
        "cost_model": BASE.name,
        "instruments": [{"id": i["id"], "label": i["label"], "feed": ctx.feed}
                        for i in instruments if i["id"] in used],
        "instances": instances_meta,
        "sessions": [{"date": str(s.date), "open_utc": _iso(s.open_utc), "close_utc": _iso(s.close_utc),
                      "early_close": s.early_close} for s in replay],
        "event_count": len(events),
        "order_submission": "disabled",
        **(extra_meta or {}),
    }
    return DemoReplay(meta, events, backtests)


def build_demo(config: dict) -> DemoReplay:
    engine_sessions, replay = _sessions(config["replay"])
    instrument_days = {}
    for inst in config["instruments"]:
        days = make_days(engine_sessions, seed=inst["seed"], start_price=inst["start_price"],
                         volume=inst.get("volume", 10_000), noise=inst.get("noise", 0.0))
        if inst.get("outage"):
            _apply_outage(days, replay, inst["outage"])
        instrument_days[inst["id"]] = days
    return build_replay(DEMO_CONTEXT, config["instruments"], instrument_days, config["instances"],
                        engine_sessions, replay)
