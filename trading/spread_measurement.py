"""SPY bid-ask spread pilot: bounded, read-only feasibility measurement. Findings are PROVISIONAL.

Pre-registered in feasibility/spread_measurement/PLAN.md, committed before any request.

    .venv\\Scripts\\python -m trading.spread_measurement limits          # no network
    .venv\\Scripts\\python -m trading.spread_measurement fetch-pilot     # GET only, capped
    .venv\\Scripts\\python -m trading.spread_measurement analyze <dir>   # offline

- Not research evaluation and not an experiment. No strategy returns, no mid-price changes,
  no fills, no strategy logic. It changes no cost model and reopens no closed experiment.
- It is separate from the gap-down candidate, whose download block in
  trading/execution_feasibility.py it neither checks nor lifts.
- Only the 6 pilot dates are allowed. The 18 pending dates, held-out dates and early-close
  sessions are refused in code.
- Limits: 600 HTTP requests in total (counted at the HTTP layer, 429 waits included), a page cap
  per window, at least 0.4 s between requests, and 75 MB of storage with a worst-case reserve
  checked before every window. Any cap stops the run; nothing is padded or treated as complete.
"""

import gzip
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from trading.execution_feasibility import ET, CountingHttp, RequestCapReached, et_utc
from trading.history import period_of

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = PROJECT_ROOT / "data" / "feasibility"
PLAN_REL = "feasibility/spread_measurement/PLAN.md"
PLAN_PATH = PROJECT_ROOT / PLAN_REL
LABEL = ("FEASIBILITY EVIDENCE, PROVISIONAL: SPY quoted bid-ask spread pilot. Alpaca SIP quotes as "
         "retrieved in 2026; timestamp clock, quote construction and condition code '?' undocumented. "
         "Quotes are not fills. Not research evaluation; no returns computed.")

SYMBOL, FEED, TAPE = "SPY", "sip", "B"

# Pilot dates in the pre-drawn fetch order (random.Random(20261109) order, pilot dates kept).
PILOT_DATES = ("2018-06-07", "2021-04-23", "2020-01-02", "2019-01-31", "2016-03-28", "2017-01-06")
# Drawn with the pilot (seed 20261108), pending a separate owner decision: refused here.
PENDING_DATES = ("2016-05-03", "2016-06-17", "2016-12-01", "2017-04-26", "2017-05-26", "2017-07-31",
                 "2018-07-25", "2018-09-07", "2018-10-11", "2019-06-10", "2019-09-23", "2019-11-15",
                 "2020-02-11", "2020-05-19", "2020-12-18", "2021-06-02", "2021-09-09", "2021-10-21")

PILOT_MAX_REQUESTS = 600
PILOT_MAX_BYTES = 75_000_000                # 75 MB (decimal), all files in the run directory
RESERVE_BYTES_PER_PAGE = 200_000            # worst-case compressed size of one 10,000-quote page
MIN_GAP_S = 0.4
STALE_S = 5.0
SNAPSHOT_MAX_AGE_S = 1.0
COVERAGE_MIN = 0.95
WIDE_SPREAD_CENTS = 10.0
WIDE_LIST_MAX = 50
HEADLINE_CODES = frozenset({"?", "R"})
COST_HALF_SPREAD_BP = {"base": 0.5, "stress": 1.0, "severe": 2.0}   # trading/costs.py, for comparison only
LOT_SHARES = 100                            # sizes before 2025-11-03 are round lots (Alpaca docs)


@dataclass(frozen=True)
class Window:
    id: str
    start: dtime
    end: dtime            # inclusive, as the provider documents
    page_cap: int
    snapshots: tuple


def _t(h, m):
    return dtime(h, m)


