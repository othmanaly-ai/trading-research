# Experiment 002: Long-only opening-range breakout in SPY (specification)

Spec version: 1.0. **APPROVED by the owner on 2026-11-04 for implementation and development
evaluation** (from draft r3a, plus the halt wording and implementation invariants in section 6a).
The fingerprint (file hash) and the tested code commit are recorded in `EXPERIMENT_LOCK.json`.

- **Design choices accepted by the owner (2026-11-04):**
  - long-only
  - completed-bar signals with later execution, and scheduled exits
  - one entry per session
  - the unchanged owner risk limits
  - an explicit drawdown-halt failure
  - one-factor robustness checks
- **r3** resolves the owner's remaining items. No market data was inspected for r1 to r3a.
- **r3a** fixes three internal inconsistencies:
  - validation runs the primary only
  - max drawdown uses intraday marks
  - B1/B3 are not computed for configurations 2-4
- **Data history:** the development data (2016-01-04 to 2021-12-31) is **reused** from experiment 001
  (closed, failed). For this rule, only trigger frequency and opening-range widths were counted;
  no returns were computed. See `research/EXPLORATION_LOG.md`.
- **Held-out data:** validation and final data have never been retrieved (verified 2026-11-04).

## 1. Notation and data

- **Data:** SPY, Alpaca SIP 1-minute bars, regular session, adjustment `all`. XNYS calendar,
  America/New_York time.
- **Bars:** bar `t` (its start) covers `[t, t + 1 min)` and is observable only at `t + 1 min`.
  `open_t`, `high_t`, `low_t` and `close_t` are its prices.
- **Session times:** O = session open (09:30). C = session close (16:00, or 13:00 on early-close days).
- **Checks(T):**
  - Structural checks on every bar ending at or before T: no duplicate or out-of-order
    timestamps, finite values, valid OHLC, positive prices, volume >= 0.
  - **No missing minute** from O to T - 1 min.
  - Uses only information available at T.

## 2. Timeline (exact timestamps)

| Step | Definition | Normal day | Early-close day |
|---|---|---|---|
| Opening range | bars `t` in [O, O + 29 min], all 30 required | 09:30-09:59, known 10:00 | same |
| Signal bars | `t` in [O + 30, C - 61] | 10:00-14:59 | 10:00-11:59 |
| Signal known | D = s + 1 min | 10:01 to 15:00 | 10:01 to 12:00 |
| Entry window | bar starts in [D, min(D + 2 min, **C - 60**)] | 10:01 to **15:00** | 10:01 to **12:00** |
| **Latest actual entry** | **C - 60** (hard limit, including the missing-bar fallback) | **15:00** | **12:00** |
| Stop active | from the entry bar through the bar starting C - 2 | to the 15:58 bar | to the 12:58 bar |
| Scheduled exit | market sell at the **open of the bar starting C - 1**, minus costs | **15:59** | **12:59** |

- **Holding opportunity:** at least **59 minutes** (C - 60 to C - 1), unless a stop or risk exit
  fires earlier.
- **Expiry:** an entry that would execute after C - 60 expires (logged "entry expired").
- **Exit price proxy:** a bar's open is the first print in that minute, not a guaranteed fill,
  and it excludes the closing auction. The official close (market-on-close) is a reported
  sensitivity only.
- **Missing exit bar:** no fill is invented. The exit happens at the first actual later bar, or at
  the next session's first bar ("unresolved: halt or missing data"), following experiment 001
  v1.3's carry rules.

## 3. Strategy (primary configuration)

**Opening range:** valid only if all 30 bars from O to O + 29 exist and pass `Checks(O + 30)`.
Otherwise there is no trade ("data: incomplete opening range").

- `H` = max over those bars of `high_t`.
- `L` = min over those bars of `low_t`.

**Breakout predicate:** `s` = the earliest `t` in [O + 30, C - 61] with **`close_t > H`**, a
completed-bar close. An intrabar cross does not count.
- If no such `t` exists, there is no trade ("no breakout").
- If `Checks(t + 1 min)` fails for some `t` before a breakout is found, the strategy **stops for the
  session** ("data: check failed before signal"). This uses only information up to that time.

