# Research workflow report: Review our existing strategy failures and recommend the next research decision.

Workflow `strategy_failure_review@20261110T164747453270Z` · evidence snapshot `65c9afc345481ec3` · generated 2026-11-10T16:48:55+00:00

**What produced this.** Evidence collection and this report: deterministic code (`trading/coordinator.py`). Strategy analysis, data/cost analysis and skeptical review: specialist ROLES, each filled by a submitted document whose author and mode are listed below. Unattended model connection: **UNAVAILABLE**. Nothing here is autonomous AI.

| Role | Author | Mode |
|---|---|---|
| Strategy analyst | Claude (Opus 5.5) in the owner's interactive Claude Code session, 2026-11-10 | claude_code_session (one-time interactive response; not an unattended or autonomous agent) |
| Data and cost analyst | Claude (Opus 5.5) in the owner's interactive Claude Code session, 2026-11-10 | claude_code_session (one-time interactive response; not an unattended or autonomous agent) |
| Skeptical reviewer | Claude (Opus 5.5) in the owner's interactive Claude Code session, 2026-11-10 - SAME session that wrote both analyses | claude_code_session (self-review; not an independent reviewer and not an autonomous agent) |

## 1. Why experiments 001 and 002 failed

### 001 intraday momentum
- **S1** 001 (late-day intraday momentum) lost 1.41% after base costs and 2.99% at stress costs on 2016-2021 development data. [E4, E3] — review: accepted
- **S2** The loss existed before costs: the zero-cost re-run still lost 0.50% and the mean move per trade was about -1.2 bp; the morning signal had essentially no relation to the last 30 minutes (correlation +0.02). [E3] — review: accepted
- **S3** It ranked at about the 10th percentile of random long/flat entry, so random days did better; it failed rules 1, 2, 4 and 5 and passed only the drawdown rule. [E4, E2] — review: accepted
- **S4** The implementation was independently recomputed with 0 mismatches, so the failure is evidence against the hypothesis, not a software defect. [E3] — review: accepted

### 002 opening-range breakout
- **S5** 002 (opening-range breakout) earned a small gross edge (+$1,166 on 1,058 trades, about +2.3 bp per trade) that the base round-trip cost of 2.3 bp consumed almost exactly. [E8, E7, E9] — review: accepted
- **S6** Net was -0.014% at base costs and -2.19% at stress costs (6.6 bp round trip): the verdict depended on unmeasured cost assumptions. [E8, E9] — review: CHALLENGED (Overstated. Costs decided D1, but D4 (positive without the 10 largest winners), D5 (midpoint-stop variation negative) and D6 (83rd vs 95th percentile, where random entries pay the same costs) failed for reasons cheaper costs would not obviously fix. 002 failed on fragility as well as on cost.)
- **S7** It ranked at the 83rd percentile of the random-entry screen (95th required), lost $1,103.73 without its 10 largest winners, and one predeclared variation (midpoint stop) was negative; it failed D1, D4, D5 and D6. [E8, E7, E6] — review: accepted
- **S8** Reopening 002 with cheaper costs or promoting its best variation would be after-the-fact rescue, which the predeclared rules forbid; both experiments are closed. [E6, E2, E7] — review: accepted

## 2. What the provisional spread evidence establishes
- **D1** On the 6 pilot sessions, SPY's quoted spread was 1 cent for most of the time in every strategy window; the time-weighted half-spread was 0.12-0.25 bp per side. [E10, E11] — review: accepted
- **D2** That is below the base model's 0.5 bp half-spread assumption, so for the spread component only, on these ordinary days, the base assumption looks conservative (provisionally). [E10, E9] — review: CHALLENGED ('Conservative' applies to the spread component only, on 6 calm days, with undocumented quote semantics. It must not be read as 'the 2.3 bp base cost is too high': slippage and fees are unmeasured and could offset it.)
- **D3** The measurement pipeline worked as pre-registered: 60 of 60 windows complete, no invalid, duplicate or out-of-order records, well inside the request and storage caps. [E10, E12] — review: accepted

### …and what it does not establish
- **D4** It says nothing about stressed or high-volatility days: none of the 6 randomly chosen sessions was a known stress day, and spreads widen exactly when costs matter most. [E10] — review: accepted
- **D5** It does not measure slippage (0.5 bp per side at base) or the sell fee: quotes are not fills, so most of the 2.3 bp base round trip remains unmeasured. [E10, E9] — review: accepted
- **D6** It cannot change the cost model or any closed verdict: the pilot itself states it is not reliable enough to change trading/costs.py, and running the remaining 18 calm sessions would not make it so. [E10] — review: accepted
- **D7** Every measured quote carries the undocumented condition code '?', and the timestamp clock and NBBO construction are undocumented, so the numbers are labelled, not verified. [E10, E13] — review: accepted

