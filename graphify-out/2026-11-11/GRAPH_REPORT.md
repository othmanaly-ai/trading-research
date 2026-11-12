# Graph Report - TradingProject  (2026-11-11)

## Corpus Check
- 223 files · ~263,111 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: .csv 3, .css 2, .example 1)

## Summary
- 3104 nodes · 8352 edges · 140 communities (127 shown, 13 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 736 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `34cd713f`
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
- experiment.py
- test_quality.py
- test_evaluation.py
- test_paper_session_controls.py
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
- test_monitor.py
- TowerSpec
- pandas
- CityView.tsx
- ExecutionLabView.tsx
- collect
- coordinator.py
- trading/validate.py
- Amendment 2: quote coverage through the proposed exit (pre-registration)
- Feasibility note: gap-down opening reversal (not an experiment)
- Automated second review (model-powered reviewer)
- package.json
- useLiveJson
- DeskView.tsx
- SPY bid-ask spread measurement: plan and pilot pre-registration
- Execution-data access check: pre-registration
- checks.py
- test_risk_metrics.py
- FakeBroker
- spread_measurement.py
- json
- lab.py
- Read-only market monitoring
- test_execution_feasibility.py
- test_paper_adapter.py
- Why experiments 001 and 002 failed: a plain-English comparison
- Verified Components (Python 3.15.2, Git, ignore rules, deps, tests)
- BrokerUnavailable
- Research workflow report: Review our existing strategy failures and recommend the next research decision.
- Draft support request to Alpaca (NOT SENT)
- types.ts
- test_operations_gate.py
- test_reliability_fixes.py
- AlpacaAccessError
- test_operations_runner.py
- Milestone 1: running the automatic session dry run
- datetime
- schedule.py
- sessions_between
- operations/__main__.py
- ReplayController
- test_preview_readonly.py
- backtest.py
- Execution-data access check: findings (2026-11-04)
- test_evidence_trace.py
- Review of the pre-holiday proposal, and one more-frequent alternative (decision paper)
- workspaces.js
- reviewer/validate.py
- Prospective monitoring reliability gate: PROPOSAL (not active)
- evidence_trace.py
- 4. Proposed experiment 003 (draft for a SPEC.md; not approved)
- scenarios.py
- Automatic market-session operation: audit and roadmap
- architecture.ts
- test_coordinator.py
- runner.py
- desk.py
- test_job_api.py
- iso
- re
- SPY bid-ask spread pilot: findings (PROVISIONAL)
- test_exposure_check.py
- Paper-order integration test plan: DRAFT, NOT AUTHORIZED, NOT EXECUTED
- Proposal: test paper-order mechanics independently of any strategy (PROPOSED, nothing approved or built)
- test_desk.py
- Lab
- 2. Partial fills: what actually protects a filled quantity
- orb_experiment.py
- execution_lab/ledger.py
- Strategy City dashboard: DEMO REPLAY
- Ledger
- operations/__main__.py
- sys
- test_reliability_fixes.py
- Readiness checklist while awaiting Alpaca (2026-11-11)
- .step
- .block
- Execution-policy decisions (PROPOSED, all inactive)
- DependencyMap.tsx
- collect
- runner.py
- root
- Data Feeds: SIP (consolidated) vs IEX (single exchange)
- controls.py
- WorkflowView.tsx
- ambient.ts
- F. Prioritized milestone plan
- Supervised paper-order test: minimum decisions (PROPOSED, nothing approved)
- Milestone 1 dry run: what counts as pass, failure, interruption and incomplete
- Refused
- killswitch.py
- candidates_overview
- .evaluation
- Coordinator research workflow (first workflow, 2026-11-10)
- classify
- RoutingHttp
- test_cli_uses_the_600_request_cap
- Operational incidents (evidence only; causes stated only when records support them)
- strict_json

## God Nodes (most connected - your core abstractions)
1. `iso()` - 68 edges
2. `MonitorStore` - 62 edges
3. `JobStore` - 50 edges
4. `ReadOnlyAlpacaClient` - 49 edges
5. `RiskLimits` - 49 edges
6. `Lab` - 44 edges
7. `Params` - 43 edges
8. `FakeBroker` - 41 edges
9. `QualityChecker` - 41 edges
10. `create_server()` - 39 edges

## Surprising Connections (you probably didn't know these)
- `Layers` --references--> `TowerSpec`  [INFERRED]
  docs/CITY.md → dashboard/web/src/components/CityView.tsx
- `Run` --references--> `run_experiment()`  [INFERRED]
  research/001_intraday_momentum/RESULTS_development.md → trading/experiment.py
- `What it is` --references--> `JobStore`  [INFERRED]
  docs/RESEARCH_WORKFLOW.md → trading/jobs.py
- `Exact measurement rules (per symbol, per session)` --references--> `incidents()`  [INFERRED]
  docs/RELIABILITY_GATE_PROPOSAL.md → trading/monitor/readiness.py
- `Evidence trace (one session)` --references--> `correct_stored_report()`  [INFERRED]
  docs/RESEARCH_DESK.md → trading/monitor/reliability.py

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

## Communities (140 total, 13 thin omitted)

### Community 0 - "Ledger"
Cohesion: 0.13
Nodes (4): test_unrealized_is_marked_while_open_and_zero_after(), test_repeat_build_reproduces_reports(), Ledger, _net_if_closed()

### Community 1 - "iso"
Cohesion: 0.11
Nodes (13): Command Centre boundary, Department-to-implementation map, Evidence trace (one session), Model assistance (DISABLED), Research desk (city view "Research desk"), h_capture(), h_structural(), bar_defects() (+5 more)

### Community 2 - "build_map"
Cohesion: 0.12
Nodes (28): by_id(), healthy(), jobs_fixture(), test_cached_job_results_are_labelled_reused(), test_collect_is_read_only_with_isolated_stores(), test_disabled_optional_review_is_not_a_blocker(), test_failed_step_blocks_dependents_as_impact_only(), test_healthy_dependencies_are_ok_and_not_blocked() (+20 more)

### Community 3 - "test_history.py"
Cohesion: 0.10
Nodes (24): alpaca_payloads(), fake_client(), hist_config(), store(), test_cli_blocked_without_credentials(), test_final_period_download_refused(), test_held_out_periods_refused(), test_historical_replay_mode_and_totals() (+16 more)

### Community 4 - "run_review"
Cohesion: 0.06
Nodes (29): setup(), test_cli_env_reads_key_from_dotenv_and_bom_authorization(), test_dashboard_blocker_wording_without_authorization(), test_server_env_strips_credentials(), review_record(), reviewer_status(), model_review(), _review_availability() (+21 more)

### Community 5 - "test_monitor.py"
Cohesion: 0.07
Nodes (23): server(), test_api_serves_the_same_records_and_writes_nothing(), test_api_and_store_emit_strict_json(), env(), server_base(), test_supervisor_only_acts_when_desired_running(), preview(), env() (+15 more)

### Community 6 - "execution_feasibility.py"
Cohesion: 0.13
Nodes (18): test_coverage_reports_empty_minutes_and_dedupes_identical_only(), test_downloads_blocked_while_deferred(), test_quote_validation_flags_crossed_and_disorder(), analyze(), analyze_coverage(), check_dates(), coverage_stats(), downloads_blocked() (+10 more)

### Community 9 - "test_backtest.py"
Cohesion: 0.13
Nodes (38): run_day(), test_accounting_identity_over_a_run(), test_breach_on_scheduled_exit_bar_uses_time_exit(), test_carry_exit_counts_against_next_session_limits(), test_daily_loss_limit_uses_unrealized_and_exits_next_bar(), test_early_close_shifts_times(), test_entry_is_one_minute_after_decision_with_costs(), test_equity_counts_each_cost_exactly_once() (+30 more)

### Community 10 - "Experiment 001: Intraday momentum in SPY (draft specification)"
Cohesion: 0.09
Nodes (22): 10. Cost assumptions (to be checked against data), 11. Baselines (same window, same exposure, same sizing), 12. Periods (chronological, fixed before any data is seen), 13. Variant accounting, 14. Evaluation criteria (fixed before running), 15. Roles (performed by one model, Claude, as checklists), 16. Unresolved decisions for owner review, 17. Implementation clarifications (2026-11-03, before any data was seen) (+14 more)

### Community 12 - "hashlib"
Cohesion: 0.11
Nodes (28): test_spec_version_and_hash(), attempts(), days(), lock_path(), read_log(), run(), _run(), test_attempts_ledger_records_completed_and_refused() (+20 more)

### Community 13 - "test_readiness.py"
Cohesion: 0.06
Nodes (43): Market readiness panel (`trading/monitor/readiness.py`, `GET /api/monitor/readiness`), Startup and recovery (what happens when…), What runs automatically, and what doesn't, BrokenDB, ev(), healthy(), _serve(), test_agg_keeps_unknown_unknown() (+35 more)

### Community 14 - "compilerOptions"
Cohesion: 0.12
Nodes (15): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, noFallthroughCasesInSwitch (+7 more)

### Community 15 - "jobs.py"
Cohesion: 0.10
Nodes (27): statuses(), test_corrupt_artifact_fails_then_recovers_with_new_attempt(), test_dashboard_endpoint_matches_store(), test_end_to_end_on_real_artifacts(), test_missing_artifact_fails_ingest_and_blocks_downstream(), test_model_review_unavailable_lists_every_blocker(), test_reconcile_detects_tampered_record(), test_retry_and_restart_never_duplicate_completed_jobs() (+19 more)

### Community 17 - "JobStore"
Cohesion: 0.11
Nodes (12): store(), env(), job_env(), test_server_job_runner_passes_no_keys(), jobs_snapshot(), _finite(), JobStore, main() (+4 more)

### Community 18 - "Experiment 002-895a4f9c5d: development-period result"
Cohesion: 0.22
Nodes (8): Acceptance rules, Comparisons (diagnostic: fixed $5,000 per trade, no halts, dollar P&L / $100,000), Data exclusions and unresolved cases, Experiment 002-895a4f9c5d: development-period result, Limitations, Primary, full account, Recommendation, Run

### Community 19 - "test_orb.py"
Cohesion: 0.28
Nodes (26): days_for(), make(), path(), run(), test_b1_b2_reproducible_unmatched_and_identical_treatment(), test_b3_entry_sizing_and_acceptance(), test_checks_function(), test_completed_bar_signal_then_next_open_entry_and_c1_open_exit() (+18 more)

### Community 20 - "test_spread_measurement.py"
Cohesion: 0.12
Nodes (19): FakeData, FakeResp, _git(), q(), rule_rows(), run(), test_access_failure_stops_quotes_without_retry(), test_analyze_end_to_end_offline() (+11 more)

### Community 21 - "Trading City: product specification"
Cohesion: 0.15
Nodes (12): N, 1. Purpose, 2. Modes (never blended), 3. Shared records, 4. Tower detail tabs, 5. Research responsibilities, 6. Historical replay rules (for milestone 4), 7. Evaluation report contents (+4 more)

### Community 22 - "do_GET"
Cohesion: 0.13
Nodes (22): test_readiness_endpoint_answers_json_on_internal_error(), st(), make_handler(), _body(), do_GET(), do_POST(), _drain(), _headers() (+14 more)

### Community 23 - "test_dashboard.py"
Cohesion: 0.10
Nodes (17): demo(), _get(), _post(), replay_all(), test_build_is_deterministic(), test_control_requires_header_and_valid_action(), test_csp_allows_only_the_local_agency_workspace(), test_depmap_endpoint_is_read_only_and_has_no_execution_path() (+9 more)

### Community 24 - "Experiment 001-fd13f1fdef: development-period result"
Cohesion: 0.20
Nodes (9): Cost sensitivity, Diagnosis (development data only; `diagnose_development.py`), Experiment 001-fd13f1fdef: development-period result, Limitations, Pass rules (fixed before the run), Recommendation, Reproducibility and file locations, Results (base costs, about 2.3 bp round trip) (+1 more)

### Community 25 - "experiment.py"
Cohesion: 0.11
Nodes (20): main(), raw_minutes(), test_random_baseline_centered_and_percentile(), _check_allowed(), _evaluate(), _git_commit(), _held_out_inspection(), _log_attempt() (+12 more)

### Community 26 - "test_quality.py"
Cohesion: 0.12
Nodes (37): bar(), checker(), Clock, FakeFeeds, iso(), latest_rows(), _parses(), run_until_idle() (+29 more)

### Community 27 - "test_evaluation.py"
Cohesion: 0.11
Nodes (16): bars(), demo_ledger(), report(), test_bars_after_exit_are_ignored(), test_classification_rules(), test_cost_accounting_and_sensitivity(), test_event_stream_only_uses_information_available_at_each_time(), test_reports_match_city() (+8 more)

### Community 28 - "test_paper_session_controls.py"
Cohesion: 0.05
Nodes (24): no_network(), _pf(), posts(), setup(), Switch, test_account_checks_block_entries(), test_exit_needs_policy_and_a_ledger_position(), test_fresh_process_drills_through_the_paper_adapter() (+16 more)

### Community 29 - "test_reviewer.py"
Cohesion: 0.08
Nodes (43): fake_sdk(), create(), __init__(), good_answer(), item_id(), MockProvider, ok(), run() (+35 more)

### Community 30 - "test_execution_lab.py"
Cohesion: 0.10
Nodes (13): _lab(), no_network_and_no_project_files(), connect(), create(), loopback_only(), test_duplicate_fill_events_never_duplicate_fills(), test_emergency_stop_can_complete_only_when_everything_is_resolved(), test_pending_orders_count_toward_exposure_used_by_the_risk_gate() (+5 more)

### Community 31 - "JobsView.tsx"
Cohesion: 0.07
Nodes (29): ACTIVE, Artifact, Boundary, Candidate, CityView, EVENT_KIND, Experiment, Experiments (+21 more)

### Community 32 - "Experiment 002: Long-only opening-range breakout in SPY (specification)"
Cohesion: 0.12
Nodes (16): 1. Notation and data, 2. Timeline (exact timestamps), 3. Strategy (primary configuration), 4. Comparisons (complete definitions), 5. Configurations and variant policy, 6. Acceptance rules, 6a. Implementation invariants (approved 2026-11-04; the hypothesis is unchanged), 7. Required tests before any evaluation (+8 more)

### Community 33 - "Overview.tsx"
Cohesion: 0.08
Nodes (32): age(), Bar, Boundary, CityView, et(), FRESH_COLORS, LiveClock(), MON_LEGEND (+24 more)

### Community 34 - "Candidates for experiment 002"
Cohesion: 0.33
Nodes (5): A. Long-only 30-minute opening-range breakout (recommended), B. Long-only gap-down reversal (speculative, partly contaminated), Candidates for experiment 002, How much evidence there is, Recommendation

### Community 36 - "App.tsx"
Cohesion: 0.11
Nodes (29): App(), Boundary, category(), CityView, CORE(), prefersReducedMotion(), STRATEGY_COLORS, strategyTower() (+21 more)

### Community 37 - "startup.py"
Cohesion: 0.25
Nodes (8): test_new_modules_have_no_network_code_and_the_real_guard_is_untouched(), test_blocked(), _order_gate(), safety_checks(), order_submission_enabled(), OrderSubmissionDisabled, require_order_submission_allowed(), trading_mode()

### Community 38 - "TowerPanel.tsx"
Cohesion: 0.17
Nodes (28): AccountPanel(), Leaderboard(), StrategyTable(), Marker, PAD, PriceChart(), DecisionsTab(), HistoricalTab() (+20 more)

### Community 39 - "Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04)"
Cohesion: 0.15
Nodes (12): 1. SPY distribution calendar (`spy_distributions_development.json`), 2. Quote interpretation (official Alpaca documentation, read 2026-11-04), 3. Locked and crossed quotes (proposed treatment, not approved), 4. Quote coverage through the proposed 10:00 exit, 5. What this is not, Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04), Future operation (proposed; required before any live use), Retrospective classification vs historical availability (+4 more)

