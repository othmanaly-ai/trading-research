# Graph Report - TradingProject  (2026-11-11)

## Corpus Check
- 224 files · ~265,019 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: .csv 3, .css 2, .example 1)

## Summary
- 3117 nodes · 8365 edges · 128 communities (115 shown, 13 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 737 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `34cd713f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Ledger
- FakeBroker
- build_map
- test_history.py
- run_review
- test_monitor.py
- spread_measurement.py
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
- server.py
- test_dashboard.py
- Experiment 001-fd13f1fdef: development-period result
- experiment.py
- test_quality.py
- AnthropicProvider
- test_paper_session_controls.py
- test_reviewer.py
- test_execution_lab.py
- JobsView.tsx
- Experiment 002: Long-only opening-range breakout in SPY (specification)
- Overview.tsx
- Candidates for experiment 002
- EXPLORATION_LOG.md
- App.tsx
- require_order_submission_allowed
- TowerPanel.tsx
- Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04)
- ReadOnlyAlpacaClient
- test_monitor.py
- TowerSpec
- orb_experiment.py
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
- review.py
- FakeBroker
- test_jobs.py
- json
- lab.py
- Read-only market monitoring
- create_server
- test_paper_adapter.py
- Why experiments 001 and 002 failed: a plain-English comparison
- Verified Components (Python 3.15.2, Git, ignore rules, deps, tests)
- BrokerUnavailable
- Research workflow report: Review our existing strategy failures and recommend the next research decision.
- Draft support request to Alpaca (NOT SENT)
- types.ts
- test_operations_gate.py
- test_reliability_fixes.py
- load_credentials
- test_operations_runner.py
- Milestone 1: running the automatic session dry run
- datetime
- schedule.py
- pandas
- os
- ReplayController
- test_preview_readonly.py
- DayData
- Execution-data access check: findings (2026-11-04)
- test_evidence_trace.py
- Review of the pre-holiday proposal, and one more-frequent alternative (decision paper)
- workspaces.js
- reviewer/validate.py
- Prospective monitoring reliability gate: PROPOSAL (not active)
- evidence_trace.py
- 4. Proposed experiment 003 (draft for a SPEC.md; not approved)
- scenarios.py
- reviewer/validate.py
- architecture.ts
- test_coordinator.py
- runner.py
- desk.py
- test_job_api.py
- iso
- conftest.py
- SPY bid-ask spread pilot: findings (PROVISIONAL)
- test_exposure_check.py
- FakeResp
- job_env
- test_desk.py
- Lab
- execution_lab/ledger.py
- Strategy City dashboard: DEMO REPLAY
- Ledger
- argparse
- test_reliability_fixes.py
- Readiness checklist while awaiting Alpaca (2026-11-11)
- QualityChecker
- .block
- Execution-policy decisions (PROPOSED, all inactive)
- DependencyMap.tsx
- collect
- runner.py
- Final test plan: one supervised paper-order mechanics session (PROPOSED; NOT AUTHORIZED; NOTHING SENT)
- WorkflowView.tsx
- ambient.ts
- F. Prioritized milestone plan
- Supervised paper-order test: minimum decisions (PROPOSED, nothing approved)
- dashboard/ledger.py
- Coordinator research workflow (first workflow, 2026-11-10)
- RoutingHttp
- Operational incidents (evidence only; causes stated only when records support them)

## God Nodes (most connected - your core abstractions)
1. `iso()` - 68 edges
2. `MonitorStore` - 62 edges
3. `JobStore` - 50 edges
4. `ReadOnlyAlpacaClient` - 49 edges
5. `RiskLimits` - 49 edges
6. `Lab` - 44 edges
7. `Params` - 43 edges
8. `FakeBroker` - 42 edges
9. `QualityChecker` - 41 edges
10. `create_server()` - 39 edges

## Surprising Connections (you probably didn't know these)
- `Layers` --references--> `TowerSpec`  [INFERRED]
  docs/CITY.md → dashboard/web/src/components/CityView.tsx
- `Run` --references--> `run_experiment()`  [INFERRED]
  research/001_intraday_momentum/RESULTS_development.md → trading/experiment.py
- `What it is` --references--> `JobStore`  [INFERRED]
  docs/RESEARCH_WORKFLOW.md → trading/jobs.py
- `Department-to-implementation map` --references--> `h_capture()`  [INFERRED]
  docs/RESEARCH_DESK.md → trading/monitor/evidence_trace.py
- `Exact measurement rules (per symbol, per session)` --references--> `incidents()`  [INFERRED]
  docs/RELIABILITY_GATE_PROPOSAL.md → trading/monitor/readiness.py

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

## Communities (128 total, 13 thin omitted)

### Community 0 - "Ledger"
Cohesion: 0.15
Nodes (3): test_wrong_mode_event_rejected(), Ledger, _net_if_closed()

### Community 2 - "build_map"
Cohesion: 0.12
Nodes (28): by_id(), healthy(), jobs_fixture(), test_cached_job_results_are_labelled_reused(), test_collect_is_read_only_with_isolated_stores(), test_disabled_optional_review_is_not_a_blocker(), test_failed_step_blocks_dependents_as_impact_only(), test_healthy_dependencies_are_ok_and_not_blocked() (+20 more)

### Community 3 - "test_history.py"
Cohesion: 0.13
Nodes (18): alpaca_payloads(), fake_client(), hist_config(), store(), test_cli_blocked_without_credentials(), test_final_period_download_refused(), test_held_out_periods_refused(), test_historical_replay_mode_and_totals() (+10 more)

### Community 4 - "run_review"
Cohesion: 0.09
Nodes (19): setup(), review_record(), reviewer_status(), _review_availability(), _review_gate(), BudgetDenied, cost_usd(), load_authorization() (+11 more)

### Community 5 - "test_monitor.py"
Cohesion: 0.08
Nodes (22): test_evidence_after_the_cutoff_is_later_evidence_not_a_difference(), env(), server_base(), test_start_launches_once_and_supervisor_recovers_without_duplicates(), test_supervisor_only_acts_when_desired_running(), preview(), env(), store() (+14 more)

### Community 6 - "spread_measurement.py"
Cohesion: 0.05
Nodes (43): FakeInner, FakeResp, test_access_failure_stops_path_without_retry_and_no_substitution(), test_classification_keeps_every_quote(), test_counting_http_enforces_cap_and_logs_no_headers(), test_coverage_reports_empty_minutes_and_dedupes_identical_only(), test_downloads_blocked_while_deferred(), test_held_out_dates_refused() (+35 more)

### Community 9 - "test_backtest.py"
Cohesion: 0.12
Nodes (39): days(), run_day(), test_accounting_identity_over_a_run(), test_breach_on_scheduled_exit_bar_uses_time_exit(), test_carry_exit_counts_against_next_session_limits(), test_daily_loss_limit_uses_unrealized_and_exits_next_bar(), test_early_close_shifts_times(), test_entry_is_one_minute_after_decision_with_costs() (+31 more)

### Community 10 - "Experiment 001: Intraday momentum in SPY (draft specification)"
Cohesion: 0.09
Nodes (22): 10. Cost assumptions (to be checked against data), 11. Baselines (same window, same exposure, same sizing), 12. Periods (chronological, fixed before any data is seen), 13. Variant accounting, 14. Evaluation criteria (fixed before running), 15. Roles (performed by one model, Claude, as checklists), 16. Unresolved decisions for owner review, 17. Implementation clarifications (2026-11-03, before any data was seen) (+14 more)

### Community 12 - "hashlib"
Cohesion: 0.12
Nodes (28): test_reports_match_city(), attempts(), days(), lock_path(), read_log(), run(), _run(), test_attempts_ledger_records_completed_and_refused() (+20 more)

### Community 13 - "test_readiness.py"
Cohesion: 0.05
Nodes (46): Market readiness panel (`trading/monitor/readiness.py`, `GET /api/monitor/readiness`), BrokenDB, ev(), healthy(), _isolated_runner(), test_agg_keeps_unknown_unknown(), test_all_unavailable_per_symbol_counts_become_unknown(), test_closed_market_is_expected_and_healthy_state_passes() (+38 more)

### Community 14 - "compilerOptions"
Cohesion: 0.12
Nodes (15): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, noFallthroughCasesInSwitch (+7 more)

### Community 15 - "jobs.py"
Cohesion: 0.11
Nodes (24): How text from the artifacts is handled, What it is, and what it is not, What makes a response valid, What the reviewer receives, analysis(), execute_pipeline(), _finite(), ingest() (+16 more)

### Community 17 - "JobStore"
Cohesion: 0.11
Nodes (10): store(), env(), test_server_job_runner_passes_no_keys(), jobs_snapshot(), JobRunner, JobStore, main(), request_cancel() (+2 more)

### Community 18 - "Experiment 002-895a4f9c5d: development-period result"
Cohesion: 0.22
Nodes (8): Acceptance rules, Comparisons (diagnostic: fixed $5,000 per trade, no halts, dollar P&L / $100,000), Data exclusions and unresolved cases, Experiment 002-895a4f9c5d: development-period result, Limitations, Primary, full account, Recommendation, Run

### Community 19 - "test_orb.py"
Cohesion: 0.13
Nodes (41): days_for(), make(), path(), run(), test_b1_b2_reproducible_unmatched_and_identical_treatment(), test_b3_entry_sizing_and_acceptance(), test_checks_function(), test_closed_experiment_refuses_runs_but_allows_inspection() (+33 more)

### Community 20 - "test_spread_measurement.py"
Cohesion: 0.10
Nodes (22): FakeData, FakeResp, _git(), q(), rule_rows(), run(), test_access_failure_stops_quotes_without_retry(), test_analyze_end_to_end_offline() (+14 more)

### Community 21 - "Trading City: product specification"
Cohesion: 0.15
Nodes (12): N, 1. Purpose, 2. Modes (never blended), 3. Shared records, 4. Tower detail tabs, 5. Research responsibilities, 6. Historical replay rules (for milestone 4), 7. Evaluation report contents (+4 more)

### Community 22 - "server.py"
Cohesion: 0.08
Nodes (29): test_candidates_overview_lists_deferred_candidate_read_only(), test_candidates_overview_tolerates_corrupt_status(), test_research_status_is_honest(), candidates_overview(), _epoch(), experiments_overview(), build(), _lock_status() (+21 more)

### Community 23 - "test_dashboard.py"
Cohesion: 0.08
Nodes (23): demo(), _get(), _post(), replay_all(), test_build_is_deterministic(), test_control_requires_header_and_valid_action(), test_csp_allows_only_the_local_agency_workspace(), test_depmap_endpoint_is_read_only_and_has_no_execution_path() (+15 more)

### Community 24 - "Experiment 001-fd13f1fdef: development-period result"
Cohesion: 0.20
Nodes (9): Cost sensitivity, Diagnosis (development data only; `diagnose_development.py`), Experiment 001-fd13f1fdef: development-period result, Limitations, Pass rules (fixed before the run), Recommendation, Reproducibility and file locations, Results (base costs, about 2.3 bp round trip) (+1 more)

### Community 25 - "experiment.py"
Cohesion: 0.12
Nodes (20): test_random_baseline_centered_and_percentile(), BacktestResult, _check_allowed(), _evaluate(), _held_out_inspection(), data_inspection_status(), _log_attempt(), _pass_rules() (+12 more)

### Community 26 - "test_quality.py"
Cohesion: 0.11
Nodes (35): bar(), checker(), Clock, FakeFeeds, iso(), latest_rows(), _parses(), run_until_idle() (+27 more)

### Community 27 - "AnthropicProvider"
Cohesion: 0.12
Nodes (13): fake_sdk(), create(), __init__(), test_anthropic_provider_error_mapping_with_mock_sdk(), behaviour(), test_anthropic_provider_success_with_mock_sdk(), test_real_sdk_error_mapping_against_closed_local_port(), AnthropicProvider (+5 more)

### Community 28 - "test_paper_session_controls.py"
Cohesion: 0.09
Nodes (24): no_network(), _pf(), posts(), setup(), Switch, test_account_checks_block_entries(), test_exit_needs_policy_and_a_ledger_position(), test_fresh_process_drills_through_the_paper_adapter() (+16 more)

### Community 29 - "test_reviewer.py"
Cohesion: 0.20
Nodes (27): good_answer(), item_id(), MockProvider, ok(), run(), test_artifact_instruction_injection_is_flagged_and_cannot_flip_gates(), test_cache_reuses_review_and_keys_on_evidence_prompt_and_model(), test_call_budget_per_run() (+19 more)

### Community 30 - "test_execution_lab.py"
Cohesion: 0.11
Nodes (12): _lab(), no_network_and_no_project_files(), connect(), create(), loopback_only(), test_duplicate_fill_events_never_duplicate_fills(), test_emergency_stop_can_complete_only_when_everything_is_resolved(), test_pending_orders_count_toward_exposure_used_by_the_risk_gate() (+4 more)

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

### Community 37 - "require_order_submission_allowed"
Cohesion: 0.09
Nodes (23): 1. Does the roadmap permit it?, 2. What it would test, and what it cannot, 3. Design principles (from the existing plan, unchanged), 4. What exists, and what is missing, 5. Proposed sequence (each step needs its own owner decision), 6. The next decision, Proposal: test paper-order mechanics independently of any strategy (PROPOSED, nothing approved or built), Controls that must work before the first order: status on 2026-11-11 (+15 more)

### Community 38 - "TowerPanel.tsx"
Cohesion: 0.17
Nodes (28): AccountPanel(), Leaderboard(), StrategyTable(), Marker, PAD, PriceChart(), DecisionsTab(), HistoricalTab() (+20 more)

### Community 39 - "Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04)"
Cohesion: 0.15
Nodes (12): 1. SPY distribution calendar (`spy_distributions_development.json`), 2. Quote interpretation (official Alpaca documentation, read 2026-11-04), 3. Locked and crossed quotes (proposed treatment, not approved), 4. Quote coverage through the proposed 10:00 exit, 5. What this is not, Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04), Future operation (proposed; required before any live use), Retrospective classification vs historical availability (+4 more)

### Community 40 - "ReadOnlyAlpacaClient"
Cohesion: 0.08
Nodes (21): FakeHttp, FakeResponse, test_access_refusal_on_quotes_raises_without_retry(), test_account_keeps_only_listed_fields(), test_client_has_no_order_methods(), test_clock_is_a_paper_host_get_with_listed_fields_only(), test_corporate_actions_merge_and_cap(), test_feed_refusal_raises_and_is_not_substituted() (+13 more)

### Community 41 - "test_monitor.py"
Cohesion: 0.12
Nodes (20): _call(), Clock, FakeClient, make_worker(), synthetic_bar(), test_access_errors_recorded_and_feed_never_switched(), test_connection_failures_back_off_and_reconnect(), test_dead_worker_shows_disconnected() (+12 more)

### Community 42 - "TowerSpec"
Cohesion: 0.13
Nodes (14): Ambient life and real events (2026-11-05, second pass), Building vocabulary (procedural, no external assets), Controls and access, Decorative (no data; module `city/ambient.ts`), Deferred, Effects, Effects levels, Layers (+6 more)

### Community 43 - "orb_experiment.py"
Cohesion: 0.06
Nodes (29): bars(), report(), test_bars_after_exit_are_ignored(), test_classification_rules(), test_cost_accounting_and_sensitivity(), test_event_stream_only_uses_information_available_at_each_time(), test_result_hash_is_reproducible_and_sensitive(), test_spec_version_and_hash() (+21 more)

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
Cohesion: 0.12
Nodes (19): _active(), advance(), _claims(), _close(), collect_evidence(), _finish(), guard_path(), main() (+11 more)

### Community 48 - "trading/validate.py"
Cohesion: 0.17
Nodes (17): Data Check Exit Codes (0 success, 1 API failure, 2 no credentials), Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json), Missing-Credential Handling (BLOCKED, exit 2, no network call), full_session(), synthetic_bar(), test_clean_synthetic_session_passes(), test_daily_coverage_maps_midnight_et_stamps_to_dates(), test_detects_each_structural_problem() (+9 more)

### Community 49 - "Amendment 2: quote coverage through the proposed exit (pre-registration)"
Cohesion: 0.40
Nodes (4): Amendment 2: quote coverage through the proposed exit (pre-registration), Dates, Requests (HTTP GET only, `https://data.alpaca.markets`), Validation (pre-declared)

### Community 50 - "Feasibility note: gap-down opening reversal (not an experiment)"
Cohesion: 0.18
Nodes (10): 0. Correction, 1. Rules using only information available at each time, 2. Previous close and opening price in real operation, 3. Can minute bars represent the opening?, 4. Prior exploration (from `EXPLORATION_LOG.md`), 5. Does it warrant an experiment now?, Feasibility note: gap-down opening reversal (not an experiment), Recommendation (+2 more)

### Community 51 - "Automated second review (model-powered reviewer)"
Cohesion: 0.15
Nodes (12): After the call, Automated second review (model-powered reviewer), Before each call, How cost enforcement works, Limitations, Owner decision (2026-11-04), Proposed limits (not yet authorized), Provider options (+4 more)

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
Cohesion: 0.11
Nodes (17): Amendment 2026-11-10: broker evidence for "no exposure" (owner-authorized correction), Counting five consecutive sessions, FAIL: a safety or correctness violation, Fixed parameters, INCOMPLETE: not enough evidence to judge, INTERRUPTED: it started properly, but operation broke, Milestone 1 dry run: what counts as pass, failure, interruption and incomplete, PASS: all of these, with evidence (+9 more)

### Community 58 - "review.py"
Cohesion: 0.11
Nodes (10): test_cli_env_reads_key_from_dotenv_and_bom_authorization(), test_dashboard_blocker_wording_without_authorization(), test_server_env_strips_credentials(), _server_env(), render_user_message(), _blocked(), cache_key(), cli_env() (+2 more)

### Community 59 - "FakeBroker"
Cohesion: 0.08
Nodes (12): FakeClient, run_session(), test_account_switch_during_session_is_unverifiable(), test_broker_unavailable_at_closing_is_never_a_pass(), get_positions(), test_empty_account_session_passes_with_closing_evidence(), test_local_assertion_and_fresh_heartbeat_cannot_substitute_for_broker_evidence(), test_on_time_session_compares_every_calendar_check_and_still_passes() (+4 more)

### Community 60 - "test_jobs.py"
Cohesion: 0.22
Nodes (9): statuses(), test_api_and_store_emit_strict_json(), test_corrupt_artifact_fails_then_recovers_with_new_attempt(), test_end_to_end_on_real_artifacts(), test_missing_artifact_fails_ingest_and_blocks_downstream(), test_model_review_unavailable_lists_every_blocker(), test_reconcile_detects_tampered_record(), test_retry_and_restart_never_duplicate_completed_jobs() (+1 more)

### Community 61 - "json"
Cohesion: 0.12
Nodes (15): test_demo_research_run_writes_consistent_outputs(), test_historical_research_run_refuses_without_data(), test_journal_matches_ledger_engine_and_report(), test_journal_mid_replay_marks_session_in_progress(), test_skipped_and_blocked_sessions_are_journaled(), collect(), _drills(), load_config() (+7 more)

### Community 62 - "lab.py"
Cohesion: 0.09
Nodes (17): lab(), no_network(), test_a_cancel_requested_again_by_a_fresh_broker_client_is_recorded_not_dropped(), test_emergency_exposure_action_unset_is_reported_not_chosen(), test_emergency_stop_never_cancels_protective_stops(), test_escalation_timing_follows_policy_and_unset_is_an_owner_decision(), test_invalid_policy_value_blocks(), test_ledger_cash_equals_broker_cash_after_a_round_trip_with_fees() (+9 more)

### Community 63 - "Read-only market monitoring"
Cohesion: 0.12
Nodes (16): Behaviour, Checklist for observing several consecutive sessions, Controls, Daily report sections, Data permissions measured on 2026-11-04, Data quality: delayed SIP vs IEX (`trading/monitor/quality.py`), Finalization, Limitations (+8 more)

### Community 64 - "create_server"
Cohesion: 0.18
Nodes (9): server(), test_api_serves_the_same_records_and_writes_nothing(), test_dashboard_endpoint_matches_store(), test_journal_endpoints(), _serve(), test_existing_server_detection(), create_server(), existing_server() (+1 more)

### Community 65 - "test_paper_adapter.py"
Cohesion: 0.09
Nodes (21): Execution core (2026-11-10, offline), _imports(), lab_with(), no_network(), order(), test_accept_fill_and_full_reconciliation_of_orders_fills_positions_and_cash(), test_adapter_has_no_network_transport_and_guards_every_write(), test_adapter_is_unreachable_from_dashboard_dry_run_and_lab() (+13 more)

### Community 66 - "Why experiments 001 and 002 failed: a plain-English comparison"
Cohesion: 0.22
Nodes (8): Glossary, Recommended next research task, Side by side, The two strategies in one line each, What the two failures have in common, Why 001 failed: there was no edge to begin with, Why 002 failed: a small edge, entirely eaten by costs, Why experiments 001 and 002 failed: a plain-English comparison

### Community 67 - "Verified Components (Python 3.15.2, Git, ignore rules, deps, tests)"
Cohesion: 0.08
Nodes (24): Allowed Hosts (paper-api and data.alpaca.markets only), Completed Session Rule (15 min after close, SIP delay), Data Feeds: SIP (consolidated) vs IEX (single exchange), daytrading-starter skill (planning/analysis only), .env.example template, 1-Minute Bar Coverage ([open, close), trade-only bars), Order Submission Guard (TRADING_MODE=paper, ORDER_SUBMISSION_ENABLED=true), requirements.lock (full pip freeze) (+16 more)

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
Cohesion: 0.09
Nodes (29): _imports(), test_only_data_health_opens_the_monitoring_database_and_reads_no_prices(), test_operations_imports_from_monitoring_are_limited(), test_recorded_data_health_has_no_market_values(), test_research_code_never_imports_monitoring_or_operations(), green(), test_closed_failed_deferred_unknown_and_multiple_are_refused(), test_dry_run_denies_even_when_everything_else_is_green() (+21 more)

### Community 73 - "test_reliability_fixes.py"
Cohesion: 0.10
Nodes (26): Command Centre boundary, Department-to-implementation map, Evidence trace (one session), Model assistance (DISABLED), Research desk (city view "Research desk"), test_correction_that_drops_reclassified_events_is_flagged_and_now_counted(), _stored(), test_correction_is_a_new_version_with_reason_and_keeps_the_original() (+18 more)

### Community 74 - "load_credentials"
Cohesion: 0.25
Nodes (8): test_credentials_from_dotenv(), test_missing_credentials(), test_missing_credentials_at_closing_is_never_a_pass(), factory(), load_credentials(), MissingCredentials, _read_dotenv(), main()

### Community 75 - "test_operations_runner.py"
Cohesion: 0.16
Nodes (21): test_position_found_fails_the_session_and_blocks_acceptance(), et(), simulate(), test_broker_outage_at_final_check_and_in_session(), test_holiday_does_nothing(), test_late_start_is_incomplete_and_missed_minutes_are_not_replayed(), test_machine_sleep_leaves_missing_minutes_and_heartbeat_gap(), test_not_run_pending_and_injected_violations() (+13 more)

### Community 76 - "Milestone 1: running the automatic session dry run"
Cohesion: 0.20
Nodes (9): Each trading day: one start-up command (2026-11-09), Known limitations, Milestone 1: running the automatic session dry run, Other commands (none of them place orders), Persistent background operation: PROPOSED, not installed, Recovering the production city server (port 8765), Start from a normal PowerShell window, not a Claude desktop terminal (2026-11-10), What it checks (+1 more)

### Community 77 - "datetime"
Cohesion: 0.13
Nodes (5): test_sessions_before_the_correction_keep_their_original_rules(), test_acceptance_needs_five_consecutive_passes_with_one_fingerprint(), collect(), now_iso(), OpsStore

### Community 78 - "schedule.py"
Cohesion: 0.14
Nodes (19): _clock(), test_a_not_compared_periodic_calendar_check_cannot_count_as_verified(), test_calendar_at_the_final_check_and_in_session_is_a_positive_comparison(), test_calendar_not_compared_near_a_boundary_is_not_ok(), test_dst_transitions_move_utc_times_not_et_times(), test_early_close_shifts_closing_and_report(), test_et_date_uses_new_york_not_utc(), test_holiday_and_weekend_have_no_session() (+11 more)

### Community 79 - "pandas"
Cohesion: 0.07
Nodes (25): Offline Test Suite (22 passed), main(), raw_minutes(), test_max_drawdown(), test_dst_changes_utc_open(), test_requires_timezone_aware_now(), test_session_not_completed_until_data_delay_passes(), test_thanksgiving_skipped_and_black_friday_early_close() (+17 more)

### Community 80 - "os"
Cohesion: 0.09
Nodes (27): test_runtime_dir_refuses_onedrive_and_project(), test_app_private_copy_of_the_records_is_detected(), test_run_records_each_startup_step_and_logs(), test_second_runner_is_refused_and_says_so(), ops_part(), stored_report(), SingleInstanceLock, _load_heavy() (+19 more)

### Community 81 - "ReplayController"
Cohesion: 0.32
Nodes (4): test_controller_pause_restart_speed(), test_controller_replay_with_injected_duplicates_matches_direct(), ReplayController, _ticker()

### Community 82 - "test_preview_readonly.py"
Cohesion: 0.31
Nodes (5): _dump_sha(), _post(), test_preview_reads_change_no_records(), test_preview_refuses_state_changes_but_keeps_replay_controls(), test_preview_starts_no_worker_supervisor_or_job_runner()

### Community 83 - "DayData"
Cohesion: 0.06
Nodes (35): B. Evidence table, Milestone 2: forward observation of an approved strategy without orders (SHADOW), test_baseline_notional_cap_binds_and_rounds_down(), test_daily_breach_uses_session_start_equity(), test_daily_loss_limit(), test_daily_losses_accumulate_across_trades_and_marks(), test_drawdown_uses_high_water_mark_and_never_resets(), test_entry_that_cannot_fit_is_rejected() (+27 more)

### Community 84 - "Execution-data access check: findings (2026-11-04)"
Cohesion: 0.29
Nodes (6): 1. Historical SIP quotes, 09:30-09:35 ET, 2. Raw SIP minute bars, 09:30-10:02 ET, 3. Prior raw closes and corporate actions, 4. Limitations of this execution data, Conclusion on feasibility, Execution-data access check: findings (2026-11-04)

### Community 85 - "test_evidence_trace.py"
Cohesion: 0.16
Nodes (21): traced(), desk(), dump_sha(), _live(), make_session(), _reset_hooks(), states(), test_changed_handler_source_is_recomputed_not_reused() (+13 more)

### Community 86 - "Review of the pre-holiday proposal, and one more-frequent alternative (decision paper)"
Cohesion: 0.18
Nodes (10): 1. Does the published pre-holiday evidence cover our interval? No., 2. Basis of the three statements in the proposal, 3. Can 53 trades, and about 9 a year, produce useful evidence in practical time? No., 4. How the 2% stop relates to the risk limits (correction), 5. One more frequent alternative our data can honestly evaluate, 6. Comparison, 7. Recommendation, 8. Decisions prepared for you (+2 more)

### Community 87 - "workspaces.js"
Cohesion: 0.83
Nodes (3): check(), probe(), select()

### Community 88 - "reviewer/validate.py"
Cohesion: 0.17
Nodes (10): test_evidence_scope_excludes_data_and_held_out(), test_secrets_and_local_paths_are_redacted(), build_package(), add(), EvidenceError, EvidenceTooLarge, _Sanitizer, _sections() (+2 more)

### Community 89 - "Prospective monitoring reliability gate: PROPOSAL (not active)"
Cohesion: 0.22
Nodes (8): Decisions for the owner, Definitions (all from records the monitor already keeps), Exact measurement rules (per symbol, per session), Proposed gate (all must hold, for every one of SPY, QQQ, IWM), Prospective monitoring reliability gate: PROPOSAL (not active), What approval would change, What "on time within 180 s" establishes, and what it does not, Why a second measure is needed

### Community 90 - "evidence_trace.py"
Cohesion: 0.08
Nodes (21): test_a_result_may_not_claim_the_proposed_gate_is_active(), _active_run(), Blocked, classify_difference(), code_version(), config_version(), evidence_cutoff(), _fp() (+13 more)

### Community 91 - "4. Proposed experiment 003 (draft for a SPEC.md; not approved)"
Cohesion: 0.11
Nodes (17): 1. What research can proceed now, and what waits for Alpaca, 2. Three hypotheses compared, 3. Recommendation: H2, pre-holiday sessions, 4.1 Data, 4.2 Which sessions trade, 4.3 Trading rules, 4.4 Costs, 4.5 Benchmarks (computed with the same engine, costs and limits) (+9 more)

### Community 92 - "scenarios.py"
Cohesion: 0.14
Nodes (27): stop_report(), api(), _expect(), _intents(), invariants(), _new(), run(), run_all() (+19 more)

### Community 93 - "reviewer/validate.py"
Cohesion: 0.35
Nodes (7): lookup(), resolve(), _citations(), _expect(), _obj(), _str(), validate()

### Community 94 - "architecture.ts"
Cohesion: 0.19
Nodes (17): BUILDERS, Kit, worldUV(), buildScenery(), rng(), Scenery, skyDome(), BAY_W (+9 more)

### Community 95 - "test_coordinator.py"
Cohesion: 0.16
Nodes (21): claim(), data_doc(), make_root(), review_doc(), root(), strategy_doc(), tasks(), test_duplicates_are_prevented() (+13 more)

### Community 96 - "runner.py"
Cohesion: 0.18
Nodes (5): test_committed_code_state_shape(), test_runner_status_file_tracks_the_run(), code_fingerprint(), committed_code_state(), Runner

### Community 97 - "desk.py"
Cohesion: 0.29
Nodes (13): _age_s(), archive(), build_desk(), command_centre(), data_centre(), _fmt_counts(), _from_trace(), operations_dept() (+5 more)

### Community 98 - "test_job_api.py"
Cohesion: 0.24
Nodes (15): call(), setup(), start(), test_cancel_queued_pipeline_immediately(), test_cancel_running_pipeline_keeps_completed_evidence(), test_dashboard_records_match_database(), test_experiments_and_preview(), test_get_with_foreign_host_refused() (+7 more)

### Community 99 - "iso"
Cohesion: 0.13
Nodes (11): test_worker_marks_sessions_it_monitors(), _freshness(), iso(), market_state(), session_date_et(), _tz(), default_client_factory(), _floor_minute() (+3 more)

### Community 101 - "SPY bid-ask spread pilot: findings (PROVISIONAL)"
Cohesion: 0.33
Nodes (5): 1. Coverage and exclusions, 2. Provisional spread measurements, 3. Actual resource usage, 4. Reliability, and whether the remaining 18 sessions are justified, SPY bid-ask spread pilot: findings (PROVISIONAL)

### Community 102 - "test_exposure_check.py"
Cohesion: 0.16
Nodes (11): check(), Fake, test_broker_unavailable_is_unverifiable(), test_empty_account_is_verified_none_with_time_and_identity(), test_incomplete_or_malformed_responses_are_unverifiable(), test_open_position_is_exposure_found_and_nothing_is_closed(), test_outstanding_or_partially_filled_order_is_exposure(), test_slow_evidence_is_stale() (+3 more)

### Community 105 - "test_desk.py"
Cohesion: 0.29
Nodes (9): base_inputs(), tasks(), test_api_desk_serves_the_same_records(), test_command_centre_is_deterministic_and_only_names_manual_authorized_commands(), test_desk_tasks_agree_with_stored_trace_records(), test_dry_run_record_discrepancy_is_a_failure_not_a_pass(), test_every_state_is_honest_and_from_the_allowed_set(), test_missing_sources_are_unknown_never_ok() (+1 more)

### Community 106 - "Lab"
Cohesion: 0.13
Nodes (9): test_never_sent_only_with_durable_proof_and_uncertain_outcomes_stay_unresolved(), test_orphaned_intent_from_a_crash_during_the_checks_expires_on_reconciliation(), test_restart_preserves_outstanding_obligations(), _crash(), Lab, since(), _ts(), describe_missing() (+1 more)

### Community 109 - "execution_lab/ledger.py"
Cohesion: 0.15
Nodes (11): Execution lab: LOCAL EXECUTION SIMULATION, Isolation from the dry run, Open execution-policy decisions (the lab does not choose them), Order lifecycle, Scenarios (all deterministic, seed 0), can_transition(), derive(), _move() (+3 more)

### Community 110 - "Strategy City dashboard: DEMO REPLAY"
Cohesion: 0.25
Nodes (7): Architecture, City workspaces (Trading City / Website Agency), Connecting real Alpaca data (separate, not started), Launch, Research jobs tab (REAL records, not demo), Strategy City dashboard: DEMO REPLAY, Verification

### Community 113 - "argparse"
Cohesion: 0.16
Nodes (13): test_fresh_process_crash_drill(), check(), main(), _no_network(), _open(), run_all(), run_drill(), run_step() (+5 more)

### Community 114 - "test_reliability_fixes.py"
Cohesion: 0.10
Nodes (23): _at(), FakeRunner, _files(), _record(), _startup(), test_after_report_time_completed_or_not(), test_alive_runner_without_recorded_progress_is_never_healthy(), test_check_only_never_launches() (+15 more)

### Community 115 - "Readiness checklist while awaiting Alpaca (2026-11-11)"
Cohesion: 0.40
Nodes (4): A. Blocked by the historical-quote questions, B. Can proceed independently now, C. Blocked by something other than Alpaca, Readiness checklist while awaiting Alpaca (2026-11-11)

### Community 116 - "QualityChecker"
Cohesion: 0.12
Nodes (10): quality_report(), bar_defects(), boundary(), _bps(), classify(), _median(), _num(), QualityChecker (+2 more)

### Community 117 - ".block"
Cohesion: 0.46
Nodes (8): Builder, command(), construction(), finned(), operations(), paired(), terraced(), twisted()

### Community 118 - "Execution-policy decisions (PROPOSED, all inactive)"
Cohesion: 0.11
Nodes (17): 1. Breach policy: research rules, lab behaviour and a broker policy are three different things, 2. Partial fills: what actually protects a filled quantity, 3. Unknown submission outcomes, 4. Decisions, in two groups, Broker facts (DOCUMENTED, checked 2026-11-10), DOCUMENTED (Alpaca, "Placing Orders", Bracket / OTO / OCO sections), Execution-policy decisions (PROPOSED, all inactive), Group A: needed to define a bounded paper-integration test (scripted, tiny, no strategy) (+9 more)

### Community 119 - "DependencyMap.tsx"
Cohesion: 0.14
Nodes (13): EdgeSpec, TowerSpec, ARCH, Boundary, Cause, CityView, DependencyMap(), DepMap (+5 more)

### Community 120 - "collect"
Cohesion: 0.13
Nodes (10): collect(), depmap_part(), locks_part(), monitor_part(), trace_part(), _rows(), main(), open_monitor_readonly() (+2 more)

### Community 121 - "runner.py"
Cohesion: 0.14
Nodes (6): test_data_health_reads_monitor_store(), operations_cross_check(), local_checks(), _parse(), read(), code_version()

### Community 124 - "Final test plan: one supervised paper-order mechanics session (PROPOSED; NOT AUTHORIZED; NOTHING SENT)"
Cohesion: 0.07
Nodes (21): 10. Remaining decisions, 1. Account and endpoint, 2. Instruments, order types, quantities, exposure [proposed], 3. Order count and duration [proposed], 4. The session script (the only allowed actions), 5. Stop conditions (any one ends new orders immediately; then cleanup only), 6. Cleanup and reconciliation, 7. Deliberate omissions (smallest scope) (+13 more)

### Community 125 - "WorkflowView.tsx"
Cohesion: 0.18
Nodes (9): ARCH, Boundary, CityView, COLOR, Data, SLOT, Task, Workflow (+1 more)

### Community 126 - "ambient.ts"
Cohesion: 0.20
Nodes (11): Ambient, buildAmbient(), Car, Effects, Landmark, rng(), signTexture(), VEHICLES (+3 more)

### Community 127 - "F. Prioritized milestone plan"
Cohesion: 0.10
Nodes (19): A. Goal and present blockers (plain English), Any live pilot, Automatic market-session operation: audit and roadmap, C. Architecture, D. Operating-state model, E. Failure-response matrix, F. Prioritized milestone plan, G. Owner decisions that block Milestone 1 (+11 more)

### Community 128 - "Supervised paper-order test: minimum decisions (PROPOSED, nothing approved)"
Cohesion: 0.22
Nodes (8): 1. Intended paper account [A1, A10], 2. Instruments, maximum quantity, notional exposure, test-loss limit [A1, plus a new item], 3. Entry order type and handling of partial fills [A2], 4. Unprotected exposure and emergency action [A3, A6], 5. Unknown-outcome and cancellation escalation [A4, A5], 6. Reset authority and manual-account activity [A7, A8], Evidence for "offline milestone verified" (2026-11-11), Supervised paper-order test: minimum decisions (PROPOSED, nothing approved)

### Community 134 - "Coordinator research workflow (first workflow, 2026-11-10)"
Cohesion: 0.33
Nodes (5): Commands (read-only research), Coordinator research workflow (first workflow, 2026-11-10), Guarantees and safety, Roles vs agents, What it is

## Knowledge Gaps
- **5 isolated node(s):** `pandas==3.1.0`, `Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json)`, `Playwright MCP Server (connected, unused)`, `pytest==9.2.0`, `Raw Adjustment Default (no split/dividend adjustment)`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1084 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Lab` connect `Lab` to `test_paper_adapter.py`, `BrokerUnavailable`, `scenarios.py`, `argparse`, `DayData`, `test_execution_lab.py`, `test_paper_session_controls.py`, `lab.py`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `iso()` (e.g. with `healthy()` and `jobs_fixture()`) actually correct?**
  _`iso()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `pandas==3.1.0`, `Output Layout (data/alpaca/<UTC time>/ CSV, provenance.json, validation.json, account.json)`, `Playwright MCP Server (connected, unused)` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FakeBroker` be split into smaller, more focused modules?**
  _Cohesion score 0.11724137931034483 - nodes in this community are weakly interconnected._
- **Why does `Ledger` connect `Ledger` to `test_history.py`, `dashboard/ledger.py`, `orb_experiment.py`, `ReplayController`, `server.py`, `test_dashboard.py`, `json`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Should `build_map` be split into smaller, more focused modules?**
  _Cohesion score 0.12179487179487179 - nodes in this community are weakly interconnected._
- **Why does `JobStore` connect `JobStore` to `test_job_api.py`, `build_map`, `test_monitor.py`, `Coordinator research workflow (first workflow, 2026-11-10)`, `job_env`, `test_desk.py`, `coordinator.py`, `jobs.py`, `test_evidence_trace.py`, `server.py`, `collect`, `evidence_trace.py`, `test_coordinator.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._