**Entry at D = s + 1 min:**
1. If `Checks(D)` fails, there is no trade.
2. `e` = the first existing bar with start in [D, min(D + 2, C - 60)]. If none exists, the entry
   expires ("data: no entry price").
3. If `open_e <= L`, there is no trade ("invalid stop at entry").
4. Shares are decided at D with decision price `P_D = close_s`. Shares = floor(min of):
   - risk: `0.001 x E_D / ((P_D - L) + RT_D)`, where `RT_D` = the modeled round-trip cost per
     share at `P_D`
   - notional: `0.05 x E_D / P_D`
   - gross: `(0.10 x E_D - exposure in use, including pending) / P_D`
   - participation: `0.01 x` the median volume of the 30 bars ending at D
   - `E_D` = mark-to-market equity at D, after costs. Zero shares means rejected ("risk: size").
5. Fill: `open_e x (1 + per-side cost)`.

**Exit:**
- **Stop:** `L`, applied cautiously within each bar: a touch counts, and a gap below fills at the open.
- **Daily and drawdown breaches:** detected on completed-bar marks after costs; the exit fills
  at the next bar's open.
- Otherwise the scheduled exit (section 2). One entry per session; no re-entry.

**Account controls:** the owner baseline, always applied to strategy performance results.
- $100,000 start.
- **Daily loss 0.50%** of that session's start equity (the mark at the prior session's last bar,
  including any carried position). It **resets each session**.
- **Drawdown 3%** below the high-water mark of mark-to-market equity. A breach exits at the next
  executable bar and **halts permanently**; overshoot is preserved.

## 4. Comparisons (complete definitions)

All three use the strategy's cost models, stop at `L`, scheduled exit, and one entry per session.

**Common definitions:**
- **OR-eligible session:** the opening range is valid at O + 30 (section 3). Known at 10:00.
- **Valid random entry at minute `m`:**
  - bar `m` exists with `m` in [O + 31, C - 60]
  - `Checks(m)` passes
  - `open_m > L`
  - Each part uses only information available at `m`.

### B1: random-time participation comparison (diagnostic)

- **Purpose:** whether the breakout *timing and selection* beat random entries with similar
  participation.
- **Sessions:** every OR-eligible session.
- **Participation:** enter with probability `p = N_strategy_entries / N_OR_eligible`. These are the
  strategy's actual entry count and the eligible-session count from the same run. Trade counts are
  used, not returns.
- **Entry minute:** `m` uniform over the integer minutes in [O + 31, C - 60], drawn independently
  of the strategy's entry time.
- **If `m` is not a valid entry:** recorded as **unmatched**, with **no redraw** and no trade.
- **Diagnostic analysis:** each trade has a fixed **$5,000 notional at its entry fill** (fractional
  shares), with no account halts or daily limit.
  - Per-trade net dollar P&L = `(5000 / entry_fill) x (exit_fill - entry_fill) - sell fee`.
  - **Diagnostic account return = total net dollar P&L / $100,000** (non-compounded, invariant 1).
  - The strategy is put through the **identical** analysis for this comparison only.
- **Randomization:** numpy `Generator(PCG64(20261104))`, 10,000 runs. Per run and session, one
  uniform draw decides participation and one independent uniform integer picks the minute. A
  second seed, 20261105, is reported as a stability check only.
- **Labeling:** a **diagnostic benchmark**. It is **not fully risk- or exposure-matched**, because
  holding times, stop distances and the absence of halts differ.
- **Unmatched cases:** they shift B1 toward sessions where price is above `L` at the drawn
  minute. **The direction of the effect on B1's result is not known in advance**; it is reported,
  not assumed.

### B2: conditional timing context (reported only, no pass role)

- **Sessions:** only sessions where the strategy entered, at entry bar `e`.
- **Entry minute:** `m` uniform over [O + 31, e - 1]. If `e = O + 31`, there is no B2 trade
  (recorded).
- **Validity and analysis:** the same as B1, but only one random entry per strategy session, with
  the same seeds.
- **Conditioning:** selecting these sessions uses **later information** (that a breakout occurred
  at `e`). B2 is biased toward breakout-day price paths and shows only within-day timing.

### B3: always-long benchmark (full account; used in acceptance rule D3/V3)