### Community 40 - "ReadOnlyAlpacaClient"
Cohesion: 0.08
Nodes (17): FakeHttp, FakeResponse, test_account_keeps_only_listed_fields(), test_clock_is_a_paper_host_get_with_listed_fields_only(), test_corporate_actions_merge_and_cap(), test_multi_symbol_pagination_merges_pages_and_keeps_feed(), test_only_paper_and_data_hosts_allowed(), test_pagination_follows_tokens() (+9 more)

### Community 41 - "test_monitor.py"
Cohesion: 0.11
Nodes (22): _call(), Clock, FakeClient, make_worker(), synthetic_bar(), test_access_errors_recorded_and_feed_never_switched(), test_connection_failures_back_off_and_reconnect(), test_dead_worker_shows_disconnected() (+14 more)

### Community 42 - "TowerSpec"
Cohesion: 0.13
Nodes (14): Ambient life and real events (2026-11-05, second pass), Building vocabulary (procedural, no external assets), Controls and access, Decorative (no data; module `city/ambient.ts`), Deferred, Effects, Effects levels, Layers (+6 more)

### Community 43 - "pandas"
Cohesion: 0.09
Nodes (20): days(), DayData, last30_return(), _apply_outage(), build_demo(), build_replay(), ConfigError, Context (+12 more)

