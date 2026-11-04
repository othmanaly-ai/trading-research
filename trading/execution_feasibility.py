"""Bounded, read-only execution-data access check (feasibility evidence, not research evaluation).

Pre-registered in feasibility/execution_data/PREREGISTRATION.md (commit 883f7bb) before any request.

    .venv\\Scripts\\python -m trading.execution_feasibility fetch      # GET only, capped
    .venv\\Scripts\\python -m trading.execution_feasibility analyze <dir>

- Downloads go to data/feasibility/execution_<UTC>/ (git-ignored), separate from data/history/ and
  every experiment. No strategy returns are computed; no parameters are chosen.
- Every HTTP call is counted at the HTTP layer (including the client's bounded 429 waits), and
  stops at the hard cap. A page cap that is reached means INCOMPLETE COVERAGE, never complete.
- An access failure stops that request path for all remaining dates, without retries. No feed or
  adjustment is ever substituted.
"""

import gzip
import json
import sys
import time
from datetime import date, datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from trading.history import HISTORY_DIR, period_of

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = PROJECT_ROOT / "data" / "feasibility"
ET = ZoneInfo("America/New_York")

# (session, prior session, reason): exactly the pre-registered list.
DATES = [
    ("2016-10-19", "2016-10-18", "random draw (seed 20261105)"),
    ("2017-01-19", "2017-01-18", "random draw (seed 20261105)"),
    ("2017-03-27", "2017-03-24", "random draw (seed 20261105)"),
    ("2019-05-07", "2019-05-06", "random draw (seed 20261105)"),
    ("2020-12-02", "2020-12-01", "random draw (seed 20261105)"),
    ("2021-07-20", "2021-07-19", "random draw (seed 20261105)"),
    ("2019-06-21", "2019-06-20", "expected ex-dividend date (corporate-action check)"),
]
SYMBOL, FEED = "SPY", "sip"
MAX_REQUESTS = 240
MIN_GAP_S = 0.4
QUOTE_PAGE_CAP, CA_PAGE_CAP = 30, 3
QUOTE_WINDOW = (dtime(9, 30), dtime(9, 35))
BAR_WINDOW = (dtime(9, 30), dtime(10, 2))          # bars 09:30 .. 10:01
CA_RANGE = ("2016-01-04", "2021-12-31")


class RequestCapReached(RuntimeError):
    pass


CANDIDATE_STATUS = PROJECT_ROOT / "research" / "candidates" / "gap_down_opening" / "STATUS.json"
BLOCKING_STATES = ("DEFERRED_DATA_SEMANTICS",)


def downloads_blocked(status_path: Path = CANDIDATE_STATUS) -> str | None:
    """Reason downloads are refused for this candidate, or None. A missing or unreadable status
    file also blocks (fail closed)."""
    try:
        state = json.loads(status_path.read_text(encoding="utf-8")).get("state")
    except (OSError, ValueError) as exc:
        return f"candidate status unreadable ({type(exc).__name__}); downloads refused"
    if state in BLOCKING_STATES:
        return f"candidate state is {state}: downloads for this candidate are stopped (owner decision)"
    return None


class CountingHttp:
    """Wraps a requests.Session: counts and paces every GET, refuses beyond the cap. Logs only the
    path, parameters, status and local times (never headers, so never credentials)."""

    def __init__(self, inner, cap=MAX_REQUESTS, gap=MIN_GAP_S, clock=time.monotonic, sleep=time.sleep):
        self.inner, self.cap, self.gap, self.clock, self.sleep = inner, cap, gap, clock, sleep
        self.count, self.log, self._last = 0, [], None

    def get(self, url, headers, params, timeout):
        if self.count >= self.cap:
            raise RequestCapReached(f"hard cap of {self.cap} HTTP requests reached")
        if self._last is not None and self.clock() - self._last < self.gap:
            self.sleep(self.gap - (self.clock() - self._last))
        self.count += 1
        sent = datetime.now(timezone.utc)
        resp = self.inner.get(url, headers=headers, params=params, timeout=timeout)
        self._last = self.clock()
        self.log.append({"n": self.count, "path": url.split(".markets", 1)[-1],
                         "params": {k: v for k, v in (params or {}).items() if k != "page_token"},
                         "page_token_sent": bool((params or {}).get("page_token")),
                         "status": resp.status_code, "local_sent_utc": sent.isoformat(),
                         "local_received_utc": datetime.now(timezone.utc).isoformat()})
        return resp


