# Scoring method and limits

Scores compare eligible unpicked/unbanned candidates in the selected user role. **They are not win probabilities, calibrated confidence estimates or causal effects.** The data is historical professional play and does not establish solo-queue performance. No ML model is included.

## Evidence, smoothing and normalization

All reads use one exact dataset, patch, rank/competition and region/league. Missing rows remain missing. The initial minimum support is **20 observations for every statistic and its candidate/counterpart baselines**. Users can change this threshold. Passing it does not establish reliability.

For wins `w`, games `n`, prior `p` and configurable strength `alpha=20`, the smoothed rate is `(w + alpha*p)/(n + alpha)`. Baselines use `p=0.5`. Baseline component score is `clip(50 + 250*(smoothed_baseline - 0.5), 0, 100)`.

The expected matchup rate uses `sigmoid(logit(candidate_baseline) - logit(opponent_baseline))`. The expected synergy rate uses `sigmoid((logit(candidate_baseline) + logit(ally_baseline))/2)`. These are explicit descriptive reference models, not trained predictions. Pair outcomes are smoothed toward that expected rate. The residual is `smoothed_pair - expected`; its normalized score is `clip(50 + 250*residual, 0, 100)`. Thus residuals of -20 and +20 percentage points map to 0 and 100. Equal counterpart weights average the supported residuals, with latent-role probabilities where applicable. This scale is a heuristic comparison contract, not an empirical calibration.

Pair rows are **correlated observations from overlapping games**. Samples are shown separately for every pair and are never summed into an independent sample size. Baseline adjustment reduces simple meta-rate confounding but does not isolate champion interactions from player, team, side, tournament, draft-order or series effects. The scorer does not claim those factors are controlled.

## Components and weights

| Component | Initial weight | Definition |
| --- | ---: | --- |
| Lane matchup | 30% | Supported residuals against opponents occupying the user role |
| Other enemy matchup | 15% | Supported residuals against other opponent roles |
| Ally synergy | 25% | Supported residuals with selected allies in different roles |
| Composition | 15% | Class-based frontline, engage and utility gap filling |
| Baseline | 10% | Smoothed champion-role historical result rate |
| Blind robustness | 5% | 20th percentile of supported lane residuals, requiring at least three distinct opponents |

A known lane opponent contributes only to lane matchup. Unknown roles use the counterpart's observed role frequencies in the exact filter. The corresponding possible-role rows are partitioned into lane versus other roles, so a single pair row never appears in both components. A champion with no role observations provides no pair evidence; the scorer does not silently assign a role. This marginalization exposes uncertainty; it does not identify the hidden role.

With no selected enemies, uncertainty is 1. Otherwise uncertainty is the fraction of selected enemies with unknown roles. Half the lane weight, multiplied by uncertainty, moves to robustness. Robustness coverage is `min(supported_lane_opponents/10, 1)`. It does not pool patches to fill gaps.

Unavailable components are dropped and positive weights renormalized. Coverage is the requested-weight fraction supported by available evidence: baseline coverage is 1 above the threshold; pair coverage is the supported latent-role probability mass divided by possible mass; composition coverage is the fraction of selected allies with attributes. Coverage is not a calibrated confidence interval. A score requires at least one available statistical component with positive weight; composition alone never produces a ranking. All-zero weights produce no scores.

Composition uses explicit Riot-class heuristics documented in DATA_SOURCES.md. For each of frontline, engage and utility, the remaining deficit is `max(0, 1 - selected_ally_total)`. The candidate's deficit-weighted attribute mean maps to `50 + 50*mean`; if there are no deficits, the component is 50. Unknown attributes remain unavailable. The selected ally occupying the user's role is excluded when evaluating replacement candidates. No measured damage-balance claim is made.

## Display and behavior

The Analysis view shows all role-eligible candidates, including unavailable scores as a dash. Its table reports score, evidence coverage and baseline appearances. Evidence details show raw wins/games, expected and smoothed pair rates, residuals, role weights, missing components and limitations. Multiple rows can be compared. Top comparisons also appear on the Draft tab.

Calculations run in a background Qt worker after a 120 ms debounce. Cached exact-filter snapshots avoid repeated database reads. Generation tokens discard results for older draft/filter states. Settings and filters persist locally; imports are validated and committed atomically. Historical and DEMO data never mix implicitly.