### Community 44 - "CityView.tsx"
Cohesion: 0.15
Nodes (20): buildArchetype(), Built, makeKit(), Archetype, ARCHETYPE_LABEL, ARCHETYPES, PALETTE, CityMode (+12 more)

### Community 45 - "ExecutionLabView.tsx"
Cohesion: 0.10
Nodes (24): Boundary, Check, CityView, CTRL_COL(), Data, Ev, ExecutionLabView(), FN_OF (+16 more)

### Community 46 - "collect"
Cohesion: 0.29
Nodes (6): Dependency-and-health map (2026-11-05), Interaction, Statuses and reasoning, Tests (`tests/test_depmap.py`, synthetic fixtures only), Verification, What is backed by what

### Community 47 - "coordinator.py"
Cohesion: 0.16
Nodes (16): _active(), advance(), _claims(), collect_evidence(), _finish(), guard_path(), main(), _now() (+8 more)

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
Cohesion: 0.12
Nodes (16): After the call, Automated second review (model-powered reviewer), Before each call, How cost enforcement works, How text from the artifacts is handled, Limitations, Owner decision (2026-11-04), Proposed limits (not yet authorized) (+8 more)

### Community 52 - "package.json"
Cohesion: 0.09
Nodes (26): dependencies, react@19.3.1, react-dom@19.3.1, three@0.187.0, devDependencies, @types/react@19.3.0, @types/react-dom@19.3.0, @types/three@0.187.0 (+18 more)

