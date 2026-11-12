# Graph Report - TradingProject  (2026-11-08)

## Corpus Check
- 168 files · ~176,062 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: .csv 3, .css 2, .example 1)

## Summary
- 2119 nodes · 5843 edges · 103 communities (93 shown, 10 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 525 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `cd3ba7d6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_dashboard.py
- RoutingHttp
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
- require_order_submission_allowed
- Experiment 001-fd13f1fdef: development-period result
- DayData
- test_recovery.py
- test_evaluation.py
- _isolate_monitor
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
- orb_experiment.py
- test_jobs.py
- server.py
- Ledger
- types.ts
- collect
- demo_replay.py
- trading/validate.py
- Amendment 2: quote coverage through the proposed exit (pre-registration)
- Feasibility note: gap-down opening reversal (not an experiment)
- Automated second review (model-powered reviewer)
- CityView.tsx
- control.py
- test_journal.py
- SPY bid-ask spread measurement: plan and pilot pre-registration
- Execution-data access check: pre-registration
- metrics.py
- MonitorView.tsx
- Worker
- spread_measurement.py
- Strategy City dashboard: DEMO REPLAY
- pytest
- Read-only market monitoring
- test_execution_feasibility.py
- AlpacaAccessError
- Why experiments 001 and 002 failed: a plain-English comparison
- experiment_lock.py
- The city: architectural district (2026-11-05)
- MonitorStore
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
- architecture.ts
- Automatic market-session operation: audit and roadmap
- experiment.py
- RiskLimits
- Execution-data access check: findings (2026-11-04)
- Params
- classify
- workspaces.js
- review.py
- .block
- Progress Record (2026-11-03)
- checks.py
- verify_data_access.py
- ambient.ts
- RiskState
- window_stats
- .run
- Milestone 1 dry run: what counts as pass, failure, interruption and incomplete
- fixtures/synthetic.py
- monitor/store.py
- Milestone 1: running the automatic session dry run
- SPY bid-ask spread pilot: findings (PROVISIONAL)
- What it is, and what it is not

## God Nodes (most connected - your core abstractions)
1. `iso()` - 50 edges
2. `RiskLimits` - 47 edges
3. `MonitorStore` - 44 edges
4. `ReadOnlyAlpacaClient` - 43 edges
5. `Params` - 43 edges
6. `QualityChecker` - 40 edges
7. `Ledger` - 38 edges
8. `run_backtest()` - 37 edges
9. `sessions_between()` - 36 edges
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
- 2-file cycle: `trading/monitor/quality.py -> trading/monitor/reliability.py -> trading/monitor/quality.py`
- 2-file cycle: `trading/jobs.py -> trading/reviewer/budget.py -> trading/jobs.py`
- 2-file cycle: `trading/jobs.py -> trading/reviewer/review.py -> trading/jobs.py`
- 3-file cycle: `trading/jobs.py -> trading/reviewer/review.py -> trading/reviewer/budget.py -> trading/jobs.py`
- 3-file cycle: `trading/jobs.py -> trading/reviewer/review.py -> trading/reviewer/evidence.py -> trading/jobs.py`
- 4-file cycle: `trading/jobs.py -> trading/reviewer/review.py -> trading/reviewer/validate.py -> trading/reviewer/evidence.py -> trading/jobs.py`

## Hyperedges (group relationships)
- **Market data conventions (calendar, sessions, feeds, adjustment, bar coverage, output)** — claude_xnys_exchange_calendar, claude_completed_session_rule, claude_data_feeds_sip_iex, claude_raw_adjustment, claude_minute_bar_coverage, claude_output_layout [EXTRACTED 1.00]
- **Progress status tiers (verified, implemented-unverified, missing, limitations)** — progress_verified_components, progress_implemented_unverified, progress_missing_items, progress_known_limitations [EXTRACTED 1.00]
- **Software-enforced execution safety controls** — claude_execution_boundary, claude_allowed_hosts_guard, claude_read_only_client_rule, claude_order_submission_guard, trading_safety_require_order_submission_allowed, trading_alpaca_client [EXTRACTED 1.00]

## Communities (103 total, 10 thin omitted)

### Community 0 - "test_dashboard.py"
Cohesion: 0.09
Nodes (21): demo(), _get(), _post(), replay_all(), test_build_is_deterministic(), test_candidates_overview_lists_deferred_candidate_read_only(), test_candidates_overview_tolerates_corrupt_status(), test_control_requires_header_and_valid_action() (+13 more)

### Community 2 - "build_map"
Cohesion: 0.12
Nodes (28): by_id(), healthy(), jobs_fixture(), test_cached_job_results_are_labelled_reused(), test_collect_is_read_only_with_isolated_stores(), test_disabled_optional_review_is_not_a_blocker(), test_failed_step_blocks_dependents_as_impact_only(), test_healthy_dependencies_are_ok_and_not_blocked() (+20 more)

### Community 3 - "test_spread_measurement.py"
Cohesion: 0.13
Nodes (14): FakeData, FakeResp, _git(), run(), test_access_failure_stops_quotes_without_retry(), test_analyze_end_to_end_offline(), test_cli_uses_the_600_request_cap(), test_fetch_counts_every_page_and_records_usage() (+6 more)

### Community 4 - "run_review"
Cohesion: 0.09
Nodes (17): setup(), review_record(), reviewer_status(), _review_availability(), _review_gate(), BudgetDenied, cost_usd(), load_authorization() (+9 more)

### Community 5 - "test_monitor.py"
Cohesion: 0.11
Nodes (22): _call(), Clock, env(), FakeClient, make_worker(), server_base(), synthetic_bar(), test_access_errors_recorded_and_feed_never_switched() (+14 more)

### Community 6 - "execution_feasibility.py"
Cohesion: 0.16
Nodes (16): test_downloads_blocked_while_deferred(), analyze(), analyze_coverage(), check_dates(), coverage_stats(), downloads_blocked(), et_utc(), fetch() (+8 more)

### Community 9 - "test_backtest.py"
Cohesion: 0.17
Nodes (24): run_day(), test_breach_on_scheduled_exit_bar_uses_time_exit(), test_daily_loss_limit_uses_unrealized_and_exits_next_bar(), test_early_close_shifts_times(), test_entry_is_one_minute_after_decision_with_costs(), test_fill_fraction_halves_size(), test_future_bars_cannot_change_decision(), test_gap_before_decision_skips() (+16 more)

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
Cohesion: 0.16
Nodes (17): analysis(), execute_pipeline(), ingest(), inventory(), _keys(), _load_csv(), plan_pipeline(), _plan_rows() (+9 more)

### Community 17 - "JobStore"
Cohesion: 0.08
Nodes (13): env(), job_env(), test_cli_env_reads_key_from_dotenv_and_bom_authorization(), test_server_job_runner_passes_no_keys(), jobs_snapshot(), _finite(), JobRunner, JobStore (+5 more)

### Community 18 - "Experiment 002-895a4f9c5d: development-period result"
Cohesion: 0.22
Nodes (8): Acceptance rules, Comparisons (diagnostic: fixed $5,000 per trade, no halts, dollar P&L / $100,000), Data exclusions and unresolved cases, Experiment 002-895a4f9c5d: development-period result, Limitations, Primary, full account, Recommendation, Run

### Community 19 - "test_orb.py"
Cohesion: 0.28
Nodes (26): days_for(), make(), path(), run(), test_b1_b2_reproducible_unmatched_and_identical_treatment(), test_b3_entry_sizing_and_acceptance(), test_checks_function(), test_completed_bar_signal_then_next_open_entry_and_c1_open_exit() (+18 more)

### Community 20 - "engine.py"
Cohesion: 0.08
Nodes (16): main(), raw_minutes(), BacktestResult, _carry_exit(), DayResult, last30_return(), _net_if_closed(), _scheduled_exit() (+8 more)

### Community 21 - "Trading City: product specification"
Cohesion: 0.17
Nodes (11): 1. Purpose, 2. Modes (never blended), 3. Shared records, 4. Tower detail tabs, 5. Research responsibilities, 6. Historical replay rules (for milestone 4), 7. Evaluation report contents, 8. Scenario simulation method (PROPOSED: awaiting owner review) (+3 more)

### Community 22 - "make_handler"
Cohesion: 0.15
Nodes (20): st(), experiments_overview(), build(), make_handler(), _body(), do_GET(), do_POST(), _drain() (+12 more)

### Community 23 - "require_order_submission_allowed"
Cohesion: 0.28
Nodes (7): test_blocked(), _order_gate(), safety_checks(), order_submission_enabled(), OrderSubmissionDisabled, require_order_submission_allowed(), trading_mode()

### Community 24 - "Experiment 001-fd13f1fdef: development-period result"
Cohesion: 0.20
Nodes (9): Cost sensitivity, Diagnosis (development data only; `diagnose_development.py`), Experiment 001-fd13f1fdef: development-period result, Limitations, Pass rules (fixed before the run), Recommendation, Reproducibility and file locations, Results (base costs, about 2.3 bp round trip) (+1 more)

### Community 25 - "DayData"
Cohesion: 0.14
Nodes (10): DayData, _carry(), checks(), Decision, EntryPlan, first_bad_minute(), SessionStrategy, AlwaysLongB3 (+2 more)

### Community 26 - "test_recovery.py"
Cohesion: 0.11
Nodes (34): bar(), checker(), Clock, FakeFeeds, iso(), latest_rows(), run_until_idle(), test_access_failure_is_recorded_backs_off_and_does_not_substitute() (+26 more)

### Community 27 - "test_evaluation.py"
Cohesion: 0.10
Nodes (14): bars(), report(), test_bars_after_exit_are_ignored(), test_classification_rules(), test_cost_accounting_and_sensitivity(), test_event_stream_only_uses_information_available_at_each_time(), test_reports_match_city(), test_research_status_is_honest() (+6 more)

### Community 29 - "test_reviewer.py"
Cohesion: 0.20
Nodes (27): good_answer(), item_id(), MockProvider, ok(), run(), test_artifact_instruction_injection_is_flagged_and_cannot_flip_gates(), test_cache_reuses_review_and_keys_on_evidence_prompt_and_model(), test_call_budget_per_run() (+19 more)

### Community 30 - "quality.py"
Cohesion: 0.13
Nodes (13): _parses(), quality_report(), bar_defects(), boundary(), _bps(), classify(), _median(), _num() (+5 more)

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
Cohesion: 0.14
Nodes (18): App(), Boundary, category(), CityView, CORE(), prefersReducedMotion(), STRATEGY_COLORS, strategyTower() (+10 more)

### Community 37 - "test_job_api.py"
Cohesion: 0.22
Nodes (15): call(), setup(), start(), test_cancel_queued_pipeline_immediately(), test_cancel_running_pipeline_keeps_completed_evidence(), test_dashboard_records_match_database(), test_experiments_and_preview(), test_get_with_foreign_host_refused() (+7 more)

### Community 38 - "TowerPanel.tsx"
Cohesion: 0.16
Nodes (29): AccountPanel(), Leaderboard(), StrategyTable(), Marker, PAD, PriceChart(), DecisionsTab(), HistoricalTab() (+21 more)

### Community 39 - "Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04)"
Cohesion: 0.18
Nodes (10): 1. SPY distribution calendar (`spy_distributions_development.json`), 2. Quote interpretation (official Alpaca documentation, read 2026-11-04), 3. Locked and crossed quotes (proposed treatment, not approved), 4. Quote coverage through the proposed 10:00 exit, 5. What this is not, Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04), Future operation (proposed; required before any live use), Retrospective classification vs historical availability (+2 more)

### Community 40 - "ReadOnlyAlpacaClient"
Cohesion: 0.10
Nodes (18): Connecting real Alpaca data (separate, not started), FakeHttp, FakeResponse, test_access_refusal_on_quotes_raises_without_retry(), test_account_keeps_only_listed_fields(), test_client_has_no_order_methods(), test_clock_is_a_paper_host_get_with_listed_fields_only(), test_corporate_actions_merge_and_cap() (+10 more)

### Community 41 - "orb_experiment.py"
Cohesion: 0.22
Nodes (16): test_journal_endpoints(), test_closed_experiment_refuses_runs_but_allows_inspection(), test_lock_refuses_changed_definition_and_dirty_tree(), test_only_four_configurations_and_held_out_refused(), check_lock(), experiment_id(), fingerprint(), _git_commit() (+8 more)

### Community 42 - "test_jobs.py"
Cohesion: 0.17
Nodes (12): server(), statuses(), test_api_and_store_emit_strict_json(), test_corrupt_artifact_fails_then_recovers_with_new_attempt(), test_dashboard_endpoint_matches_store(), test_end_to_end_on_real_artifacts(), test_missing_artifact_fails_ingest_and_blocks_downstream(), test_model_review_unavailable_lists_every_blocker() (+4 more)

### Community 43 - "server.py"
Cohesion: 0.08
Nodes (29): hist_config(), test_cli_blocked_without_credentials(), test_final_period_download_refused(), test_held_out_periods_refused(), test_historical_replay_mode_and_totals(), test_load_days_round_trip_and_excludes_unusable(), test_missing_data_refuses_without_fallback(), test_research_status_reflects_stored_coverage() (+21 more)

### Community 44 - "Ledger"
Cohesion: 0.10
Nodes (8): test_unrealized_is_marked_while_open_and_zero_after(), test_wrong_mode_event_rejected(), demo_ledger(), test_repeat_build_reproduces_reports(), demo(), Ledger, _net_if_closed(), _ts()

### Community 45 - "types.ts"
Cohesion: 0.14
Nodes (23): DEMO_VIEWS, MODE_KEYS, MODE_LABELS, REAL_VIEWS, SPEEDS, Props, utc(), Account (+15 more)

### Community 46 - "collect"
Cohesion: 0.29
Nodes (6): Dependency-and-health map (2026-11-05), Interaction, Statuses and reasoning, Tests (`tests/test_depmap.py`, synthetic fixtures only), Verification, What is backed by what

### Community 47 - "demo_replay.py"
Cohesion: 0.22
Nodes (12): _apply_outage(), build_demo(), build_replay(), Context, DemoReplay, _instrument_events(), _iso(), _sessions() (+4 more)

### Community 48 - "trading/validate.py"
Cohesion: 0.24
Nodes (11): full_session(), synthetic_bar(), test_clean_synthetic_session_passes(), test_daily_coverage_maps_midnight_et_stamps_to_dates(), test_detects_each_structural_problem(), test_minute_gaps_and_outside_bars_reported(), bars_to_frame(), check_bars() (+3 more)

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
Cohesion: 0.15
Nodes (20): buildArchetype(), Built, makeKit(), Archetype, ARCHETYPE_LABEL, ARCHETYPES, PALETTE, CityMode (+12 more)

### Community 54 - "test_journal.py"
Cohesion: 0.14
Nodes (14): alpaca_payloads(), fake_client(), store(), test_demo_research_run_writes_consistent_outputs(), test_historical_research_run_logs_inspection(), test_historical_research_run_refuses_without_data(), test_journal_matches_ledger_engine_and_report(), test_journal_mid_replay_marks_session_in_progress() (+6 more)

### Community 55 - "SPY bid-ask spread measurement: plan and pilot pre-registration"
Cohesion: 0.17
Nodes (11): 1. Do the open Alpaca questions block a meaningful measurement?, 2. Dates, 3. Quote windows (unchanged; regular 16:00-close sessions; times ET; start and end inclusive, as Alpaca documents), 4. Rules for each quote, 5. Measurements (pilot), 6. Pilot hard limits (implemented in `trading/spread_measurement.py`, tested before any request), 7. Limitations (repeated in the findings), 8. Decisions (+3 more)

### Community 56 - "Execution-data access check: pre-registration"
Cohesion: 0.33
Nodes (5): Dates (all in the development period, 2016-01-04 to 2021-12-31), Execution-data access check: pre-registration, Requests (HTTP GET only, host `https://data.alpaca.markets`), Storage, Validation (pre-declared)

### Community 57 - "metrics.py"
Cohesion: 0.19
Nodes (10): bootstrap_sharpe_ci(), daily_returns(), equity_curve(), max_drawdown(), sharpe(), summarize(), _account(), diagnostic_trades() (+2 more)

### Community 58 - "MonitorView.tsx"
Cohesion: 0.10
Nodes (28): age(), Bar, Boundary, CityView, et(), FRESH_COLORS, LiveClock(), MON_LEGEND (+20 more)

### Community 59 - "Worker"
Cohesion: 0.11
Nodes (7): test_connection_failures_back_off_and_reconnect(), test_worker_marks_sessions_it_monitors(), code_version(), _floor_minute(), main(), _StopRequested, Worker

### Community 60 - "spread_measurement.py"
Cohesion: 0.11
Nodes (16): test_early_close_and_held_out_refused_even_if_listed(), test_fetch_refused_before_credentials_when_plan_not_committed(), test_group_summary_pools_by_time_and_excludes_partial(), test_only_pilot_dates_allowed(), RequestCapReached, analyze(), check_pilot_dates(), _codes() (+8 more)

### Community 61 - "Strategy City dashboard: DEMO REPLAY"
Cohesion: 0.29
Nodes (6): Architecture, City workspaces (Trading City / Website Agency), Launch, Research jobs tab (REAL records, not demo), Strategy City dashboard: DEMO REPLAY, Verification

### Community 62 - "pytest"
Cohesion: 0.21
Nodes (18): attempts(), days(), lock_path(), read_log(), run(), _run(), test_attempts_ledger_records_completed_and_refused(), test_changed_definition_refused() (+10 more)

### Community 63 - "Read-only market monitoring"
Cohesion: 0.12
Nodes (15): Behaviour, Checklist for observing several consecutive sessions, Controls, Daily report sections, Data permissions measured on 2026-11-04, Data quality: delayed SIP vs IEX (`trading/monitor/quality.py`), Finalization, Limitations (+7 more)

### Community 64 - "test_execution_feasibility.py"
Cohesion: 0.12
Nodes (9): FakeClient, FakeInner, FakeResp, test_access_failure_stops_path_without_retry_and_no_substitution(), test_counting_http_enforces_cap_and_logs_no_headers(), test_coverage_reports_empty_minutes_and_dedupes_identical_only(), test_held_out_dates_refused(), test_quote_validation_flags_crossed_and_disorder() (+1 more)

### Community 65 - "AlpacaAccessError"
Cohesion: 0.10
Nodes (17): Allowed Hosts (paper-api and data.alpaca.markets only), daytrading-starter skill (planning/analysis only), Order Submission Guard (TRADING_MODE=paper, ORDER_SUBMISSION_ENABLED=true), Missing (Alpaca connection, real data, risk controls, Playwright package), Offline Test Suite (22 passed), Playwright MCP Server (connected, unused), Risk Controls Gap (no position sizing or loss limits), Verified Components (Python 3.15.2, Git, ignore rules, deps, tests) (+9 more)

### Community 66 - "Why experiments 001 and 002 failed: a plain-English comparison"
Cohesion: 0.22
Nodes (8): Glossary, Recommended next research task, Side by side, The two strategies in one line each, What the two failures have in common, Why 001 failed: there was no edge to begin with, Why 002 failed: a small edge, entirely eaten by costs, Why experiments 001 and 002 failed: a plain-English comparison

### Community 67 - "experiment_lock.py"
Cohesion: 0.23
Nodes (7): test_experiment_id_changes_with_limits_and_primary_params(), build_lock(), check_lock(), data_inspection_status(), experiment_id(), fingerprint(), main()

### Community 68 - "The city: architectural district (2026-11-05)"
Cohesion: 0.14
Nodes (13): Ambient life and real events (2026-11-05, second pass), Building vocabulary (procedural, no external assets), Controls and access, Decorative (no data; module `city/ambient.ts`), Deferred, Effects, Effects levels, Measured performance (2026-11-05, in-app Chromium, 1213×618, pixel ratio 1) (+5 more)

### Community 69 - "MonitorStore"
Cohesion: 0.10
Nodes (21): test_start_launches_once_and_supervisor_recovers_without_duplicates(), env(), env(), monitor_control(), monitor_report(), monitor_sessions(), quality_minute(), launch() (+13 more)

### Community 70 - "Draft support request to Alpaca (NOT SENT)"
Cohesion: 0.50
Nodes (3): Answers needed to resume the gap-down candidate (owner checklist), Draft support request to Alpaca (NOT SENT), Notes for the owner (not part of the message)

### Community 71 - "DependencyMap.tsx"
Cohesion: 0.13
Nodes (14): EdgeSpec, TowerSpec, ARCH, Boundary, Cause, CityView, DependencyMap(), DepMap (+6 more)

### Community 72 - "pathlib"
Cohesion: 0.08
Nodes (25): test_spec_version_and_hash(), green(), test_closed_failed_deferred_unknown_and_multiple_are_refused(), test_dry_run_denies_even_when_everything_else_is_green(), test_empty_registry_means_no_approved_strategy(), test_every_failing_condition_is_reported(), test_fingerprint_mismatch_and_no_approvable_state(), test_missing_or_corrupt_file_fails_closed() (+17 more)

### Community 73 - "ReplayController"
Cohesion: 0.32
Nodes (4): test_controller_pause_restart_speed(), test_controller_replay_with_injected_duplicates_matches_direct(), ReplayController, _ticker()

### Community 74 - "sessions.py"
Cohesion: 0.24
Nodes (9): test_dst_changes_utc_open(), test_requires_timezone_aware_now(), test_session_not_completed_until_data_delay_passes(), test_thanksgiving_skipped_and_black_friday_early_close(), test_weekend_and_observed_holiday(), utc(), _calendar(), completed_sessions() (+1 more)

### Community 75 - "test_operations_runner.py"
Cohesion: 0.12
Nodes (19): et(), FakeBroker, FakeClock, simulate(), test_broker_outage_at_final_check_and_in_session(), test_holiday_does_nothing(), test_late_start_is_incomplete_and_missed_minutes_are_not_replayed(), test_machine_sleep_leaves_missing_minutes_and_heartbeat_gap() (+11 more)

### Community 76 - "runner.py"
Cohesion: 0.14
Nodes (16): test_kill_switch_on_off_and_fail_closed(), SingleInstanceLock, _history(), KillSwitchState, set_off(), set_on(), state(), main() (+8 more)

### Community 77 - "datetime"
Cohesion: 0.12
Nodes (4): test_acceptance_needs_five_consecutive_passes_with_one_fingerprint(), collect(), now_iso(), OpsStore

### Community 78 - "schedule.py"
Cohesion: 0.18
Nodes (14): test_dst_transitions_move_utc_times_not_et_times(), test_early_close_shifts_closing_and_report(), test_et_date_uses_new_york_not_utc(), test_holiday_and_weekend_have_no_session(), test_regular_day_phases_and_decision_minutes(), test_start_classification_late_and_missed(), U(), et_date() (+6 more)

### Community 79 - "AnthropicProvider"
Cohesion: 0.12
Nodes (13): fake_sdk(), create(), __init__(), test_anthropic_provider_error_mapping_with_mock_sdk(), behaviour(), test_anthropic_provider_success_with_mock_sdk(), test_real_sdk_error_mapping_against_closed_local_port(), AnthropicProvider (+5 more)

### Community 80 - "architecture.ts"
Cohesion: 0.19
Nodes (17): BUILDERS, Kit, worldUV(), buildScenery(), rng(), Scenery, skyDome(), BAY_W (+9 more)

### Community 81 - "Automatic market-session operation: audit and roadmap"
Cohesion: 0.10
Nodes (20): A. Goal and present blockers (plain English), Any live pilot, Automatic market-session operation: audit and roadmap, C. Architecture, D. Operating-state model, E. Failure-response matrix, F. Prioritized milestone plan, G. Owner decisions that block Milestone 1 (+12 more)

### Community 82 - "experiment.py"
Cohesion: 0.17
Nodes (12): test_random_baseline_centered_and_percentile(), _check_allowed(), _evaluate(), _git_commit(), _held_out_inspection(), _log_attempt(), _pass_rules(), _pct() (+4 more)

### Community 83 - "RiskLimits"
Cohesion: 0.22
Nodes (14): B. Evidence table, test_baseline_notional_cap_binds_and_rounds_down(), test_cost_levels_ordered_and_round_trip(), test_entry_that_cannot_fit_is_rejected(), test_gross_exposure_includes_pending_and_open(), test_invalid_sizing_inputs_give_zero(), test_max_drawdown(), test_max_positions_counts_pending() (+6 more)

### Community 84 - "Execution-data access check: findings (2026-11-04)"
Cohesion: 0.29
Nodes (6): 1. Historical SIP quotes, 09:30-09:35 ET, 2. Raw SIP minute bars, 09:30-10:02 ET, 3. Prior raw closes and corporate actions, 4. Limitations of this execution data, Conclusion on feasibility, Execution-data access check: findings (2026-11-04)

### Community 85 - "Params"
Cohesion: 0.20
Nodes (14): days(), test_accounting_identity_over_a_run(), test_carry_exit_counts_against_next_session_limits(), test_equity_counts_each_cost_exactly_once(), test_kill_switch_blocks_after_drawdown(), test_positions_never_held_past_close_except_halt(), test_stress_entry_failures_are_deterministic(), test_warmup_and_first_day() (+6 more)

### Community 87 - "workspaces.js"
Cohesion: 0.83
Nodes (3): check(), probe(), select()

### Community 88 - "review.py"
Cohesion: 0.15
Nodes (9): test_dashboard_blocker_wording_without_authorization(), test_server_env_strips_credentials(), render_user_message(), _blocked(), cache_key(), estimate_input_tokens(), run_review(), server_env() (+1 more)

### Community 89 - ".block"
Cohesion: 0.46
Nodes (8): Builder, command(), construction(), finned(), operations(), paired(), terraced(), twisted()

### Community 90 - "Progress Record (2026-11-03)"
Cohesion: 0.13
Nodes (15): Completed Session Rule (15 min after close, SIP delay), Data Feeds: SIP (consolidated) vs IEX (single exchange), .env.example template, 1-Minute Bar Coverage ([open, close), trade-only bars), requirements.lock (full pip freeze), Setup Procedure (venv + requirements.lock), TradingProject (paper-trading research system), Verification Commands (pytest + verify_data_access) (+7 more)

### Community 91 - "checks.py"
Cohesion: 0.19
Nodes (6): account_check(), calendar_agreement(), clock_check(), _parse(), broker_checks(), local_checks()

### Community 92 - "verify_data_access.py"
Cohesion: 0.24
Nodes (8): Data Check Exit Codes (0 success, 1 API failure, 2 no credentials), Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json), Missing-Credential Handling (BLOCKED, exit 2, no network call), test_verify_refuses_held_out_sample_before_network(), _iso(), main(), _now(), _write_json()