## 3. Questions blocked on Alpaca
- **D8** Five questions remain open with Alpaca (A1 timestamp clock, A2 condition '?', A3 consolidated-quote construction, A4 locked/crossed meaning, A5 filtering/corrections); the support request is drafted and unsent - sending it is the owner's decision. [E13] — review: accepted
- **D9** The same answers gate the deferred gap-down candidate, which stays DEFERRED_DATA_SEMANTICS (never evaluated on performance) until all five are answered in writing. [E14, E15, E13] — review: accepted

## 4. Next research decision (PROPOSAL ONLY)

**Recommended:** Do not start a third strategy experiment now. Make resolving the quote-data semantics the next research step: the owner sends the prepared Alpaca support request (questions A1-A5) and research waits for written answers before any further data spend or hypothesis test.

**Review challenge:** Reasonable but incomplete. (1) It depends on Alpaca answering; set a date to revisit if no answer arrives, so research is not paused indefinitely. (2) The minimum-edge rule alternative needs no data and no Alpaca answer and could be adopted in parallel by the owner. (3) Even with answers, spread data alone will not measure slippage, so cost uncertainty remains.

**Alternatives:**
- Pre-register a stress-day spread stratum now (dates chosen by a public event calendar, no returns), accepting it stays PROVISIONAL until A1-A5 are answered.
- Run the remaining 18 pilot sessions (cheap, but the pilot itself expects little new information from more calm days).
- Adopt a minimum-edge rule for future specs (expected gross edge must clear the 6.6 bp stress round trip with margin) - a process change needing no data.
- Start a new hypothesis on 2016-2021 SPY - not recommended: the exploration log shows late-day, breakout and down-morning ideas already seen, and both failures hit the same cost wall.

**Evidence needed:**
- Written Alpaca answers to A1 (timestamp clock), A2 (condition '?'), A3 (NBBO construction), A4 (locked/crossed), A5 (filtering/corrections) for 2016-2021.
- For a stress stratum: a public, return-free date rule fixed in a pre-registration before any download.
- For any future hypothesis: a stated expected gross edge per trade above the stress round-trip cost, and data not already used by 001/002.

This is a proposal. It authorizes no strategy implementation, no evaluation, no data download, no experiment and no change to any lock, risk limit or acceptance rule. Only the owner can decide.

## Skeptical review summary
Self-review by the same Claude Code session that wrote the analyses - it can catch overstatement against the saved evidence but is not independent. Two claims were challenged (S6: 002 did not fail on cost alone; D2: 'conservative' covers the spread component only) and the decision was challenged for depending on an external reply with no fallback date. No claim was rejected. An independent review would need a different reviewer, for example the owner or a separately authorized model, which is currently UNAVAILABLE.

## Evidence
| Id | File | SHA-256 (first 12) |
|---|---|---|
| E1 | `research/001_intraday_momentum/SPEC.md` | `551c57bf641e` |
| E2 | `research/001_intraday_momentum/STATUS.json` | `23f0b56db719` |
| E3 | `research/001_intraday_momentum/RESULTS_development.md` | `95419f874aae` |
| E4 | `research/001_intraday_momentum/runs/20261104T001504609413Z-d11b3023b7bf.json` | `10603ef7cd41` |
| E5 | `research/002_opening_range_breakout/SPEC.md` | `49d1a3f3de58` |
| E6 | `research/002_opening_range_breakout/STATUS.json` | `8f9304922b14` |
| E7 | `research/002_opening_range_breakout/RESULTS_development.md` | `bcdc7804dd3f` |
| E8 | `research/002_opening_range_breakout/runs/20261104T034149Z.json` | `af80dda8e4c2` |
| E9 | `trading/costs.py` | `d1b51b7edc8f` |
| E10 | `feasibility/spread_measurement/FINDINGS_pilot.md` | `3c94b32043d2` |
| E11 | `feasibility/spread_measurement/findings_pilot.json` | `6c2f28e568b2` |
| E12 | `feasibility/spread_measurement/PLAN.md` | `cb9a1e275f96` |
| E13 | `feasibility/execution_data/ALPACA_SUPPORT_REQUEST_DRAFT.md` | `9b14ac906fce` |
| E14 | `research/candidates/gap_down_opening/STATUS.json` | `1aac0f902552` |
| E15 | `research/FEASIBILITY_gap_down_opening.md` | `e6926f5636b9` |
| E16 | `research/NEXT_HYPOTHESES.md` | `140777bd1d8f` |
| E17 | `research/EXPLORATION_LOG.md` | `6495767b3e2b` |
| E18 | `research/FAILURE_COMPARISON_001_002.md` | `44aa46b51f9c` |
