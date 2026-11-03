"""Trade journal built from the ledger's records (the same records the city shows).

One row per strategy per replayed session, including sessions with no trade,
so inactivity, rejections and data outages are as visible as trades.
"""

import csv
import json
from pathlib import Path

COLUMNS = [
    "mode", "session_date", "strategy_id", "instrument", "spec_version", "spec_sha256", "variant_id",
    "feed", "signal_direction", "signal_r1", "signal_note", "decision", "decision_reason",
    "risk_status", "shares", "binding_cap", "entry_time_utc", "entry_reference", "entry_fill",
    "notional", "exposure_of_equity", "stop_price", "exit_time_utc", "exit_reference", "exit_fill",
    "exit_reason", "outcome", "holding_minutes", "gross_pnl", "modeled_costs", "net_pnl",
    "equity_before", "equity_after", "flags",
]


def build_journal(ledger, sid: str) -> list[dict]:
    """Journal rows for one strategy, in session order, from ledger records."""
    rec = ledger.records.get(sid)
    if rec is None:
        raise KeyError(sid)
    inst = next(i for i in ledger.meta["instances"] if i["id"] == sid)
    spec = inst.get("spec", {})
    by_day = lambda items: {x["ts_utc"][:10]: x for x in items}
    signals, decisions = by_day(rec["signals"]), by_day(rec["decisions"])
    risk = {}
    for r in rec["risk"]:
        risk[r["ts_utc"][:10]] = r            # last risk record of each day wins
    entries = {f["ts_utc"][:10]: f for f in rec["fills"] if f["leg"] == "entry"}
    exits = {f["entry_day"]: f for f in _pair_exits(rec["fills"])}
    trades = {t["session_date"]: t for t in rec["trades"]}

    equity = inst["allocation"]
    rows = []
    last_risk = "unknown"
    for day in sorted(ledger.sessions):
        sig, dec, ent, ext, tr = (signals.get(day), decisions.get(day), entries.get(day),
                                  exits.get(day), trades.get(day))
        if day in risk:
            last_risk = risk[day]["status"]
        net = tr["net_pnl"] if tr else 0.0
        notional = ent["shares"] * ent["fill_price"] if ent else None
        rows.append({
            "mode": ledger.mode, "session_date": day, "strategy_id": sid, "instrument": inst["instrument"],
            "spec_version": spec.get("spec_version"), "spec_sha256": spec.get("spec_sha256"),
            "variant_id": spec.get("variant_id"), "feed": ledger.meta.get("feed"),
            "signal_direction": sig["direction"] if sig else None,
            "signal_r1": sig["r1"] if sig else None,
            "signal_note": (sig.get("skip_reason") or "") if sig else "no signal record",
            "decision": dec["action"] if dec else "none",
            "decision_reason": dec.get("reason", "") if dec else "no decision record (session in progress or missing)",
            "risk_status": last_risk,
            "shares": ent["shares"] if ent else None,
            "binding_cap": dec.get("binding_cap") if dec and dec["action"] == "enter" else None,
            "entry_time_utc": ent["ts_utc"] if ent else None,
            "entry_reference": ent["reference_price"] if ent else None,
            "entry_fill": ent["fill_price"] if ent else None,
            "notional": notional,
            "exposure_of_equity": notional / equity if notional else None,
            "stop_price": ent.get("stop_price") if ent else None,
            "exit_time_utc": ext["ts_utc"] if ext else None,
            "exit_reference": ext["reference_price"] if ext else None,
            "exit_fill": ext["fill_price"] if ext else None,
            "exit_reason": tr["exit_reason"] if tr else None,
            "outcome": tr["outcome"] if tr else None,
            "holding_minutes": tr["holding_minutes"] if tr else None,
            "gross_pnl": tr["gross_pnl"] if tr else None,
            "modeled_costs": tr["gross_pnl"] - tr["net_pnl"] if tr else None,
            "net_pnl": tr["net_pnl"] if tr else None,
            "equity_before": equity, "equity_after": equity + net,
            "flags": ";".join(tr.get("flags", [])) if tr else "",
        })
        equity += net
    return rows


def _pair_exits(fills: list[dict]) -> list[dict]:
    """Attach each exit fill to the session of the entry it closes (exits can be next day)."""
    out, open_day = [], None
    for f in fills:
        if f["leg"] == "entry":
            open_day = f["ts_utc"][:10]
        elif open_day is not None:
            out.append({**f, "entry_day": open_day})
            open_day = None
    return out


def write_journal(rows: list[dict], path: Path, provenance: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    path.with_suffix(".provenance.json").write_text(json.dumps(provenance, indent=2, default=str),
                                                    encoding="utf-8")