### Community 53 - "useLiveJson"
Cohesion: 0.12
Nodes (24): et(), OperationsView(), Ops, Check, cls(), et(), Incident, Readiness (+16 more)

### Community 54 - "DeskView.tsx"
Cohesion: 0.14
Nodes (16): ARCH, Boundary, CityView, Data, Dept, DeskView(), hex(), SLOT (+8 more)

### Community 55 - "SPY bid-ask spread measurement: plan and pilot pre-registration"
Cohesion: 0.17
Nodes (11): 1. Do the open Alpaca questions block a meaningful measurement?, 2. Dates, 3. Quote windows (unchanged; regular 16:00-close sessions; times ET; start and end inclusive, as Alpaca documents), 4. Rules for each quote, 5. Measurements (pilot), 6. Pilot hard limits (implemented in `trading/spread_measurement.py`, tested before any request), 7. Limitations (repeated in the findings), 8. Decisions (+3 more)

### Community 56 - "Execution-data access check: pre-registration"
Cohesion: 0.33
Nodes (5): Dates (all in the development period, 2016-01-04 to 2021-12-31), Execution-data access check: pre-registration, Requests (HTTP GET only, host `https://data.alpaca.markets`), Storage, Validation (pre-declared)

### Community 57 - "checks.py"
Cohesion: 0.16
Nodes (12): _clock(), test_a_not_compared_periodic_calendar_check_cannot_count_as_verified(), test_calendar_at_the_final_check_and_in_session_is_a_positive_comparison(), test_calendar_not_compared_near_a_boundary_is_not_ok(), account_check(), calendar_agreement(), clock_check(), exposure_check() (+4 more)

### Community 58 - "test_risk_metrics.py"
Cohesion: 0.10
Nodes (21): Milestone 2: forward observation of an approved strategy without orders (SHADOW), test_baseline_notional_cap_binds_and_rounds_down(), test_cost_levels_ordered_and_round_trip(), test_daily_breach_uses_session_start_equity(), test_daily_loss_limit(), test_daily_losses_accumulate_across_trades_and_marks(), test_drawdown_uses_high_water_mark_and_never_resets(), test_entry_that_cannot_fit_is_rejected() (+13 more)

### Community 59 - "FakeBroker"
Cohesion: 0.10
Nodes (12): run_session(), test_account_switch_during_session_is_unverifiable(), test_broker_unavailable_at_closing_is_never_a_pass(), get_positions(), test_empty_account_session_passes_with_closing_evidence(), test_local_assertion_and_fresh_heartbeat_cannot_substitute_for_broker_evidence(), test_missing_credentials_at_closing_is_never_a_pass(), factory() (+4 more)

### Community 60 - "spread_measurement.py"
Cohesion: 0.11
Nodes (19): test_early_close_and_held_out_refused_even_if_listed(), test_fetch_refused_before_credentials_when_plan_not_committed(), test_group_summary_pools_by_time_and_excludes_partial(), test_only_pilot_dates_allowed(), analyze(), check_pilot_dates(), _codes(), dir_bytes() (+11 more)

### Community 61 - "json"
Cohesion: 0.06
Nodes (23): demo(), test_demo_research_run_writes_consistent_outputs(), test_historical_research_run_refuses_without_data(), test_journal_endpoints(), test_journal_matches_ledger_engine_and_report(), test_journal_mid_replay_marks_session_in_progress(), test_skipped_and_blocked_sessions_are_journaled(), test_intended_account_file_rules() (+15 more)

### Community 62 - "lab.py"
Cohesion: 0.09
Nodes (18): lab(), no_network(), test_a_cancel_requested_again_by_a_fresh_broker_client_is_recorded_not_dropped(), test_emergency_exposure_action_unset_is_reported_not_chosen(), test_emergency_stop_never_cancels_protective_stops(), test_escalation_timing_follows_policy_and_unset_is_an_owner_decision(), test_invalid_policy_value_blocks(), test_ledger_cash_equals_broker_cash_after_a_round_trip_with_fees() (+10 more)

### Community 63 - "Read-only market monitoring"
Cohesion: 0.13
Nodes (14): Behaviour, Checklist for observing several consecutive sessions, Controls, Daily report sections, Data permissions measured on 2026-11-04, Data quality: delayed SIP vs IEX (`trading/monitor/quality.py`), Finalization, Limitations (+6 more)

### Community 64 - "test_execution_feasibility.py"
Cohesion: 0.12
Nodes (8): FakeClient, FakeInner, FakeResp, test_access_failure_stops_path_without_retry_and_no_substitution(), test_counting_http_enforces_cap_and_logs_no_headers(), test_held_out_dates_refused(), CountingHttp, RequestCapReached

