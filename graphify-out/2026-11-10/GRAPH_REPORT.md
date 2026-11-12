# Graph Report - TradingProject  (2026-11-10)

## Corpus Check
- 202 files · ~235,930 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: .csv 3, .css 2, .example 1)

## Summary
- 2811 nodes · 7669 edges · 121 communities (112 shown, 9 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 689 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1ed518e5`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Ledger
- iso
- build_map
- test_history.py
- run_review
- test_monitor.py
- execution_feasibility.py
- Raw Price Adjustment
- test_backtest.py
- Experiment 001: Intraday momentum in SPY (draft specification)
- hashlib
- test_readiness.py
- compilerOptions
- jobs.py
- JobStore
- Experiment 002-895a4f9c5d: development-period result
- test_orb.py
- test_spread_measurement.py
- Trading City: product specification
- do_GET
- test_dashboard.py
- Experiment 001-fd13f1fdef: development-period result
- test_risk_metrics.py
- test_quality.py
- test_evaluation.py
- lab.py
- test_reviewer.py
- test_execution_lab.py
- JobsView.tsx
- Experiment 002: Long-only opening-range breakout in SPY (specification)
- Overview.tsx
- Candidates for experiment 002
- EXPLORATION_LOG.md
- App.tsx
- startup.py
- TowerPanel.tsx
- Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04)
- ReadOnlyAlpacaClient
- metrics.py
- TowerSpec
- demo_replay.py
- CityView.tsx
- ExecutionLabView.tsx
- collect
- coordinator.py
- trading/validate.py
- Amendment 2: quote coverage through the proposed exit (pre-registration)
- Feasibility note: gap-down opening reversal (not an experiment)
- Automated second review (model-powered reviewer)
- CityView.tsx
- WorkflowView.tsx
- test_journal.py
- SPY bid-ask spread measurement: plan and pilot pre-registration
- Execution-data access check: pre-registration
- checks.py
- MonitorView.tsx
- MonitorStore
- spread_measurement.py
- test_coordinator.py
- random_direction_returns
- Read-only market monitoring
- test_execution_feasibility.py
- load_credentials
- Why experiments 001 and 002 failed: a plain-English comparison
- alpaca_client.py
- reviewer/validate.py
- Research workflow report: Review our existing strategy failures and recommend the next research decision.
- Draft support request to Alpaca (NOT SENT)
- DependencyMap.tsx
- test_operations_gate.py
- test_reliability_fixes.py
- sessions_between
- test_operations_runner.py
- runner.py
- datetime
- schedule.py
- AnthropicProvider
- operations/__main__.py
- ReplayController
- test_preview_readonly.py
- backtest.py
- Execution-data access check: findings (2026-11-04)
- test_evidence_trace.py
- classify
- workspaces.js
- reviewer/validate.py
- Prospective monitoring reliability gate: PROPOSAL (not active)
- evidence_trace.py
- Progress Record (2026-11-03)
- scenarios.py
- Automatic market-session operation: audit and roadmap
- test_jobs.py
- DeskView.tsx
- runner.py
- Automatic market-session operation: audit and roadmap
- test_job_api.py
- Worker
- re
- SPY bid-ask spread pilot: findings (PROVISIONAL)
- test_exposure_check.py
- plan_gate
- Coordinator research workflow (first workflow, 2026-11-10)
- 2. Partial fills: what actually protects a filled quantity
- Lab
- server.py
- orb_experiment.py
- execution_lab/ledger.py
- Paper-order integration test plan: DRAFT, NOT AUTHORIZED, NOT EXECUTED
- Ledger
- no_network_and_no_project_files
- Clock
- test_reliability_fixes.py
- Credential Handling (APCA_API_KEY_ID / APCA_API_SECRET_KEY in .env)
- DayData
- Execution-policy decisions (PROPOSED, all inactive)
- root
- dashboard/ledger.py
- execute_pipeline

## God Nodes (most connected - your core abstractions)
1. `iso()` - 68 edges
2. `MonitorStore` - 62 edges
3. `JobStore` - 50 edges
4. `ReadOnlyAlpacaClient` - 49 edges
5. `RiskLimits` - 49 edges
6. `Params` - 43 edges
7. `QualityChecker` - 41 edges
8. `create_server()` - 39 edges
9. `sessions_between()` - 39 edges
10. `Ledger` - 38 edges

## Surprising Connections (you probably didn't know these)
- `Layers` --references--> `TowerSpec`  [INFERRED]
  docs/CITY.md → dashboard/web/src/components/CityView.tsx
- `Run` --references--> `run_experiment()`  [INFERRED]
  research/001_intraday_momentum/RESULTS_development.md → trading/experiment.py
- `What it is` --references--> `JobStore`  [INFERRED]
  docs/RESEARCH_WORKFLOW.md → trading/jobs.py
- `Exact measurement rules (per symbol, per session)` --references--> `incidents()`  [INFERRED]
  docs/RELIABILITY_GATE_PROPOSAL.md → trading/monitor/readiness.py
- `Group B: needed later, before any strategy-driven paper trading (can wait)` --references--> `size_position()`  [INFERRED]
  docs/EXECUTION_POLICY_DECISIONS.md → trading/risk.py

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

## Communities (121 total, 9 thin omitted)

### Community 0 - "Ledger"
Cohesion: 0.15
Nodes (3): test_wrong_mode_event_rejected(), Ledger, _net_if_closed()

### Community 1 - "iso"
Cohesion: 0.08
Nodes (25): run_until_idle(), monitored_day(), session(), state(), test_bounded_backlog_lookback_and_request_budget(), test_early_close_session_recovered_and_finalized(), test_interval_without_run_records_is_unrecorded_not_downtime(), test_midnight_boundaries_do_not_abandon_the_session() (+17 more)

### Community 2 - "build_map"
Cohesion: 0.12
Nodes (28): by_id(), healthy(), jobs_fixture(), test_cached_job_results_are_labelled_reused(), test_collect_is_read_only_with_isolated_stores(), test_disabled_optional_review_is_not_a_blocker(), test_failed_step_blocks_dependents_as_impact_only(), test_healthy_dependencies_are_ok_and_not_blocked() (+20 more)

### Community 3 - "test_history.py"
Cohesion: 0.09
Nodes (27): alpaca_payloads(), fake_client(), hist_config(), store(), test_cli_blocked_without_credentials(), test_final_period_download_refused(), test_held_out_periods_refused(), test_historical_replay_mode_and_totals() (+19 more)

### Community 4 - "run_review"
Cohesion: 0.06
Nodes (26): setup(), test_cli_env_reads_key_from_dotenv_and_bom_authorization(), review_record(), reviewer_status(), model_review(), _review_availability(), _review_gate(), BudgetDenied (+18 more)

### Community 5 - "test_monitor.py"
Cohesion: 0.13
Nodes (19): _call(), Clock, FakeClient, make_worker(), synthetic_bar(), test_access_errors_recorded_and_feed_never_switched(), test_dead_worker_shows_disconnected(), test_early_close_session_window() (+11 more)

### Community 6 - "execution_feasibility.py"
Cohesion: 0.16
Nodes (16): test_downloads_blocked_while_deferred(), analyze(), analyze_coverage(), check_dates(), coverage_stats(), downloads_blocked(), et_utc(), fetch() (+8 more)

### Community 9 - "test_backtest.py"
Cohesion: 0.12
Nodes (39): days(), run_day(), test_accounting_identity_over_a_run(), test_breach_on_scheduled_exit_bar_uses_time_exit(), test_carry_exit_counts_against_next_session_limits(), test_daily_loss_limit_uses_unrealized_and_exits_next_bar(), test_early_close_shifts_times(), test_entry_is_one_minute_after_decision_with_costs() (+31 more)

### Community 10 - "Experiment 001: Intraday momentum in SPY (draft specification)"
Cohesion: 0.09
Nodes (22): 10. Cost assumptions (to be checked against data), 11. Baselines (same window, same exposure, same sizing), 12. Periods (chronological, fixed before any data is seen), 13. Variant accounting, 14. Evaluation criteria (fixed before running), 15. Roles (performed by one model, Claude, as checklists), 16. Unresolved decisions for owner review, 17. Implementation clarifications (2026-11-03, before any data was seen) (+14 more)

### Community 12 - "hashlib"
Cohesion: 0.10
Nodes (35): attempts(), days(), lock_path(), read_log(), run(), _run(), test_attempts_ledger_records_completed_and_refused(), test_changed_definition_refused() (+27 more)

### Community 13 - "test_readiness.py"
Cohesion: 0.05
Nodes (48): Market readiness panel (`trading/monitor/readiness.py`, `GET /api/monitor/readiness`), Each trading day: one start-up command (2026-11-09), When something looks wrong: where the evidence is, BrokenDB, ev(), healthy(), _isolated_runner(), _serve() (+40 more)

### Community 14 - "compilerOptions"
Cohesion: 0.12
Nodes (15): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, noFallthroughCasesInSwitch (+7 more)

### Community 15 - "jobs.py"
Cohesion: 0.18
Nodes (14): ingest(), inventory(), _keys(), _load_csv(), plan_pipeline(), _plan_rows(), preview(), reconcile() (+6 more)

### Community 17 - "JobStore"
Cohesion: 0.15
Nodes (12): store(), test_overview_is_read_only_when_no_workflow_exists(), env(), job_env(), test_server_job_runner_passes_no_keys(), overview(), jobs_snapshot(), JobStore (+4 more)

### Community 18 - "Experiment 002-895a4f9c5d: development-period result"
Cohesion: 0.22
Nodes (8): Acceptance rules, Comparisons (diagnostic: fixed $5,000 per trade, no halts, dollar P&L / $100,000), Data exclusions and unresolved cases, Experiment 002-895a4f9c5d: development-period result, Limitations, Primary, full account, Recommendation, Run

### Community 19 - "test_orb.py"
Cohesion: 0.28
Nodes (26): days_for(), make(), path(), run(), test_b1_b2_reproducible_unmatched_and_identical_treatment(), test_b3_entry_sizing_and_acceptance(), test_checks_function(), test_completed_bar_signal_then_next_open_entry_and_c1_open_exit() (+18 more)

### Community 20 - "test_spread_measurement.py"
Cohesion: 0.13
Nodes (17): FakeData, FakeResp, q(), rule_rows(), run(), test_access_failure_stops_quotes_without_retry(), test_analyze_end_to_end_offline(), test_dense_window_is_measured_and_wide_spreads_listed() (+9 more)

### Community 21 - "Trading City: product specification"
Cohesion: 0.15
Nodes (12): N, 1. Purpose, 2. Modes (never blended), 3. Shared records, 4. Tower detail tabs, 5. Research responsibilities, 6. Historical replay rules (for milestone 4), 7. Evaluation report contents (+4 more)

### Community 22 - "do_GET"
Cohesion: 0.10
Nodes (27): test_candidates_overview_lists_deferred_candidate_read_only(), test_candidates_overview_tolerates_corrupt_status(), st(), candidates_overview(), experiments_overview(), build(), make_handler(), _body() (+19 more)

### Community 23 - "test_dashboard.py"
Cohesion: 0.11
Nodes (14): _get(), _post(), replay_all(), test_control_requires_header_and_valid_action(), test_csp_allows_only_the_local_agency_workspace(), test_depmap_endpoint_is_read_only_and_has_no_execution_path(), test_duplicates_do_not_double_count(), test_empty_config() (+6 more)

### Community 24 - "Experiment 001-fd13f1fdef: development-period result"
Cohesion: 0.20
Nodes (9): Cost sensitivity, Diagnosis (development data only; `diagnose_development.py`), Experiment 001-fd13f1fdef: development-period result, Limitations, Pass rules (fixed before the run), Recommendation, Reproducibility and file locations, Results (base costs, about 2.3 bp round trip) (+1 more)

### Community 25 - "test_risk_metrics.py"
Cohesion: 0.13
Nodes (18): B. Evidence table, test_client_has_no_order_methods(), test_baseline_notional_cap_binds_and_rounds_down(), test_cost_levels_ordered_and_round_trip(), test_daily_breach_uses_session_start_equity(), test_daily_loss_limit(), test_daily_losses_accumulate_across_trades_and_marks(), test_drawdown_uses_high_water_mark_and_never_resets() (+10 more)

### Community 26 - "test_quality.py"
Cohesion: 0.15
Nodes (22): bar(), checker(), Clock, FakeFeeds, iso(), latest_rows(), _parses(), test_access_failure_is_recorded_backs_off_and_does_not_substitute() (+14 more)

### Community 27 - "test_evaluation.py"
Cohesion: 0.09
Nodes (16): bars(), report(), test_bars_after_exit_are_ignored(), test_classification_rules(), test_cost_accounting_and_sensitivity(), test_event_stream_only_uses_information_available_at_each_time(), test_reports_match_city(), test_research_status_is_honest() (+8 more)

### Community 28 - "lab.py"
Cohesion: 0.12
Nodes (4): BrokerUnavailable, ConnectionLost, FakeBroker, FakeOrder

### Community 29 - "test_reviewer.py"
Cohesion: 0.17
Nodes (30): good_answer(), item_id(), MockProvider, ok(), run(), test_artifact_instruction_injection_is_flagged_and_cannot_flip_gates(), test_cache_reuses_review_and_keys_on_evidence_prompt_and_model(), test_call_budget_per_run() (+22 more)

### Community 30 - "test_execution_lab.py"
Cohesion: 0.11
Nodes (8): _lab(), test_duplicate_fill_events_never_duplicate_fills(), test_pending_orders_count_toward_exposure_used_by_the_risk_gate(), test_reuses_the_approved_risk_and_cost_definitions(), test_scenario_expectations_and_invariants(), test_unknown_outcome_blocks_resubmission_and_is_never_a_rejection(), LabConfig, api()

### Community 31 - "JobsView.tsx"
Cohesion: 0.07
Nodes (29): ACTIVE, Artifact, Boundary, Candidate, CityView, EVENT_KIND, Experiment, Experiments (+21 more)

### Community 32 - "Experiment 002: Long-only opening-range breakout in SPY (specification)"
Cohesion: 0.12
Nodes (16): 1. Notation and data, 2. Timeline (exact timestamps), 3. Strategy (primary configuration), 4. Comparisons (complete definitions), 5. Configurations and variant policy, 6. Acceptance rules, 6a. Implementation invariants (approved 2026-11-04; the hypothesis is unchanged), 7. Required tests before any evaluation (+8 more)

### Community 33 - "Overview.tsx"
Cohesion: 0.11
Nodes (19): ageText(), Boundary, C, CityView, districtTowers(), Exps, floorStations(), FRESH (+11 more)

### Community 34 - "Candidates for experiment 002"
Cohesion: 0.33
Nodes (5): A. Long-only 30-minute opening-range breakout (recommended), B. Long-only gap-down reversal (speculative, partly contaminated), Candidates for experiment 002, How much evidence there is, Recommendation

### Community 36 - "App.tsx"
Cohesion: 0.08
Nodes (44): App(), Boundary, category(), CityView, CORE(), prefersReducedMotion(), STRATEGY_COLORS, strategyTower() (+36 more)

### Community 37 - "startup.py"
Cohesion: 0.28
Nodes (7): test_blocked(), _order_gate(), safety_checks(), order_submission_enabled(), OrderSubmissionDisabled, require_order_submission_allowed(), trading_mode()

### Community 38 - "TowerPanel.tsx"
Cohesion: 0.16
Nodes (29): AccountPanel(), Leaderboard(), StrategyTable(), Marker, PAD, PriceChart(), DecisionsTab(), HistoricalTab() (+21 more)

### Community 39 - "Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04)"
Cohesion: 0.18
Nodes (10): 1. SPY distribution calendar (`spy_distributions_development.json`), 2. Quote interpretation (official Alpaca documentation, read 2026-11-04), 3. Locked and crossed quotes (proposed treatment, not approved), 4. Quote coverage through the proposed 10:00 exit, 5. What this is not, Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04), Future operation (proposed; required before any live use), Retrospective classification vs historical availability (+2 more)

### Community 40 - "ReadOnlyAlpacaClient"
Cohesion: 0.06
Nodes (29): Architecture, City workspaces (Trading City / Website Agency), Connecting real Alpaca data (separate, not started), Launch, Research jobs tab (REAL records, not demo), Strategy City dashboard: DEMO REPLAY, Verification, FakeHttp (+21 more)

### Community 41 - "metrics.py"
Cohesion: 0.19
Nodes (10): test_max_drawdown(), BacktestResult, Trade, EngineResult, bootstrap_sharpe_ci(), daily_returns(), equity_curve(), max_drawdown() (+2 more)

### Community 42 - "TowerSpec"
Cohesion: 0.13
Nodes (14): Ambient life and real events (2026-11-05, second pass), Building vocabulary (procedural, no external assets), Controls and access, Decorative (no data; module `city/ambient.ts`), Deferred, Effects, Effects levels, Layers (+6 more)

### Community 43 - "demo_replay.py"
Cohesion: 0.09
Nodes (22): demo(), test_build_is_deterministic(), test_invalid_config_rejected(), demo_ledger(), test_repeat_build_reproduces_reports(), demo(), _apply_outage(), build_demo() (+14 more)

### Community 44 - "CityView.tsx"
Cohesion: 0.15
Nodes (20): Built, makeKit(), Archetype, ARCHETYPE_LABEL, ARCHETYPES, PALETTE, CityMode, CityView() (+12 more)

### Community 45 - "ExecutionLabView.tsx"
Cohesion: 0.13
Nodes (17): Boundary, Check, CityView, Data, Ev, ExecutionLabView(), hex(), KIND (+9 more)

### Community 46 - "collect"
Cohesion: 0.29
Nodes (6): Dependency-and-health map (2026-11-05), Interaction, Statuses and reasoning, Tests (`tests/test_depmap.py`, synthetic fixtures only), Verification, What is backed by what

### Community 47 - "coordinator.py"
Cohesion: 0.12
Nodes (19): _active(), advance(), _claims(), _close(), collect_evidence(), _finish(), guard_path(), main() (+11 more)

### Community 48 - "trading/validate.py"
Cohesion: 0.13
Nodes (22): Completed Session Rule (15 min after close, SIP delay), Data Check Exit Codes (0 success, 1 API failure, 2 no credentials), Data Feeds: SIP (consolidated) vs IEX (single exchange), 1-Minute Bar Coverage ([open, close), trade-only bars), Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json), Verification Commands (pytest + verify_data_access), Missing-Credential Handling (BLOCKED, exit 2, no network call), full_session() (+14 more)

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
Cohesion: 0.06
Nodes (63): dependencies, react@19.3.1, react-dom@19.3.1, three@0.187.0, devDependencies, @types/react@19.3.0, @types/react-dom@19.3.0, @types/three@0.187.0 (+55 more)

### Community 53 - "WorkflowView.tsx"
Cohesion: 0.18
Nodes (9): ARCH, Boundary, CityView, COLOR, Data, SLOT, Task, Workflow (+1 more)

### Community 54 - "test_journal.py"
Cohesion: 0.15
Nodes (12): test_demo_research_run_writes_consistent_outputs(), test_journal_endpoints(), test_journal_matches_ledger_engine_and_report(), test_journal_mid_replay_marks_session_in_progress(), test_skipped_and_blocked_sessions_are_journaled(), _git_commit(), build_journal(), _pair_exits() (+4 more)

### Community 55 - "SPY bid-ask spread measurement: plan and pilot pre-registration"
Cohesion: 0.17
Nodes (11): 1. Do the open Alpaca questions block a meaningful measurement?, 2. Dates, 3. Quote windows (unchanged; regular 16:00-close sessions; times ET; start and end inclusive, as Alpaca documents), 4. Rules for each quote, 5. Measurements (pilot), 6. Pilot hard limits (implemented in `trading/spread_measurement.py`, tested before any request), 7. Limitations (repeated in the findings), 8. Decisions (+3 more)

### Community 56 - "Execution-data access check: pre-registration"
Cohesion: 0.33
Nodes (5): Dates (all in the development period, 2016-01-04 to 2021-12-31), Execution-data access check: pre-registration, Requests (HTTP GET only, host `https://data.alpaca.markets`), Storage, Validation (pre-declared)

### Community 57 - "checks.py"
Cohesion: 0.09
Nodes (19): Amendment 2026-11-10: broker evidence for "no exposure" (owner-authorized correction), Counting five consecutive sessions, FAIL: a safety or correctness violation, Fixed parameters, INCOMPLETE: not enough evidence to judge, INTERRUPTED: it started properly, but operation broke, Milestone 1 dry run: what counts as pass, failure, interruption and incomplete, PASS: all of these, with evidence (+11 more)

### Community 58 - "MonitorView.tsx"
Cohesion: 0.08
Nodes (36): age(), Bar, Boundary, CityView, et(), FRESH_COLORS, LiveClock(), MON_LEGEND (+28 more)

### Community 59 - "MonitorStore"
Cohesion: 0.08
Nodes (23): server(), test_api_serves_the_same_records_and_writes_nothing(), env(), server_base(), test_start_launches_once_and_supervisor_recovers_without_duplicates(), test_supervisor_only_acts_when_desired_running(), preview(), env() (+15 more)

### Community 60 - "spread_measurement.py"
Cohesion: 0.16
Nodes (12): test_group_summary_pools_by_time_and_excludes_partial(), RequestCapReached, analyze(), _codes(), dir_bytes(), fetch_pilot(), _r(), summarize_groups() (+4 more)

### Community 61 - "test_coordinator.py"
Cohesion: 0.25
Nodes (15): claim(), data_doc(), review_doc(), strategy_doc(), tasks(), test_duplicates_are_prevented(), test_full_workflow_transitions_and_report(), test_invalid_document_fails_then_new_attempt_recovers() (+7 more)

### Community 62 - "random_direction_returns"
Cohesion: 0.33
Nodes (4): test_random_baseline_centered_and_percentile(), percentile_of(), random_direction_returns(), random_long_flat_returns()

### Community 63 - "Read-only market monitoring"
Cohesion: 0.12
Nodes (16): Behaviour, Checklist for observing several consecutive sessions, Controls, Daily report sections, Data permissions measured on 2026-11-04, Data quality: delayed SIP vs IEX (`trading/monitor/quality.py`), Finalization, Limitations (+8 more)

### Community 64 - "test_execution_feasibility.py"
Cohesion: 0.12
Nodes (9): FakeClient, FakeInner, FakeResp, test_access_failure_stops_path_without_retry_and_no_substitution(), test_counting_http_enforces_cap_and_logs_no_headers(), test_coverage_reports_empty_minutes_and_dedupes_identical_only(), test_held_out_dates_refused(), test_quote_validation_flags_crossed_and_disorder() (+1 more)

### Community 65 - "load_credentials"
Cohesion: 0.16
Nodes (10): test_missing_credentials(), test_cli_uses_the_600_request_cap(), test_early_close_and_held_out_refused_even_if_listed(), test_only_pilot_dates_allowed(), load_credentials(), MissingCredentials, _read_dotenv(), check_pilot_dates() (+2 more)

### Community 66 - "Why experiments 001 and 002 failed: a plain-English comparison"
Cohesion: 0.22
Nodes (8): Glossary, Recommended next research task, Side by side, The two strategies in one line each, What the two failures have in common, Why 001 failed: there was no edge to begin with, Why 002 failed: a small edge, entirely eaten by costs, Why experiments 001 and 002 failed: a plain-English comparison

### Community 67 - "alpaca_client.py"
Cohesion: 0.21
Nodes (7): Allowed Hosts (paper-api and data.alpaca.markets only), daytrading-starter skill (planning/analysis only), Offline Test Suite (22 passed), Playwright MCP Server (connected, unused), Verified Components (Python 3.15.2, Git, ignore rules, deps, tests), pytest==9.2.0, requests==2.34.2

### Community 68 - "reviewer/validate.py"
Cohesion: 0.35
Nodes (7): lookup(), resolve(), _citations(), _expect(), _obj(), _str(), validate()

### Community 69 - "Research workflow report: Review our existing strategy failures and recommend the next research decision."
Cohesion: 0.18
Nodes (10): 001 intraday momentum, 002 opening-range breakout, 1. Why experiments 001 and 002 failed, 2. What the provisional spread evidence establishes, 3. Questions blocked on Alpaca, 4. Next research decision (PROPOSAL ONLY), …and what it does not establish, Evidence (+2 more)

### Community 70 - "Draft support request to Alpaca (NOT SENT)"
Cohesion: 0.50
Nodes (3): Answers needed to resume the gap-down candidate (owner checklist), Draft support request to Alpaca (NOT SENT), Notes for the owner (not part of the message)

### Community 71 - "DependencyMap.tsx"
Cohesion: 0.15
Nodes (12): EdgeSpec, ARCH, Boundary, Cause, CityView, DependencyMap(), DepMap, MapEdge (+4 more)

### Community 72 - "test_operations_gate.py"
Cohesion: 0.08
Nodes (30): test_recorded_data_health_has_no_market_values(), green(), test_closed_failed_deferred_unknown_and_multiple_are_refused(), test_dry_run_denies_even_when_everything_else_is_green(), test_empty_registry_means_no_approved_strategy(), test_every_failing_condition_is_reported(), test_fingerprint_mismatch_and_no_approvable_state(), test_kill_switch_on_off_and_fail_closed() (+22 more)

### Community 73 - "test_reliability_fixes.py"
Cohesion: 0.10
Nodes (27): Command Centre boundary, Department-to-implementation map, Evidence trace (one session), Model assistance (DISABLED), Research desk (city view "Research desk"), test_all_unavailable_per_symbol_counts_become_unknown(), test_unmonitored_scheduled_session_breaks_the_streak(), _stored() (+19 more)

### Community 74 - "sessions_between"
Cohesion: 0.18
Nodes (12): XNYS Exchange Calendar (America/New_York, UTC + ET timestamps), exchange_calendars==4.13.2, test_dst_changes_utc_open(), test_requires_timezone_aware_now(), test_session_not_completed_until_data_delay_passes(), test_thanksgiving_skipped_and_black_friday_early_close(), test_weekend_and_observed_holiday(), utc() (+4 more)

### Community 75 - "test_operations_runner.py"
Cohesion: 0.13
Nodes (21): et(), FakeClock, simulate(), test_broker_outage_at_final_check_and_in_session(), test_holiday_does_nothing(), test_late_start_is_incomplete_and_missed_minutes_are_not_replayed(), test_machine_sleep_leaves_missing_minutes_and_heartbeat_gap(), test_not_run_pending_and_injected_violations() (+13 more)

### Community 76 - "runner.py"
Cohesion: 0.14
Nodes (16): Known limitations, Milestone 1: running the automatic session dry run, Other commands (none of them place orders), Persistent background operation: PROPOSED, not installed, Start from a normal PowerShell window, not a Claude desktop terminal (2026-11-10), What it checks, test_app_private_copy_of_the_records_is_detected(), check_outside_onedrive() (+8 more)

### Community 77 - "datetime"
Cohesion: 0.13
Nodes (5): test_sessions_before_the_correction_keep_their_original_rules(), test_acceptance_needs_five_consecutive_passes_with_one_fingerprint(), collect(), now_iso(), OpsStore

### Community 78 - "schedule.py"
Cohesion: 0.18
Nodes (14): test_dst_transitions_move_utc_times_not_et_times(), test_early_close_shifts_closing_and_report(), test_et_date_uses_new_york_not_utc(), test_holiday_and_weekend_have_no_session(), test_regular_day_phases_and_decision_minutes(), test_start_classification_late_and_missed(), U(), et_date() (+6 more)

### Community 79 - "AnthropicProvider"
Cohesion: 0.12
Nodes (13): fake_sdk(), create(), __init__(), test_anthropic_provider_error_mapping_with_mock_sdk(), behaviour(), test_anthropic_provider_success_with_mock_sdk(), test_real_sdk_error_mapping_against_closed_local_port(), AnthropicProvider (+5 more)

### Community 80 - "operations/__main__.py"
Cohesion: 0.13
Nodes (16): test_run_records_each_startup_step_and_logs(), test_second_runner_is_refused_and_says_so(), ops_part(), operations_cross_check(), SingleInstanceLock, _load_heavy(), main(), _run() (+8 more)

### Community 81 - "ReplayController"
Cohesion: 0.28
Nodes (5): test_controller_pause_restart_speed(), test_controller_replay_with_injected_duplicates_matches_direct(), _epoch(), ReplayController, _ticker()

### Community 82 - "test_preview_readonly.py"
Cohesion: 0.23
Nodes (6): _dump_sha(), _post(), test_preview_reads_change_no_records(), test_preview_refuses_state_changes_but_keeps_replay_controls(), test_preview_starts_no_worker_supervisor_or_job_runner(), JobRunner

### Community 83 - "backtest.py"
Cohesion: 0.13
Nodes (7): main(), raw_minutes(), _carry_exit(), last30_return(), _scheduled_exit(), _simulate_day(), signal()

### Community 84 - "Execution-data access check: findings (2026-11-04)"
Cohesion: 0.29
Nodes (6): 1. Historical SIP quotes, 09:30-09:35 ET, 2. Raw SIP minute bars, 09:30-10:02 ET, 3. Prior raw closes and corporate actions, 4. Limitations of this execution data, Conclusion on feasibility, Execution-data access check: findings (2026-11-04)

### Community 85 - "test_evidence_trace.py"
Cohesion: 0.05
Nodes (59): base_inputs(), tasks(), test_api_desk_serves_the_same_records(), test_command_centre_is_deterministic_and_only_names_manual_authorized_commands(), test_desk_tasks_agree_with_stored_trace_records(), test_dry_run_record_discrepancy_is_a_failure_not_a_pass(), test_every_state_is_honest_and_from_the_allowed_set(), test_missing_sources_are_unknown_never_ok() (+51 more)

### Community 87 - "workspaces.js"
Cohesion: 0.83
Nodes (3): check(), probe(), select()

### Community 88 - "reviewer/validate.py"
Cohesion: 0.11
Nodes (16): How text from the artifacts is handled, What it is, and what it is not, What makes a response valid, What the reviewer receives, test_evidence_scope_excludes_data_and_held_out(), test_secrets_and_local_paths_are_redacted(), analysis(), rule_checks() (+8 more)

### Community 89 - "Prospective monitoring reliability gate: PROPOSAL (not active)"
Cohesion: 0.22
Nodes (8): Decisions for the owner, Definitions (all from records the monitor already keeps), Exact measurement rules (per symbol, per session), Proposed gate (all must hold, for every one of SPY, QQQ, IWM), Prospective monitoring reliability gate: PROPOSAL (not active), What approval would change, What "on time within 180 s" establishes, and what it does not, Why a second measure is needed

### Community 90 - "evidence_trace.py"
Cohesion: 0.13
Nodes (15): Blocked, classify_difference(), code_version(), config_version(), evidence_cutoff(), _fp(), gather_inputs(), h_comparison() (+7 more)

### Community 91 - "Progress Record (2026-11-03)"
Cohesion: 0.25
Nodes (9): Order Submission Guard (TRADING_MODE=paper, ORDER_SUBMISSION_ENABLED=true), TradingProject (paper-trading research system), Implemented, Not Yet Verified Against Real API, Known Limitations (pandas deprecation warning, OneDrive venv, feed not echoed), Missing (Alpaca connection, real data, risk controls, Playwright package), Progress Record (2026-11-03), Risk Controls Gap (no position sizing or loss limits), TradingProject README (+1 more)

### Community 92 - "scenarios.py"
Cohesion: 0.22
Nodes (19): test_emergency_stop_can_complete_only_when_everything_is_resolved(), stop_report(), _expect(), invariants(), _new(), run(), run_all(), s01_normal() (+11 more)

### Community 93 - "Automatic market-session operation: audit and roadmap"
Cohesion: 0.18
Nodes (11): Any live pilot, F. Prioritized milestone plan, JARVIS's role, Milestone 1: automatic no-order session dry run (DRY_RUN), Milestone 3: separately authorized automatic paper trading (PAPER), Milestone 4: evidence review, Records and dashboard, Risk-limit mapping (for M2 and M3) (+3 more)

### Community 94 - "test_jobs.py"
Cohesion: 0.21
Nodes (10): statuses(), test_api_and_store_emit_strict_json(), test_corrupt_artifact_fails_then_recovers_with_new_attempt(), test_dashboard_endpoint_matches_store(), test_end_to_end_on_real_artifacts(), test_missing_artifact_fails_ingest_and_blocks_downstream(), test_model_review_unavailable_lists_every_blocker(), test_reconcile_detects_tampered_record() (+2 more)

### Community 95 - "DeskView.tsx"
Cohesion: 0.14
Nodes (17): ARCH, Boundary, CityView, Data, Dept, DeskView(), hex(), SLOT (+9 more)

### Community 96 - "runner.py"
Cohesion: 0.17
Nodes (5): test_committed_code_state_shape(), test_runner_status_file_tracks_the_run(), code_version(), committed_code_state(), Runner

### Community 97 - "Automatic market-session operation: audit and roadmap"
Cohesion: 0.22
Nodes (8): A. Goal and present blockers (plain English), Automatic market-session operation: audit and roadmap, C. Architecture, D. Operating-state model, E. Failure-response matrix, G. Owner decisions that block Milestone 1, H. Smallest useful next task (after your approval), I. Costs and hosting

### Community 98 - "test_job_api.py"
Cohesion: 0.24
Nodes (15): call(), setup(), start(), test_cancel_queued_pipeline_immediately(), test_cancel_running_pipeline_keeps_completed_evidence(), test_dashboard_records_match_database(), test_experiments_and_preview(), test_get_with_foreign_host_refused() (+7 more)

### Community 99 - "Worker"
Cohesion: 0.14
Nodes (10): test_evidence_after_the_cutoff_is_later_evidence_not_a_difference(), test_connection_failures_back_off_and_reconnect(), test_report_operations_downtime_restarts_and_failures(), test_worker_marks_sessions_it_monitors(), _freshness(), iso(), market_state(), _floor_minute() (+2 more)

### Community 100 - "re"
Cohesion: 0.29
Nodes (5): _imports(), test_only_data_health_opens_the_monitoring_database_and_reads_no_prices(), test_operations_imports_from_monitoring_are_limited(), test_research_code_never_imports_monitoring_or_operations(), test_operations_package_has_no_order_capable_code()

### Community 101 - "SPY bid-ask spread pilot: findings (PROVISIONAL)"
Cohesion: 0.33
Nodes (5): 1. Coverage and exclusions, 2. Provisional spread measurements, 3. Actual resource usage, 4. Reliability, and whether the remaining 18 sessions are justified, SPY bid-ask spread pilot: findings (PROVISIONAL)

### Community 102 - "test_exposure_check.py"
Cohesion: 0.07
Nodes (26): check(), _clock(), Fake, FakeHttp, FakeResp, run_session(), test_a_not_compared_periodic_calendar_check_cannot_count_as_verified(), test_account_switch_during_session_is_unverifiable() (+18 more)

### Community 103 - "plan_gate"
Cohesion: 0.25
Nodes (5): _git(), test_fetch_refused_before_credentials_when_plan_not_committed(), test_plan_gate_requires_committed_unchanged_plan(), plan_gate(), PlanNotCommitted

### Community 104 - "Coordinator research workflow (first workflow, 2026-11-10)"
Cohesion: 0.33
Nodes (5): Commands (read-only research), Coordinator research workflow (first workflow, 2026-11-10), Guarantees and safety, Roles vs agents, What it is

### Community 105 - "2. Partial fills: what actually protects a filled quantity"
Cohesion: 0.33
Nodes (6): 2. Partial fills: what actually protects a filled quantity, DOCUMENTED (Alpaca, "Placing Orders", Bracket / OTO / OCO sections), PAPER TEST (must be established, not assumed), UNVERIFIED (assumptions; not stated), Ways to bound the unprotected interval (options, not decisions), What protects a filled quantity in each situation

### Community 106 - "Lab"
Cohesion: 0.29
Nodes (3): test_restart_preserves_outstanding_obligations(), Lab, s08_restart()

### Community 107 - "server.py"
Cohesion: 0.08
Nodes (10): _isolate_monitor(), _isolate_reviewer(), existing_server(), _StopRequested, code_fingerprint(), get_readiness(), launch_window(), main() (+2 more)

### Community 108 - "orb_experiment.py"
Cohesion: 0.17
Nodes (17): test_closed_experiment_refuses_runs_but_allows_inspection(), test_lock_refuses_changed_definition_and_dirty_tree(), test_only_four_configurations_and_held_out_refused(), _popen(), _account(), check_lock(), experiment_id(), fingerprint() (+9 more)

### Community 109 - "execution_lab/ledger.py"
Cohesion: 0.17
Nodes (10): Execution lab: LOCAL EXECUTION SIMULATION, Isolation from the dry run, Open execution-policy decisions (the lab does not choose them), Order lifecycle, Scenarios (all deterministic, seed 0), can_transition(), derive(), _move() (+2 more)

### Community 110 - "Paper-order integration test plan: DRAFT, NOT AUTHORIZED, NOT EXECUTED"
Cohesion: 0.33
Nodes (5): Paper-order integration test plan: DRAFT, NOT AUTHORIZED, NOT EXECUTED, Part 1: safety controls required BEFORE the first test order, Part 2: broker behaviours the test itself must establish, Part 3: stop conditions (any one ends the session; the owner reviews before any further test), Part 4: exit criteria for the test campaign

### Community 112 - "no_network_and_no_project_files"
Cohesion: 0.38
Nodes (4): no_network_and_no_project_files(), connect(), create(), loopback_only()

### Community 114 - "test_reliability_fixes.py"
Cohesion: 0.14
Nodes (18): _at(), FakeRunner, _files(), _plan(), _record(), _startup(), test_after_report_time_completed_or_not(), test_alive_runner_without_recorded_progress_is_never_healthy() (+10 more)

### Community 115 - "Credential Handling (APCA_API_KEY_ID / APCA_API_SECRET_KEY in .env)"
Cohesion: 0.50
Nodes (3): .env.example template, requirements.lock (full pip freeze), Setup Procedure (venv + requirements.lock)

### Community 116 - "DayData"
Cohesion: 0.09
Nodes (20): Milestone 2: forward observation of an approved strategy without orders (SHADOW), DayData, DayResult, _net_if_closed(), CostModel, acceptance_limit(), _carry(), checks() (+12 more)

### Community 118 - "Execution-policy decisions (PROPOSED, all inactive)"
Cohesion: 0.17
Nodes (11): 1. Breach policy: research rules, lab behaviour and a broker policy are three different things, 3. Unknown submission outcomes, 4. Decisions, in two groups, Broker facts (DOCUMENTED, checked 2026-11-10), Execution-policy decisions (PROPOSED, all inactive), Group A: needed to define a bounded paper-integration test (scripted, tiny, no strategy), Group B: needed later, before any strategy-driven paper trading (can wait), LAB (execution rehearsal) (+3 more)

### Community 122 - "root"
Cohesion: 0.33
Nodes (4): make_root(), root(), _w(), git()

### Community 126 - "execute_pipeline"
Cohesion: 0.20
Nodes (4): execute_pipeline(), _finite(), _now(), request_cancel()

## Knowledge Gaps
- **5 isolated node(s):** `Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json)`, `Raw Adjustment Default (no split/dividend adjustment)`, `Playwright MCP Server (connected, unused)`, `pandas==3.1.0`, `pytest==9.2.0`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 959 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Ledger` connect `Ledger` to `test_history.py`, `demo_replay.py`, `dashboard/ledger.py`, `server.py`, `ReplayController`, `test_journal.py`, `test_dashboard.py`, `test_evaluation.py`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `iso()` (e.g. with `healthy()` and `jobs_fixture()`) actually correct?**
  _`iso()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json)`, `Raw Adjustment Default (no split/dividend adjustment)`, `Playwright MCP Server (connected, unused)` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `iso` be split into smaller, more focused modules?**
  _Cohesion score 0.08032786885245902 - nodes in this community are weakly interconnected._
- **Why does `AlpacaAccessError` connect `iso` to `test_execution_feasibility.py`, `load_credentials`, `alpaca_client.py`, `test_history.py`, `test_monitor.py`, `test_exposure_check.py`, `execution_feasibility.py`, `ReadOnlyAlpacaClient`, `Worker`, `test_operations_runner.py`, `server.py`, `trading/validate.py`, `test_quality.py`, `spread_measurement.py`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Should `build_map` be split into smaller, more focused modules?**
  _Cohesion score 0.12179487179487179 - nodes in this community are weakly interconnected._
- **Why does `FakeBroker` connect `lab.py` to `Lab`, `scenarios.py`, `test_execution_lab.py`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._