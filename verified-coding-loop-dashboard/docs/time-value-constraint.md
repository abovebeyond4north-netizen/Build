# Internal quality credits

Schema version 3 rewards only a new structural-quality high-water mark when the latest verification explicitly reports approved, passing tests, and a passing build. Replaying a result, changing its timestamp, preserving quality, or returning to a previous score earns nothing. These checks measure the dashboard's structural contract; they do not demonstrate acquired skills or general capability.

Each qualifying result earns 5 internal credits and a 0.25 virtual-rate increase (capped at 100 by default). There is no rate-based payout bonus and no reward for merely selecting an experiment or recording a meta score. Newly rewarded skills remain zero. The high-water mark provides constant-time eligibility checks; complete ledger validation takes linear time and storage in rewarded events. Reward history is retained without truncation.

## Migration and audit

On the first run, older state is preserved in `legacySnapshot`. Its balance and rate become explicit opening values without awarding anything or retroactively certifying old rewards. The current best quality score becomes the starting high-water mark. Canonical balance and rate fields replace parallel legacy fields at the top level. `npm run time:value` performs migration and creates the reconciled report.

`npm test` checks report/state equality, ledger arithmetic, unique evidence, rate changes, repeated evidence, rejected and failed results, retention, and CLI replay. The time-value report is derived entirely from persisted reward state, so running the command again repairs an interrupted report write without re-awarding credits. Do not run concurrent writers against the same working directory; the scheduled workflow already serializes runs.

Verification records include measured test/build elapsed seconds for new runs. Missing duration remains null. No six-hour estimate or credits-per-hour efficiency claim is made; the virtual rate is a bounded internal score, not measured hourly productivity.

## Interpretation

The meta-learning score is a process/activity proxy based on history length, diversity, run count, and declared safeguards. Its increase must not be described as an independently verified capability gain. Actual capability evaluation needs separate held-out tasks and measured outcomes.

These credits are not money. Human review remains required for external actions; this subsystem does not initiate transfers, outreach, or deployment.
