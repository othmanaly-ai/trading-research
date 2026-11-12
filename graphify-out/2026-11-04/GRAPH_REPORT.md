# Graph Report - TradingProject  (2026-11-04)

## Corpus Check
- 135 files · ~126,982 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 7 file(s) not represented in the graph (top: .csv 3, .example 1, (none) 1)

## Summary
- 1725 nodes · 4831 edges · 78 communities (68 shown, 10 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 459 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `30b5d10f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_dashboard.py
- test_history.py
- architecture.ts
- review.py
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
- test_risk_metrics.py
- Trading City: product specification
- make_handler
- require_order_submission_allowed
- Experiment 001-fd13f1fdef: development-period result
- Data Feeds: SIP (consolidated) vs IEX (single exchange)
- test_recovery.py
- test_evaluation.py
- control.py
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
- _finite
- Execution-data access check: pre-registration
- orb_experiment.py
- MonitorView.tsx
- Worker
- AlpacaAccessError
- Strategy City dashboard: DEMO REPLAY
- test_experiment.py
- Read-only market monitoring
- .block
- verify_data_access.py
- json
- server.py
- The city: architectural district (2026-11-05)
- daily_report
- Draft support request to Alpaca (NOT SENT)
- ambient.ts
- backtest.py
- ReplayController
- completed_sessions
- model_review
- conftest.py
- RoutingHttp

## God Nodes (most connected - your core abstractions)
1. `RiskLimits` - 46 edges
2. `iso()` - 45 edges
3. `MonitorStore` - 43 edges
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
- `What it is, and what it is not` --references--> `reconcile()`  [INFERRED]
  docs/MODEL_REVIEW.md → trading/jobs.py

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

## Communities (78 total, 10 thin omitted)

### Community 0 - "test_dashboard.py"
Cohesion: 0.10
Nodes (23): demo(), _get(), _post(), replay_all(), test_build_is_deterministic(), test_control_requires_header_and_valid_action(), test_duplicates_do_not_double_count(), test_empty_config() (+15 more)

### Community 1 - "test_history.py"
Cohesion: 0.16
Nodes (16): alpaca_payloads(), fake_client(), hist_config(), store(), test_final_period_download_refused(), test_held_out_periods_refused(), test_historical_replay_mode_and_totals(), test_load_days_round_trip_and_excludes_unusable() (+8 more)

### Community 2 - "architecture.ts"
Cohesion: 0.19
Nodes (17): BUILDERS, Kit, worldUV(), buildScenery(), rng(), Scenery, skyDome(), BAY_W (+9 more)

### Community 3 - "review.py"
Cohesion: 0.11
Nodes (10): test_cli_env_reads_key_from_dotenv_and_bom_authorization(), test_dashboard_blocker_wording_without_authorization(), test_server_env_strips_credentials(), _server_env(), _blocked(), cache_key(), cli_env(), estimate_input_tokens() (+2 more)

### Community 4 - "run_review"
Cohesion: 0.10
Nodes (18): setup(), review_record(), reviewer_status(), _review_availability(), _review_gate(), BudgetDenied, cost_usd(), load_authorization() (+10 more)

### Community 5 - "test_monitor.py"
Cohesion: 0.15
Nodes (18): _call(), Clock, FakeClient, make_worker(), synthetic_bar(), test_access_errors_recorded_and_feed_never_switched(), test_dead_worker_shows_disconnected(), test_early_close_session_window() (+10 more)

### Community 6 - "execution_feasibility.py"
Cohesion: 0.05
Nodes (35): 1. Historical SIP quotes, 09:30-09:35 ET, 2. Raw SIP minute bars, 09:30-10:02 ET, 3. Prior raw closes and corporate actions, 4. Limitations of this execution data, Conclusion on feasibility, Execution-data access check: findings (2026-11-04), FakeClient, FakeInner (+27 more)

### Community 9 - "pytest"
Cohesion: 0.15
Nodes (28): run_day(), test_accounting_identity_over_a_run(), test_breach_on_scheduled_exit_bar_uses_time_exit(), test_carry_exit_counts_against_next_session_limits(), test_daily_loss_limit_uses_unrealized_and_exits_next_bar(), test_early_close_shifts_times(), test_entry_is_one_minute_after_decision_with_costs(), test_equity_counts_each_cost_exactly_once() (+20 more)

### Community 10 - "Experiment 001: Intraday momentum in SPY (draft specification)"
Cohesion: 0.09
Nodes (22): 10. Cost assumptions (to be checked against data), 11. Baselines (same window, same exposure, same sizing), 12. Periods (chronological, fixed before any data is seen), 13. Variant accounting, 14. Evaluation criteria (fixed before running), 15. Roles (performed by one model, Claude, as checklists), 16. Unresolved decisions for owner review, 17. Implementation clarifications (2026-11-03, before any data was seen) (+14 more)

### Community 12 - "package.json"
Cohesion: 0.09
Nodes (26): dependencies, react@19.3.1, react-dom@19.3.1, three@0.187.0, devDependencies, @types/react@19.3.0, @types/react-dom@19.3.0, @types/three@0.187.0 (+18 more)

### Community 13 - "QualityChecker"
Cohesion: 0.14
Nodes (15): run_until_idle(), monitored_day(), session(), state(), test_bounded_backlog_lookback_and_request_budget(), test_early_close_session_recovered_and_finalized(), test_midnight_boundaries_do_not_abandon_the_session(), test_repeated_finalization_is_idempotent_and_amendments_keep_history() (+7 more)

### Community 14 - "compilerOptions"
Cohesion: 0.12
Nodes (15): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, noFallthroughCasesInSwitch (+7 more)

### Community 15 - "jobs.py"
Cohesion: 0.12
Nodes (19): analysis(), execute_pipeline(), ingest(), inventory(), JobRunner, _keys(), _load_csv(), plan_pipeline() (+11 more)

### Community 17 - "JobStore"
Cohesion: 0.13
Nodes (8): env(), job_env(), test_server_job_runner_passes_no_keys(), jobs_snapshot(), JobStore, main(), _now(), request_cancel()

### Community 18 - "Experiment 002-895a4f9c5d: development-period result"
Cohesion: 0.22
Nodes (8): Acceptance rules, Comparisons (diagnostic: fixed $5,000 per trade, no halts, dollar P&L / $100,000), Data exclusions and unresolved cases, Experiment 002-895a4f9c5d: development-period result, Limitations, Primary, full account, Recommendation, Run

### Community 19 - "test_orb.py"
Cohesion: 0.12
Nodes (42): days_for(), make(), path(), run(), test_b1_b2_reproducible_unmatched_and_identical_treatment(), test_b3_entry_sizing_and_acceptance(), test_checks_function(), test_closed_experiment_refuses_runs_but_allows_inspection() (+34 more)

### Community 20 - "test_risk_metrics.py"
Cohesion: 0.08
Nodes (24): test_kill_switch_blocks_after_drawdown(), test_baseline_notional_cap_binds_and_rounds_down(), test_daily_breach_uses_session_start_equity(), test_daily_loss_limit(), test_daily_losses_accumulate_across_trades_and_marks(), test_drawdown_uses_high_water_mark_and_never_resets(), test_entry_that_cannot_fit_is_rejected(), test_gross_exposure_includes_pending_and_open() (+16 more)

### Community 21 - "Trading City: product specification"
Cohesion: 0.17
Nodes (11): 1. Purpose, 2. Modes (never blended), 3. Shared records, 4. Tower detail tabs, 5. Research responsibilities, 6. Historical replay rules (for milestone 4), 7. Evaluation report contents, 8. Scenario simulation method (PROPOSED: awaiting owner review) (+3 more)

### Community 22 - "make_handler"
Cohesion: 0.17
Nodes (18): experiments_overview(), build(), make_handler(), _body(), do_GET(), do_POST(), _drain(), _headers() (+10 more)

### Community 23 - "require_order_submission_allowed"
Cohesion: 0.30
Nodes (6): test_blocked(), _order_gate(), order_submission_enabled(), OrderSubmissionDisabled, require_order_submission_allowed(), trading_mode()

### Community 24 - "Experiment 001-fd13f1fdef: development-period result"
Cohesion: 0.20
Nodes (9): Cost sensitivity, Diagnosis (development data only; `diagnose_development.py`), Experiment 001-fd13f1fdef: development-period result, Limitations, Pass rules (fixed before the run), Recommendation, Reproducibility and file locations, Results (base costs, about 2.3 bp round trip) (+1 more)

### Community 25 - "Data Feeds: SIP (consolidated) vs IEX (single exchange)"
Cohesion: 0.11
Nodes (18): Completed Session Rule (15 min after close, SIP delay), Data Feeds: SIP (consolidated) vs IEX (single exchange), .env.example template, 1-Minute Bar Coverage ([open, close), trade-only bars), Order Submission Guard (TRADING_MODE=paper, ORDER_SUBMISSION_ENABLED=true), requirements.lock (full pip freeze), Setup Procedure (venv + requirements.lock), TradingProject (paper-trading research system) (+10 more)

### Community 26 - "test_recovery.py"
Cohesion: 0.20
Nodes (18): bar(), checker(), Clock, FakeFeeds, iso(), latest_rows(), test_access_failure_is_recorded_backs_off_and_does_not_substitute(), test_backlog_is_worked_off_in_bounded_chunks_and_restart_resumes() (+10 more)

### Community 27 - "test_evaluation.py"
Cohesion: 0.13
Nodes (13): bars(), report(), test_bars_after_exit_are_ignored(), test_classification_rules(), test_classifier_agrees_with_engine_stop_exits(), test_cost_accounting_and_sensitivity(), test_event_stream_only_uses_information_available_at_each_time(), test_reports_match_city() (+5 more)

### Community 29 - "test_reviewer.py"
Cohesion: 0.20
Nodes (27): good_answer(), item_id(), MockProvider, ok(), run(), test_artifact_instruction_injection_is_flagged_and_cannot_flip_gates(), test_cache_reuses_review_and_keys_on_evidence_prompt_and_model(), test_call_budget_per_run() (+19 more)

### Community 30 - "quality.py"
Cohesion: 0.13
Nodes (13): _parses(), bar_defects(), boundary(), _bps(), classify(), _median(), _num(), report() (+5 more)

### Community 31 - "JobsView.tsx"
Cohesion: 0.07
Nodes (29): ACTIVE, Artifact, Boundary, Candidate, CityView, EVENT_KIND, Experiment, Experiments (+21 more)

### Community 32 - "Experiment 002: Long-only opening-range breakout in SPY (specification)"
Cohesion: 0.12
Nodes (16): 1. Notation and data, 2. Timeline (exact timestamps), 3. Strategy (primary configuration), 4. Comparisons (complete definitions), 5. Configurations and variant policy, 6. Acceptance rules, 6a. Implementation invariants (approved 2026-11-04; the hypothesis is unchanged), 7. Required tests before any evaluation (+8 more)

### Community 33 - "Overview.tsx"
Cohesion: 0.10
Nodes (23): TowerSpec, LiveClock(), ageText(), Boundary, C, CityView, districtTowers(), etTime() (+15 more)

### Community 34 - "Candidates for experiment 002"
Cohesion: 0.33
Nodes (5): A. Long-only 30-minute opening-range breakout (recommended), B. Long-only gap-down reversal (speculative, partly contaminated), Candidates for experiment 002, How much evidence there is, Recommendation

### Community 36 - "App.tsx"
Cohesion: 0.12
Nodes (25): App(), Boundary, category(), CityView, CORE(), prefersReducedMotion(), STRATEGY_COLORS, strategyTower() (+17 more)

### Community 37 - "test_job_api.py"
Cohesion: 0.22
Nodes (15): call(), setup(), start(), test_cancel_queued_pipeline_immediately(), test_cancel_running_pipeline_keeps_completed_evidence(), test_dashboard_records_match_database(), test_experiments_and_preview(), test_get_with_foreign_host_refused() (+7 more)

### Community 38 - "TowerPanel.tsx"
Cohesion: 0.21
Nodes (24): AccountPanel(), Leaderboard(), StrategyTable(), PriceChart(), DecisionsTab(), HistoricalTab(), JournalRow, JournalTab() (+16 more)

### Community 39 - "Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04)"
Cohesion: 0.18
Nodes (10): 1. SPY distribution calendar (`spy_distributions_development.json`), 2. Quote interpretation (official Alpaca documentation, read 2026-11-04), 3. Locked and crossed quotes (proposed treatment, not approved), 4. Quote coverage through the proposed 10:00 exit, 5. What this is not, Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04), Future operation (proposed; required before any live use), Retrospective classification vs historical availability (+2 more)

### Community 40 - "ReadOnlyAlpacaClient"
Cohesion: 0.11
Nodes (17): FakeHttp, FakeResponse, test_access_refusal_on_quotes_raises_without_retry(), test_account_keeps_only_listed_fields(), test_client_has_no_order_methods(), test_corporate_actions_merge_and_cap(), test_feed_refusal_raises_and_is_not_substituted(), test_multi_symbol_pagination_merges_pages_and_keeps_feed() (+9 more)

### Community 41 - "build_package"
Cohesion: 0.15
Nodes (11): test_evidence_scope_excludes_data_and_held_out(), test_secrets_and_local_paths_are_redacted(), build_package(), add(), EvidenceError, EvidenceTooLarge, lookup(), _Sanitizer (+3 more)

### Community 42 - "test_jobs.py"
Cohesion: 0.18
Nodes (8): statuses(), test_api_and_store_emit_strict_json(), test_corrupt_artifact_fails_then_recovers_with_new_attempt(), test_end_to_end_on_real_artifacts(), test_missing_artifact_fails_ingest_and_blocks_downstream(), test_reconcile_detects_tampered_record(), test_retry_and_restart_never_duplicate_completed_jobs(), run_pipeline()

### Community 43 - "server.py"
Cohesion: 0.14
Nodes (9): main(), _iso(), load_days(), read_manifest(), _received(), series_dir(), _calendar(), _session() (+1 more)

### Community 44 - "Ledger"
Cohesion: 0.11
Nodes (4): Ledger, _net_if_closed(), _ts(), evaluate()

### Community 45 - "types.ts"
Cohesion: 0.13
Nodes (21): Marker, PAD, Props, Account, Bar, Connection, Evaluation, EventType (+13 more)

### Community 46 - "AnthropicProvider"
Cohesion: 0.12
Nodes (13): fake_sdk(), create(), __init__(), test_anthropic_provider_error_mapping_with_mock_sdk(), behaviour(), test_anthropic_provider_success_with_mock_sdk(), test_real_sdk_error_mapping_against_closed_local_port(), AnthropicProvider (+5 more)

### Community 47 - "demo_replay.py"
Cohesion: 0.12
Nodes (16): days(), BacktestResult, DayData, _apply_outage(), build_replay(), Context, DemoReplay, _instrument_events() (+8 more)

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

### Community 53 - "iso"
Cohesion: 0.11
Nodes (17): env(), test_monitor_api_matches_store_and_controls_work(), test_start_launches_once_and_supervisor_recovers_without_duplicates(), test_supervisor_only_acts_when_desired_running(), env(), env(), test_interval_without_run_records_is_unrecorded_not_downtime(), test_report_operations_downtime_restarts_and_failures() (+9 more)

### Community 54 - "test_journal.py"
Cohesion: 0.16
Nodes (9): test_demo_research_run_writes_consistent_outputs(), test_journal_matches_ledger_engine_and_report(), test_journal_mid_replay_marks_session_in_progress(), test_skipped_and_blocked_sessions_are_journaled(), build_journal(), _pair_exits(), write_journal(), main() (+1 more)

### Community 56 - "Execution-data access check: pre-registration"
Cohesion: 0.33
Nodes (5): Dates (all in the development period, 2016-01-04 to 2021-12-31), Execution-data access check: pre-registration, Requests (HTTP GET only, host `https://data.alpaca.markets`), Storage, Validation (pre-declared)

### Community 57 - "orb_experiment.py"
Cohesion: 0.09
Nodes (23): main(), raw_minutes(), test_max_drawdown(), test_random_baseline_centered_and_percentile(), Decision, EntryPlan, first_bad_minute(), bootstrap_sharpe_ci() (+15 more)

### Community 58 - "MonitorView.tsx"
Cohesion: 0.11
Nodes (24): age(), Bar, Boundary, CityView, et(), FRESH_COLORS, MON_LEGEND, MonitorData (+16 more)

### Community 59 - "Worker"
Cohesion: 0.13
Nodes (7): test_connection_failures_back_off_and_reconnect(), test_worker_marks_sessions_it_monitors(), code_version(), _floor_minute(), SingleInstanceLock, _StopRequested, Worker

### Community 60 - "AlpacaAccessError"
Cohesion: 0.09
Nodes (15): Allowed Hosts (paper-api and data.alpaca.markets only), daytrading-starter skill (planning/analysis only), Offline Test Suite (22 passed), Playwright MCP Server (connected, unused), Verified Components (Python 3.15.2, Git, ignore rules, deps, tests), pytest==9.2.0, requests==2.34.2, test_credentials_from_dotenv() (+7 more)

### Community 61 - "Strategy City dashboard: DEMO REPLAY"
Cohesion: 0.29
Nodes (6): Architecture, Connecting real Alpaca data (separate, not started), Launch, Research jobs tab (REAL records, not demo), Strategy City dashboard: DEMO REPLAY, Verification

### Community 62 - "test_experiment.py"
Cohesion: 0.08
Nodes (40): test_spec_version_and_hash(), attempts(), days(), lock_path(), read_log(), run(), _run(), test_attempts_ledger_records_completed_and_refused() (+32 more)

### Community 63 - "Read-only market monitoring"
Cohesion: 0.12
Nodes (15): Behaviour, Checklist for observing several consecutive sessions, Controls, Daily report sections, Data permissions measured on 2026-11-04, Data quality: delayed SIP vs IEX (`trading/monitor/quality.py`), Finalization, Limitations (+7 more)

### Community 64 - ".block"
Cohesion: 0.46
Nodes (8): Builder, command(), construction(), finned(), operations(), paired(), terraced(), twisted()

### Community 65 - "verify_data_access.py"
Cohesion: 0.24
Nodes (8): Data Check Exit Codes (0 success, 1 API failure, 2 no credentials), Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json), Missing-Credential Handling (BLOCKED, exit 2, no network call), test_verify_refuses_held_out_sample_before_network(), _iso(), main(), _now(), _write_json()

