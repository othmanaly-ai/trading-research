# Graph Report - TradingProject  (2026-11-08)

## Corpus Check
- 172 files · ~183,783 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: .csv 3, .css 2, .example 1)

## Summary
- 2201 nodes · 6105 edges · 94 communities (86 shown, 8 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 538 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c07138ea`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_dashboard.py
- test_history.py
- build_map
- test_spread_measurement.py
- run_review
- test_monitor.py
- execution_feasibility.py
- Raw Price Adjustment
- test_backtest.py
- Experiment 001: Intraday momentum in SPY (draft specification)
- package.json
- build_package
- compilerOptions
- jobs.py
- JobStore
- Experiment 002-895a4f9c5d: development-period result
- test_orb.py
- engine.py
- Trading City: product specification
- make_handler
- server.py
- Experiment 001-fd13f1fdef: development-period result
- orb_experiment.py
- test_recovery.py
- test_evaluation.py
- readiness.py
- test_reviewer.py
- quality.py
- JobsView.tsx
- Experiment 002: Long-only opening-range breakout in SPY (specification)
- Overview.tsx
- Candidates for experiment 002
- EXPLORATION_LOG.md
- App.tsx
- test_job_api.py
- TowerPanel.tsx
- Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04)
- ReadOnlyAlpacaClient
- parse
- test_jobs.py
- demo_replay.py
- Ledger
- types.ts
- collect
- re
- trading/validate.py
- Amendment 2: quote coverage through the proposed exit (pre-registration)
- Feasibility note: gap-down opening reversal (not an experiment)
- Automated second review (model-powered reviewer)
- CityView.tsx
- create_server
- test_journal.py
- SPY bid-ask spread measurement: plan and pilot pre-registration
- Execution-data access check: pre-registration
- load_credentials
- MonitorView.tsx
- Worker
- spread_measurement.py
- Strategy City dashboard: DEMO REPLAY
- pytest
- Read-only market monitoring
- test_execution_feasibility.py
- AlpacaAccessError
- Why experiments 001 and 002 failed: a plain-English comparison
- ledger.py
- plan_gate
- iso
- Draft support request to Alpaca (NOT SENT)
- DependencyMap.tsx
- pathlib
- ReplayController
- sessions.py
- test_operations_runner.py
- runner.py
- datetime
- schedule.py
- AnthropicProvider
- CountingHttp
- Automatic market-session operation: audit and roadmap
- main
- test_risk_metrics.py
- Execution-data access check: findings (2026-11-04)
- test_cli_uses_the_600_request_cap
- classify
- workspaces.js
- Progress Record (2026-11-03)
- checks.py
- runner.py
- Milestone 1 dry run: what counts as pass, failure, interruption and incomplete
- Milestone 1: running the automatic session dry run
- SPY bid-ask spread pilot: findings (PROVISIONAL)

## God Nodes (most connected - your core abstractions)
1. `iso()` - 61 edges
2. `MonitorStore` - 49 edges
3. `RiskLimits` - 47 edges
4. `ReadOnlyAlpacaClient` - 43 edges
5. `Params` - 43 edges
6. `QualityChecker` - 40 edges
7. `sessions_between()` - 39 edges
8. `Ledger` - 38 edges
9. `run_backtest()` - 37 edges
10. `DayData` - 35 edges

## Surprising Connections (you probably didn't know these)
- `Run` --references--> `run_experiment()`  [INFERRED]
  research/001_intraday_momentum/RESULTS_development.md → trading/experiment.py
- `Milestone 3: separately authorized automatic paper trading (PAPER)` --references--> `require_order_submission_allowed()`  [INFERRED]
  docs/AUTO_TRADING_ROADMAP.md → trading/safety.py
- `Layers` --references--> `TowerSpec`  [INFERRED]
  docs/CITY.md → dashboard/web/src/components/CityView.tsx
- `Connecting real Alpaca data (separate, not started)` --references--> `bar()`  [INFERRED]
  dashboard/README.md → tests/test_quality.py
- `B. Evidence table` --references--> `load_credentials()`  [INFERRED]
  docs/AUTO_TRADING_ROADMAP.md → trading/alpaca_client.py

## Import Cycles
- 2-file cycle: `trading/jobs.py -> trading/reviewer/budget.py -> trading/jobs.py`
- 2-file cycle: `trading/jobs.py -> trading/reviewer/review.py -> trading/jobs.py`
- 2-file cycle: `trading/monitor/quality.py -> trading/monitor/reliability.py -> trading/monitor/quality.py`
- 3-file cycle: `trading/jobs.py -> trading/reviewer/review.py -> trading/reviewer/budget.py -> trading/jobs.py`
- 3-file cycle: `trading/jobs.py -> trading/reviewer/review.py -> trading/reviewer/evidence.py -> trading/jobs.py`
- 4-file cycle: `trading/jobs.py -> trading/reviewer/review.py -> trading/reviewer/validate.py -> trading/reviewer/evidence.py -> trading/jobs.py`

## Hyperedges (group relationships)
- **Market data conventions (calendar, sessions, feeds, adjustment, bar coverage, output)** — claude_xnys_exchange_calendar, claude_completed_session_rule, claude_data_feeds_sip_iex, claude_raw_adjustment, claude_minute_bar_coverage, claude_output_layout [EXTRACTED 1.00]
- **Progress status tiers (verified, implemented-unverified, missing, limitations)** — progress_verified_components, progress_implemented_unverified, progress_missing_items, progress_known_limitations [EXTRACTED 1.00]
- **Software-enforced execution safety controls** — claude_execution_boundary, claude_allowed_hosts_guard, claude_read_only_client_rule, claude_order_submission_guard, trading_safety_require_order_submission_allowed, trading_alpaca_client [EXTRACTED 1.00]

## Communities (94 total, 8 thin omitted)

### Community 0 - "test_dashboard.py"
Cohesion: 0.08
Nodes (24): demo(), _get(), _post(), replay_all(), test_build_is_deterministic(), test_candidates_overview_lists_deferred_candidate_read_only(), test_candidates_overview_tolerates_corrupt_status(), test_control_requires_header_and_valid_action() (+16 more)

### Community 1 - "test_history.py"
Cohesion: 0.14
Nodes (10): fake_client(), RoutingHttp, store(), test_final_period_download_refused(), test_load_days_round_trip_and_excludes_unusable(), test_validation_period_download_refused(), fetch_and_store(), _iso() (+2 more)

### Community 2 - "build_map"
Cohesion: 0.14
Nodes (26): by_id(), healthy(), jobs_fixture(), test_cached_job_results_are_labelled_reused(), test_collect_is_read_only_with_isolated_stores(), test_disabled_optional_review_is_not_a_blocker(), test_failed_step_blocks_dependents_as_impact_only(), test_healthy_dependencies_are_ok_and_not_blocked() (+18 more)

### Community 3 - "test_spread_measurement.py"
Cohesion: 0.13
Nodes (17): FakeData, FakeResp, q(), rule_rows(), run(), test_access_failure_stops_quotes_without_retry(), test_analyze_end_to_end_offline(), test_dense_window_is_measured_and_wide_spreads_listed() (+9 more)

### Community 4 - "run_review"
Cohesion: 0.07
Nodes (25): setup(), test_cli_env_reads_key_from_dotenv_and_bom_authorization(), review_record(), reviewer_status(), _review_availability(), _review_gate(), BudgetDenied, cost_usd() (+17 more)

### Community 5 - "test_monitor.py"
Cohesion: 0.12
Nodes (20): _call(), Clock, FakeClient, make_worker(), synthetic_bar(), test_access_errors_recorded_and_feed_never_switched(), test_connection_failures_back_off_and_reconnect(), test_dead_worker_shows_disconnected() (+12 more)

### Community 6 - "execution_feasibility.py"
Cohesion: 0.12
Nodes (19): test_coverage_reports_empty_minutes_and_dedupes_identical_only(), test_downloads_blocked_while_deferred(), test_held_out_dates_refused(), test_quote_validation_flags_crossed_and_disorder(), analyze(), analyze_coverage(), check_dates(), coverage_stats() (+11 more)

### Community 9 - "test_backtest.py"
Cohesion: 0.10
Nodes (41): days(), run_day(), test_accounting_identity_over_a_run(), test_breach_on_scheduled_exit_bar_uses_time_exit(), test_carry_exit_counts_against_next_session_limits(), test_daily_loss_limit_uses_unrealized_and_exits_next_bar(), test_early_close_shifts_times(), test_entry_is_one_minute_after_decision_with_costs() (+33 more)

### Community 10 - "Experiment 001: Intraday momentum in SPY (draft specification)"
Cohesion: 0.09
Nodes (22): 10. Cost assumptions (to be checked against data), 11. Baselines (same window, same exposure, same sizing), 12. Periods (chronological, fixed before any data is seen), 13. Variant accounting, 14. Evaluation criteria (fixed before running), 15. Roles (performed by one model, Claude, as checklists), 16. Unresolved decisions for owner review, 17. Implementation clarifications (2026-11-03, before any data was seen) (+14 more)

### Community 12 - "package.json"
Cohesion: 0.09
Nodes (26): dependencies, react@19.3.1, react-dom@19.3.1, three@0.187.0, devDependencies, @types/react@19.3.0, @types/react-dom@19.3.0, @types/three@0.187.0 (+18 more)

### Community 13 - "build_package"
Cohesion: 0.12
Nodes (17): test_evidence_scope_excludes_data_and_held_out(), test_secrets_and_local_paths_are_redacted(), build_package(), add(), EvidenceError, EvidenceTooLarge, lookup(), resolve() (+9 more)

### Community 14 - "compilerOptions"
Cohesion: 0.12
Nodes (15): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, noFallthroughCasesInSwitch (+7 more)

### Community 15 - "jobs.py"
Cohesion: 0.10
Nodes (25): How text from the artifacts is handled, What it is, and what it is not, What makes a response valid, What the reviewer receives, analysis(), execute_pipeline(), _finite(), ingest() (+17 more)

### Community 17 - "JobStore"
Cohesion: 0.08
Nodes (14): env(), job_env(), test_dashboard_blocker_wording_without_authorization(), test_server_env_strips_credentials(), test_server_job_runner_passes_no_keys(), collect(), static_relations(), jobs_snapshot() (+6 more)

### Community 18 - "Experiment 002-895a4f9c5d: development-period result"
Cohesion: 0.22
Nodes (8): Acceptance rules, Comparisons (diagnostic: fixed $5,000 per trade, no halts, dollar P&L / $100,000), Data exclusions and unresolved cases, Experiment 002-895a4f9c5d: development-period result, Limitations, Primary, full account, Recommendation, Run

### Community 19 - "test_orb.py"
Cohesion: 0.13
Nodes (41): days_for(), make(), path(), run(), test_b1_b2_reproducible_unmatched_and_identical_treatment(), test_b3_entry_sizing_and_acceptance(), test_checks_function(), test_closed_experiment_refuses_runs_but_allows_inspection() (+33 more)

### Community 20 - "engine.py"
Cohesion: 0.09
Nodes (17): main(), raw_minutes(), test_max_drawdown(), BacktestResult, _carry_exit(), last30_return(), _scheduled_exit(), _simulate_day() (+9 more)

### Community 21 - "Trading City: product specification"
Cohesion: 0.17
Nodes (11): 1. Purpose, 2. Modes (never blended), 3. Shared records, 4. Tower detail tabs, 5. Research responsibilities, 6. Historical replay rules (for milestone 4), 7. Evaluation report contents, 8. Scenario simulation method (PROPOSED: awaiting owner review) (+3 more)

### Community 22 - "make_handler"
Cohesion: 0.13
Nodes (21): experiments_overview(), build(), make_handler(), _body(), do_GET(), do_POST(), _drain(), _headers() (+13 more)

### Community 23 - "server.py"
Cohesion: 0.13
Nodes (12): test_research_status_is_honest(), test_blocked(), load_config(), _lock_status(), _order_gate(), paper_account_reason(), research_status(), safety_checks() (+4 more)

### Community 24 - "Experiment 001-fd13f1fdef: development-period result"
Cohesion: 0.20
Nodes (9): Cost sensitivity, Diagnosis (development data only; `diagnose_development.py`), Experiment 001-fd13f1fdef: development-period result, Limitations, Pass rules (fixed before the run), Recommendation, Reproducibility and file locations, Results (base costs, about 2.3 bp round trip) (+1 more)

### Community 25 - "orb_experiment.py"
Cohesion: 0.10
Nodes (17): B. Evidence table, DayData, _net_if_closed(), CostModel, acceptance_limit(), _carry(), checks(), Decision (+9 more)

### Community 26 - "test_recovery.py"
Cohesion: 0.13
Nodes (31): bar(), checker(), Clock, FakeFeeds, iso(), latest_rows(), run_until_idle(), test_access_failure_is_recorded_backs_off_and_does_not_substitute() (+23 more)

### Community 27 - "test_evaluation.py"
Cohesion: 0.09
Nodes (19): bars(), report(), test_bars_after_exit_are_ignored(), test_classification_rules(), test_cost_accounting_and_sensitivity(), test_event_stream_only_uses_information_available_at_each_time(), test_reports_match_city(), test_result_hash_is_reproducible_and_sensitive() (+11 more)

### Community 28 - "readiness.py"
Cohesion: 0.10
Nodes (29): BrokenDB, ev(), healthy(), test_closed_market_is_expected_and_healthy_state_passes(), test_database_failure_is_fail_and_recorded_after_recovery(), test_duplicate_workers_fail_but_venv_launcher_child_is_one_worker(), test_early_close_and_calendar_cross_check_states(), test_missing_evidence_is_unknown_never_pass() (+21 more)

### Community 29 - "test_reviewer.py"
Cohesion: 0.20
Nodes (27): good_answer(), item_id(), MockProvider, ok(), run(), test_artifact_instruction_injection_is_flagged_and_cannot_flip_gates(), test_cache_reuses_review_and_keys_on_evidence_prompt_and_model(), test_call_budget_per_run() (+19 more)

### Community 30 - "quality.py"
Cohesion: 0.12
Nodes (10): quality_report(), bar_defects(), boundary(), _bps(), classify(), _median(), _num(), QualityChecker (+2 more)

### Community 31 - "JobsView.tsx"
Cohesion: 0.07
Nodes (29): ACTIVE, Artifact, Boundary, Candidate, CityView, EVENT_KIND, Experiment, Experiments (+21 more)

### Community 32 - "Experiment 002: Long-only opening-range breakout in SPY (specification)"
Cohesion: 0.12
Nodes (16): 1. Notation and data, 2. Timeline (exact timestamps), 3. Strategy (primary configuration), 4. Comparisons (complete definitions), 5. Configurations and variant policy, 6. Acceptance rules, 6a. Implementation invariants (approved 2026-11-04; the hypothesis is unchanged), 7. Required tests before any evaluation (+8 more)

### Community 33 - "Overview.tsx"
Cohesion: 0.12
Nodes (20): ageText(), Boundary, C, CityView, districtTowers(), etTime(), Exps, floorStations() (+12 more)

### Community 34 - "Candidates for experiment 002"
Cohesion: 0.33
Nodes (5): A. Long-only 30-minute opening-range breakout (recommended), B. Long-only gap-down reversal (speculative, partly contaminated), Candidates for experiment 002, How much evidence there is, Recommendation

### Community 36 - "App.tsx"
Cohesion: 0.15
Nodes (17): App(), Boundary, category(), CityView, CORE(), prefersReducedMotion(), STRATEGY_COLORS, strategyTower() (+9 more)

### Community 37 - "test_job_api.py"
Cohesion: 0.22
Nodes (15): call(), setup(), start(), test_cancel_queued_pipeline_immediately(), test_cancel_running_pipeline_keeps_completed_evidence(), test_dashboard_records_match_database(), test_experiments_and_preview(), test_get_with_foreign_host_refused() (+7 more)

### Community 38 - "TowerPanel.tsx"
Cohesion: 0.12
Nodes (36): AccountPanel(), Leaderboard(), SessionHistory(), StrategyTable(), Marker, PAD, PriceChart(), DecisionsTab() (+28 more)

### Community 39 - "Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04)"
Cohesion: 0.18
Nodes (10): 1. SPY distribution calendar (`spy_distributions_development.json`), 2. Quote interpretation (official Alpaca documentation, read 2026-11-04), 3. Locked and crossed quotes (proposed treatment, not approved), 4. Quote coverage through the proposed 10:00 exit, 5. What this is not, Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04), Future operation (proposed; required before any live use), Retrospective classification vs historical availability (+2 more)

### Community 40 - "ReadOnlyAlpacaClient"
Cohesion: 0.10
Nodes (18): FakeHttp, FakeResponse, test_access_refusal_on_quotes_raises_without_retry(), test_account_keeps_only_listed_fields(), test_client_has_no_order_methods(), test_clock_is_a_paper_host_get_with_listed_fields_only(), test_corporate_actions_merge_and_cap(), test_feed_refusal_raises_and_is_not_substituted() (+10 more)

### Community 41 - "parse"
Cohesion: 0.20
Nodes (13): _parses(), test_unmonitored_scheduled_session_breaks_the_streak(), monitor_sessions(), ensure_schema(), daily_report(), _intervals_uncovered(), _median(), _secs() (+5 more)

### Community 42 - "test_jobs.py"
Cohesion: 0.20
Nodes (11): server(), statuses(), test_api_and_store_emit_strict_json(), test_corrupt_artifact_fails_then_recovers_with_new_attempt(), test_dashboard_endpoint_matches_store(), test_end_to_end_on_real_artifacts(), test_missing_artifact_fails_ingest_and_blocks_downstream(), test_model_review_unavailable_lists_every_blocker() (+3 more)

### Community 43 - "demo_replay.py"
Cohesion: 0.08
Nodes (29): test_experiment_id_changes_with_limits_and_primary_params(), _apply_outage(), build_replay(), Context, DemoReplay, _instrument_events(), _iso(), _sessions() (+21 more)

### Community 44 - "Ledger"
Cohesion: 0.12
Nodes (7): test_unrealized_is_marked_while_open_and_zero_after(), test_wrong_mode_event_rejected(), test_repeat_build_reproduces_reports(), test_historical_replay_mode_and_totals(), test_journal_mid_replay_marks_session_in_progress(), Ledger, _net_if_closed()

### Community 45 - "types.ts"
Cohesion: 0.18
Nodes (17): DEMO_VIEWS, MODE_KEYS, MODE_LABELS, REAL_VIEWS, SPEEDS, Account, Connection, EventType (+9 more)

### Community 46 - "collect"
Cohesion: 0.29
Nodes (6): Dependency-and-health map (2026-11-05), Interaction, Statuses and reasoning, Tests (`tests/test_depmap.py`, synthetic fixtures only), Verification, What is backed by what

### Community 47 - "re"
Cohesion: 0.23
Nodes (5): _imports(), test_only_data_health_opens_the_monitoring_database_and_reads_no_prices(), test_operations_imports_from_monitoring_are_limited(), test_research_code_never_imports_monitoring_or_operations(), test_operations_package_has_no_order_capable_code()

### Community 48 - "trading/validate.py"
Cohesion: 0.16
Nodes (18): Data Check Exit Codes (0 success, 1 API failure, 2 no credentials), Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json), Missing-Credential Handling (BLOCKED, exit 2, no network call), full_session(), synthetic_bar(), test_clean_synthetic_session_passes(), test_daily_coverage_maps_midnight_et_stamps_to_dates(), test_detects_each_structural_problem() (+10 more)

### Community 49 - "Amendment 2: quote coverage through the proposed exit (pre-registration)"
Cohesion: 0.40
Nodes (4): Amendment 2: quote coverage through the proposed exit (pre-registration), Dates, Requests (HTTP GET only, `https://data.alpaca.markets`), Validation (pre-declared)

### Community 50 - "Feasibility note: gap-down opening reversal (not an experiment)"
Cohesion: 0.18
Nodes (10): 0. Correction, 1. Rules using only information available at each time, 2. Previous close and opening price in real operation, 3. Can minute bars represent the opening?, 4. Prior exploration (from `EXPLORATION_LOG.md`), 5. Does it warrant an experiment now?, Feasibility note: gap-down opening reversal (not an experiment), Recommendation (+2 more)

### Community 51 - "Automated second review (model-powered reviewer)"
Cohesion: 0.15
Nodes (12): After the call, Automated second review (model-powered reviewer), Before each call, How cost enforcement works, Limitations, Owner decision (2026-11-04), Proposed limits (not yet authorized), Provider options (+4 more)

### Community 52 - "CityView.tsx"
Cohesion: 0.05
Nodes (71): Ambient, buildAmbient(), Car, Effects, Landmark, rng(), signTexture(), VEHICLES (+63 more)

### Community 53 - "create_server"
Cohesion: 0.13
Nodes (10): test_journal_endpoints(), env(), server_base(), test_supervisor_only_acts_when_desired_running(), env(), store(), test_api_panel_and_records_agree(), env() (+2 more)

### Community 54 - "test_journal.py"
Cohesion: 0.13
Nodes (14): alpaca_payloads(), hist_config(), test_held_out_periods_refused(), test_missing_data_refuses_without_fallback(), test_research_status_reflects_stored_coverage(), test_demo_research_run_writes_consistent_outputs(), test_historical_research_run_logs_inspection(), test_historical_research_run_refuses_without_data() (+6 more)

### Community 55 - "SPY bid-ask spread measurement: plan and pilot pre-registration"
Cohesion: 0.17
Nodes (11): 1. Do the open Alpaca questions block a meaningful measurement?, 2. Dates, 3. Quote windows (unchanged; regular 16:00-close sessions; times ET; start and end inclusive, as Alpaca documents), 4. Rules for each quote, 5. Measurements (pilot), 6. Pilot hard limits (implemented in `trading/spread_measurement.py`, tested before any request), 7. Limitations (repeated in the findings), 8. Decisions (+3 more)

### Community 56 - "Execution-data access check: pre-registration"
Cohesion: 0.33
Nodes (5): Dates (all in the development period, 2016-01-04 to 2021-12-31), Execution-data access check: pre-registration, Requests (HTTP GET only, host `https://data.alpaca.markets`), Storage, Validation (pre-declared)

### Community 57 - "load_credentials"
Cohesion: 0.24
Nodes (7): test_credentials_from_dotenv(), test_missing_credentials(), test_cli_blocked_without_credentials(), load_credentials(), MissingCredentials, _read_dotenv(), main()

### Community 58 - "MonitorView.tsx"
Cohesion: 0.08
Nodes (35): age(), Bar, Boundary, CityView, et(), FRESH_COLORS, LiveClock(), MON_LEGEND (+27 more)

### Community 59 - "Worker"
Cohesion: 0.13
Nodes (9): test_worker_marks_sessions_it_monitors(), git_version(), session_date_et(), code_version(), default_client_factory(), _floor_minute(), main(), _StopRequested (+1 more)

### Community 60 - "spread_measurement.py"
Cohesion: 0.12
Nodes (18): test_early_close_and_held_out_refused_even_if_listed(), test_group_summary_pools_by_time_and_excludes_partial(), st(), test_only_pilot_dates_allowed(), _popen(), analyze(), check_pilot_dates(), _codes() (+10 more)

### Community 61 - "Strategy City dashboard: DEMO REPLAY"
Cohesion: 0.25
Nodes (7): Architecture, City workspaces (Trading City / Website Agency), Connecting real Alpaca data (separate, not started), Launch, Research jobs tab (REAL records, not demo), Strategy City dashboard: DEMO REPLAY, Verification

### Community 62 - "pytest"
Cohesion: 0.11
Nodes (28): attempts(), days(), lock_path(), read_log(), run(), _run(), test_attempts_ledger_records_completed_and_refused(), test_changed_definition_refused() (+20 more)

### Community 63 - "Read-only market monitoring"
Cohesion: 0.11
Nodes (17): Behaviour, Checklist for observing several consecutive sessions, Controls, Daily report sections, Data permissions measured on 2026-11-04, Data quality: delayed SIP vs IEX (`trading/monitor/quality.py`), Finalization, Limitations (+9 more)

### Community 64 - "test_execution_feasibility.py"
Cohesion: 0.14
Nodes (5): FakeClient, FakeInner, FakeResp, test_access_failure_stops_path_without_retry_and_no_substitution(), AlpacaAccessError

### Community 65 - "AlpacaAccessError"
Cohesion: 0.14
Nodes (14): Allowed Hosts (paper-api and data.alpaca.markets only), daytrading-starter skill (planning/analysis only), Order Submission Guard (TRADING_MODE=paper, ORDER_SUBMISSION_ENABLED=true), TradingProject (paper-trading research system), Implemented, Not Yet Verified Against Real API, Missing (Alpaca connection, real data, risk controls, Playwright package), Offline Test Suite (22 passed), Playwright MCP Server (connected, unused) (+6 more)

### Community 66 - "Why experiments 001 and 002 failed: a plain-English comparison"
Cohesion: 0.22
Nodes (8): Glossary, Recommended next research task, Side by side, The two strategies in one line each, What the two failures have in common, Why 001 failed: there was no edge to begin with, Why 002 failed: a small edge, entirely eaten by costs, Why experiments 001 and 002 failed: a plain-English comparison

### Community 68 - "plan_gate"
Cohesion: 0.22
Nodes (5): _git(), test_fetch_refused_before_credentials_when_plan_not_committed(), test_plan_gate_requires_committed_unchanged_plan(), plan_gate(), PlanNotCommitted

### Community 69 - "iso"
Cohesion: 0.10
Nodes (16): _isolate_monitor(), _isolate_reviewer(), test_start_launches_once_and_supervisor_recovers_without_duplicates(), test_interval_without_run_records_is_unrecorded_not_downtime(), test_report_operations_downtime_restarts_and_failures(), test_sessions_overview_separates_on_time_catch_up_and_missing(), monitor_control(), quality_minute() (+8 more)

### Community 70 - "Draft support request to Alpaca (NOT SENT)"
Cohesion: 0.50
Nodes (3): Answers needed to resume the gap-down candidate (owner checklist), Draft support request to Alpaca (NOT SENT), Notes for the owner (not part of the message)

### Community 71 - "DependencyMap.tsx"
Cohesion: 0.15
Nodes (12): EdgeSpec, ARCH, Boundary, Cause, CityView, DependencyMap(), DepMap, MapEdge (+4 more)

### Community 72 - "pathlib"
Cohesion: 0.16
Nodes (16): green(), test_closed_failed_deferred_unknown_and_multiple_are_refused(), test_dry_run_denies_even_when_everything_else_is_green(), test_empty_registry_means_no_approved_strategy(), test_every_failing_condition_is_reported(), test_fingerprint_mismatch_and_no_approvable_state(), test_missing_or_corrupt_file_fails_closed(), test_runtime_dir_refuses_onedrive_and_project() (+8 more)

### Community 73 - "ReplayController"
Cohesion: 0.28
Nodes (5): test_controller_pause_restart_speed(), test_controller_replay_with_injected_duplicates_matches_direct(), _epoch(), ReplayController, _ticker()

### Community 74 - "sessions.py"
Cohesion: 0.40
Nodes (7): test_dst_changes_utc_open(), test_requires_timezone_aware_now(), test_session_not_completed_until_data_delay_passes(), test_thanksgiving_skipped_and_black_friday_early_close(), test_weekend_and_observed_holiday(), utc(), completed_sessions()

### Community 75 - "test_operations_runner.py"
Cohesion: 0.12
Nodes (19): et(), FakeBroker, FakeClock, simulate(), test_broker_outage_at_final_check_and_in_session(), test_holiday_does_nothing(), test_late_start_is_incomplete_and_missed_minutes_are_not_replayed(), test_machine_sleep_leaves_missing_minutes_and_heartbeat_gap() (+11 more)

### Community 76 - "runner.py"
Cohesion: 0.15
Nodes (16): test_kill_switch_on_off_and_fail_closed(), SingleInstanceLock, _history(), KillSwitchState, set_off(), set_on(), state(), main() (+8 more)

### Community 77 - "datetime"
Cohesion: 0.13
Nodes (5): test_acceptance_needs_five_consecutive_passes_with_one_fingerprint(), test_not_run_pending_and_injected_violations(), collect(), now_iso(), OpsStore

### Community 78 - "schedule.py"
Cohesion: 0.19
Nodes (14): test_dst_transitions_move_utc_times_not_et_times(), test_early_close_shifts_closing_and_report(), test_et_date_uses_new_york_not_utc(), test_holiday_and_weekend_have_no_session(), test_regular_day_phases_and_decision_minutes(), test_start_classification_late_and_missed(), U(), et_date() (+6 more)

### Community 79 - "AnthropicProvider"
Cohesion: 0.12
Nodes (13): fake_sdk(), create(), __init__(), test_anthropic_provider_error_mapping_with_mock_sdk(), behaviour(), test_anthropic_provider_success_with_mock_sdk(), test_real_sdk_error_mapping_against_closed_local_port(), AnthropicProvider (+5 more)

### Community 80 - "CountingHttp"
Cohesion: 0.33
Nodes (3): test_counting_http_enforces_cap_and_logs_no_headers(), CountingHttp, RequestCapReached

### Community 81 - "Automatic market-session operation: audit and roadmap"
Cohesion: 0.10
Nodes (20): A. Goal and present blockers (plain English), Any live pilot, Automatic market-session operation: audit and roadmap, C. Architecture, D. Operating-state model, E. Failure-response matrix, F. Prioritized milestone plan, G. Owner decisions that block Milestone 1 (+12 more)

### Community 82 - "main"
Cohesion: 0.33
Nodes (4): _serve(), test_existing_server_detection(), existing_server(), main()

### Community 83 - "test_risk_metrics.py"
Cohesion: 0.11
Nodes (18): test_baseline_notional_cap_binds_and_rounds_down(), test_cost_levels_ordered_and_round_trip(), test_daily_breach_uses_session_start_equity(), test_daily_loss_limit(), test_daily_losses_accumulate_across_trades_and_marks(), test_drawdown_uses_high_water_mark_and_never_resets(), test_entry_that_cannot_fit_is_rejected(), test_gross_exposure_includes_pending_and_open() (+10 more)

### Community 84 - "Execution-data access check: findings (2026-11-04)"
Cohesion: 0.29
Nodes (6): 1. Historical SIP quotes, 09:30-09:35 ET, 2. Raw SIP minute bars, 09:30-10:02 ET, 3. Prior raw closes and corporate actions, 4. Limitations of this execution data, Conclusion on feasibility, Execution-data access check: findings (2026-11-04)

### Community 87 - "workspaces.js"
Cohesion: 0.83
Nodes (3): check(), probe(), select()

### Community 90 - "Progress Record (2026-11-03)"
Cohesion: 0.17
Nodes (11): Completed Session Rule (15 min after close, SIP delay), Data Feeds: SIP (consolidated) vs IEX (single exchange), .env.example template, 1-Minute Bar Coverage ([open, close), trade-only bars), requirements.lock (full pip freeze), Setup Procedure (venv + requirements.lock), Verification Commands (pytest + verify_data_access), XNYS Exchange Calendar (America/New_York, UTC + ET timestamps) (+3 more)

### Community 91 - "checks.py"
Cohesion: 0.16
Nodes (7): test_recorded_data_health_has_no_market_values(), env(), test_data_health_reads_monitor_store(), local_checks(), _parse(), read(), DataHealth

### Community 96 - "runner.py"
Cohesion: 0.12
Nodes (11): test_committed_code_state_shape(), test_report_records_the_committed_code_version(), account_check(), calendar_agreement(), clock_check(), _parse(), broker_checks(), code_fingerprint() (+3 more)

### Community 97 - "Milestone 1 dry run: what counts as pass, failure, interruption and incomplete"
Cohesion: 0.20
Nodes (9): Counting five consecutive sessions, FAIL: a safety or correctness violation, Fixed parameters, INCOMPLETE: not enough evidence to judge, INTERRUPTED: it started properly, but operation broke, Milestone 1 dry run: what counts as pass, failure, interruption and incomplete, PASS: all of these, with evidence, Principle: missing evidence is never a pass (+1 more)

### Community 100 - "Milestone 1: running the automatic session dry run"
Cohesion: 0.33
Nodes (5): Each trading day, Known limitations, Milestone 1: running the automatic session dry run, Other commands (none of them place orders), What it checks

### Community 101 - "SPY bid-ask spread pilot: findings (PROVISIONAL)"
Cohesion: 0.33
Nodes (5): 1. Coverage and exclusions, 2. Provisional spread measurements, 3. Actual resource usage, 4. Reliability, and whether the remaining 18 sessions are justified, SPY bid-ask spread pilot: findings (PROVISIONAL)

## Knowledge Gaps
- **5 isolated node(s):** `Playwright MCP Server (connected, unused)`, `pytest==9.2.0`, `Raw Adjustment Default (no split/dividend adjustment)`, `pandas==3.1.0`, `Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json)`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 749 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ReadOnlyAlpacaClient` connect `ReadOnlyAlpacaClient` to `runner.py`, `AlpacaAccessError`, `test_history.py`, `test_spread_measurement.py`, `execution_feasibility.py`, `demo_replay.py`, `runner.py`, `trading/validate.py`, `load_credentials`, `Worker`, `spread_measurement.py`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `iso()` (e.g. with `healthy()` and `jobs_fixture()`) actually correct?**
  _`iso()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Playwright MCP Server (connected, unused)`, `pytest==9.2.0`, `Raw Adjustment Default (no split/dividend adjustment)` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_dashboard.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07564102564102564 - nodes in this community are weakly interconnected._
- **Why does `RiskLimits` connect `test_backtest.py` to `demo_replay.py`, `test_orb.py`, `test_risk_metrics.py`, `engine.py`, `server.py`, `orb_experiment.py`, `test_evaluation.py`, `pytest`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Should `test_history.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1380952380952381 - nodes in this community are weakly interconnected._
- **Why does `sessions_between()` connect `demo_replay.py` to `test_history.py`, `iso`, `test_backtest.py`, `test_operations_runner.py`, `schedule.py`, `test_orb.py`, `engine.py`, `server.py`, `orb_experiment.py`, `test_evaluation.py`, `readiness.py`, `pytest`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._