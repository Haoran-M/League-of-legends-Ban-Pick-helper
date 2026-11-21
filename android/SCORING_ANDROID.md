# Android scoring and evidence

The Android app runs the same Python recommendation engine as the desktop app, inside the app process. All queries and calculations use local SQLite data. Scores compare eligible unpicked/unbanned champions for your selected role. They are not win probabilities or calibrated confidence estimates. Historical professional results do not establish solo-queue or current-patch performance.

Initial weights: lane matchup 30%, other enemy matchup 15%, ally synergy 25%, composition 15%, baseline 10%, blind robustness 5%. Settings can change the weights, smoothing prior strength and minimum observations. Default minimum support is 20 observations for every statistic and its corresponding baselines.

Smoothed rate is `(wins + alpha * prior) / (games + alpha)`, initially alpha 20. Baselines use prior 0.5. Matchup expectation uses the difference of candidate/opponent baseline logits; synergy expectation uses their mean logit. Pair rates are smoothed toward that expectation. A baseline-adjusted pair residual maps to `clip(50 + 250 * residual, 0, 100)`. Baseline scores use the same mapping around 0.5.

Known lane opponents are counted only in the lane component. Unknown roles are marginalized using observed counterpart-role frequencies in the exact selected filter. More unknown opponents shift half the uncertain lane weight toward robustness. Robustness is a lower-tail summary of supported lane residuals, requiring at least three opponents; the Android standard-library percentile implementation matches NumPy's default linear interpolation.

Composition uses explicit class-tag heuristics for frontline, engage and utility gap filling, documented in DATA_SOURCES.md. These are not measured champion interaction effects, and no physical/magic damage profile is invented from class tags.

Unavailable components are dropped and positive weights renormalized. A statistical component with positive weight is required to produce a score; composition alone does not create a ranking. All-zero weights produce unavailable scores. Coverage describes supported requested weights, not a calibrated confidence interval. Overlapping pair samples come from the same matches and must not be summed as independent evidence. Minimum support does not by itself establish reliability.

The Analysis view shows score, coverage and baseline appearances; tap a candidate for raw wins/games, pair residuals, role probabilities, component weights and limitations. The selected dataset, patch, competition level and league are exact filters, with no implicit cross-patch fallback. DEMO observations and their attributes are kept separate from historical data.

Android serializes commands and analysis on a background executor with a 120 ms debounce. Generation tokens reject stale results. Up to two exact-filter snapshots are cached. All portraits, reference data and notices are bundled; the APK has no network permission. The update target is under 10 seconds per pick; measured emulator results are recorded in the docs/TESTING.md, not claimed as a guarantee for all physical devices or custom datasets.