### Community 66 - "json"
Cohesion: 0.26
Nodes (7): resolve(), render_user_message(), _citations(), _expect(), _obj(), _str(), validate()

### Community 67 - "server.py"
Cohesion: 0.09
Nodes (16): server(), test_candidates_overview_lists_deferred_candidate_read_only(), test_candidates_overview_tolerates_corrupt_status(), test_research_status_is_honest(), test_dashboard_endpoint_matches_store(), test_journal_endpoints(), server_base(), load_config() (+8 more)

### Community 68 - "The city: architectural district (2026-11-05)"
Cohesion: 0.14
Nodes (13): Ambient life and real events (2026-11-05, second pass), Building vocabulary (procedural, no external assets), Controls and access, Decorative (no data; module `city/ambient.ts`), Deferred, Effects, Effects levels, Measured performance (2026-11-05, in-app Chromium, 1213×618, pixel ratio 1) (+5 more)

### Community 69 - "daily_report"
Cohesion: 0.20
Nodes (12): monitor_sessions(), quality_minute(), ensure_schema(), minute_record(), daily_report(), _intervals_uncovered(), _median(), _secs() (+4 more)

### Community 71 - "ambient.ts"
Cohesion: 0.20
Nodes (11): Ambient, buildAmbient(), Car, Effects, Landmark, rng(), signTexture(), VEHICLES (+3 more)

