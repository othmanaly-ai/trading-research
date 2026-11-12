# Graph Report - TradingProject  (2026-11-03)

## Corpus Check
- 89 files · ~57,077 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 7 file(s) not represented in the graph (top: .csv 3, .example 1, (none) 1)

## Summary
- 936 nodes · 2682 edges · 34 communities (28 shown, 6 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 232 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `827a62cd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Ledger
- server.py
- test_dashboard.py
- jobs.py
- Panels.tsx
- experiment.py
- backtest.py
- Raw Price Adjustment
- test_backtest.py
- Experiment 001: Intraday momentum in SPY (draft specification)
- package.json
- RiskLimits
- compilerOptions
- RiskState
- ReplayController
- Experiment 002-895a4f9c5d: development-period result
- verify_data_access.py
- test_orb.py
- Trading City: product specification
- make_handler
- require_order_submission_allowed
- Experiment 001-fd13f1fdef: development-period result
- sessions.py
- engine.py
- pandas
- .apply
- demo_replay.py
- Trade
- Experiment 002: Long-only opening-range breakout in SPY (specification)
- Candidates for experiment 002
- EXPLORATION_LOG.md

## God Nodes (most connected - your core abstractions)
1. `RiskLimits` - 46 edges
2. `Params` - 43 edges
3. `Ledger` - 38 edges
4. `run_backtest()` - 37 edges
5. `DayData` - 35 edges
6. `sessions_between()` - 30 edges
7. `Session` - 28 edges
8. `run_pipeline()` - 27 edges
9. `run_day()` - 26 edges
10. `replace_day()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `Run` --references--> `run_experiment()`  [INFERRED]
  research/001_intraday_momentum/RESULTS_development.md → trading/experiment.py
- `Connecting real Alpaca data (separate, not started)` --references--> `run_backtest()`  [INFERRED]
  dashboard/README.md → trading/backtest.py
- `Offline Test Suite (22 passed)` --references--> `require_order_submission_allowed()`  [INFERRED]
  PROGRESS.md → trading/safety.py
- `Order Submission Guard (TRADING_MODE=paper, ORDER_SUBMISSION_ENABLED=true)` --references--> `require_order_submission_allowed()`  [EXTRACTED]
  CLAUDE.md → trading/safety.py
- `test_client_has_no_order_methods()` --uses--> `ReadOnlyAlpacaClient`  [INFERRED]
  tests/test_alpaca_client.py → trading/alpaca_client.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Market data conventions (calendar, sessions, feeds, adjustment, bar coverage, output)** — claude_xnys_exchange_calendar, claude_completed_session_rule, claude_data_feeds_sip_iex, claude_raw_adjustment, claude_minute_bar_coverage, claude_output_layout [EXTRACTED 1.00]
- **Progress status tiers (verified, implemented-unverified, missing, limitations)** — progress_verified_components, progress_implemented_unverified, progress_missing_items, progress_known_limitations [EXTRACTED 1.00]
- **Software-enforced execution safety controls** — claude_execution_boundary, claude_allowed_hosts_guard, claude_read_only_client_rule, claude_order_submission_guard, trading_safety_require_order_submission_allowed, trading_alpaca_client [EXTRACTED 1.00]

## Communities (34 total, 6 thin omitted)

### Community 0 - "Ledger"
Cohesion: 0.18
Nodes (3): test_historical_replay_mode_and_totals(), Ledger, _net_if_closed()

### Community 1 - "server.py"
Cohesion: 0.05
Nodes (49): demo(), server(), test_invalid_config_rejected(), alpaca_payloads(), fake_client(), hist_config(), store(), test_cli_blocked_without_credentials() (+41 more)

### Community 2 - "test_dashboard.py"
Cohesion: 0.14
Nodes (12): _get(), _post(), replay_all(), test_build_is_deterministic(), test_control_requires_header_and_valid_action(), test_duplicates_do_not_double_count(), test_empty_config(), test_http_endpoints() (+4 more)

### Community 3 - "jobs.py"
Cohesion: 0.08
Nodes (25): env(), statuses(), test_corrupt_artifact_fails_then_recovers_with_new_attempt(), test_end_to_end_on_real_artifacts(), test_missing_artifact_fails_ingest_and_blocks_downstream(), test_model_review_blocked_without_key_or_authorization(), test_reconcile_detects_tampered_record(), test_retry_and_restart_never_duplicate_completed_jobs() (+17 more)

### Community 4 - "Panels.tsx"
Cohesion: 0.06
Nodes (75): App(), Boundary, CityView, prefersReducedMotion(), SUPPORTED_MODES, category(), CityView(), COLORS (+67 more)

### Community 5 - "experiment.py"
Cohesion: 0.07
Nodes (49): report(), test_classifier_agrees_with_engine_stop_exits(), test_cost_accounting_and_sensitivity(), test_event_stream_only_uses_information_available_at_each_time(), test_reports_match_city(), test_research_status_is_honest(), test_result_hash_is_reproducible_and_sensitive(), test_spec_version_and_hash() (+41 more)

### Community 6 - "backtest.py"
Cohesion: 0.14
Nodes (13): test_accounting_identity_over_a_run(), test_equity_counts_each_cost_exactly_once(), test_positions_never_held_past_close_except_halt(), test_stress_entry_failures_are_deterministic(), test_warmup_and_first_day(), _carry_exit(), DayResult, last30_return() (+5 more)

### Community 9 - "test_backtest.py"
Cohesion: 0.15
Nodes (25): run_day(), test_breach_on_scheduled_exit_bar_uses_time_exit(), test_carry_exit_counts_against_next_session_limits(), test_daily_loss_limit_uses_unrealized_and_exits_next_bar(), test_early_close_shifts_times(), test_entry_is_one_minute_after_decision_with_costs(), test_fill_fraction_halves_size(), test_future_bars_cannot_change_decision() (+17 more)

### Community 10 - "Experiment 001: Intraday momentum in SPY (draft specification)"
Cohesion: 0.09
Nodes (22): 10. Cost assumptions (to be checked against data), 11. Baselines (same window, same exposure, same sizing), 12. Periods (chronological, fixed before any data is seen), 13. Variant accounting, 14. Evaluation criteria (fixed before running), 15. Roles (performed by one model, Claude, as checklists), 16. Unresolved decisions for owner review, 17. Implementation clarifications (2026-11-03, before any data was seen) (+14 more)

### Community 12 - "package.json"
Cohesion: 0.09
Nodes (27): dependencies, react@19.3.1, react-dom@19.3.1, three@0.187.0, devDependencies, @types/react@19.3.0, @types/react-dom@19.3.0, @types/three@0.187.0 (+19 more)

### Community 13 - "RiskLimits"
Cohesion: 0.24
Nodes (11): test_baseline_notional_cap_binds_and_rounds_down(), test_entry_that_cannot_fit_is_rejected(), test_gross_exposure_includes_pending_and_open(), test_invalid_sizing_inputs_give_zero(), test_max_positions_counts_pending(), test_notional_cap_binds(), test_participation_cap_binds(), test_risk_cap_binds() (+3 more)

### Community 14 - "compilerOptions"
Cohesion: 0.12
Nodes (15): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, noFallthroughCasesInSwitch (+7 more)

### Community 15 - "RiskState"
Cohesion: 0.35
Nodes (5): test_daily_breach_uses_session_start_equity(), test_daily_loss_limit(), test_daily_losses_accumulate_across_trades_and_marks(), test_drawdown_uses_high_water_mark_and_never_resets(), RiskState

### Community 17 - "ReplayController"
Cohesion: 0.25
Nodes (5): test_controller_pause_restart_speed(), test_controller_replay_with_injected_duplicates_matches_direct(), _epoch(), ReplayController, _ticker()

### Community 18 - "Experiment 002-895a4f9c5d: development-period result"
Cohesion: 0.22
Nodes (8): Acceptance rules, Comparisons (diagnostic: fixed $5,000 per trade, no halts, dollar P&L / $100,000), Data exclusions and unresolved cases, Experiment 002-895a4f9c5d: development-period result, Limitations, Primary, full account, Recommendation, Run

### Community 19 - "verify_data_access.py"
Cohesion: 0.05
Nodes (44): Allowed Hosts (paper-api and data.alpaca.markets only), Data Check Exit Codes (0 success, 1 API failure, 2 no credentials), daytrading-starter skill (planning/analysis only), Order Submission Guard (TRADING_MODE=paper, ORDER_SUBMISSION_ENABLED=true), Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json), TradingProject (paper-trading research system), Architecture, Connecting real Alpaca data (separate, not started) (+36 more)

