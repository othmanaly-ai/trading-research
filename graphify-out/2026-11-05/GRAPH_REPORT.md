# Graph Report - TradingProject  (2026-11-04)

## Corpus Check
- 139 files · ~133,589 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 7 file(s) not represented in the graph (top: .csv 3, .example 1, (none) 1)

## Summary
- 1789 nodes · 4990 edges · 81 communities (74 shown, 7 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 469 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1eb9f629`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_dashboard.py
- test_history.py
- build_map
- json
- run_review
- test_monitor.py
- execution_feasibility.py
- Raw Price Adjustment
- pytest
- Experiment 001: Intraday momentum in SPY (draft specification)
- package.json
- QualityChecker
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
- Data Feeds: SIP (consolidated) vs IEX (single exchange)
- test_recovery.py
- test_evaluation.py
- threading
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
- build_package
- test_jobs.py
- server.py
- Ledger
- types.ts
- AnthropicProvider
- demo_replay.py
- trading/validate.py
- Amendment 2: quote coverage through the proposed exit (pre-registration)
- Feasibility note: gap-down opening reversal (not an experiment)
- Automated second review (model-powered reviewer)
- CityView.tsx
- iso
- test_journal.py
- _now
- Execution-data access check: pre-registration
- test_risk_metrics.py
- MonitorView.tsx
- Worker
- AlpacaAccessError
- Strategy City dashboard: DEMO REPLAY
- test_experiment.py
- Read-only market monitoring
- DayData
- verify_data_access.py
- json
- orb_experiment.py
- The city: architectural district (2026-11-05)
- daily_report
- Draft support request to Alpaca (NOT SENT)
- DependencyMap.tsx
- run_strategy
- ReplayController
- completed_sessions
- model_review
- ledger.py
- .apply
- Progress Record (2026-11-03)
- server_env

## God Nodes (most connected - your core abstractions)
1. `iso()` - 50 edges
2. `RiskLimits` - 46 edges
3. `MonitorStore` - 44 edges
4. `Params` - 43 edges
5. `QualityChecker` - 40 edges
6. `Ledger` - 38 edges
7. `run_backtest()` - 37 edges
8. `ReadOnlyAlpacaClient` - 35 edges
9. `DayData` - 35 edges
10. `build_package()` - 32 edges

## Surprising Connections (you probably didn't know these)
- `Run` --references--> `run_experiment()`  [INFERRED]
  research/001_intraday_momentum/RESULTS_development.md → trading/experiment.py
- `Layers` --references--> `TowerSpec`  [INFERRED]
  docs/CITY.md → dashboard/web/src/components/CityView.tsx
- `Connecting real Alpaca data (separate, not started)` --references--> `bar()`  [INFERRED]
  dashboard/README.md → tests/test_quality.py
- `Connecting real Alpaca data (separate, not started)` --references--> `run_backtest()`  [INFERRED]
  dashboard/README.md → trading/backtest.py
- `Tests (`tests/test_depmap.py`, synthetic fixtures only)` --references--> `collect()`  [INFERRED]
  docs/DEPENDENCY_MAP.md → trading/dashboard/depmap.py

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

## Communities (81 total, 7 thin omitted)

### Community 0 - "test_dashboard.py"
Cohesion: 0.09
Nodes (22): demo(), _get(), _post(), replay_all(), server(), test_build_is_deterministic(), test_candidates_overview_lists_deferred_candidate_read_only(), test_candidates_overview_tolerates_corrupt_status() (+14 more)

### Community 1 - "test_history.py"
Cohesion: 0.13
Nodes (13): alpaca_payloads(), fake_client(), hist_config(), RoutingHttp, store(), test_final_period_download_refused(), test_held_out_periods_refused(), test_load_days_round_trip_and_excludes_unusable() (+5 more)

### Community 2 - "build_map"
Cohesion: 0.09
Nodes (34): Dependency-and-health map (2026-11-05), Interaction, Statuses and reasoning, Tests (`tests/test_depmap.py`, synthetic fixtures only), Verification, What is backed by what, by_id(), healthy() (+26 more)

### Community 3 - "json"
Cohesion: 0.12
Nodes (13): test_cli_env_reads_key_from_dotenv_and_bom_authorization(), cost_usd(), load_authorization(), row_dict(), worst_case_usd(), main(), render_user_message(), _blocked() (+5 more)

### Community 4 - "run_review"
Cohesion: 0.10
Nodes (13): setup(), review_record(), reviewer_status(), model_review(), _review_availability(), _review_gate(), BudgetDenied, month() (+5 more)

### Community 5 - "test_monitor.py"
Cohesion: 0.14
Nodes (17): Clock, FakeClient, make_worker(), synthetic_bar(), test_access_errors_recorded_and_feed_never_switched(), test_dead_worker_shows_disconnected(), test_early_close_session_window(), test_freshness_fresh_then_stale_with_iex_note() (+9 more)

### Community 6 - "execution_feasibility.py"
Cohesion: 0.05
Nodes (34): 1. Historical SIP quotes, 09:30-09:35 ET, 2. Raw SIP minute bars, 09:30-10:02 ET, 3. Prior raw closes and corporate actions, 4. Limitations of this execution data, Conclusion on feasibility, Execution-data access check: findings (2026-11-04), FakeClient, FakeInner (+26 more)

### Community 9 - "pytest"
Cohesion: 0.14
Nodes (37): run_day(), test_accounting_identity_over_a_run(), test_breach_on_scheduled_exit_bar_uses_time_exit(), test_carry_exit_counts_against_next_session_limits(), test_daily_loss_limit_uses_unrealized_and_exits_next_bar(), test_early_close_shifts_times(), test_entry_is_one_minute_after_decision_with_costs(), test_equity_counts_each_cost_exactly_once() (+29 more)

### Community 10 - "Experiment 001: Intraday momentum in SPY (draft specification)"
Cohesion: 0.09
Nodes (22): 10. Cost assumptions (to be checked against data), 11. Baselines (same window, same exposure, same sizing), 12. Periods (chronological, fixed before any data is seen), 13. Variant accounting, 14. Evaluation criteria (fixed before running), 15. Roles (performed by one model, Claude, as checklists), 16. Unresolved decisions for owner review, 17. Implementation clarifications (2026-11-03, before any data was seen) (+14 more)

### Community 12 - "package.json"
Cohesion: 0.09
Nodes (26): dependencies, react@19.3.1, react-dom@19.3.1, three@0.187.0, devDependencies, @types/react@19.3.0, @types/react-dom@19.3.0, @types/three@0.187.0 (+18 more)

### Community 13 - "QualityChecker"
Cohesion: 0.14
Nodes (17): run_until_idle(), monitored_day(), session(), state(), test_bounded_backlog_lookback_and_request_budget(), test_early_close_session_recovered_and_finalized(), test_interval_without_run_records_is_unrecorded_not_downtime(), test_midnight_boundaries_do_not_abandon_the_session() (+9 more)

### Community 14 - "compilerOptions"
Cohesion: 0.12
Nodes (15): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, noFallthroughCasesInSwitch (+7 more)

### Community 15 - "jobs.py"
Cohesion: 0.16
Nodes (17): analysis(), execute_pipeline(), ingest(), inventory(), _keys(), _load_csv(), plan_pipeline(), _plan_rows() (+9 more)

### Community 17 - "JobStore"
Cohesion: 0.13
Nodes (8): env(), job_env(), test_server_job_runner_passes_no_keys(), jobs_snapshot(), JobRunner, JobStore, main(), _row()

### Community 18 - "Experiment 002-895a4f9c5d: development-period result"
Cohesion: 0.22
Nodes (8): Acceptance rules, Comparisons (diagnostic: fixed $5,000 per trade, no halts, dollar P&L / $100,000), Data exclusions and unresolved cases, Experiment 002-895a4f9c5d: development-period result, Limitations, Primary, full account, Recommendation, Run

### Community 19 - "test_orb.py"
Cohesion: 0.28
Nodes (26): days_for(), make(), path(), run(), test_b1_b2_reproducible_unmatched_and_identical_treatment(), test_b3_entry_sizing_and_acceptance(), test_checks_function(), test_completed_bar_signal_then_next_open_entry_and_c1_open_exit() (+18 more)

### Community 20 - "engine.py"
Cohesion: 0.16
Nodes (8): _net_if_closed(), Trade, CostModel, acceptance_limit(), _carry(), EngineResult, execute_plan(), diagnostic_trades()

### Community 21 - "Trading City: product specification"
Cohesion: 0.17
Nodes (11): 1. Purpose, 2. Modes (never blended), 3. Shared records, 4. Tower detail tabs, 5. Research responsibilities, 6. Historical replay rules (for milestone 4), 7. Evaluation report contents, 8. Scenario simulation method (PROPOSED: awaiting owner review) (+3 more)

### Community 22 - "make_handler"
Cohesion: 0.15
Nodes (20): experiments_overview(), build(), make_handler(), _body(), do_GET(), do_POST(), _drain(), _headers() (+12 more)

### Community 23 - "require_order_submission_allowed"
Cohesion: 0.27
Nodes (6): test_blocked(), _order_gate(), order_submission_enabled(), OrderSubmissionDisabled, require_order_submission_allowed(), trading_mode()

### Community 24 - "Experiment 001-fd13f1fdef: development-period result"
Cohesion: 0.20
Nodes (9): Cost sensitivity, Diagnosis (development data only; `diagnose_development.py`), Experiment 001-fd13f1fdef: development-period result, Limitations, Pass rules (fixed before the run), Recommendation, Reproducibility and file locations, Results (base costs, about 2.3 bp round trip) (+1 more)

### Community 25 - "Data Feeds: SIP (consolidated) vs IEX (single exchange)"
Cohesion: 0.17
Nodes (11): Completed Session Rule (15 min after close, SIP delay), Data Feeds: SIP (consolidated) vs IEX (single exchange), .env.example template, 1-Minute Bar Coverage ([open, close), trade-only bars), requirements.lock (full pip freeze), Setup Procedure (venv + requirements.lock), Verification Commands (pytest + verify_data_access), XNYS Exchange Calendar (America/New_York, UTC + ET timestamps) (+3 more)

### Community 26 - "test_recovery.py"
Cohesion: 0.20
Nodes (17): bar(), checker(), Clock, FakeFeeds, iso(), latest_rows(), test_access_failure_is_recorded_backs_off_and_does_not_substitute(), test_backlog_is_worked_off_in_bounded_chunks_and_restart_resumes() (+9 more)

### Community 27 - "test_evaluation.py"
Cohesion: 0.11
Nodes (16): report(), test_cost_accounting_and_sensitivity(), test_event_stream_only_uses_information_available_at_each_time(), test_reports_match_city(), test_research_status_is_honest(), test_result_hash_is_reproducible_and_sensitive(), test_spec_version_and_hash(), test_target_classes_not_applicable_without_target() (+8 more)

### Community 28 - "threading"
Cohesion: 0.09
Nodes (9): _isolate_monitor(), _isolate_reviewer(), env(), server_base(), test_supervisor_only_acts_when_desired_running(), env(), env(), _popen() (+1 more)

### Community 29 - "test_reviewer.py"
Cohesion: 0.20
Nodes (27): good_answer(), item_id(), MockProvider, ok(), run(), test_artifact_instruction_injection_is_flagged_and_cannot_flip_gates(), test_cache_reuses_review_and_keys_on_evidence_prompt_and_model(), test_call_budget_per_run() (+19 more)

### Community 30 - "quality.py"
Cohesion: 0.15
Nodes (10): _parses(), bar_defects(), boundary(), _bps(), classify(), _median(), _num(), report() (+2 more)

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
Cohesion: 0.12
Nodes (25): App(), Boundary, category(), CityView, CORE(), prefersReducedMotion(), STRATEGY_COLORS, strategyTower() (+17 more)

### Community 37 - "test_job_api.py"
Cohesion: 0.24
Nodes (15): call(), setup(), start(), test_cancel_queued_pipeline_immediately(), test_cancel_running_pipeline_keeps_completed_evidence(), test_dashboard_records_match_database(), test_experiments_and_preview(), test_get_with_foreign_host_refused() (+7 more)

### Community 38 - "TowerPanel.tsx"
Cohesion: 0.18
Nodes (27): AccountPanel(), Leaderboard(), StrategyTable(), Marker, PAD, PriceChart(), DecisionsTab(), HistoricalTab() (+19 more)

### Community 39 - "Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04)"
Cohesion: 0.18
Nodes (10): 1. SPY distribution calendar (`spy_distributions_development.json`), 2. Quote interpretation (official Alpaca documentation, read 2026-11-04), 3. Locked and crossed quotes (proposed treatment, not approved), 4. Quote coverage through the proposed 10:00 exit, 5. What this is not, Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04), Future operation (proposed; required before any live use), Retrospective classification vs historical availability (+2 more)

### Community 40 - "ReadOnlyAlpacaClient"
Cohesion: 0.16
Nodes (16): FakeHttp, FakeResponse, test_access_refusal_on_quotes_raises_without_retry(), test_account_keeps_only_listed_fields(), test_client_has_no_order_methods(), test_corporate_actions_merge_and_cap(), test_feed_refusal_raises_and_is_not_substituted(), test_multi_symbol_pagination_merges_pages_and_keeps_feed() (+8 more)

### Community 41 - "build_package"
Cohesion: 0.14
Nodes (12): test_evidence_scope_excludes_data_and_held_out(), test_secrets_and_local_paths_are_redacted(), build_package(), add(), EvidenceError, EvidenceTooLarge, lookup(), resolve() (+4 more)

### Community 42 - "test_jobs.py"
Cohesion: 0.18
Nodes (9): statuses(), test_api_and_store_emit_strict_json(), test_corrupt_artifact_fails_then_recovers_with_new_attempt(), test_end_to_end_on_real_artifacts(), test_missing_artifact_fails_ingest_and_blocks_downstream(), test_model_review_unavailable_lists_every_blocker(), test_reconcile_detects_tampered_record(), test_retry_and_restart_never_duplicate_completed_jobs() (+1 more)

### Community 43 - "server.py"
Cohesion: 0.10
Nodes (17): main(), raw_minutes(), test_cli_blocked_without_credentials(), Context, build_historical(), load_config(), main(), fetch_and_store() (+9 more)

### Community 44 - "Ledger"
Cohesion: 0.18
Nodes (3): test_historical_replay_mode_and_totals(), Ledger, _net_if_closed()

### Community 45 - "types.ts"
Cohesion: 0.16
Nodes (18): Props, Account, Bar, Connection, Evaluation, EventType, Instance, InstrumentView (+10 more)

### Community 46 - "AnthropicProvider"
Cohesion: 0.12
Nodes (13): fake_sdk(), create(), __init__(), test_anthropic_provider_error_mapping_with_mock_sdk(), behaviour(), test_anthropic_provider_success_with_mock_sdk(), test_real_sdk_error_mapping_against_closed_local_port(), AnthropicProvider (+5 more)

### Community 47 - "demo_replay.py"
Cohesion: 0.09
Nodes (20): days(), bars(), test_bars_after_exit_are_ignored(), test_classification_rules(), _apply_outage(), build_demo(), build_replay(), ConfigError (+12 more)

### Community 48 - "trading/validate.py"
Cohesion: 0.13
Nodes (16): full_session(), synthetic_bar(), test_clean_synthetic_session_passes(), test_daily_coverage_maps_midnight_et_stamps_to_dates(), test_detects_each_structural_problem(), test_minute_gaps_and_outside_bars_reported(), _carry_exit(), last30_return() (+8 more)

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
Cohesion: 0.07
Nodes (56): Ambient, buildAmbient(), Car, Effects, Landmark, rng(), signTexture(), VEHICLES (+48 more)

### Community 53 - "iso"
Cohesion: 0.12
Nodes (16): _call(), test_monitor_api_matches_store_and_controls_work(), test_start_launches_once_and_supervisor_recovers_without_duplicates(), test_report_operations_downtime_restarts_and_failures(), monitor_control(), quality_minute(), launch(), start() (+8 more)

### Community 54 - "test_journal.py"
Cohesion: 0.19
Nodes (8): test_demo_research_run_writes_consistent_outputs(), test_journal_matches_ledger_engine_and_report(), test_journal_mid_replay_marks_session_in_progress(), test_skipped_and_blocked_sessions_are_journaled(), build_journal(), _pair_exits(), write_journal(), run()

### Community 55 - "_now"
Cohesion: 0.22
Nodes (3): _finite(), _now(), request_cancel()

### Community 56 - "Execution-data access check: pre-registration"
Cohesion: 0.33
Nodes (5): Dates (all in the development period, 2016-01-04 to 2021-12-31), Execution-data access check: pre-registration, Requests (HTTP GET only, host `https://data.alpaca.markets`), Storage, Validation (pre-declared)

### Community 57 - "test_risk_metrics.py"
Cohesion: 0.11
Nodes (23): test_baseline_notional_cap_binds_and_rounds_down(), test_cost_levels_ordered_and_round_trip(), test_entry_that_cannot_fit_is_rejected(), test_gross_exposure_includes_pending_and_open(), test_invalid_sizing_inputs_give_zero(), test_max_drawdown(), test_max_positions_counts_pending(), test_notional_cap_binds() (+15 more)

### Community 58 - "MonitorView.tsx"
Cohesion: 0.11
Nodes (25): age(), Bar, Boundary, CityView, et(), FRESH_COLORS, LiveClock(), MON_LEGEND (+17 more)

### Community 59 - "Worker"
Cohesion: 0.11
Nodes (9): test_connection_failures_back_off_and_reconnect(), test_worker_marks_sessions_it_monitors(), code_version(), default_client_factory(), _floor_minute(), main(), SingleInstanceLock, _StopRequested (+1 more)

### Community 60 - "AlpacaAccessError"
Cohesion: 0.14
Nodes (12): Allowed Hosts (paper-api and data.alpaca.markets only), daytrading-starter skill (planning/analysis only), Offline Test Suite (22 passed), Playwright MCP Server (connected, unused), Verified Components (Python 3.15.2, Git, ignore rules, deps, tests), pytest==9.2.0, requests==2.34.2, test_credentials_from_dotenv() (+4 more)

### Community 61 - "Strategy City dashboard: DEMO REPLAY"
Cohesion: 0.22
Nodes (6): Architecture, Connecting real Alpaca data (separate, not started), Launch, Research jobs tab (REAL records, not demo), Strategy City dashboard: DEMO REPLAY, Verification

### Community 62 - "test_experiment.py"
Cohesion: 0.08
Nodes (35): attempts(), days(), lock_path(), read_log(), run(), _run(), test_attempts_ledger_records_completed_and_refused(), test_changed_definition_refused() (+27 more)

### Community 63 - "Read-only market monitoring"
Cohesion: 0.12
Nodes (15): Behaviour, Checklist for observing several consecutive sessions, Controls, Daily report sections, Data permissions measured on 2026-11-04, Data quality: delayed SIP vs IEX (`trading/monitor/quality.py`), Finalization, Limitations (+7 more)

### Community 64 - "DayData"
Cohesion: 0.15
Nodes (10): DayData, checks(), Decision, EntryPlan, first_bad_minute(), SessionStrategy, diagnostics(), session_arrays() (+2 more)

### Community 65 - "verify_data_access.py"
Cohesion: 0.21
Nodes (9): Data Check Exit Codes (0 success, 1 API failure, 2 no credentials), Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json), Missing-Credential Handling (BLOCKED, exit 2, no network call), test_verify_refuses_held_out_sample_before_network(), AlpacaAccessError, _iso(), main(), _now() (+1 more)

