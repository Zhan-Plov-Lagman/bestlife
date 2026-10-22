# Shadow Mode — deferred

No online Shadow Mode, paired portfolio dashboard, strategy-comparison report or automatic promotion is implemented. The original dashboard remains functional; it does not advertise unavailable shadow controls.

The offline replay runner can generate two isolated run databases using identical JSONL and explicit baseline versions. These independent artifacts are not equivalent to a completed shadow subsystem. A future paired runner must fan out identical immutable snapshots at identical virtual times, keep orders/cash/feature histories separate, align decisions by event key, and report net P&L, drawdown, turnover, fees, slippage, coverage, provenance and disagreement. Differences need enough observations and confidence analysis; a short synthetic run cannot establish superiority.

Online shadow must be opt-in/off in ECO, obey bounded resource budgets and the same risk engine, and never change the primary account or promote a candidate automatically.
