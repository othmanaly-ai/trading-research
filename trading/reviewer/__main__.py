"""CLI for the automated second reviewer.

  python -m trading.reviewer status                  readiness gates, budget, spend (no call)
  python -m trading.reviewer preview --experiment X  evidence package summary, size, worst-case cost (no call)
  python -m trading.reviewer verify --experiment X --i-authorize-one-paid-call
                                                     the first paid call; owner-run only
  python -m trading.reviewer acknowledge <review_id> allow a new attempt after an uncertain/failed billed one
  python -m trading.reviewer list                    recent review records
"""

import argparse
import json
import sys

from trading import jobs
from trading.reviewer import budget, evidence, prompt, review


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m trading.reviewer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("preview")
    p.add_argument("--experiment", required=True, choices=jobs.ALLOWED_EXPERIMENTS)
    v = sub.add_parser("verify")
    v.add_argument("--experiment", required=True, choices=jobs.ALLOWED_EXPERIMENTS)
    v.add_argument("--i-authorize-one-paid-call", action="store_true")
    a = sub.add_parser("acknowledge")
    a.add_argument("review_id")
    sub.add_parser("list")
    args = ap.parse_args(argv)
    store = budget.ReviewStore()
    try:
        if args.cmd == "status":
            print(json.dumps(review.readiness(review.cli_env(), store), indent=2, default=str))
        elif args.cmd == "preview":
            pkg = evidence.build_package(args.experiment)
            user = prompt.render_user_message(pkg)
            auth, problems = budget.load_authorization()
            print(json.dumps({"experiment": args.experiment, "fingerprint": pkg["fingerprint"],
                              "items": [(i["id"], i["path"], i["field"]) for i in pkg["items"]],
                              "failed_gates": pkg["failed_gates"], "untrusted_text_flags": pkg["untrusted_text_flags"],
                              "truncations": pkg["truncations"], "redactions": pkg["redactions"],
                              "estimated_input_tokens": review.estimate_input_tokens(prompt.SYSTEM, user),
                              "worst_case_usd": budget.worst_case_usd(auth) if auth else None,
                              "authorization_problems": problems}, indent=2))
        elif args.cmd == "verify":
            if not args.i_authorize_one_paid_call:
                print("Refusing: this makes a billable API call. Re-run with --i-authorize-one-paid-call.")
                return 2
            store.recover_in_flight()
            res = review.verify(args.experiment, review.cli_env(), store)
            print(json.dumps({k: v for k, v in res.items() if k != "review"}, indent=2, default=str))
            return 0 if res.get("verified") else 1
        elif args.cmd == "acknowledge":
            ok = store.acknowledge(args.review_id)
            print("acknowledged" if ok else "nothing to acknowledge (unknown id, or not uncertain/failed)")
            return 0 if ok else 1
        else:
            print(json.dumps(store.recent(), indent=2, default=str))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