### Community 66 - "json"
Cohesion: 0.57
Nodes (5): _citations(), _expect(), _obj(), _str(), validate()

### Community 67 - "orb_experiment.py"
Cohesion: 0.19
Nodes (16): test_closed_experiment_refuses_runs_but_allows_inspection(), test_lock_refuses_changed_definition_and_dirty_tree(), test_only_four_configurations_and_held_out_refused(), _account(), check_lock(), experiment_id(), fingerprint(), _git_commit() (+8 more)

### Community 68 - "The city: architectural district (2026-11-05)"
Cohesion: 0.14
Nodes (13): Ambient life and real events (2026-11-05, second pass), Building vocabulary (procedural, no external assets), Controls and access, Decorative (no data; module `city/ambient.ts`), Deferred, Effects, Effects levels, Measured performance (2026-11-05, in-app Chromium, 1213×618, pixel ratio 1) (+5 more)

### Community 69 - "daily_report"
Cohesion: 0.24
Nodes (11): monitor_report(), monitor_sessions(), ensure_schema(), daily_report(), _intervals_uncovered(), _median(), _secs(), _session() (+3 more)

### Community 71 - "DependencyMap.tsx"
Cohesion: 0.13
Nodes (14): EdgeSpec, TowerSpec, ARCH, Boundary, Cause, CityView, DependencyMap(), DepMap (+6 more)