### Community 65 - "test_paper_adapter.py"
Cohesion: 0.09
Nodes (21): Execution core (2026-11-10, offline), _imports(), lab_with(), no_network(), order(), test_accept_fill_and_full_reconciliation_of_orders_fills_positions_and_cash(), test_adapter_has_no_network_transport_and_guards_every_write(), test_adapter_is_unreachable_from_dashboard_dry_run_and_lab() (+13 more)

### Community 66 - "Why experiments 001 and 002 failed: a plain-English comparison"
Cohesion: 0.22
Nodes (8): Glossary, Recommended next research task, Side by side, The two strategies in one line each, What the two failures have in common, Why 001 failed: there was no edge to begin with, Why 002 failed: a small edge, entirely eaten by costs, Why experiments 001 and 002 failed: a plain-English comparison

### Community 67 - "Verified Components (Python 3.15.2, Git, ignore rules, deps, tests)"
Cohesion: 0.15
Nodes (13): Allowed Hosts (paper-api and data.alpaca.markets only), daytrading-starter skill (planning/analysis only), Order Submission Guard (TRADING_MODE=paper, ORDER_SUBMISSION_ENABLED=true), TradingProject (paper-trading research system), Implemented, Not Yet Verified Against Real API, Missing (Alpaca connection, real data, risk controls, Playwright package), Playwright MCP Server (connected, unused), Progress Record (2026-11-03) (+5 more)

### Community 68 - "BrokerUnavailable"
Cohesion: 0.13
Nodes (5): BrokerUnavailable, ConnectionLost, AlpacaPaperOrderAdapter, _num(), Transport

### Community 69 - "Research workflow report: Review our existing strategy failures and recommend the next research decision."
Cohesion: 0.18
Nodes (10): 001 intraday momentum, 002 opening-range breakout, 1. Why experiments 001 and 002 failed, 2. What the provisional spread evidence establishes, 3. Questions blocked on Alpaca, 4. Next research decision (PROPOSAL ONLY), …and what it does not establish, Evidence (+2 more)

### Community 70 - "Draft support request to Alpaca (NOT SENT)"
Cohesion: 0.40
Nodes (4): Answers needed to resume the gap-down candidate (owner checklist), Notes for the owner (not part of the message), Support request to Alpaca: FINAL for the owner to send (NOT SENT), What the answers would resolve, and what stays unknown (owner notes, 2026-11-11)

### Community 71 - "types.ts"
Cohesion: 0.18
Nodes (16): Props, Account, Connection, Evaluation, EventType, Instance, InstrumentView, Meta (+8 more)

### Community 72 - "test_operations_gate.py"
Cohesion: 0.13
Nodes (19): test_recorded_data_health_has_no_market_values(), green(), test_closed_failed_deferred_unknown_and_multiple_are_refused(), test_dry_run_denies_even_when_everything_else_is_green(), test_empty_registry_means_no_approved_strategy(), test_every_failing_condition_is_reported(), test_fingerprint_mismatch_and_no_approvable_state(), test_missing_or_corrupt_file_fails_closed() (+11 more)

### Community 73 - "test_reliability_fixes.py"
Cohesion: 0.15
Nodes (15): test_finalized_state_never_carries_pending_wording(), test_incident_events_are_not_request_failures(), monitor_sessions(), ensure_schema(), git_version(), daily_report(), _intervals_uncovered(), _median() (+7 more)

### Community 74 - "AlpacaAccessError"
Cohesion: 0.14
Nodes (12): B. Evidence table, test_access_refusal_on_quotes_raises_without_retry(), test_client_has_no_order_methods(), test_credentials_from_dotenv(), test_feed_refusal_raises_and_is_not_substituted(), test_missing_credentials(), test_verify_refuses_held_out_sample_before_network(), AlpacaAccessError (+4 more)

### Community 75 - "test_operations_runner.py"
Cohesion: 0.16
Nodes (21): test_position_found_fails_the_session_and_blocks_acceptance(), et(), simulate(), test_broker_outage_at_final_check_and_in_session(), test_holiday_does_nothing(), test_late_start_is_incomplete_and_missed_minutes_are_not_replayed(), test_machine_sleep_leaves_missing_minutes_and_heartbeat_gap(), test_not_run_pending_and_injected_violations() (+13 more)

### Community 76 - "Milestone 1: running the automatic session dry run"
Cohesion: 0.20
Nodes (9): Each trading day: one start-up command (2026-11-09), Known limitations, Milestone 1: running the automatic session dry run, Other commands (none of them place orders), Persistent background operation: PROPOSED, not installed, Recovering the production city server (port 8765), Start from a normal PowerShell window, not a Claude desktop terminal (2026-11-10), What it checks (+1 more)

### Community 77 - "datetime"
Cohesion: 0.13
Nodes (6): test_sessions_before_the_correction_keep_their_original_rules(), test_acceptance_needs_five_consecutive_passes_with_one_fingerprint(), _record(), collect(), now_iso(), OpsStore

### Community 78 - "schedule.py"
Cohesion: 0.18
Nodes (14): test_dst_transitions_move_utc_times_not_et_times(), test_early_close_shifts_closing_and_report(), test_et_date_uses_new_york_not_utc(), test_holiday_and_weekend_have_no_session(), test_regular_day_phases_and_decision_minutes(), test_start_classification_late_and_missed(), U(), et_date() (+6 more)

### Community 79 - "sessions_between"
Cohesion: 0.17
Nodes (11): Offline Test Suite (22 passed), test_dst_changes_utc_open(), test_requires_timezone_aware_now(), test_session_not_completed_until_data_delay_passes(), test_thanksgiving_skipped_and_black_friday_early_close(), test_weekend_and_observed_holiday(), utc(), _calendar() (+3 more)

### Community 80 - "operations/__main__.py"
Cohesion: 0.22
Nodes (10): test_app_private_copy_of_the_records_is_detected(), check_outside_onedrive(), private_copies(), reports_dir(), runtime_dir(), RuntimeDirRefused, _under_packages(), view_redirected() (+2 more)