- **Sessions:** every OR-eligible session.
- **Entry:** at minute O + 31 (10:01, the same on early-close days), if it is a valid entry (as
  above). Otherwise no trade, recorded.
- **Sizing:** the strategy's sizing rule at decision time O + 31, with decision price
  `close_{O+30}` and the same four caps.
- **Account:** the **full account with every control** (daily limit, drawdown halt, costs), exactly
  like the strategy. After a drawdown breach, no new entries are allowed. Any open position stays in
  equity and risk calculations until it actually exits under the modeled executable-price rules,
  including an involuntary carry and its gap loss. The run's final equity is its equity after that
  exit; equity is constant only from then on.
- **Exposure:** about 1.4x the strategy's sessions and longer holds, so **not** exposure-matched.

### Comparison reporting (strategy vs B1 and B2)

Reported side by side:
- participation rate
- actual trades, and unmatched count and rate
- mean and median holding minutes
- mean and median stop distance `(entry - L) / entry` in bp
- total and per-trade modeled costs
- diagnostic net return
- B1's percentile

## 5. Configurations and variant policy

This specification allows **exactly four** development configurations. No others may be evaluated
under it:

| # | Configuration | Change from the primary |
|---|---|---|
| 1 | **Primary** | none |
| 2 | Robustness: 15-minute range | Opening range [O, O + 14]; signal bars [O + 15, C - 61] |
| 3 | Robustness: 45-minute range | Opening range [O, O + 44]; signal bars [O + 45, C - 61] |
| 4 | Robustness: midpoint stop | Stop = `(H + L) / 2`. "Invalid stop" means `open_e` <= that midpoint. |

- The robustness configurations are one-factor changes, not a grid, and are never promoted. The
  primary is the only candidate.
- B1, B2 and B3 are computed for the **primary only**. Configurations 2-4 are judged only by
  their own full-account results (D5).
- The former six spare development slots **are removed**; there is no 1 - 0.05/k rule.
- Any later hypothesis needs a **separately recorded research decision** and disclosure of all
  prior exploration (`research/EXPLORATION_LOG.md`).
- All four runs are logged (`variants.csv`, `experiment_attempts.csv`), including failures.

## 6. Acceptance rules

**Common to both stages:**
- Results use the **full account with all controls** ($100,000 start, a fresh account for each
  stage).
- "Net return" = final equity / starting equity - 1 after modeled costs.
- **After a drawdown breach**, no new entries are allowed. Any open position stays in equity and
  risk calculations until it actually exits under the modeled executable-price rules, including an
  involuntary carry and its gap loss. The run's final equity is its equity after that exit; equity
  is constant only from then on.
- **Max drawdown** = the largest fall of mark-to-market equity (after modeled costs, at every
  completed-bar mark: the same series the drawdown halt uses) below its running peak. Overshoot
  from next-executable-price exits is included. End-of-day equity alone is not used.

### Development (all required, using configurations 1-4 only)

| Rule | Requirement |
|---|---|
| **D1** | Primary net return > 0 at **base** costs, **and** >= 0 at **stress** costs. |
| **D2** | **No permanent drawdown halt** in the primary's base or stress run, **and** max drawdown <= 3%. A halt **fails** the stage regardless of the recorded drawdown. |
| **D3** | **Beats B3:** the primary's full-account net return at base costs > B3's full-account net return at base costs, over the same period with identical controls. If either run halted, its final equity is its equity after its open position actually exited (including any carry, gap and costs). |
| **D4** | Primary net P&L at base costs, minus the 10 largest winning trades' net P&L, > 0. |
| **D5** | Configurations 2, 3 and 4 each have net return > 0 at base costs **and no drawdown halt**. |
| **D6 (engineering screening criterion)** | The primary's diagnostic net return ranks at or above the **95th percentile** of B1's 10,000 runs (seed 20261104), under the fixed-size, no-halt analysis. This is a screening criterion: **not a calibrated significance test and not a probability of future profit**. |

### Validation (fixed gate)

Validation applies only if all of D1-D6 pass. The **primary** is run unchanged (same spec hash,
lock and code commit), once.

