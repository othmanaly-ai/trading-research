"""Checks on the model's answer. Anything that fails is recorded as a failed review; nothing is
repaired or substituted. Deterministic checks stay the authority: a review whose gate results
differ from them is rejected."""

import json
import re

from trading.reviewer.evidence import resolve

MAX_TEXT = 2_000
MAX_FINDINGS = 40
FORBIDDEN = [  # model opinions may not approve, promote or trade
    r"\bapproved?\b.{0,40}\b(for (live|paper) trading|strategy|for deployment)",
    r"\bready for (live|real|production) (trading|use)",
    r"\b(place|submit) (an? |the )?(live )?orders?\b",
    r"\b(promote|deploy) (this|the) strategy\b",
    r"\b(run|use|fetch|evaluate)\b.{0,30}\b(final|validation)[- ](period|data|test)\b",
]


def _expect(cond: bool, errors: list, msg: str) -> bool:
    if not cond:
        errors.append(msg)
    return cond


def _obj(v, keys: set, where: str, errors: list) -> bool:
    if not _expect(isinstance(v, dict), errors, f"{where}: expected object"):
        return False
    _expect(set(v) == keys, errors, f"{where}: keys {sorted(v)} != required {sorted(keys)}")
    return set(v) == keys


def _str(v, where, errors, limit=MAX_TEXT) -> bool:
    return (_expect(isinstance(v, str) and v.strip() != "", errors, f"{where}: expected non-empty string")
            and _expect(len(v) <= limit, errors, f"{where}: longer than {limit} chars"))


def _citations(cits, package, where, errors) -> list:
    out = []
    if not _expect(isinstance(cits, list), errors, f"{where}: citations must be a list"):
        return out
    by_id = {i["id"]: i for i in package["items"]}
    for k, c in enumerate(cits):
        if not _obj(c, {"item_id", "subfield"}, f"{where}.citations[{k}]", errors):
            continue
        item = by_id.get(c["item_id"])
        if not _expect(item is not None, errors, f"{where}: cites unknown evidence item {c['item_id']!r}"):
            continue
        sub = (c["subfield"] or "").strip().strip(".")
        try:
            value = resolve(item["value"], sub) if sub else item["value"]
        except KeyError:
            errors.append(f"{where}: subfield {sub!r} does not exist in {c['item_id']}")
            continue
        out.append({"item_id": item["id"], "path": item["path"],
                    "field": item["field"] + (f".{sub}" if sub else ""),
                    "source": item["source"], "value_excerpt": json.dumps(value, default=str)[:300]})
    return out


def validate(text: str, package: dict) -> tuple[dict | None, list[str]]:
    errors: list[str] = []
    try:
        data = json.loads(text)
    except (TypeError, ValueError) as exc:
        return None, [f"response is not valid JSON ({type(exc).__name__})"]
    if not _obj(data, {"summary", "failed_gates", "findings", "limitations_of_this_review"}, "response", errors):
        return None, errors
    _str(data["summary"], "summary", errors)

    det = package["deterministic_gates"]
    gates_out = []
    if _expect(isinstance(data["failed_gates"], list), errors, "failed_gates: expected list"):
        named = []
        for k, g in enumerate(data["failed_gates"]):
            w = f"failed_gates[{k}]"
            if not _obj(g, {"gate", "deterministic_result", "explanation", "citations"}, w, errors):
                continue
            named.append(g["gate"])
            if g["gate"] not in det:
                errors.append(f"{w}: unknown gate {g['gate']!r}")
                continue
            truth = "PASSED" if det[g["gate"]] else "FAILED"
            _expect(g["deterministic_result"] == truth, errors,
                    f"{w}: says {g['gate']} {g['deterministic_result']} but the deterministic check says {truth} "
                    "(model opinions cannot override deterministic checks)")
            _str(g["explanation"], f"{w}.explanation", errors)
            cits = _citations(g["citations"], package, w, errors)
            _expect(bool(cits), errors, f"{w}: explanation needs at least one valid citation")
            gates_out.append({"gate": g["gate"], "deterministic_result": truth, "explanation": g["explanation"],
                              "citations": cits})
        _expect(sorted(named) == sorted(package["failed_gates"]), errors,
                f"failed_gates covers {sorted(named)}; deterministic failed gates are {package['failed_gates']}")

    findings_out = []
    if _expect(isinstance(data["findings"], list), errors, "findings: expected list"):
        _expect(len(data["findings"]) <= MAX_FINDINGS, errors, f"findings: more than {MAX_FINDINGS}")
        for k, f in enumerate(data["findings"][:MAX_FINDINGS]):
            w = f"findings[{k}]"
            if not _obj(f, {"category", "topic", "statement", "citations"}, w, errors):
                continue
            _expect(f["category"] in ("fact", "deduction", "suggestion"), errors, f"{w}: bad category")
            _expect(f["topic"] in ("failed_gate", "methodology", "discrepancy", "limitation", "injection", "other"),
                    errors, f"{w}: bad topic")
            _str(f["statement"], f"{w}.statement", errors)
            cits = _citations(f["citations"], package, w, errors)
            if f["category"] in ("fact", "deduction"):
                _expect(bool(cits), errors, f"{w}: a {f['category']} must cite at least one evidence item")
            findings_out.append({"category": f["category"], "topic": f["topic"], "statement": f["statement"],
                                 "citations": cits})

    lims = data["limitations_of_this_review"]
    if _expect(isinstance(lims, list), errors, "limitations_of_this_review: expected list"):
        for k, s in enumerate(lims):
            _str(s, f"limitations_of_this_review[{k}]", errors)

    texts = [data.get("summary", "")] + [g.get("explanation", "") for g in gates_out] + \
            [f.get("statement", "") for f in findings_out]
    for t in texts:
        for pat in FORBIDDEN:
            if isinstance(t, str) and re.search(pat, t, re.IGNORECASE):
                errors.append(f"forbidden content (approval/trading/held-out request) matched {pat!r}")
    if errors:
        return None, errors
    return {"review_kind": "automated second review (not proof of independent correctness)",
            "summary": data["summary"], "failed_gates": gates_out, "findings": findings_out,
            "limitations_of_this_review": lims}, []