### Community 93 - "ambient.ts"
Cohesion: 0.20
Nodes (11): Ambient, buildAmbient(), Car, Effects, Landmark, rng(), signTexture(), VEHICLES (+3 more)

### Community 94 - "RiskState"
Cohesion: 0.35
Nodes (5): test_daily_breach_uses_session_start_equity(), test_daily_loss_limit(), test_daily_losses_accumulate_across_trades_and_marks(), test_drawdown_uses_high_water_mark_and_never_resets(), RiskState

### Community 95 - "window_stats"
Cohesion: 0.25
Nodes (10): q(), rule_rows(), test_dense_window_is_measured_and_wide_spreads_listed(), test_quote_rules_counts_and_time_shares(), test_snapshots_ok_ambiguous_unresolved(), test_spread_statistics_hand_computed(), _r(), window_stats() (+2 more)

### Community 96 - ".run"
Cohesion: 0.36
Nodes (3): code_fingerprint(), code_version(), Runner

### Community 97 - "Milestone 1 dry run: what counts as pass, failure, interruption and incomplete"
Cohesion: 0.20
Nodes (9): Counting five consecutive sessions, FAIL: a safety or correctness violation, Fixed parameters, INCOMPLETE: not enough evidence to judge, INTERRUPTED: it started properly, but operation broke, Milestone 1 dry run: what counts as pass, failure, interruption and incomplete, PASS: all of these, with evidence, Principle: missing evidence is never a pass (+1 more)