### Community 72 - "run_strategy"
Cohesion: 0.21
Nodes (8): test_daily_breach_uses_session_start_equity(), test_daily_loss_limit(), test_daily_losses_accumulate_across_trades_and_marks(), test_drawdown_uses_high_water_mark_and_never_resets(), DayResult, run_strategy(), full(), RiskState

### Community 73 - "ReplayController"
Cohesion: 0.28
Nodes (5): test_controller_pause_restart_speed(), test_controller_replay_with_injected_duplicates_matches_direct(), _epoch(), ReplayController, _ticker()

### Community 74 - "completed_sessions"
Cohesion: 0.24
Nodes (9): test_dst_changes_utc_open(), test_requires_timezone_aware_now(), test_session_not_completed_until_data_delay_passes(), test_thanksgiving_skipped_and_black_friday_early_close(), test_weekend_and_observed_holiday(), utc(), _calendar(), completed_sessions() (+1 more)

### Community 75 - "model_review"
Cohesion: 0.50
Nodes (4): How text from the artifacts is handled, What it is, and what it is not, What makes a response valid, What the reviewer receives

### Community 76 - "ledger.py"
Cohesion: 0.19
Nodes (3): test_repeat_build_reproduces_reports(), _ts(), evaluate()

### Community 77 - ".apply"
Cohesion: 0.22
Nodes (4): test_unrealized_is_marked_while_open_and_zero_after(), test_wrong_mode_event_rejected(), demo_ledger(), demo()