### Community 81 - "ReplayController"
Cohesion: 0.28
Nodes (5): test_controller_pause_restart_speed(), test_controller_replay_with_injected_duplicates_matches_direct(), _epoch(), ReplayController, _ticker()

### Community 82 - "test_preview_readonly.py"
Cohesion: 0.12
Nodes (8): _isolate_monitor(), _isolate_reviewer(), _dump_sha(), _post(), test_preview_reads_change_no_records(), test_preview_refuses_state_changes_but_keeps_replay_controls(), test_preview_starts_no_worker_supervisor_or_job_runner(), JobRunner

### Community 83 - "backtest.py"
Cohesion: 0.07
Nodes (21): BacktestResult, _carry_exit(), DayResult, _net_if_closed(), _scheduled_exit(), _simulate_day(), Trade, CostModel (+13 more)

### Community 84 - "Execution-data access check: findings (2026-11-04)"
Cohesion: 0.29
Nodes (6): 1. Historical SIP quotes, 09:30-09:35 ET, 2. Raw SIP minute bars, 09:30-10:02 ET, 3. Prior raw closes and corporate actions, 4. Limitations of this execution data, Conclusion on feasibility, Execution-data access check: findings (2026-11-04)

### Community 85 - "test_evidence_trace.py"
Cohesion: 0.17
Nodes (22): desk(), dump_sha(), _live(), make_session(), _reset_hooks(), states(), test_changed_handler_source_is_recomputed_not_reused(), test_correction_that_drops_reclassified_events_is_flagged_and_now_counted() (+14 more)

### Community 86 - "Review of the pre-holiday proposal, and one more-frequent alternative (decision paper)"
Cohesion: 0.18
Nodes (10): 1. Does the published pre-holiday evidence cover our interval? No., 2. Basis of the three statements in the proposal, 3. Can 53 trades, and about 9 a year, produce useful evidence in practical time? No., 4. How the 2% stop relates to the risk limits (correction), 5. One more frequent alternative our data can honestly evaluate, 6. Comparison, 7. Recommendation, 8. Decisions prepared for you (+2 more)

### Community 87 - "workspaces.js"
Cohesion: 0.83
Nodes (3): check(), probe(), select()

### Community 88 - "reviewer/validate.py"
Cohesion: 0.13
Nodes (14): add(), EvidenceError, EvidenceTooLarge, lookup(), resolve(), _Sanitizer, _sections(), _sha() (+6 more)

### Community 89 - "Prospective monitoring reliability gate: PROPOSAL (not active)"
Cohesion: 0.22
Nodes (8): Decisions for the owner, Definitions (all from records the monitor already keeps), Exact measurement rules (per symbol, per session), Proposed gate (all must hold, for every one of SPY, QQQ, IWM), Prospective monitoring reliability gate: PROPOSAL (not active), What approval would change, What "on time within 180 s" establishes, and what it does not, Why a second measure is needed

### Community 90 - "evidence_trace.py"
Cohesion: 0.09
Nodes (21): test_a_result_may_not_claim_the_proposed_gate_is_active(), _active_run(), Blocked, classify_difference(), code_version(), config_version(), evidence_cutoff(), _fp() (+13 more)

### Community 91 - "4. Proposed experiment 003 (draft for a SPEC.md; not approved)"
Cohesion: 0.11
Nodes (17): 1. What research can proceed now, and what waits for Alpaca, 2. Three hypotheses compared, 3. Recommendation: H2, pre-holiday sessions, 4.1 Data, 4.2 Which sessions trade, 4.3 Trading rules, 4.4 Costs, 4.5 Benchmarks (computed with the same engine, costs and limits) (+9 more)

### Community 92 - "scenarios.py"
Cohesion: 0.17
Nodes (25): stop_report(), _expect(), _intents(), invariants(), _new(), run(), run_all(), s01_normal() (+17 more)

### Community 93 - "Automatic market-session operation: audit and roadmap"
Cohesion: 0.22
Nodes (8): A. Goal and present blockers (plain English), Automatic market-session operation: audit and roadmap, C. Architecture, D. Operating-state model, E. Failure-response matrix, G. Owner decisions that block Milestone 1, H. Smallest useful next task (after your approval), I. Costs and hosting

### Community 94 - "architecture.ts"
Cohesion: 0.19
Nodes (17): BUILDERS, Kit, worldUV(), buildScenery(), rng(), Scenery, skyDome(), BAY_W (+9 more)

### Community 95 - "test_coordinator.py"
Cohesion: 0.29
Nodes (14): claim(), data_doc(), review_doc(), strategy_doc(), tasks(), test_duplicates_are_prevented(), test_full_workflow_transitions_and_report(), test_invalid_document_fails_then_new_attempt_recovers() (+6 more)

### Community 96 - "runner.py"
Cohesion: 0.26
Nodes (3): test_runner_status_file_tracks_the_run(), code_version(), Runner

### Community 97 - "desk.py"
Cohesion: 0.29
Nodes (13): _age_s(), archive(), build_desk(), command_centre(), data_centre(), _fmt_counts(), _from_trace(), operations_dept() (+5 more)

### Community 98 - "test_job_api.py"
Cohesion: 0.24
Nodes (15): call(), setup(), start(), test_cancel_queued_pipeline_immediately(), test_cancel_running_pipeline_keeps_completed_evidence(), test_dashboard_records_match_database(), test_experiments_and_preview(), test_get_with_foreign_host_refused() (+7 more)

### Community 99 - "iso"
Cohesion: 0.11
Nodes (14): test_report_operations_downtime_restarts_and_failures(), test_worker_marks_sessions_it_monitors(), launch(), correct_stored_report(), _freshness(), iso(), market_state(), now_utc() (+6 more)

### Community 100 - "re"
Cohesion: 0.29
Nodes (5): _imports(), test_only_data_health_opens_the_monitoring_database_and_reads_no_prices(), test_operations_imports_from_monitoring_are_limited(), test_research_code_never_imports_monitoring_or_operations(), test_operations_package_has_no_order_capable_code()

