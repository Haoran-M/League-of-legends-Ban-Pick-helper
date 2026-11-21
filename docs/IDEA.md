# Project idea: practical draft help for everyday players

## Problem

A champion can work well in coordinated professional play while being an unsuitable choice for a casual ranked player. Mechanics, matchup knowledge, practice and coordination matter. A global win-rate list also cannot explain how a champion fits a specific lane opponent or unfinished team composition.

The project asks: **what can I comfortably play in this draft, and what evidence supports that choice?** Its intended audience is ordinary players practicing or reviewing drafts on Windows or Android. The foundation is implemented; the next priority is matching the evidence to that audience.

## Intended experience

A player enters a partial draft and sees role-appropriate, playable options within ten seconds of a pick. Explanations cover lane matchup, other threats, allies, team gaps, sample sizes and uncertainty. Dragging picks and roles makes exploration quick and undoable.

For example, a Mid player facing a known enemy should eventually select a supported ranked cohort and their personal champion pool, then compare observed counters among those familiar champions. Missing evidence should remain explicit. Ranked cohorts and champion-pool controls are planned, not current capabilities.

## Principles

- Match the population: solo queue, professional competition and DEMO fixtures are different evidence.
- Respect comfort: difficulty and familiarity help narrow choices but are not observed matchup effects.
- Explain comparisons: show wins/games, roles, patch, cohort, smoothing and missing support.
- Stay responsive: background computation and stale-result rejection support the ten-second budget.
- Work offline: local snapshots and imports; no account, telemetry or client integration.
- Keep exploration reversible: validate atomically, support Unknown roles and provide undo/reset.

## Data needed for average-player counters

A usable source needs an explicit redistribution/derivative-use license and enough information to establish queue, rank/cohort definition, patch, region, dates, champion identity, observed role, opposing champion/role, outcome and observation counts. Ally observations are needed if synergy is offered. Sampling, deduplication and limitations must be documented.

A dataset with one sampled champion per match might support baselines but cannot establish lane counters without the opponent/role observations. Class tags cannot replace observed lane roles. Rank labels must explain whether they describe a player, match average or another population rule.

No average rank band is finalized. The app should state the exact supported cohort rather than calling an arbitrary sample “average.” Combining ranks or patches must be explicit. Professional data must never silently replace missing solo-queue evidence.

## Difficulty and familiarity

Difficulty metadata can be a labeled selection aid, but does not measure personal proficiency or guarantee an easy counter. A personal champion pool can better express comfort. Planned controls should remain separate from observed results; no difficulty cutoff or ease-based score adjustment is implemented yet.

## Current foundation and next steps

Manual drafting, portraits, swaps, undo, imports, scoring, explanations and two native interfaces work today. Current statistics are historical professional aggregates. The [roadmap](ROADMAP.md) prioritizes licensed ranked cohorts, supported counter explanations, personal champion pools and broader device testing.

Success means correct cohorts and roles, honest missing evidence, useful explanations and responsive editing. Predictive-quality claims require a separate held-out evaluation; functional tests do not establish that quality. Live-client integration, automated picking, overlays and account collection are outside the current plan.