### Community 72 - "backtest.py"
Cohesion: 0.12
Nodes (13): test_positions_never_held_past_close_except_halt(), test_stress_entry_failures_are_deterministic(), test_warmup_and_first_day(), _carry_exit(), DayResult, last30_return(), run_backtest(), _scheduled_exit() (+5 more)

### Community 73 - "ReplayController"
Cohesion: 0.32
Nodes (4): test_controller_pause_restart_speed(), test_controller_replay_with_injected_duplicates_matches_direct(), ReplayController, _ticker()

### Community 74 - "completed_sessions"
Cohesion: 0.40
Nodes (7): test_dst_changes_utc_open(), test_requires_timezone_aware_now(), test_session_not_completed_until_data_delay_passes(), test_thanksgiving_skipped_and_black_friday_early_close(), test_weekend_and_observed_holiday(), utc(), completed_sessions()

### Community 75 - "model_review"
Cohesion: 0.29
Nodes (6): How text from the artifacts is handled, What it is, and what it is not, What makes a response valid, What the reviewer receives, test_model_review_unavailable_lists_every_blocker(), model_review()

## Knowledge Gaps
- **5 isolated node(s):** `pandas==3.1.0`, `Playwright MCP Server (connected, unused)`, `pytest==9.2.0`, `Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json)`, `Raw Adjustment Default (no split/dividend adjustment)`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 589 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ReadOnlyAlpacaClient` connect `ReadOnlyAlpacaClient` to `verify_data_access.py`, `test_history.py`, `execution_feasibility.py`, `server.py`, `AlpacaAccessError`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `RiskLimits` (e.g. with `run_day()` and `test_invalid_sizing_inputs_give_zero()`) actually correct?**
  _`RiskLimits` has 11 INFERRED edges - model-reasoned connections that need verification._
- **What connects `pandas==3.1.0`, `Playwright MCP Server (connected, unused)`, `pytest==9.2.0` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_dashboard.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09523809523809523 - nodes in this community are weakly interconnected._
- **Why does `AlpacaAccessError` connect `ReadOnlyAlpacaClient` to `verify_data_access.py`, `test_monitor.py`, `execution_feasibility.py`, `server.py`, `QualityChecker`, `test_recovery.py`, `Worker`, `AlpacaAccessError`, `quality.py`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Should `review.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10952380952380952 - nodes in this community are weakly interconnected._
- **Why does `What it is, and what it is not` connect `model_review` to `Automated second review (model-powered reviewer)`, `jobs.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._