| Rule | Requirement |
|---|---|
| **V1** | Net return > 0 at base costs **and** >= 0 at stress costs. |
| **V2** | No permanent drawdown halt in base or stress, **and** max drawdown <= 3%. |
| **V3** | Beats B3 (same definition as D3) on the validation period. |
| **V4** | The B1 diagnostic is **reported only** at validation (decision M3). Not a gate. |

Only the **primary** is run on validation. Configurations 2-4 are **not** run on validation
data. For the primary, the top-10 check, B2, severe costs and the closing-auction sensitivity
are **reported**, not gates.

**Failure handling:**
- If any V-rule fails, **the candidate stops**.
- No modified version may be evaluated on validation again, and the **final period is never used
  to rescue** a version changed after a validation failure.
- The final period runs once, only after V1-V3 pass, with explicit owner approval.

## 6a. Implementation invariants (approved 2026-11-04; the hypothesis is unchanged)

1. **Diagnostic normalization:**
   - Diagnostic account return = total net **dollar** P&L / the fixed $100,000 reference balance.
   - Unweighted instrument returns are never summed and called an account return.
   - The same normalization applies to the strategy, B1 and B2.
2. **Executable sizing and acceptance at the fill (strategy and B3):**
   - **Sizing:** shares are fixed at the decision time from the prior completed bar (strategy:
     the signal bar's close; B3: the 10:00 bar's close).
   - **Order model:** a **marketable limit buy** at the next bar's open. Its limit is the highest
     price at which every approved constraint still holds for those shares:
     - notional <= 5% of equity
     - gross exposure <= 10%
     - planned loss at the stop, including round-trip costs, <= 0.10% of equity
     - cash <= equity (no leverage)
   - **Acceptance:** if the bar's open is above that limit, the order is **rejected** ("risk: gap
     beyond executable limit"). It is not resized, and it is never filled later in the bar. Only the
     entry bar's open is used; the entry bar's high, low and close never decide acceptance or price.
3. **Dataset boundary:**
   - A position still open when no later stored bar exists (for example, at the end of the
     development period) is reported **unresolved**.
   - It gets a **provisional valuation** at the last available close, flagged "provisional
     valuation; not a verified liquidation".
   - It is counted separately and never described as a verified exit.

## 7. Required tests before any evaluation

- Timeline boundaries on normal and early-close days, including expiry at C - 60 with a missing
  entry bar.
- Exit at the C - 1 open, never the C - 1 close; stop active through C - 2.
- The completed-bar predicate, and `Checks` using only data available at T.
- Changing bars after a decision cannot change that decision or its size.
- B1/B2/B3 eligibility at decision time, no redraws, unmatched counts, and seed reproducibility.
- A drawdown halt fails D2/V2. Final equity for D3/V3 is measured **after the actual modeled
  liquidation** (including carry, gap and costs); equity is never frozen while a position is open.
  Max drawdown is computed from intraday marks, not end-of-day equity.
- Diagnostic normalization (invariant 1), entry acceptance at the fill (invariant 2), and dataset
  boundary handling (invariant 3).
- The lock refuses a changed definition, a fifth configuration, and validation or final runs
  before owner review.
- Account controls are present in every performance result.
- Experiment 001's recorded run reproduces exactly after the engine refactor.

## 8. Owner decisions (approved 2026-11-04)

| # | Decision | Approved answer |
|---|---|---|
| M1 | B1 participation `p` = strategy entries / OR-eligible sessions (uses the strategy's trade count, not returns) | Accepted |
| M2 | A failed data check before a signal stops the strategy for that session | Accepted. The reason and each affected session are recorded explicitly. |
| M3 | B1 percentile at validation | **Report-only** (not a gate) |
| M4 | Fresh $100,000 account at the start of validation | Accepted |
| M5 | B3 scheduled entry at 10:01, sized from the prior completed (10:00) bar | Accepted, with invariant 2 at the fill |
| M6 | Non-compounded diagnostic aggregation | Accepted, with invariant 1: dollar P&L / $100,000 |
| D1-D6, V1-V3 | Acceptance gates as written; V4 reporting only | Accepted |

E1-E5's values are unchanged: a 30-minute range; signal bars by C - 61 (now with a hard entry
limit at C - 60); stop at `L`; no re-entry; costs of base 2.3, stress 6.6 and severe 9.6 bp.
