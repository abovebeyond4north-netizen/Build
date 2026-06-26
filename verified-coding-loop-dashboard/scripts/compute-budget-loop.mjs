import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const budgetPath = path.join(root, 'src/data/computeBudgetState.json');
const verifiedPath = path.join(root, 'src/data/verifiedLearningState.json');
const metaPath = path.join(root, 'src/data/metaLearningState.json');
const valuePath = path.join(root, 'src/data/revenueLearningState.json');
const reportPath = path.join(root, 'learning/compute-budget-report.json');

function readJson(file, fallback) {
  if (!fs.existsSync(file)) return fallback;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function writeJson(file, data) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`);
}

function round2(value) {
  return Math.round(value * 100) / 100;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

const budget = readJson(budgetPath, {
  schemaVersion: 1,
  startingFloat: 1000,
  balance: 1000,
  runCount: 0,
  hourlyBurnRate: 2,
  attemptedWriteCost: 1.5,
  successfulWriteReward: 8,
  failedWritePenalty: 12,
  failedBenchmarkPenalty: 20,
  failedBuildPenalty: 25,
  skillReward: 5,
  raisePerBenchmark: 0.25,
  raisePerSkill: 0.1,
  virtualRate: 1,
  maxVirtualRate: 100,
  pauseThreshold: 100,
  ledger: []
});

const verified = readJson(verifiedPath, { verifiedRuns: 0, learningHistory: [] });
const meta = readJson(metaPath, { metaRuns: 0, strategyHistory: [] });
const value = readJson(valuePath, { loopRuns: 0, experimentHistory: [] });

const lastVerified = (verified.learningHistory || [])[0] || {};
const lastMeta = (meta.strategyHistory || [])[0] || {};
const lastValue = (value.experimentHistory || [])[0] || {};

const estimatedHours = 6;
const attemptedWrites = 1;
const testsPassed = lastVerified.testsPassed === true;
const buildPassed = lastVerified.buildPassed === true;
const benchmarkPassed = testsPassed && buildPassed;
const codeWriteSucceeded = benchmarkPassed && lastVerified.decision !== 'rejected';

const skillSignals = [
  lastMeta.learningScore > 0 ? 'meta_learning_measurement' : null,
  lastValue.id ? 'value_experiment_selection' : null,
  lastVerified.afterScore >= lastVerified.beforeScore ? 'quality_score_preserved' : null
].filter(Boolean);

const timeCost = round2(estimatedHours * Number(budget.hourlyBurnRate || 2));
const writeCost = round2(attemptedWrites * Number(budget.attemptedWriteCost || 1.5));
const failureCost = round2(
  (codeWriteSucceeded ? 0 : Number(budget.failedWritePenalty || 12)) +
  (testsPassed ? 0 : Number(budget.failedBenchmarkPenalty || 20)) +
  (buildPassed ? 0 : Number(budget.failedBuildPenalty || 25))
);
const successReward = codeWriteSucceeded ? Number(budget.successfulWriteReward || 8) : 0;
const skillReward = round2(skillSignals.length * Number(budget.skillReward || 5));

const raiseAmount = round2(
  (benchmarkPassed ? Number(budget.raisePerBenchmark || 0.25) : 0) +
  skillSignals.length * Number(budget.raisePerSkill || 0.1)
);
const nextRate = round2(clamp(Number(budget.virtualRate || 1) + raiseAmount, 0, Number(budget.maxVirtualRate || 100)));

const grossCredits = round2(successReward + skillReward + nextRate * 0.1);
const totalCosts = round2(timeCost + writeCost + failureCost);
const netChange = round2(grossCredits - totalCosts);
const nextBalance = round2(Number(budget.balance || 0) + netChange);
const now = new Date().toISOString();

const status = nextBalance <= Number(budget.pauseThreshold || 100)
  ? 'low_balance_reduce_scope'
  : benchmarkPassed
    ? 'healthy_verified_progress'
    : 'costly_failure_reduce_risk';

const ledgerEntry = {
  time: now,
  type: 'compute_budget_update',
  estimatedHours,
  attemptedWrites,
  testsPassed,
  buildPassed,
  benchmarkPassed,
  codeWriteSucceeded,
  skillSignals,
  costs: {
    timeCost,
    writeCost,
    failureCost,
    totalCosts
  },
  credits: {
    successReward,
    skillReward,
    rateBonus: round2(nextRate * 0.1),
    grossCredits
  },
  raiseAmount,
  virtualRateBefore: Number(budget.virtualRate || 1),
  virtualRateAfter: nextRate,
  netChange,
  balanceBefore: Number(budget.balance || 0),
  balanceAfter: nextBalance,
  status,
  note: 'Internal compute credits only. This is not real-world payment or financial automation.'
};

const nextBudget = {
  ...budget,
  runCount: Number(budget.runCount || 0) + 1,
  balance: nextBalance,
  virtualRate: nextRate,
  lastRunAt: now,
  lastStatus: status,
  ledger: [ledgerEntry, ...(budget.ledger || [])].slice(0, 100)
};

const report = {
  schemaVersion: 1,
  generatedAt: now,
  purpose: 'Track an internal float for compute effort, code write attempts, failures, penalties, rewards, and virtual raises.',
  rules: nextBudget,
  latestEntry: ledgerEntry,
  guidance: status === 'low_balance_reduce_scope'
    ? 'Balance is low. Prefer smaller, cheaper proposals until the ledger recovers.'
    : status === 'costly_failure_reduce_risk'
      ? 'Failure was expensive. Reduce write scope, add tests first, and avoid large changes.'
      : 'Verified progress is healthy. Continue with small reversible improvements.'
};

writeJson(budgetPath, nextBudget);
writeJson(reportPath, report);

console.log(JSON.stringify({
  ok: true,
  status,
  balanceBefore: ledgerEntry.balanceBefore,
  balanceAfter: ledgerEntry.balanceAfter,
  netChange,
  totalCosts,
  grossCredits,
  raiseAmount,
  virtualRate: nextRate
}, null, 2));