### Community 79 - "Progress Record (2026-11-03)"
Cohesion: 0.33
Nodes (7): Order Submission Guard (TRADING_MODE=paper, ORDER_SUBMISSION_ENABLED=true), TradingProject (paper-trading research system), Implemented, Not Yet Verified Against Real API, Missing (Alpaca connection, real data, risk controls, Playwright package), Progress Record (2026-11-03), Risk Controls Gap (no position sizing or loss limits), TradingProject README

### Community 80 - "server_env"
Cohesion: 0.50
Nodes (3): test_dashboard_blocker_wording_without_authorization(), test_server_env_strips_credentials(), server_env()

## Knowledge Gaps
- **5 isolated node(s):** `pandas==3.1.0`, `Playwright MCP Server (connected, unused)`, `pytest==9.2.0`, `Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json)`, `Raw Adjustment Default (no split/dividend adjustment)`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 613 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `collect()` connect `build_map` to `run_review`, `daily_report`, `server.py`, `jobs.py`, `server_env`, `JobStore`, `iso`, `make_handler`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `iso()` (e.g. with `healthy()` and `jobs_fixture()`) actually correct?**
  _`iso()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `pandas==3.1.0`, `Playwright MCP Server (connected, unused)`, `pytest==9.2.0` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_dashboard.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09090909090909091 - nodes in this community are weakly interconnected._
- **Why does `AlpacaAccessError` connect `verify_data_access.py` to `test_monitor.py`, `execution_feasibility.py`, `ReadOnlyAlpacaClient`, `server.py`, `QualityChecker`, `._get`, `test_recovery.py`, `Worker`, `AlpacaAccessError`, `quality.py`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `RiskLimits` (e.g. with `run_day()` and `test_invalid_sizing_inputs_give_zero()`) actually correct?**
  _`RiskLimits` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_history.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12648221343873517 - nodes in this community are weakly interconnected._