### Community 101 - "SPY bid-ask spread pilot: findings (PROVISIONAL)"
Cohesion: 0.33
Nodes (5): 1. Coverage and exclusions, 2. Provisional spread measurements, 3. Actual resource usage, 4. Reliability, and whether the remaining 18 sessions are justified, SPY bid-ask spread pilot: findings (PROVISIONAL)

### Community 102 - "test_exposure_check.py"
Cohesion: 0.16
Nodes (10): check(), Fake, FakeResp, test_broker_unavailable_is_unverifiable(), test_empty_account_is_verified_none_with_time_and_identity(), test_incomplete_or_malformed_responses_are_unverifiable(), test_open_position_is_exposure_found_and_nothing_is_closed(), test_outstanding_or_partially_filled_order_is_exposure() (+2 more)

### Community 103 - "Paper-order integration test plan: DRAFT, NOT AUTHORIZED, NOT EXECUTED"
Cohesion: 0.22
Nodes (8): Controls that must work before the first order: status on 2026-11-11, Exact session script, Paper-order integration test plan: DRAFT, NOT AUTHORIZED, NOT EXECUTED, Part 1: safety controls required BEFORE the first test order, Part 2: broker behaviours the test itself must establish, Part 3: stop conditions (any one ends the session; the owner reviews before any further test), Part 4: exit criteria for the test campaign, Part 5: control status today, and the exact session script (PROPOSAL, UNEXECUTED)

### Community 104 - "Proposal: test paper-order mechanics independently of any strategy (PROPOSED, nothing approved or built)"
Cohesion: 0.25
Nodes (7): 1. Does the roadmap permit it?, 2. What it would test, and what it cannot, 3. Design principles (from the existing plan, unchanged), 4. What exists, and what is missing, 5. Proposed sequence (each step needs its own owner decision), 6. The next decision, Proposal: test paper-order mechanics independently of any strategy (PROPOSED, nothing approved or built)

### Community 105 - "test_desk.py"
Cohesion: 0.24
Nodes (10): base_inputs(), tasks(), test_api_desk_serves_the_same_records(), test_command_centre_is_deterministic_and_only_names_manual_authorized_commands(), test_desk_tasks_agree_with_stored_trace_records(), test_dry_run_record_discrepancy_is_a_failure_not_a_pass(), test_every_state_is_honest_and_from_the_allowed_set(), test_missing_sources_are_unknown_never_ok() (+2 more)

### Community 106 - "Lab"
Cohesion: 0.13
Nodes (11): test_never_sent_only_with_durable_proof_and_uncertain_outcomes_stay_unresolved(), test_orphaned_intent_from_a_crash_during_the_checks_expires_on_reconciliation(), test_restart_preserves_outstanding_obligations(), test_unreadable_kill_switch_or_failing_controls_fail_closed(), _crash(), Lab, since(), _ts() (+3 more)

### Community 107 - "2. Partial fills: what actually protects a filled quantity"
Cohesion: 0.33
Nodes (6): 2. Partial fills: what actually protects a filled quantity, DOCUMENTED (Alpaca, "Placing Orders", Bracket / OTO / OCO sections), PAPER TEST (must be established, not assumed), UNVERIFIED (assumptions; not stated), Ways to bound the unprotected interval (options, not decisions), What protects a filled quantity in each situation

### Community 108 - "orb_experiment.py"
Cohesion: 0.19
Nodes (16): test_closed_experiment_refuses_runs_but_allows_inspection(), test_lock_refuses_changed_definition_and_dirty_tree(), test_only_four_configurations_and_held_out_refused(), _account(), check_lock(), experiment_id(), fingerprint(), _git_commit() (+8 more)

### Community 109 - "execution_lab/ledger.py"
Cohesion: 0.15
Nodes (11): Execution lab: LOCAL EXECUTION SIMULATION, Isolation from the dry run, Open execution-policy decisions (the lab does not choose them), Order lifecycle, Scenarios (all deterministic, seed 0), can_transition(), derive(), _move() (+3 more)

### Community 110 - "Strategy City dashboard: DEMO REPLAY"
Cohesion: 0.25
Nodes (7): Architecture, City workspaces (Trading City / Website Agency), Connecting real Alpaca data (separate, not started), Launch, Research jobs tab (REAL records, not demo), Strategy City dashboard: DEMO REPLAY, Verification

### Community 112 - "operations/__main__.py"
Cohesion: 0.19
Nodes (10): test_second_runner_is_refused_and_says_so(), SingleInstanceLock, _load_heavy(), main(), _run(), echo(), step(), _store() (+2 more)

### Community 113 - "sys"
Cohesion: 0.08
Nodes (23): test_fresh_process_crash_drill(), existing_server(), check(), main(), _no_network(), _open(), run_all(), run_drill() (+15 more)

### Community 114 - "test_reliability_fixes.py"
Cohesion: 0.10
Nodes (24): _at(), FakeRunner, _files(), _plan(), _startup(), _stored(), test_after_report_time_completed_or_not(), test_alive_runner_without_recorded_progress_is_never_healthy() (+16 more)

### Community 115 - "Readiness checklist while awaiting Alpaca (2026-11-11)"
Cohesion: 0.40
Nodes (4): A. Blocked by the historical-quote questions, B. Can proceed independently now, C. Blocked by something other than Alpaca, Readiness checklist while awaiting Alpaca (2026-11-11)

### Community 117 - ".block"
Cohesion: 0.46
Nodes (8): Builder, command(), construction(), finned(), operations(), paired(), terraced(), twisted()

### Community 118 - "Execution-policy decisions (PROPOSED, all inactive)"
Cohesion: 0.17
Nodes (11): 1. Breach policy: research rules, lab behaviour and a broker policy are three different things, 3. Unknown submission outcomes, 4. Decisions, in two groups, Broker facts (DOCUMENTED, checked 2026-11-10), Execution-policy decisions (PROPOSED, all inactive), Group A: needed to define a bounded paper-integration test (scripted, tiny, no strategy), Group B: needed later, before any strategy-driven paper trading (can wait), LAB (execution rehearsal) (+3 more)