### Community 20 - "test_orb.py"
Cohesion: 0.08
Nodes (52): days_for(), make(), path(), run(), test_b1_b2_reproducible_unmatched_and_identical_treatment(), test_b3_entry_sizing_and_acceptance(), test_checks_function(), test_closed_experiment_refuses_runs_but_allows_inspection() (+44 more)

### Community 21 - "Trading City: product specification"
Cohesion: 0.17
Nodes (11): 1. Purpose, 2. Modes (never blended), 3. Shared records, 4. Tower detail tabs, 5. Research responsibilities, 6. Historical replay rules (for milestone 4), 7. Evaluation report contents, 8. Scenario simulation method (PROPOSED: awaiting owner review) (+3 more)

### Community 22 - "make_handler"
Cohesion: 0.47
Nodes (8): make_handler(), do_GET(), do_POST(), _headers(), _json(), _send_sse(), _static(), _stream()

### Community 23 - "require_order_submission_allowed"
Cohesion: 0.33
Nodes (5): test_blocked(), order_submission_enabled(), OrderSubmissionDisabled, require_order_submission_allowed(), trading_mode()

### Community 24 - "Experiment 001-fd13f1fdef: development-period result"
Cohesion: 0.20
Nodes (9): Cost sensitivity, Diagnosis (development data only; `diagnose_development.py`), Experiment 001-fd13f1fdef: development-period result, Limitations, Pass rules (fixed before the run), Recommendation, Reproducibility and file locations, Results (base costs, about 2.3 bp round trip) (+1 more)

