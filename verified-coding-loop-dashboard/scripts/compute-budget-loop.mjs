import { projectPath, readJson, writeJson } from './lib/json-store.mjs';
import { asNumber, clamp, round2 } from './lib/number-tools.mjs';
import { getLearningSignals } from './lib/learning-signals.mjs';

const root = process.cwd();

const paths = {
  budget: projectPath(root, 'src/data/computeBudgetState.json'),
  verified: projectPath(root, 'src/data/verifiedLearningState.json'),
  meta: projectPath(root, 'src/data/metaLearningState.json'),
  value: projectPath(root, 'src/data/revenueLearningState.json'),
  report: projectPath(root, 'learning/compute-budget-report.json')
};

const defaultBudget = {
  schemaVersion: 2,
  startingCredits: 1000,
  creditBalance: 1000,
  runCount: 0,
  hourlyCostRate: 2,
  attemptCost: 1.5,
  successCredit: 8,
  writePenalty: 12,
  testPenalty: 20,
  buildPenalty: 25,
  skillCredit: 5,
  rateGainPerBenchmark: 0.25,
  rateGainPerSkill: 0.1,
  virtualRate: 1,
  maxVirtualRate: 100,
  lowCreditThreshold: 100,
  ledger: []
};

function normalizeBudget(rawBudget) {
  return {
    ...defaultBudget,
    ...rawBudget,
    startingCredits: asNumber(rawBudget.startingCredits ?? rawBudget.startingFloat, defaultBudget.startingCredits),
    creditBalance: asNumber(rawBudget.creditBalance ?? rawBudget.balance, defaultBudget.creditBalance),
    hourlyCostRate: asNumber(rawBudget.hourlyCostRate ?? rawBudget.hourlyBurnRate, defaultBudget.hourlyCostRate),
    attemptCost: asNumber(rawBudget.attemptCost ?? rawBudget.attemptedWriteCost, defaultBudget.attemptCost),
    successCredit: asNumber(rawBudget.successCredit ?? rawBudget.successfulWriteReward, defaultBudget.successCredit),
    writePenalty: asNumber(rawBudget.writePenalty ?? rawBudget.failedWritePenalty, defaultBudget.writePenalty),
    testPenalty: asNumber(rawBudget.testPenalty ?? rawBudget.failedBenchmarkPenalty, defaultBudget.testPenalty),
    buildPenalty: asNumber(rawBudget.buildPenalty ?? rawBudget.failedBuildPenalty, defaultBudget.buildPenalty),
    lowCreditThreshold: asNumber(rawBudget.lowCreditThreshold ?? rawBudget.pauseThreshold, defaultBudget.lowCreditThreshold),
    ledger: rawBudget.ledger || []
  };
}

function calculateLedgerEntry({ budget, signals }) {
  const estimatedHours = 6;
  const attemptedWrites = 1;

  const timeCost = round2(estimatedHours * budget.hourlyCostRate);
  const attemptCost = round2(attemptedWrites * budget.attemptCost);
  const penaltyCost = round2(
    (signals.codeWriteSucceeded ? 0 : budget.writePenalty) +
    (signals.testsPassed ? 0 : budget.testPenalty) +
    (signals.buildPassed ? 0 : budget.buildPenalty)
  );

  const successCredit = signals.codeWriteSucceeded ? budget.successCredit : 0;
  const skillCredit = round2(signals.skillSignals.length * budget.skillCredit);
  const rateGain = round2(
    (signals.benchmarkPassed ? budget.rateGainPerBenchmark : 0) +
    signals.skillSignals.length * budget.rateGainPerSkill
  );
  const nextRate = round2(clamp(budget.virtualRate + rateGain, 0, budget.maxVirtualRate));
  const rateBonus = round2(nextRate * 0.1);

  const grossCredit = round2(successCredit + skillCredit + rateBonus);
  const totalCost = round2(timeCost + attemptCost + penaltyCost);
  const netChange = round2(grossCredit - totalCost);
  const nextBalance = round2(budget.creditBalance + netChange);
  const status = nextBalance <= budget.lowCreditThreshold
    ? 'low_credit_reduce_scope'
    : signals.benchmarkPassed
      ? 'healthy_verified_progress'
      : 'costly_failure_reduce_risk';

  return {
    time: new Date().toISOString(),
    type: 'compute_credit_update',
    estimatedHours,
    attemptedWrites,
    testsPassed: signals.testsPassed,
    buildPassed: signals.buildPassed,
    benchmarkPassed: signals.benchmarkPassed,
    codeWriteSucceeded: signals.codeWriteSucceeded,
    skillSignals: signals.skillSignals,
    costs: { timeCost, attemptCost, penaltyCost, totalCost },
    credits: { successCredit, skillCredit, rateBonus, grossCredit },
    rateGain,
    virtualRateBefore: budget.virtualRate,
    virtualRateAfter: nextRate,
    netChange,
    balanceBefore: budget.creditBalance,
    balanceAfter: nextBalance,
    status,
    note: 'Internal score credits only for project planning.'
  };
}

function guidanceFor(status) {
  if (status === 'low_credit_reduce_scope') {
    return 'Credit balance is low. Prefer smaller proposals until the ledger recovers.';
  }
  if (status === 'costly_failure_reduce_risk') {
    return 'The failed iteration was costly. Add tests first and reduce write scope.';
  }
  return 'Verified progress is healthy. Continue with small reversible improvements.';
}

const budget = normalizeBudget(readJson(paths.budget, defaultBudget));
const verified = readJson(paths.verified, { verifiedRuns: 0, learningHistory: [] });
const meta = readJson(paths.meta, { metaRuns: 0, strategyHistory: [] });
const value = readJson(paths.value, { loopRuns: 0, experimentHistory: [] });
const signals = getLearningSignals({ verified, meta, value });
const entry = calculateLedgerEntry({ budget, signals });

const nextBudget = {
  ...budget,
  schemaVersion: 2,
  creditBalance: entry.balanceAfter,
  balance: entry.balanceAfter,
  runCount: asNumber(budget.runCount, 0) + 1,
  virtualRate: entry.virtualRateAfter,
  lastRunAt: entry.time,
  lastStatus: entry.status,
  ledger: [entry, ...(budget.ledger || [])].slice(0, 100)
};

const report = {
  schemaVersion: 2,
  generatedAt: entry.time,
  purpose: 'Track internal compute credits for time, attempts, failed checks, successful checks, skill signals, and virtual rate gains.',
  latestEntry: entry,
  stateAfter: {
    creditBalance: nextBudget.creditBalance,
    virtualRate: nextBudget.virtualRate,
    runCount: nextBudget.runCount,
    status: entry.status
  },
  guidance: guidanceFor(entry.status)
};

writeJson(paths.budget, nextBudget);
writeJson(paths.report, report);

console.log(JSON.stringify({
  ok: true,
  status: entry.status,
  balanceBefore: entry.balanceBefore,
  balanceAfter: entry.balanceAfter,
  netChange: entry.netChange,
  totalCost: entry.costs.totalCost,
  grossCredit: entry.credits.grossCredit,
  rateGain: entry.rateGain,
  virtualRate: entry.virtualRateAfter
}, null, 2));