### Community 119 - "DependencyMap.tsx"
Cohesion: 0.14
Nodes (13): EdgeSpec, TowerSpec, ARCH, Boundary, Cause, CityView, DependencyMap(), DepMap (+5 more)

### Community 120 - "collect"
Cohesion: 0.12
Nodes (10): collect(), depmap_part(), locks_part(), monitor_part(), ops_part(), research_part(), trace_part(), _rows() (+2 more)

### Community 121 - "runner.py"
Cohesion: 0.10
Nodes (8): test_committed_code_state_shape(), test_data_health_reads_monitor_store(), operations_cross_check(), local_checks(), _parse(), read(), code_fingerprint(), committed_code_state()

### Community 122 - "root"
Cohesion: 0.33
Nodes (4): make_root(), root(), _w(), git()

### Community 123 - "Data Feeds: SIP (consolidated) vs IEX (single exchange)"
Cohesion: 0.17
Nodes (11): Completed Session Rule (15 min after close, SIP delay), Data Feeds: SIP (consolidated) vs IEX (single exchange), .env.example template, 1-Minute Bar Coverage ([open, close), trade-only bars), requirements.lock (full pip freeze), Setup Procedure (venv + requirements.lock), Verification Commands (pytest + verify_data_access), XNYS Exchange Calendar (America/New_York, UTC + ET timestamps) (+3 more)

### Community 124 - "controls.py"
Cohesion: 0.21
Nodes (5): account_reasons(), EntryControls, host_reasons(), kill_switch_reasons(), session_preflight()

### Community 125 - "WorkflowView.tsx"
Cohesion: 0.18
Nodes (9): ARCH, Boundary, CityView, COLOR, Data, SLOT, Task, Workflow (+1 more)

### Community 126 - "ambient.ts"
Cohesion: 0.20
Nodes (11): Ambient, buildAmbient(), Car, Effects, Landmark, rng(), signTexture(), VEHICLES (+3 more)

### Community 127 - "F. Prioritized milestone plan"
Cohesion: 0.18
Nodes (11): Any live pilot, F. Prioritized milestone plan, JARVIS's role, Milestone 1: automatic no-order session dry run (DRY_RUN), Milestone 3: separately authorized automatic paper trading (PAPER), Milestone 4: evidence review, Records and dashboard, Risk-limit mapping (for M2 and M3) (+3 more)

### Community 128 - "Supervised paper-order test: minimum decisions (PROPOSED, nothing approved)"
Cohesion: 0.22
Nodes (8): 1. Intended paper account [A1, A10], 2. Instruments, maximum quantity, notional exposure, test-loss limit [A1, plus a new item], 3. Entry order type and handling of partial fills [A2], 4. Unprotected exposure and emergency action [A3, A6], 5. Unknown-outcome and cancellation escalation [A4, A5], 6. Reset authority and manual-account activity [A7, A8], Evidence for "offline milestone verified" (2026-11-11), Supervised paper-order test: minimum decisions (PROPOSED, nothing approved)

### Community 129 - "Milestone 1 dry run: what counts as pass, failure, interruption and incomplete"
Cohesion: 0.18
Nodes (10): Amendment 2026-11-10: broker evidence for "no exposure" (owner-authorized correction), Counting five consecutive sessions, FAIL: a safety or correctness violation, Fixed parameters, INCOMPLETE: not enough evidence to judge, INTERRUPTED: it started properly, but operation broke, Milestone 1 dry run: what counts as pass, failure, interruption and incomplete, PASS: all of these, with evidence (+2 more)

### Community 130 - "Refused"
Cohesion: 0.20
Nodes (5): test_prohibited_actions_are_refused(), _close(), Refused, request_action(), validate_document()

### Community 131 - "killswitch.py"
Cohesion: 0.44
Nodes (7): test_kill_switch_on_off_and_fail_closed(), _history(), KillSwitchState, set_off(), set_on(), state(), kill_switch_path()

### Community 132 - "candidates_overview"
Cohesion: 0.25
Nodes (5): test_candidates_overview_lists_deferred_candidate_read_only(), test_candidates_overview_tolerates_corrupt_status(), candidates_overview(), experiments_overview(), build()

### Community 134 - "Coordinator research workflow (first workflow, 2026-11-10)"
Cohesion: 0.33
Nodes (5): Commands (read-only research), Coordinator research workflow (first workflow, 2026-11-10), Guarantees and safety, Roles vs agents, What it is

## Knowledge Gaps
- **5 isolated node(s):** `pandas==3.1.0`, `Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json)`, `Playwright MCP Server (connected, unused)`, `pytest==9.2.0`, `Raw Adjustment Default (no split/dividend adjustment)`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1075 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Ledger` connect `Ledger` to `test_history.py`, `.evaluation`, `ReplayController`, `test_dashboard.py`, `test_evaluation.py`, `json`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `iso()` (e.g. with `healthy()` and `jobs_fixture()`) actually correct?**
  _`iso()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `pandas==3.1.0`, `Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json)`, `Playwright MCP Server (connected, unused)` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Ledger` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Why does `Lab` connect `Lab` to `test_paper_adapter.py`, `BrokerUnavailable`, `scenarios.py`, `sys`, `test_execution_lab.py`, `test_risk_metrics.py`, `test_paper_session_controls.py`, `lab.py`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Should `iso` be split into smaller, more focused modules?**
  _Cohesion score 0.11 - nodes in this community are weakly interconnected._
- **Why does `ReadOnlyAlpacaClient` connect `ReadOnlyAlpacaClient` to `test_history.py`, `test_exposure_check.py`, `execution_feasibility.py`, `AlpacaAccessError`, `operations/__main__.py`, `trading/validate.py`, `test_spread_measurement.py`, `runner.py`, `spread_measurement.py`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._