WINDOWS = (
    Window("B0", _t(10, 0), _t(10, 16), 60, (_t(10, 1), _t(10, 5), _t(10, 10), _t(10, 15))),
    Window("B1", _t(10, 45), _t(10, 47), 10, (_t(10, 46),)),
    Window("B2", _t(11, 30), _t(11, 32), 10, (_t(11, 31),)),
    Window("B3", _t(12, 15), _t(12, 17), 10, (_t(12, 16),)),
    Window("B4", _t(13, 0), _t(13, 2), 10, (_t(13, 1),)),
    Window("B5", _t(13, 45), _t(13, 47), 10, (_t(13, 46),)),
    Window("B6", _t(14, 30), _t(14, 32), 10, (_t(14, 31),)),
    Window("B7", _t(14, 58), _t(15, 1), 15, (_t(15, 0),)),
    Window("E1", _t(15, 29), _t(15, 34), 45, (_t(15, 30), _t(15, 31), _t(15, 32), _t(15, 33))),
    Window("X1", _t(15, 57), _t(16, 0), 40, (_t(15, 59), _t(16, 0))),
)
WINDOW_BY_ID = {w.id: w for w in WINDOWS}
GROUPS = {"E1": ("E1",), "X1": ("X1",), "B0": ("B0",),
          "B1_B7": ("B1", "B2", "B3", "B4", "B5", "B6", "B7"), "B7": ("B7",)}


class PlanNotCommitted(RuntimeError):
    pass


# ---------------------------------------------------------------- guards

def check_pilot_dates(dates=PILOT_DATES) -> None:
    """Refuse anything but the pre-registered pilot dates: pending, held-out or early-close."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import exchange_calendars as xc
        cal = xc.get_calendar("XNYS")
    for d in dates:
        if d in PENDING_DATES:
            raise ValueError(f"{d} is pending a separate owner decision; refused for the pilot")
        if d not in PILOT_DATES:
            raise ValueError(f"{d} is not a pre-registered pilot date; refused")
        if period_of(date.fromisoformat(d)) != "development":
            raise ValueError(f"{d} is not a development-period date; refused")
        if not cal.is_session(d):
            raise ValueError(f"{d} is not an XNYS session; refused")
        close_et = cal.session_close(d).tz_convert(ET)
        if (close_et.hour, close_et.minute) != (16, 0):
            raise ValueError(f"{d} is an early-close session; refused")


def plan_gate(root: Path = PROJECT_ROOT, rel: str = PLAN_REL) -> dict:
    """The plan must be tracked by git with no uncommitted (staged or unstaged) changes."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if git("ls-files", "--error-unmatch", rel).returncode != 0:
        raise PlanNotCommitted(f"{rel} is not committed; the pre-registration must be committed first")
    if git("diff", "--quiet", "HEAD", "--", rel).returncode != 0:
        raise PlanNotCommitted(f"{rel} has uncommitted changes; commit (or revert) them before fetching")
    commit = git("log", "-1", "--format=%H", "--", rel).stdout.strip()
    sha = hashlib.sha256((root / rel).read_bytes()).hexdigest()
    return {"plan": rel, "plan_commit": commit, "plan_sha256": sha,
            "head": git("rev-parse", "HEAD").stdout.strip()}


def dir_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


# ---------------------------------------------------------------- fetch

