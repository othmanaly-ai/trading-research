# Exploration log (all periods)

Every look at historical data outside a locked experiment run is recorded here, so any later
hypothesis can be judged for contamination. **Validation (2022-01-03 to 2024-06-28) and final
(2024-07-01 to 2026-10-30) data have never been retrieved.**

| Date | Data | Analysis | Outcomes seen? | Possible influence on future hypotheses |
|---|---|---|---|---|
| 2026-11-03 | SPY, 5 development sessions (2016-01-26 to 02-01) | `verify_data_access` connection check | Prices only | None |
| 2026-11-04 | SPY development 2016-2021 | Experiment 001 locked run, variant `d11b3023b7bf` (see `001_intraday_momentum/variants.csv`) | Yes: last-30-minute long returns on up-morning days | Strong for any late-day or close-to-10:00 rule |
| 2026-11-04 | same | Zero-cost re-run of the same variant (diagnostic, not a new variant) | Yes | Same as above |
| 2026-11-04 | same | `diagnose_development.py`: last-30-minute returns by r1 sign and quintile; trade/month concentration; stop vs time exits | **Yes: lowest r1 quintile (down mornings) averaged +2.46 bp in the last 30 minutes** (not statistically significant) | Contaminates any "buy after down mornings" idea on development data |
| 2026-11-04 | same | Trigger frequency only: 30-minute opening-range breakout (70.3% of sessions), opening gap <= -0.5% (11.1%), opening-range width (median 0.31%), cap-binding check | **No returns computed** | None on outcomes |