### Community 99 - "monitor/store.py"
Cohesion: 0.32
Nodes (4): _freshness(), market_state(), session_date_et(), _tz()

### Community 100 - "Milestone 1: running the automatic session dry run"
Cohesion: 0.33
Nodes (5): Each trading day, Known limitations, Milestone 1: running the automatic session dry run, Other commands (none of them place orders), What it checks

### Community 101 - "SPY bid-ask spread pilot: findings (PROVISIONAL)"
Cohesion: 0.33
Nodes (5): 1. Coverage and exclusions, 2. Provisional spread measurements, 3. Actual resource usage, 4. Reliability, and whether the remaining 18 sessions are justified, SPY bid-ask spread pilot: findings (PROVISIONAL)

### Community 102 - "What it is, and what it is not"
Cohesion: 0.50
Nodes (4): How text from the artifacts is handled, What it is, and what it is not, What makes a response valid, What the reviewer receives

## Knowledge Gaps
- **5 isolated node(s):** `Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json)`, `Playwright MCP Server (connected, unused)`, `pytest==9.2.0`, `Raw Adjustment Default (no split/dividend adjustment)`, `pandas==3.1.0`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 726 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Ledger` connect `Ledger` to `test_dashboard.py`, `ReplayController`, `server.py`, `test_journal.py`, `test_evaluation.py`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `iso()` (e.g. with `healthy()` and `jobs_fixture()`) actually correct?**
  _`iso()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json)`, `Playwright MCP Server (connected, unused)`, `pytest==9.2.0` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_dashboard.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0855614973262032 - nodes in this community are weakly interconnected._
- **Why does `sessions_between()` connect `server.py` to `monitor/store.py`, `test_backtest.py`, `orb_experiment.py`, `test_operations_runner.py`, `sessions.py`, `schedule.py`, `demo_replay.py`, `experiment.py`, `test_orb.py`, `engine.py`, `Params`, `metrics.py`, `test_evaluation.py`, `pytest`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `RiskLimits` (e.g. with `B. Evidence table` and `run_day()`) actually correct?**
  _`RiskLimits` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Should `build_map` be split into smaller, more focused modules?**
  _Cohesion score 0.12179487179487179 - nodes in this community are weakly interconnected._