def fetch_pilot(client, http: CountingHttp, out: Path, dates=PILOT_DATES, max_bytes: int = PILOT_MAX_BYTES,
                clock=time.monotonic, gate: dict | None = None) -> dict:
    from trading.alpaca_client import AlpacaAccessError
    check_pilot_dates(dates)                 # raises on any refused date, before any request
    out.mkdir(parents=True, exist_ok=True)
    t0 = clock()
    res = {"label": LABEL, "preregistration": gate, "symbol": SYMBOL, "feed": FEED,
           "limits": {"max_requests": http.cap, "max_bytes": max_bytes, "min_gap_s": http.gap,
                      "reserve_bytes_per_page": RESERVE_BYTES_PER_PAGE,
                      "page_caps": {w.id: w.page_cap for w in WINDOWS}},
           "conditions": None, "windows": {}, "stopped_paths": {}, "stop_reason": None,
           "local_started_utc": datetime.now(timezone.utc).isoformat()}

    def stop(reason):
        if res["stop_reason"] is None:
            res["stop_reason"] = reason

    try:
        cond = client.get_quote_conditions(TAPE)
        (out / f"quote_conditions_tape_{TAPE}.json").write_text(json.dumps(cond, indent=1), encoding="utf-8")
        res["conditions"] = {"status": "ok"}
    except AlpacaAccessError as exc:
        res["conditions"] = {"status": "access failure", "http_status": exc.status_code, "error": str(exc)[:400]}
    except RequestCapReached as exc:
        res["conditions"] = {"status": "NOT FETCHED", "error": str(exc)}
        stop(f"request cap: {exc}")

    for d in dates:
        for w in WINDOWS:
            key = f"{d} {w.id}"
            if res["stop_reason"]:
                res["windows"][key] = {"status": "NOT FETCHED", "reason": res["stop_reason"]}
                continue
            if "quotes" in res["stopped_paths"]:
                res["windows"][key] = {"status": "NOT REQUESTED", "reason": "quotes path stopped after access failure"}
                continue
            used = dir_bytes(out)
            reserve = w.page_cap * RESERVE_BYTES_PER_PAGE
            if used + reserve > max_bytes:
                stop(f"storage guard: {used} bytes used + {reserve} reserve for {key} > {max_bytes}")
                res["windows"][key] = {"status": "NOT FETCHED", "reason": res["stop_reason"]}
                continue
            before = http.count
            try:
                r = client.get_quotes(SYMBOL, et_utc(d, w.start), et_utc(d, w.end), feed=FEED, max_pages=w.page_cap)
            except AlpacaAccessError as exc:   # no retries; the path stops for every remaining window
                res["stopped_paths"]["quotes"] = {"http_status": exc.status_code, "error": str(exc)[:400], "at": key}
                res["windows"][key] = {"status": "access failure", "http_status": exc.status_code,
                                       "error": str(exc)[:400], "requests": http.count - before}
                continue
            except RequestCapReached as exc:
                stop(f"request cap: {exc}")
                res["windows"][key] = {"status": "INCOMPLETE", "reason": f"request cap reached during this window; nothing stored ({exc})",
                                       "requests": http.count - before}
                continue
            path = out / f"quotes_{d}_{w.id}.json.gz"
            with gzip.open(path, "wt", encoding="utf-8") as fh:
                json.dump(r["quotes"], fh)
            entry = {"status": "ok" if r["complete"] else "INCOMPLETE COVERAGE",
                     "pages": r["pages"], "requests": http.count - before, "quotes": len(r["quotes"]),
                     "complete": r["complete"], "last_t": r["quotes"][-1]["t"] if r["quotes"] else None,
                     "file": path.name, "bytes": path.stat().st_size}
            if not r["complete"]:
                entry["reason"] = f"page cap {w.page_cap} reached with a page token remaining"
            res["windows"][key] = entry
            if dir_bytes(out) > max_bytes:
                stop(f"storage cap exceeded after writing {key}")

    res["http_requests"] = http.count
    res["http_status_counts"] = pd.Series([x["status"] for x in http.log]).value_counts().to_dict() if http.log else {}
    res["elapsed_s"] = round(clock() - t0, 3)
    res["local_finished_utc"] = datetime.now(timezone.utc).isoformat()
    (out / "requests_log.json").write_text(json.dumps(http.log, indent=1), encoding="utf-8")
    res["bytes_total"] = dir_bytes(out)     # before fetch_results.json itself, which is small
    (out / "fetch_results.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    return res


# ---------------------------------------------------------------- analysis (no returns computed)

def _codes(c) -> tuple:
    if isinstance(c, (list, tuple)):
        return tuple(str(x) for x in c)
    if c is None or (isinstance(c, float) and np.isnan(c)):
        return ()
    return (str(c),)


def wquantile(values, weights, q):
    v, w = np.asarray(values, float), np.asarray(weights, float)
    keep = w > 0
    v, w = v[keep], w[keep]
    if len(v) == 0:
        return None
    order = np.argsort(v, kind="stable")
    v, cw = v[order], np.cumsum(w[order])
    return float(v[np.searchsorted(cw, q * cw[-1], side="left")])


def _r(x, n=4):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def window_stats(rows: list[dict], d: str, w: Window) -> dict:
    """Spread statistics for one date-window under PLAN.md section 4. Removes nothing from the data."""
    lo, hi = pd.Timestamp(et_utc(d, w.start)), pd.Timestamp(et_utc(d, w.end))
    length = (hi - lo).total_seconds()
    raw_n = len(rows)
    keys = [json.dumps(r, sort_keys=True) for r in rows]
    seen, uniq = set(), []
    for k, r in zip(keys, rows):
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    out = {"records_received": raw_n, "duplicates": raw_n - len(uniq), "window_seconds": length}
    f = pd.DataFrame(uniq)
    for col in ("t", "bp", "ap", "bs", "as", "c"):
        if col not in f:
            f[col] = np.nan
    f["ts"] = pd.to_datetime(f["t"], utc=True, format="ISO8601", errors="coerce")
    for col in ("bp", "ap", "bs", "as"):
        f[col] = pd.to_numeric(f[col], errors="coerce")
    invalid = f.ts.isna() | f.bp.isna() | f.ap.isna() | (f.bp < 0) | (f.ap < 0) | (f.ts < lo) | (f.ts > hi)
    out["excluded_invalid"] = int(invalid.sum())
    v = f[~invalid].copy()
    out["out_of_order"] = int((v.ts.diff().dt.total_seconds() < 0).sum())
    out["ordering_issue"] = out["out_of_order"] > 0
    v = v.sort_values("ts", kind="stable").reset_index(drop=True)
    v["codes"] = v["c"].map(_codes)
    v["code_label"] = v["codes"].map(lambda t: "+".join(t) if t else "(none)")
    headline_code = v["codes"].map(lambda t: len(t) > 0 and all(x in HEADLINE_CODES for x in t))
    cls = pd.Series("normal", index=v.index)
    cls[v.ap == v.bp] = "locked"
    cls[v.ap < v.bp] = "crossed"
    cls[(v.bp == 0) | (v.ap == 0)] = "one-sided"
    cls[(cls == "normal") & ~headline_code] = "other condition"
    v["cls"] = cls
    nxt = v.ts.shift(-1).fillna(hi)
    raw_dur = (nxt - v.ts).dt.total_seconds().clip(lower=0)
    v["dur"] = raw_dur.clip(upper=STALE_S)
    stale = float((raw_dur - v.dur).sum())
    no_quote = length if v.empty else max((v.ts.iloc[0] - lo).total_seconds(), 0.0)
    classes = ("normal", "locked", "crossed", "one-sided", "other condition")
    secs = {c: float(v.dur[v.cls == c].sum()) for c in classes}
    secs["stale"], secs["no quote"] = stale, no_quote
    out["records_valid"] = int(len(v))
    out["class_counts"] = {c: int((v.cls == c).sum()) for c in classes}
    out["excluded_counts"] = {"invalid": out["excluded_invalid"], "duplicate": out["duplicates"],
                              **{c: out["class_counts"][c] for c in classes if c != "normal"}}
    out["time_share"] = {c: _r(s / length, 6) if length > 0 else None for c, s in secs.items()}
    out["coverage"] = _r(secs["normal"] / length, 6) if length > 0 else 0.0
    out["measured"] = bool(length > 0 and secs["normal"] / length >= COVERAGE_MIN)
    out["headline_seconds"] = round(secs["normal"], 6)
    out["condition_codes"] = {k: int(n) for k, n in v.code_label.value_counts().items()}
    gaps = v.ts.diff().dt.total_seconds()
    out["largest_gap_s"] = None if len(v) < 2 else _r(gaps.max(), 6)

    h = v[v.cls == "normal"].copy()
    h["usd"] = h.ap - h.bp
    h["cents"] = (h.usd * 100).round(6)
    h["bp_"] = h.usd / ((h.ap + h.bp) / 2) * 1e4
    tw = h.dur.sum()
    if h.empty:
        out["spread"] = None
    else:
        def block(col, n):
            return {"tw_mean": _r((h[col] * h.dur).sum() / tw, n) if tw > 0 else None,
                    "tw_median": _r(wquantile(h[col], h.dur, .5), n), "tw_p90": _r(wquantile(h[col], h.dur, .9), n),
                    "tw_p99": _r(wquantile(h[col], h.dur, .99), n), "max": _r(h[col].max(), n),
                    "count_mean": _r(h[col].mean(), n), "count_median": _r(h[col].median(), n)}
        out["spread"] = {"usd": block("usd", 6), "cents": block("cents", 4), "bp": block("bp_", 4)}
        out["half_spread_bp_tw_mean"] = _r(out["spread"]["bp"]["tw_mean"] / 2, 4) if tw > 0 else None
        c2 = h.cents.round(2)
        out["time_share_by_spread"] = None if tw <= 0 else {
            "1_cent": _r(h.dur[c2 <= 1.0].sum() / tw, 6), "2_cents": _r(h.dur[(c2 > 1.0) & (c2 <= 2.0)].sum() / tw, 6),
            "3_cents_or_more": _r(h.dur[c2 > 2.0].sum() / tw, 6)}
        lk = float(v.dur[v.cls == "locked"].sum())
        out["sensitivity_locked_as_zero_tw_mean_cents"] = _r((h.cents * h.dur).sum() / (tw + lk), 4) if tw + lk > 0 else None
        wide = h[h.cents > WIDE_SPREAD_CENTS]
        out["wide_spreads"] = {"count": int(len(wide)), "listed": [
            {"t": t, "cents": _r(c, 4)} for t, c in zip(wide.t.head(WIDE_LIST_MAX), wide.cents.head(WIDE_LIST_MAX))]}
        out["displayed_size_shares_median"] = {"bid": _r(h.bs.median() * LOT_SHARES, 1), "ask": _r(h["as"].median() * LOT_SHARES, 1)}
    # Spread by condition code over price-normal records (headline or not).
    pn = v[v.cls.isin(["normal", "other condition"])]
    pn_bp = (pn.ap - pn.bp) / ((pn.ap + pn.bp) / 2) * 1e4
    out["spread_bp_tw_mean_by_code"] = {
        k: _r((pn_bp[g.index] * g.dur).sum() / g.dur.sum(), 4) if g.dur.sum() > 0 else None for k, g in pn.groupby("code_label")}
    snaps = {}
    for s in w.snapshots:
        T = pd.Timestamp(et_utc(d, s))
        before = v[v.ts <= T]
        hn = before[before.cls == "normal"]
        key = s.strftime("%H:%M:%S")
        if hn.empty or (T - hn.ts.iloc[-1]).total_seconds() > SNAPSHOT_MAX_AGE_S:
            snaps[key] = {"state": "unresolved"}
            continue
        row = hn.iloc[-1]
        usd = row.ap - row.bp
        snaps[key] = {"state": "AMBIGUOUS" if before.index[-1] != hn.index[-1] else "ok",
                      "cents": _r(usd * 100, 4), "bp": _r(usd / ((row.ap + row.bp) / 2) * 1e4, 4),
                      "quote_age_s": _r((T - row.ts).total_seconds(), 6), "label": "clock-dependent"}
    out["snapshots"] = snaps
    return out


def summarize_groups(per_window: dict) -> dict:
    """Across dates. A date enters a group only if every window in the group is fetched complete and measured."""
    out = {}
    dates = sorted({k.split(" ")[0] for k in per_window})
    for g, ids in GROUPS.items():
        incl, counts = {}, {"measured": 0, "partial": 0, "incomplete_or_not_fetched": 0}
        for d in dates:
            ws = [per_window.get(f"{d} {i}") for i in ids]
            if any(x is None or x.get("stats") is None or x["fetch_status"] != "ok" for x in ws):
                counts["incomplete_or_not_fetched"] += 1
                continue
            if not all(x["stats"]["measured"] for x in ws):
                counts["partial"] += 1
                continue
            secs = sum(x["stats"]["headline_seconds"] for x in ws)
            cents = sum(x["stats"]["spread"]["cents"]["tw_mean"] * x["stats"]["headline_seconds"] for x in ws) / secs
            bp = sum(x["stats"]["spread"]["bp"]["tw_mean"] * x["stats"]["headline_seconds"] for x in ws) / secs
            incl[d] = {"tw_mean_cents": round(cents, 4), "tw_mean_bp": round(bp, 4), "half_spread_bp": round(bp / 2, 4)}
            counts["measured"] += 1
        vals = [x["tw_mean_bp"] for x in incl.values()]
        cvals = [x["tw_mean_cents"] for x in incl.values()]
        out[g] = {"windows": list(ids), "coverage_counts": counts, "by_date": incl,
                  "daily_tw_mean_bp": None if not vals else {"min": min(vals), "median": round(float(np.median(vals)), 4), "max": max(vals)},
                  "daily_tw_mean_cents": None if not cvals else {"min": min(cvals), "median": round(float(np.median(cvals)), 4), "max": max(cvals)},
                  "dates_with_half_spread_above": {lvl: sum(1 for x in incl.values() if x["half_spread_bp"] > hb)
                                                   for lvl, hb in COST_HALF_SPREAD_BP.items()}}
    return out


def analyze(out: Path) -> dict:
    fetched = json.loads((out / "fetch_results.json").read_text(encoding="utf-8"))
    per_window = {}
    for key, entry in fetched["windows"].items():
        d, wid = key.split(" ")
        stats = None
        if entry.get("file") and (out / entry["file"]).is_file():
            with gzip.open(out / entry["file"], "rt", encoding="utf-8") as fh:
                stats = window_stats(json.load(fh), d, WINDOW_BY_ID[wid])
        per_window[key] = {"fetch_status": entry["status"], "fetch": entry, "stats": stats}
    files = {p.name: p.stat().st_size for p in sorted(out.iterdir()) if p.is_file()}
    return {"label": LABEL, "preregistration": fetched.get("preregistration"),
            "rules": {"stale_s": STALE_S, "snapshot_max_age_s": SNAPSHOT_MAX_AGE_S, "coverage_min": COVERAGE_MIN,
                      "headline_codes": sorted(HEADLINE_CODES), "wide_spread_cents": WIDE_SPREAD_CENTS,
                      "cost_model_half_spread_bp_for_comparison": COST_HALF_SPREAD_BP},
            "resource_usage": {"http_requests": fetched["http_requests"], "request_cap": fetched["limits"]["max_requests"],
                               "http_status_counts": fetched.get("http_status_counts"),
                               "pages_by_window": {k: e.get("pages") for k, e in fetched["windows"].items()},
                               "bytes_total_all_files": sum(files.values()), "bytes_cap": fetched["limits"]["max_bytes"],
                               "bytes_by_file": files, "elapsed_s": fetched.get("elapsed_s"),
                               "stop_reason": fetched.get("stop_reason"), "stopped_paths": fetched.get("stopped_paths"),
                               "local_started_utc": fetched.get("local_started_utc"),
                               "local_finished_utc": fetched.get("local_finished_utc")},
            "conditions": fetched.get("conditions"),
            "windows": per_window, "groups": summarize_groups(per_window)}


# ---------------------------------------------------------------- command line

def limits_summary() -> dict:
    return {"label": LABEL, "pilot_dates_fetch_order": list(PILOT_DATES), "pending_dates_refused": list(PENDING_DATES),
            "windows_et_inclusive": {w.id: [w.start.strftime("%H:%M"), w.end.strftime("%H:%M"), w.page_cap] for w in WINDOWS},
            "max_pages_per_date": sum(w.page_cap for w in WINDOWS), "max_requests": PILOT_MAX_REQUESTS,
            "max_bytes": PILOT_MAX_BYTES, "min_gap_s": MIN_GAP_S, "host": "https://data.alpaca.markets",
            "endpoints": ["/v2/stocks/quotes", "/v2/stocks/meta/conditions/quote"], "symbol": SYMBOL, "feed": FEED}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["limits"]:
        print(json.dumps(limits_summary(), indent=1))
        return 0
    if argv[:1] == ["fetch-pilot"]:
        try:
            gate = plan_gate()
        except PlanNotCommitted as exc:
            print(f"REFUSED: {exc}")
            return 4
        check_pilot_dates()
        import requests
        from trading.alpaca_client import MissingCredentials, ReadOnlyAlpacaClient, load_credentials
        try:
            key, secret = load_credentials()
        except MissingCredentials as exc:
            print(str(exc))
            return 2
        http = CountingHttp(requests.Session(), cap=PILOT_MAX_REQUESTS, gap=MIN_GAP_S)
        out = OUT_ROOT / ("spreads_pilot_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        res = fetch_pilot(ReadOnlyAlpacaClient(key, secret, http=http), http, out, gate=gate)
        print(json.dumps({"out": str(out.relative_to(PROJECT_ROOT)), "http_requests": res["http_requests"],
                          "bytes_total": res["bytes_total"], "elapsed_s": res["elapsed_s"],
                          "stop_reason": res["stop_reason"], "stopped_paths": res["stopped_paths"],
                          "windows": {k: {kk: v.get(kk) for kk in ("status", "pages", "quotes", "bytes")}
                                      for k, v in res["windows"].items()}}, indent=1))
        return 0
    if argv[:1] == ["analyze"] and len(argv) == 2:
        out = Path(argv[1])
        f = analyze(out)
        (out / "findings_pilot.json").write_text(json.dumps(f, indent=1, default=str), encoding="utf-8")
        print(json.dumps({"written": str(out / "findings_pilot.json"), "groups": f["groups"],
                          "resource_usage": {k: f["resource_usage"][k] for k in
                                             ("http_requests", "bytes_total_all_files", "elapsed_s", "stop_reason")}},
                         indent=1, default=str))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