### Community 25 - "sessions.py"
Cohesion: 0.07
Nodes (36): Completed Session Rule (15 min after close, SIP delay), Data Feeds: SIP (consolidated) vs IEX (single exchange), .env.example template, 1-Minute Bar Coverage ([open, close), trade-only bars), requirements.lock (full pip freeze), Setup Procedure (venv + requirements.lock), Verification Commands (pytest + verify_data_access), XNYS Exchange Calendar (America/New_York, UTC + ET timestamps) (+28 more)

### Community 26 - "engine.py"
Cohesion: 0.19
Nodes (6): test_kill_switch_blocks_after_drawdown(), _net_if_closed(), CostModel, acceptance_limit(), _carry(), execute_plan()

### Community 28 - "pandas"
Cohesion: 0.11
Nodes (18): main(), raw_minutes(), test_max_drawdown(), test_random_baseline_centered_and_percentile(), BacktestResult, utc(), bootstrap_sharpe_ci(), daily_returns() (+10 more)

### Community 29 - ".apply"
Cohesion: 0.15
Nodes (5): test_unrealized_is_marked_while_open_and_zero_after(), test_wrong_mode_event_rejected(), demo_ledger(), test_repeat_build_reproduces_reports(), _ts()

### Community 30 - "demo_replay.py"
Cohesion: 0.10
Nodes (16): bars(), test_bars_after_exit_are_ignored(), test_classification_rules(), _apply_outage(), build_demo(), build_replay(), Context, DemoReplay (+8 more)

### Community 32 - "Experiment 002: Long-only opening-range breakout in SPY (specification)"
Cohesion: 0.12
Nodes (16): 1. Notation and data, 2. Timeline (exact timestamps), 3. Strategy (primary configuration), 4. Comparisons (complete definitions), 5. Configurations and variant policy, 6. Acceptance rules, 6a. Implementation invariants (approved 2026-11-04; the hypothesis is unchanged), 7. Required tests before any evaluation (+8 more)

### Community 34 - "Candidates for experiment 002"
Cohesion: 0.33
Nodes (5): A. Long-only 30-minute opening-range breakout (recommended), B. Long-only gap-down reversal (speculative, partly contaminated), Candidates for experiment 002, How much evidence there is, Recommendation

## Knowledge Gaps
- **5 isolated node(s):** `Playwright MCP Server (connected, unused)`, `pytest==9.2.0`, `pandas==3.1.0`, `Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json)`, `Raw Adjustment Default (no split/dividend adjustment)`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 308 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Ledger` connect `Ledger` to `server.py`, `test_dashboard.py`, `experiment.py`, `ReplayController`, `.apply`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `RiskLimits` (e.g. with `run_day()` and `test_invalid_sizing_inputs_give_zero()`) actually correct?**
  _`RiskLimits` has 11 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Playwright MCP Server (connected, unused)`, `pytest==9.2.0`, `pandas==3.1.0` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `server.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05105572862582208 - nodes in this community are weakly interconnected._
- **Why does `RiskLimits` connect `RiskLimits` to `server.py`, `experiment.py`, `backtest.py`, `test_backtest.py`, `RiskState`, `test_orb.py`, `engine.py`, `demo_replay.py`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `Params` (e.g. with `run_day()` and `run_backtest()`) actually correct?**
  _`Params` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_dashboard.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14210526315789473 - nodes in this community are weakly interconnected._