"""Deliberate, sanitized evidence package for the reviewer.

Only named fields from named files inside research/<allowlisted experiment>/ are included, plus
the outputs of the deterministic checks (labelled as the authority). Nothing from data/, no
market data, no validation/final-period data, no credentials, no account identifiers.

Text is treated as untrusted: control characters are stripped, secret-looking values and
absolute paths are redacted, long strings are truncated (recorded), and instruction-like text is
FLAGGED (kept as data, never obeyed). The prompt wraps the whole package as data.
"""

import hashlib
import json
import math
import re
from pathlib import Path

from trading import jobs

PACKAGE_VERSION = "1"
MAX_PACKAGE_CHARS = 60_000          # refuse (do not silently cut) beyond this
MAX_JSON_STRING = 600
MAX_SECTION_CHARS = 3_500
ALLOWED_FILES = ("STATUS.json", "EXPERIMENT_LOCK.json", "RESULTS_development.md", "runs/")
EXCLUDED = [
    "market data and bar files (data/)",
    "validation and final-period data (never retrieved)",
    "credentials, environment variables, account snapshots",
    "SPEC.md full text (pass rules are quoted via RESULTS_development.md and the run report)",
    "per-trade records and journals",
]

INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)",
    r"disregard (the |all )?(previous|above|system)",
    r"you are now",
    r"system prompt",
    r"new instructions?",
    r"(mark|report|treat) (\w+ ){0,3}(gate|rule|d\d|experiment)\w* (as )?(pass|passed|approved)",
    r"approve (this|the) (strategy|experiment)",
    r"(place|submit|execute) (an? )?(order|trade)s?",
    r"run (this|the following) (code|command)",
    r"</?(system|assistant|user|evidence|instructions?)>",
    r"api[_ ]?key",
]
SECRET_PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"), "[REDACTED-KEY]"),
    (re.compile(r"\b(APCA_API_[A-Z_]+|ANTHROPIC_API_KEY|[A-Z_]*SECRET[A-Z_]*)\s*[=:]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"[A-Za-z]:\\\\?Users\\\\?[^\s\"']+"), "[LOCAL-PATH]"),
    (re.compile(r"/(home|Users)/[^\s\"']+"), "[LOCAL-PATH]"),
]
DROP_KEYS = {"id", "account_number", "api_key", "secret", "token"}
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class EvidenceError(Exception):
    pass


class EvidenceTooLarge(EvidenceError):
    pass


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _Sanitizer:
    def __init__(self):
        self.flags, self.truncations, self.redactions = [], [], 0

    def text(self, s: str, where: str, limit: int) -> str:
        s = CONTROL.sub("", s)
        for pat, repl in SECRET_PATTERNS:
            s, n = pat.subn(repl, s)
            self.redactions += n
        for pat in INJECTION_PATTERNS:
            m = re.search(pat, s, re.IGNORECASE)
            if m:
                self.flags.append({"where": where, "pattern": pat, "excerpt": s[max(0, m.start() - 40):m.end() + 40]})
        if len(s) > limit:
            self.truncations.append({"where": where, "original_chars": len(s), "kept_chars": limit})
            s = s[:limit] + " [TRUNCATED]"
        return s

    def value(self, v, where: str):
        if isinstance(v, str):
            return self.text(v, where, MAX_JSON_STRING)
        if isinstance(v, float):
            return v if math.isfinite(v) else None
        if isinstance(v, dict):
            return {k: self.value(x, f"{where}.{k}") for k, x in v.items() if k.lower() not in DROP_KEYS}
        if isinstance(v, list):
            return [self.value(x, f"{where}[{i}]") for i, x in enumerate(v)]
        return v


def resolve(obj, dotted: str):
    """Follow a dotted field path (dict keys; list indexes as digits). Raises KeyError."""
    if dotted in ("", "."):
        return obj
    for part in dotted.split("."):
        if isinstance(obj, dict) and part in obj:
            obj = obj[part]
        elif isinstance(obj, list) and part.isdigit() and int(part) < len(obj):
            obj = obj[int(part)]
        else:
            raise KeyError(dotted)
    return obj


def _sections(md: str, wanted: tuple[str, ...]) -> dict[str, str]:
    out, current, buf = {}, None, []
    for line in md.splitlines():
        if line.startswith("## "):
            if current:
                out[current] = "\n".join(buf).strip()
            title = line[3:].strip()
            current = title if any(title.lower().startswith(w.lower()) for w in wanted) else None
            buf = []
        elif current:
            buf.append(line)
    if current:
        out[current] = "\n".join(buf).strip()
    return out


REPORT_FIELDS_001 = ["period", "start_equity", "risk_limits", "results_by_cost.base", "results_by_cost.stress",
                     "results_by_cost.severe.net_return", "baseline_always_long.net_return", "baseline_no_trade_return",
                     "random_direction", "neighbors_net_return", "pass_rules", "all_pass_rules", "held_out_inspection"]
REPORT_FIELDS_002 = ["period", "risk_limits", "primary.base", "primary.stress", "primary.severe.net_return",
                     "B3.net_return", "robustness", "diagnostics.B1", "rules", "all_pass"]