def check_dates(dates=DATES) -> None:
    for d, prior, _ in dates:
        for x in (d, prior):
            if period_of(date.fromisoformat(x)) != "development":
                raise ValueError(f"{x} is not a development-period date; refused")


def et_utc(d: str, t: dtime) -> str:
    return datetime.combine(date.fromisoformat(d), t, ET).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(client, http: CountingHttp, out: Path, dates=DATES) -> dict:
    from trading.alpaca_client import AlpacaAccessError
    check_dates(dates)
    out.mkdir(parents=True, exist_ok=True)
    stopped: dict[str, dict] = {}
    results: dict = {"corporate_actions": None, "dates": {}}

    def run(path: str, fn):
        if path in stopped:
            return {"status": "not requested", "reason": f"path stopped after access failure: {stopped[path]['error']}"}
        try:
            return {"status": "ok", **fn()}
        except AlpacaAccessError as exc:
            stopped[path] = {"http_status": exc.status_code, "error": str(exc)[:400]}   # no retries
            return {"status": "access failure", "http_status": exc.status_code, "error": str(exc)[:400]}
        except RequestCapReached as exc:
            return {"status": "INCOMPLETE COVERAGE", "error": str(exc)}

    def ca():
        r = client.get_corporate_actions([SYMBOL], ["cash_dividend"], *CA_RANGE, max_pages=CA_PAGE_CAP)
        (out / "corporate_actions.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
        return {"pages": r["pages"], "complete": r["complete"],
                "records": sum(len(v) for v in r["corporate_actions"].values())}
    results["corporate_actions"] = run("corporate_actions", ca)

    for d, prior, reason in dates:
        res = {"reason": reason, "prior_session": prior}

        def daily():
            r = client.get_bars(SYMBOL, "1Day", prior, d, feed=FEED, adjustment="raw")
            (out / f"daily_raw_{d}.json").write_text(json.dumps(r["bars"]), encoding="utf-8")
            return {"pages": r["pages"], "bars": len(r["bars"])}

        def minute():
            r = client.get_bars(SYMBOL, "1Min", et_utc(d, BAR_WINDOW[0]), et_utc(d, BAR_WINDOW[1]),
                                feed=FEED, adjustment="raw")
            (out / f"minute_raw_{d}.json").write_text(json.dumps(r["bars"]), encoding="utf-8")
            return {"pages": r["pages"], "bars": len(r["bars"])}

        def quotes():
            r = client.get_quotes(SYMBOL, et_utc(d, QUOTE_WINDOW[0]), et_utc(d, QUOTE_WINDOW[1]),
                                  feed=FEED, max_pages=QUOTE_PAGE_CAP)
            with gzip.open(out / f"quotes_{d}.json.gz", "wt", encoding="utf-8") as f:
                json.dump(r["quotes"], f)
            status = {} if r["complete"] else {"status": "INCOMPLETE COVERAGE",
                                               "reason": f"page cap {QUOTE_PAGE_CAP} reached with a page token remaining"}
            return {"pages": r["pages"], "quotes": len(r["quotes"]), "complete": r["complete"],
                    "last_t": r["quotes"][-1]["t"] if r["quotes"] else None, **status}

        res["daily_raw"] = run("daily_raw", daily)
        res["minute_raw"] = run("minute_raw", minute)
        res["quotes"] = run("quotes", quotes)
        results["dates"][d] = res

    results["stopped_paths"] = stopped
    results["http_requests"] = http.count
    results["request_cap"] = MAX_REQUESTS
    (out / "requests_log.json").write_text(json.dumps(http.log, indent=1), encoding="utf-8")
    (out / "fetch_results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    return results


# ---------------------------------------------------------------- validation (no returns computed)

def _q(v, p):
    return None if len(v) == 0 else round(float(v.quantile(p)), 4)


def validate_quotes(rows: list[dict], d: str) -> dict:
    if not rows:
        return {"quotes": 0}
    f = pd.DataFrame(rows)
    f["ts"] = pd.to_datetime(f["t"], utc=True, format="ISO8601")
    lo, hi = pd.Timestamp(et_utc(d, QUOTE_WINDOW[0])), pd.Timestamp(et_utc(d, QUOTE_WINDOW[1]))
    out = {"quotes": len(f), "first_t": f["t"].iloc[0], "last_t": f["t"].iloc[-1],
           "outside_window": int(((f.ts < lo) | (f.ts >= hi)).sum()),
           "out_of_order": int((f.ts.diff().dt.total_seconds() < 0).sum()),
           "nonpositive_bid": int((f.bp <= 0).sum()), "nonpositive_ask": int((f.ap <= 0).sum()),
           "negative_size": int(((f.bs < 0) | (f["as"] < 0)).sum()),
           "crossed": int((f.ap < f.bp).sum()), "locked": int((f.ap == f.bp).sum())}
    conds = f["c"].explode().value_counts() if "c" in f else pd.Series(dtype=int)
    out["condition_codes"] = {str(k): int(v) for k, v in conds.items()}
    out["tape_codes"] = {str(k): int(v) for k, v in f["z"].value_counts().items()} if "z" in f else {}
    ok = f[(f.bp > 0) & (f.ap > 0) & (f.ap >= f.bp)].copy()
    ok["spread_c"] = ((ok.ap - ok.bp) * 100).round(4)
    ok["spread_bp"] = (ok.ap - ok.bp) / ((ok.ap + ok.bp) / 2) * 1e4
    ok["dur"] = ok.ts.shift(-1).sub(ok.ts).dt.total_seconds().fillna(0).clip(lower=0)
    per_min = {}
    for m in range(5):
        a, b = lo + pd.Timedelta(minutes=m), lo + pd.Timedelta(minutes=m + 1)
        g, allq = ok[(ok.ts >= a) & (ok.ts < b)], f[(f.ts >= a) & (f.ts < b)]
        gaps = allq.ts.diff().dt.total_seconds()
        tw = g.dur.sum()
        per_min[a.tz_convert(ET).strftime("%H:%M")] = {
            "quotes": int(len(allq)), "valid": int(len(g)),
            "first_quote_after_minute_start_s": None if allq.empty else round((allq.ts.iloc[0] - a).total_seconds(), 6),
            "largest_gap_s": None if len(allq) < 2 else round(float(gaps.max()), 6),
            "spread_cents_median": _q(g.spread_c, .5), "spread_cents_p90": _q(g.spread_c, .9),
            "spread_cents_max": None if g.empty else round(float(g.spread_c.max()), 4),
            "spread_bp_median": _q(g.spread_bp, .5), "spread_bp_p90": _q(g.spread_bp, .9),
            "share_1_cent_by_count": None if g.empty else round(float((g.spread_c.round(2) <= 1.0).mean()), 4),
            "share_1_cent_time_weighted": None if tw <= 0 else round(float(g.dur[g.spread_c.round(2) <= 1.0].sum() / tw), 4),
        }
    out["by_minute_et"] = per_min
    return out


def validate_bars(rows: list[dict], d: str) -> dict:
    if not rows:
        return {"bars": 0}
    f = pd.DataFrame(rows)
    f["ts"] = pd.to_datetime(f["t"], utc=True)
    expected = pd.date_range(et_utc(d, BAR_WINDOW[0]), et_utc(d, dtime(10, 1)), freq="1min", tz="UTC")
    bad = ((f.h < f[["o", "c"]].max(axis=1)) | (f.l > f[["o", "c"]].min(axis=1)) | (f.l > f.h) | (f.v < 0)).sum()
    return {"bars": len(f), "expected": len(expected),
            "missing_minutes_et": [t.tz_convert(ET).strftime("%H:%M") for t in expected.difference(pd.DatetimeIndex(f.ts))],
            "ohlc_or_volume_violations": int(bad), "out_of_order": int((f.ts.diff().dt.total_seconds() <= 0).sum()),
            "open_0930_raw": float(f.o.iloc[0]) if f.ts.iloc[0] == expected[0] else None}


def raw_vs_adjusted(rows: list[dict], d: str) -> dict:
    """Adjustment factor only (raw price / stored `all` price, same minutes). Not a return."""
    p = HISTORY_DIR / SYMBOL / FEED / "all" / "minute" / f"{d}.csv"
    if not rows or not p.is_file():
        return {"available": False}
    raw = pd.DataFrame(rows).assign(ts=lambda x: pd.to_datetime(x.t, utc=True)).set_index("ts")
    adj = pd.read_csv(p).assign(ts=lambda x: pd.to_datetime(x.timestamp_utc, utc=True)).set_index("ts")
    j = raw.join(adj[["close"]], how="inner")
    r = j.c / j.close
    return {"available": True, "minutes_matched": int(len(j)), "ratio_raw_over_adjusted_min": round(float(r.min()), 6),
            "ratio_raw_over_adjusted_max": round(float(r.max()), 6)}


def analyze(out: Path) -> dict:
    fetched = json.loads((out / "fetch_results.json").read_text(encoding="utf-8"))
    log = json.loads((out / "requests_log.json").read_text(encoding="utf-8"))
    ca_path = out / "corporate_actions.json"
    ca = json.loads(ca_path.read_text(encoding="utf-8")) if ca_path.is_file() else None
    divs = (ca or {}).get("corporate_actions", {}).get("cash_dividends", [])
    findings = {"label": "FEASIBILITY EVIDENCE: execution-data access check. Not research evaluation; no returns computed.",
                "preregistration": "feasibility/execution_data/PREREGISTRATION.md (commit 883f7bb)",
                "host": "https://data.alpaca.markets", "feed": FEED, "symbol": SYMBOL,
                "http_requests": fetched["http_requests"], "request_cap": fetched["request_cap"],
                "stopped_paths": fetched["stopped_paths"],
                "local_retrieval_utc": {"first": log[0]["local_sent_utc"] if log else None,
                                        "last": log[-1]["local_received_utc"] if log else None},
                "http_status_counts": pd.Series([r["status"] for r in log]).value_counts().to_dict() if log else {},
                "corporate_actions": {**(fetched["corporate_actions"] or {}),
                                      "fields_returned": sorted({k for r in divs for k in r}),
                                      "records_in_range": len(divs)},
                "dates": {}}
    ex_dates = {r.get("ex_date") for r in divs}
    findings["corporate_actions"]["declaration_before_ex_date"] = {
        "with_declaration_date": sum(1 for r in divs if r.get("declaration_date")),
        "declaration_before_ex": sum(1 for r in divs if r.get("declaration_date") and r.get("ex_date")
                                     and r["declaration_date"] < r["ex_date"])}
    for d, res in fetched["dates"].items():
        e = {"reason": res["reason"], "prior_session": res["prior_session"],
             "fetch": {k: res[k] for k in ("daily_raw", "minute_raw", "quotes")},
             "is_ex_dividend_date_per_record": d in ex_dates if divs else None,
             "dividend_record": next((r for r in divs if r.get("ex_date") == d), None)}
        p = out / f"daily_raw_{d}.json"
        if p.is_file():
            bars = json.loads(p.read_text(encoding="utf-8"))
            by_day = {pd.Timestamp(b["t"]).tz_convert(ET).date().isoformat(): b for b in bars}
            pr, td = by_day.get(res["prior_session"]), by_day.get(d)
            e["daily_raw"] = {"prior_close_raw": pr and pr["c"], "day_open_raw": td and td["o"],
                              "days_returned": sorted(by_day)}
        p = out / f"minute_raw_{d}.json"
        if p.is_file():
            rows = json.loads(p.read_text(encoding="utf-8"))
            e["minute_raw"] = validate_bars(rows, d)
            e["raw_vs_adjusted"] = raw_vs_adjusted(rows, d)
            if e.get("daily_raw") and e["minute_raw"].get("open_0930_raw") and e["daily_raw"]["day_open_raw"]:
                e["daily_open_minus_0930_bar_open_cents"] = round((e["daily_raw"]["day_open_raw"] - e["minute_raw"]["open_0930_raw"]) * 100, 2)
        p = out / f"quotes_{d}.json.gz"
        if p.is_file():
            with gzip.open(p, "rt", encoding="utf-8") as f:
                e["quotes"] = validate_quotes(json.load(f), d)
        findings["dates"][d] = e
    return findings


# ---------------------------------------------------------------- amendment 2: coverage to the exit

COVERAGE_WINDOW = (dtime(9, 35), dtime(10, 1))      # both ends inclusive per the provider docs
COVERAGE_PAGE_CAP, COVERAGE_MAX_REQUESTS = 100, 360


def fetch_coverage(client, http: CountingHttp, out: Path, dates=DATES) -> dict:
    from trading.alpaca_client import AlpacaAccessError
    check_dates(dates)
    out.mkdir(parents=True, exist_ok=True)
    res = {"conditions": None, "dates": {}, "stopped_paths": {}}
    try:
        cond = client.get_quote_conditions("B")
        (out / "quote_conditions_tape_B.json").write_text(json.dumps(cond, indent=1), encoding="utf-8")
        res["conditions"] = {"status": "ok"}
    except AlpacaAccessError as exc:
        res["conditions"] = {"status": "access failure", "http_status": exc.status_code, "error": str(exc)[:400]}
    except RequestCapReached as exc:
        res["conditions"] = {"status": "INCOMPLETE COVERAGE", "error": str(exc)}
    for d, _, _ in dates:
        if "quotes" in res["stopped_paths"]:
            res["dates"][d] = {"status": "not requested", "reason": "path stopped after access failure"}
            continue
        try:
            r = client.get_quotes(SYMBOL, et_utc(d, COVERAGE_WINDOW[0]), et_utc(d, COVERAGE_WINDOW[1]),
                                  feed=FEED, max_pages=COVERAGE_PAGE_CAP)
            with gzip.open(out / f"quotes_cov_{d}.json.gz", "wt", encoding="utf-8") as f:
                json.dump(r["quotes"], f)
            res["dates"][d] = {"status": "ok" if r["complete"] else "INCOMPLETE COVERAGE", "pages": r["pages"],
                               "quotes": len(r["quotes"]), "complete": r["complete"],
                               "last_t": r["quotes"][-1]["t"] if r["quotes"] else None}
        except AlpacaAccessError as exc:
            res["stopped_paths"]["quotes"] = {"http_status": exc.status_code, "error": str(exc)[:400]}
            res["dates"][d] = {"status": "access failure", "http_status": exc.status_code, "error": str(exc)[:400]}
        except RequestCapReached as exc:
            res["dates"][d] = {"status": "INCOMPLETE COVERAGE", "error": str(exc)}
    res["http_requests"], res["request_cap"] = http.count, COVERAGE_MAX_REQUESTS
    (out / "requests_log.json").write_text(json.dumps(http.log, indent=1), encoding="utf-8")
    (out / "fetch_results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def classify(f: pd.DataFrame) -> pd.Series:
    """normal / locked / crossed / one-sided. Every quote keeps its class; nothing is deleted."""
    cls = pd.Series("normal", index=f.index)
    cls[f.ap == f.bp] = "locked"
    cls[f.ap < f.bp] = "crossed"
    cls[(f.bp <= 0) | (f.ap <= 0)] = "one-sided"
    return cls


def coverage_stats(rows: list[dict], d: str, start: dtime, end: dtime) -> dict:
    """Per-minute coverage for minutes start..end (inclusive). Only byte-identical duplicate
    records (the window-boundary overlap) are counted once."""
    f = pd.DataFrame(rows)
    if f.empty:
        return {"quotes": 0}
    f["c_key"] = f["c"].astype(str)
    f = f.drop_duplicates(subset=["t", "ap", "as", "ax", "bp", "bs", "bx", "z", "c_key"]).reset_index(drop=True)
    f["ts"] = pd.to_datetime(f["t"], utc=True, format="ISO8601")
    f["cls"] = classify(f)
    f["dur"] = f.ts.shift(-1).sub(f.ts).dt.total_seconds().fillna(0).clip(lower=0)
    lo = pd.Timestamp(et_utc(d, start))
    n_min = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute) + 1
    classes = ("normal", "locked", "crossed", "one-sided")
    total = max(float(f.dur.sum()), 1e-9)
    out = {"quotes": len(f), "first_t": f.t.iloc[0], "last_t": f.t.iloc[-1],
           "out_of_order": int((f.ts.diff().dt.total_seconds() < 0).sum()),
           "class_counts": {c: int((f.cls == c).sum()) for c in classes},
           "class_time_share": {c: round(float(f.dur[f.cls == c].sum()) / total, 5) for c in classes},
           "condition_codes": {str(k): int(v) for k, v in f["c"].explode().value_counts().items()},
           "minutes_without_quote": [], "by_minute_et": {}}
    for m in range(n_min):
        a, b = lo + pd.Timedelta(minutes=m), lo + pd.Timedelta(minutes=m + 1)
        g = f[(f.ts >= a) & (f.ts < b)]
        key = a.tz_convert(ET).strftime("%H:%M")
        if g.empty:
            out["minutes_without_quote"].append(key)
            continue
        nrm = g[g.cls == "normal"]
        sc = ((nrm.ap - nrm.bp) * 100).round(4)
        gap = g.ts.diff().dt.total_seconds().max()
        out["by_minute_et"][key] = {
            "quotes": int(len(g)), "largest_gap_s": None if pd.isna(gap) else round(float(gap), 6),
            "normal": int(len(nrm)), "locked": int((g.cls == "locked").sum()),
            "crossed": int((g.cls == "crossed").sum()), "one_sided": int((g.cls == "one-sided").sum()),
            "spread_cents_median_normal": _q(sc, .5), "spread_cents_p90_normal": _q(sc, .9),
            "share_1_cent_time_weighted_normal": None if nrm.dur.sum() <= 0
            else round(float(nrm.dur[sc.round(2) <= 1.0].sum() / nrm.dur.sum()), 4)}
    return out


def analyze_coverage(out: Path, first_run: Path) -> dict:
    fetched = json.loads((out / "fetch_results.json").read_text(encoding="utf-8"))
    log = json.loads((out / "requests_log.json").read_text(encoding="utf-8"))
    res = {"label": "FEASIBILITY EVIDENCE: quote coverage to the exit. Not research evaluation; no returns computed.",
           "preregistration": "feasibility/execution_data/PREREGISTRATION_2_coverage.md (commit a67fc20)",
           "http_requests": fetched["http_requests"], "request_cap": fetched["request_cap"],
           "http_status_counts": pd.Series([r["status"] for r in log]).value_counts().to_dict() if log else {},
           "local_retrieval_utc": {"first": log[0]["local_sent_utc"] if log else None,
                                   "last": log[-1]["local_received_utc"] if log else None},
           "conditions": fetched["conditions"], "stopped_paths": fetched["stopped_paths"], "dates": {}}
    cp = out / "quote_conditions_tape_B.json"
    if cp.is_file():
        res["condition_meanings"] = json.loads(cp.read_text(encoding="utf-8"))
    for d, r in fetched["dates"].items():
        e = {"fetch": r}
        p = out / f"quotes_cov_{d}.json.gz"
        if p.is_file():
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                e["window_0935_1001"] = coverage_stats(json.load(fh), d, *COVERAGE_WINDOW)
        p0 = first_run / f"quotes_{d}.json.gz"
        if p0.is_file():
            with gzip.open(p0, "rt", encoding="utf-8") as fh:
                full = coverage_stats(json.load(fh), d, dtime(9, 30), dtime(9, 34))
            e["window_0930_0935_reclassified"] = {k: full[k] for k in
                                                  ("quotes", "class_counts", "class_time_share", "minutes_without_quote")}
        res["dates"][d] = e
    return res


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["fetch"]:
        blocked = downloads_blocked()
        if blocked:
            print(blocked)
            return 3
        import requests
        from trading.alpaca_client import MissingCredentials, ReadOnlyAlpacaClient, load_credentials
        check_dates()
        try:
            key, secret = load_credentials()
        except MissingCredentials as exc:
            print(str(exc))
            return 2
        http = CountingHttp(requests.Session())
        out = OUT_ROOT / ("execution_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        res = fetch(ReadOnlyAlpacaClient(key, secret, http=http), http, out)
        print(json.dumps({"out": str(out.relative_to(PROJECT_ROOT)), "http_requests": res["http_requests"],
                          "stopped_paths": res["stopped_paths"],
                          "corporate_actions": res["corporate_actions"],
                          "dates": {d: {k: {kk: vv for kk, vv in v.items() if kk in ("status", "pages", "quotes", "bars", "complete", "http_status", "error", "reason")}
                                        for k, v in r.items() if isinstance(v, dict)} for d, r in res["dates"].items()}}, indent=1))
        return 0
    if argv[:1] == ["coverage"]:
        blocked = downloads_blocked()
        if blocked:
            print(blocked)
            return 3
        import requests
        from trading.alpaca_client import MissingCredentials, ReadOnlyAlpacaClient, load_credentials
        check_dates()
        try:
            key, secret = load_credentials()
        except MissingCredentials as exc:
            print(str(exc))
            return 2
        http = CountingHttp(requests.Session(), cap=COVERAGE_MAX_REQUESTS)
        out = OUT_ROOT / ("coverage_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        res = fetch_coverage(ReadOnlyAlpacaClient(key, secret, http=http), http, out)
        print(json.dumps({"out": str(out.relative_to(PROJECT_ROOT)),
                          **{k: res[k] for k in ("http_requests", "conditions", "stopped_paths", "dates")}}, indent=1))
        return 0
    if argv[:1] == ["analyze-coverage"] and len(argv) == 3:
        out = Path(argv[1])
        f = analyze_coverage(out, Path(argv[2]))
        (out / "coverage_findings.json").write_text(json.dumps(f, indent=1, default=str), encoding="utf-8")
        print("written", out / "coverage_findings.json")
        return 0
    if argv[:1] == ["analyze"] and len(argv) == 2:
        out = Path(argv[1])
        f = analyze(out)
        (out / "findings.json").write_text(json.dumps(f, indent=1, default=str), encoding="utf-8")
        print(json.dumps(f, indent=1, default=str))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
