"""Idempotent projection of the event stream into account and strategy state.

The dashboard displays these numbers and never computes P&L itself. Applying
the same event twice (same event_id) changes nothing, so a resent or duplicated
event cannot double-count results.

Realized P&L comes only from position_closed events (net of simulated costs).
Unrealized P&L is a mark at the latest bar close against the entry fill,
before exit costs.
"""

from collections import defaultdict
from datetime import datetime

from trading.evaluation import evaluate

RECENT_EVENTS = 200


def _ts(iso: str) -> float:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


class Ledger:
    def __init__(self, meta: dict):
        self.meta = meta
        self.mode = meta["mode"]
        self.seen: set[str] = set()
        self.applied = 0
        self.duplicates_ignored = 0
        self.rejected = 0
        self.as_of = None
        self.current_session = None
        self.instruments = {i["id"]: {"id": i["id"], "label": i["label"], "feed": i["feed"],
                                      "feed_status": "no data yet", "last_bar_end_utc": None,
                                      "last_price": None, "stale_since_utc": None}
                            for i in meta["instruments"]}
        self.bars = defaultdict(list)                     # (instrument, session) -> bars
        self.strategies = {}
        for inst in meta["instances"]:
            self.strategies[inst["id"]] = {
                "id": inst["id"], "name": inst["name"], "instrument": inst["instrument"],
                "allocation": inst["allocation"], "status": "NOT STARTED",
                "status_detail": "", "position": None, "realized_pnl": 0.0,
                "unrealized_pnl": 0.0, "trades": 0, "wins": 0, "losses": 0,
                "gross_wins": 0.0, "gross_losses": 0.0, "peak_equity": inst["allocation"],
                "max_drawdown": 0.0, "risk_status": "unknown", "risk_reason": "",
                "halted": False, "last_signal": None, "last_decision": None, "version": 0,
            }
        self.records = {sid: {"signals": [], "decisions": [], "fills": [], "trades": [],
                              "risk": []} for sid in self.strategies}
        self.sessions = {}
        self.recent = []

    # -- ingestion -----------------------------------------------------------

    def apply(self, ev: dict) -> bool:
        """Apply one event dict. Returns False if it was a duplicate or rejected."""
        if ev["event_id"] in self.seen:
            self.duplicates_ignored += 1
            return False
        if ev.get("mode") != self.mode or (ev.get("strategy_id") and
                                           ev["strategy_id"] not in self.strategies):
            self.rejected += 1
            return False
        self.seen.add(ev["event_id"])
        self.applied += 1
        self.as_of = ev["ts_utc"]
        getattr(self, "_on_" + ev["type"])(ev)
        if ev["type"] != "bar":
            self.recent.append(ev)
            del self.recent[:-RECENT_EVENTS]
        return True

    def _touch(self, s: dict) -> None:
        s["version"] += 1
        equity = s["allocation"] + s["realized_pnl"] + s["unrealized_pnl"]
        s["peak_equity"] = max(s["peak_equity"], equity)
        s["max_drawdown"] = max(s["max_drawdown"], (s["peak_equity"] - equity) / s["peak_equity"])

    def _set_status(self, s: dict, status: str, detail: str = "") -> None:
        if s["halted"]:
            return
        s["status"], s["status_detail"] = status, detail

    def _on_session_open(self, ev):
        p = ev["payload"]
        self.current_session = p["session_date"]
        self.sessions[p["session_date"]] = {
            "date": p["session_date"], "early_close": p["early_close"], "status": "open",
            "open_utc": p["open_utc"], "close_utc": p["close_utc"],
            "per_strategy": {sid: {"realized_pnl": 0.0, "trades": 0, "skips": 0, "skip_reasons": []}
                             for sid in self.strategies},
            "end_equity": None,
        }
        for s in self.strategies.values():
            self._set_status(s, "WAITING", "session open; signal at open + 30 min")
            s["version"] += 1

    def _on_session_close(self, ev):
        row = self.sessions.get(ev["payload"]["session_date"])
        if row:
            row["status"] = "closed"
            row["end_equity"] = self.account()["equity"]
        for s in self.strategies.values():
            if s["position"] is None:
                self._set_status(s, "MARKET CLOSED", "flat overnight")
            s["version"] += 1

    def _on_feed_status(self, ev):
        inst = self.instruments.get(ev["instrument"])
        if inst is None:
            return
        status = ev["payload"]["status"]
        inst["feed_status"] = status
        inst["stale_since_utc"] = ev["ts_utc"] if status == "stale" else None

    def _on_bar(self, ev):
        inst = self.instruments.get(ev["instrument"])
        if inst is None:
            return
        p = ev["payload"]
        inst["last_bar_end_utc"], inst["last_price"] = ev["ts_utc"], p["c"]
        self.bars[(ev["instrument"], self.current_session)].append(p)
        for s in self.strategies.values():
            pos = s["position"]
            if pos and s["instrument"] == ev["instrument"]:
                s["unrealized_pnl"] = pos["direction"] * pos["shares"] * (p["c"] - pos["entry_fill"])
                pos["mark_price"], pos["mark_utc"] = p["c"], ev["ts_utc"]
                self._touch(s)

    def _on_signal(self, ev):
        s, p = self.strategies[ev["strategy_id"]], ev["payload"]
        s["last_signal"] = {"ts_utc": ev["ts_utc"], **p}
        self.records[s["id"]]["signals"].append({"ts_utc": ev["ts_utc"], "event_id": ev["event_id"], **p})
        label = {1: "SIGNAL LONG", -1: "SIGNAL SHORT"}.get(p["direction"], "NO SIGNAL")
        detail = f"r1 = {p['r1']:+.3%}" if p["r1"] is not None else (p["skip_reason"] or "")
        self._set_status(s, label, detail)
        s["version"] += 1

    def _on_risk_status(self, ev):
        s, p = self.strategies[ev["strategy_id"]], ev["payload"]
        s["risk_status"], s["risk_reason"] = p["status"], p["reason"]
        self.records[s["id"]]["risk"].append({"ts_utc": ev["ts_utc"], "event_id": ev["event_id"], **p})
        if p["status"] == "halted":
            s["status"], s["status_detail"], s["halted"] = "HALTED (RISK)", p["reason"], True
        s["version"] += 1

    def _on_decision(self, ev):
        s, p = self.strategies[ev["strategy_id"]], ev["payload"]
        s["last_decision"] = {"ts_utc": ev["ts_utc"], **p}
        self.records[s["id"]]["decisions"].append({"ts_utc": ev["ts_utc"], "event_id": ev["event_id"], **p})
        if p["action"] == "skip":
            row = self._session_row(s["id"])
            if row:
                row["skips"] += 1
                row["skip_reasons"].append(p["reason"])
            self._set_status(s, "SKIPPED", p["reason"])
        else:
            self._set_status(s, "ENTERING", f"{p['shares']} shares, simulated")
        s["version"] += 1

    def _on_fill(self, ev):
        s, p = self.strategies[ev["strategy_id"]], ev["payload"]
        self.records[s["id"]]["fills"].append({"ts_utc": ev["ts_utc"], "event_id": ev["event_id"], **p})
        if p["leg"] == "entry":
            direction = 1 if p["side"] == "buy" else -1
            s["position"] = {"direction": direction, "shares": p["shares"],
                             "entry_fill": p["fill_price"], "entry_utc": ev["ts_utc"],
                             "stop_price": p.get("stop_price"), "mark_price": p["reference_price"],
                             "mark_utc": ev["ts_utc"]}
            s["unrealized_pnl"] = direction * p["shares"] * (p["reference_price"] - p["fill_price"])
            self._set_status(s, "IN POSITION " + ("LONG" if direction > 0 else "SHORT"),
                             f"{p['shares']} shares @ {p['fill_price']:.2f} (simulated)")
            self._touch(s)

    def _on_position_closed(self, ev):
        s, p = self.strategies[ev["strategy_id"]], ev["payload"]
        net = p["net_pnl"]
        s["realized_pnl"] += net
        s["unrealized_pnl"] = 0.0
        s["position"] = None
        s["trades"] += 1
        if net > 0:
            s["wins"] += 1
            s["gross_wins"] += net
        else:
            s["losses"] += 1
            s["gross_losses"] += -net
        self.records[s["id"]]["trades"].append({"ts_utc": ev["ts_utc"], "event_id": ev["event_id"], **p})
        row = self._session_row(s["id"])
        if row:
            row["realized_pnl"] += net
            row["trades"] += 1
        self._set_status(s, "FLAT", f"closed: {p['exit_reason']}")
        self._touch(s)

    def _session_row(self, sid):
        row = self.sessions.get(self.current_session)
        return row["per_strategy"][sid] if row else None

    # -- views ---------------------------------------------------------------

    def account(self) -> dict:
        ss = list(self.strategies.values())
        start = sum(s["allocation"] for s in ss)
        realized = sum(s["realized_pnl"] for s in ss)
        unrealized = sum(s["unrealized_pnl"] for s in ss)
        equity = start + realized + unrealized
        gross = sum(s["position"]["shares"] * s["position"]["mark_price"] for s in ss if s["position"])
        notes = [f"{s['id']}: {s['risk_status']} ({s['risk_reason']})"
                 for s in ss if s["risk_status"] in ("blocked", "halted")]
        return {
            "start_equity": start, "equity": equity, "realized_pnl": realized,
            "unrealized_pnl": unrealized, "gross_exposure": gross,
            "exposure_pct": gross / equity if equity else 0.0,
            "open_positions": sum(1 for s in ss if s["position"]),
            "risk_status": "ATTENTION" if notes else ("OK" if ss else "NO STRATEGIES"),
            "risk_notes": notes,
        }

    def _strategy_view(self, s: dict) -> dict:
        trades = s["trades"]
        inst = self.instruments.get(s["instrument"], {})
        return {
            "id": s["id"], "name": s["name"], "instrument": s["instrument"],
            "instrument_label": inst.get("label", s["instrument"]),
            "status": s["status"], "status_detail": s["status_detail"],
            "feed_status": inst.get("feed_status"),
            "position": s["position"], "allocation": s["allocation"],
            "realized_pnl": s["realized_pnl"], "unrealized_pnl": s["unrealized_pnl"],
            "net_pnl": s["realized_pnl"] + s["unrealized_pnl"],
            "equity": s["allocation"] + s["realized_pnl"] + s["unrealized_pnl"],
            "trades": trades, "wins": s["wins"], "losses": s["losses"],
            "win_rate": s["wins"] / trades if trades else None,
            "avg_win": s["gross_wins"] / s["wins"] if s["wins"] else None,
            "avg_loss": -s["gross_losses"] / s["losses"] if s["losses"] else None,
            "profit_factor": s["gross_wins"] / s["gross_losses"] if s["gross_losses"] else None,
            "max_drawdown": s["max_drawdown"], "risk_status": s["risk_status"],
            "risk_reason": s["risk_reason"], "last_signal": s["last_signal"],
            "last_decision": s["last_decision"], "version": s["version"],
        }

    def snapshot(self) -> dict:
        strategies = [self._strategy_view(s) for s in self.strategies.values()]
        board = sorted(strategies, key=lambda v: (-v["realized_pnl"], v["id"]))
        return {
            "mode": self.mode, "source": self.meta["source"], "as_of_utc": self.as_of,
            "current_session": self.current_session, "applied": self.applied,
            "duplicates_ignored": self.duplicates_ignored, "rejected": self.rejected,
            "account": self.account(), "strategies": strategies,
            "leaderboard": [{"rank": k + 1, "id": v["id"]} for k, v in enumerate(board)],
            "instruments": list(self.instruments.values()),
            "sessions": list(self.sessions.values()),
        }

    def _session_minutes(self) -> float:
        """Regular-session minutes elapsed so far (completed sessions + the open one)."""
        total = 0.0
        for row in self.sessions.values():
            start, close = _ts(row["open_utc"]), _ts(row["close_utc"])
            end = close if row["status"] == "closed" else min(close, _ts(self.as_of))
            total += max(0.0, (end - start) / 60)
        return total

    def evaluation(self, sid: str) -> dict | None:
        """Evaluation report from this strategy's records up to the current replay time."""
        s = self.strategies.get(sid)
        if s is None:
            return None
        inst = next(i for i in self.meta["instances"] if i["id"] == sid)
        report = evaluate(
            mode=self.mode, trades=self.records[sid]["trades"],
            decisions=self.records[sid]["decisions"], sessions_evaluated=list(self.sessions),
            expected_sessions=len(self.meta["sessions"]), session_minutes=self._session_minutes(),
            allocation=s["allocation"], max_drawdown=s["max_drawdown"],
            target_defined=inst.get("spec", {}).get("target_defined", False))
        report["as_of_utc"] = self.as_of
        report["strategy_id"] = sid
        return report

    def strategy_records(self, sid: str) -> dict | None:
        s = self.strategies.get(sid)
        if s is None:
            return None
        return {"strategy": self._strategy_view(s), **self.records[sid],
                "bars": self.bars.get((s["instrument"], self.current_session), []),
                "session": self.current_session}