DROP_BULKY = ("by_year", "m2_detail", "dates", "exit_reasons")
STATUS_FIELDS = ["experiment_id", "spec_version", "status", "state", "closed", "failed_rules", "passed_rules",
                 "development_run_id", "validation_data", "final_data", "known_reporting_defect", "not_promoted"]
LOCK_FIELDS = ["experiment_id", "hypothesis", "metrics", "risk_limits_are_placeholders", "data_status_at_lock"]


def _strip_bulky(v):
    if isinstance(v, dict):
        return {k: _strip_bulky(x) for k, x in v.items() if k not in DROP_BULKY}
    return v


def build_package(experiment: str, research_dir: Path = jobs.RESEARCH_DIR) -> dict:
    """Read-only. Raises EvidenceError (missing/corrupt artifact) or EvidenceTooLarge."""
    jobs._validate(experiment)
    exp_dir = research_dir / experiment
    try:
        ing, ing_ev = jobs.ingest(exp_dir)
        rec, rec_ev = jobs.reconcile(ing)
        ana, _ = jobs.analysis(ing)
        chk, _ = jobs.rule_checks(ing, rec, ana)
        md = (exp_dir / "RESULTS_development.md").read_text(encoding="utf-8")
        status = json.loads((exp_dir / "STATUS.json").read_text(encoding="utf-8"))
        lock = json.loads((exp_dir / "EXPERIMENT_LOCK.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError) as exc:
        raise EvidenceError(f"{type(exc).__name__}: {exc}") from exc

    report = ing["report"]
    gates = jobs._rules_001(report) if "results_by_cost" in report else jobs._rules_002(report)
    base = f"research/{experiment}"
    run_rel = f"{base}/runs/{ing['run_id']}.json"
    san = _Sanitizer()
    items = []

    def add(path, field, value, source="artifact"):
        rel = path[len(base) + 1:] if path.startswith(base + "/") else None
        if source == "artifact" and not (rel and any(rel == a or (a.endswith("/") and rel.startswith(a))
                                                    for a in ALLOWED_FILES)):
            raise EvidenceError(f"path outside the evidence allowlist: {path}")
        items.append({"id": f"E{len(items) + 1:02d}", "path": path, "field": field, "source": source,
                      "value": san.value(value, f"{path}#{field}")})

    for f in STATUS_FIELDS:
        if f in status:
            add(f"{base}/STATUS.json", f, status[f])
    for f in LOCK_FIELDS:
        if f in lock:
            add(f"{base}/EXPERIMENT_LOCK.json", f, lock[f])
    for f in (REPORT_FIELDS_001 if "results_by_cost" in report else REPORT_FIELDS_002):
        try:
            add(run_rel, f, _strip_bulky(resolve(report, f)))
        except KeyError:
            continue
    wanted = ("Pass rules", "Acceptance rules", "Results", "Primary", "Cost sensitivity", "Data exclusions",
              "Limitations", "Diagnosis", "Recommendation")
    for title, body in _sections(md, wanted).items():
        items.append({"id": f"E{len(items) + 1:02d}", "path": f"{base}/RESULTS_development.md",
                      "field": f"section:{title}", "source": "artifact",
                      "value": san.text(body, f"RESULTS_development.md#{title}", MAX_SECTION_CHARS)})
    add("deterministic:reconcile", "checks", rec_ev["checks"], source="deterministic_check")
    add("deterministic:reconcile", "reconciled", rec["reconciled"], source="deterministic_check")
    add("deterministic:analysis", "metrics", ana, source="deterministic_check")
    add("deterministic:rule_checks", "findings", chk["findings"], source="deterministic_check")
    add("deterministic:gates", "recomputed", gates, source="deterministic_check")

    body = {"items": items, "deterministic_gates": gates}
    fingerprint = _sha(json.dumps(body, sort_keys=True, default=str))
    package = {
        "package_version": PACKAGE_VERSION, "experiment": experiment, "experiment_id": ing["experiment_id"],
        "run_id": ing["run_id"], "items": items, "deterministic_gates": gates,
        "failed_gates": sorted(k for k, v in gates.items() if not v),
        "source_files": ing_ev["files"], "untrusted_text_flags": san.flags, "truncations": san.truncations,
        "redactions": san.redactions, "excluded": EXCLUDED, "fingerprint": fingerprint,
    }
    package["chars"] = len(json.dumps(items, default=str))
    if package["chars"] > MAX_PACKAGE_CHARS:
        raise EvidenceTooLarge(f"evidence package is {package['chars']} chars; limit {MAX_PACKAGE_CHARS}. "
                               "Nothing was sent; reduce the selection rather than truncating silently.")
    return package


def lookup(package: dict, path: str, field: str):
    """Resolve a citation against the package. Returns the cited value or raises KeyError."""
    for item in package["items"]:
        if item["path"] != path:
            continue
        if field == item["field"]:
            return item["value"]
        if field.startswith(item["field"] + "."):
            return resolve(item["value"], field[len(item["field"]) + 1:])
    raise KeyError(f"{path}#{field}")
