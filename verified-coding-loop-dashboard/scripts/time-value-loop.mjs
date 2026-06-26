import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const timeStatePath = path.join(root, 'src/data/timeValueState.json');
const verifiedStatePath = path.join(root, 'src/data/verifiedLearningState.json');
const metaStatePath = path.join(root, 'src/data/metaLearningState.json');
const valueStatePath = path.join(root, 'src/data/revenueLearningState.json');
const reportPath = path.join(root, 'learning/time-value-report.json');

function readJson(file, fallback) {
  if (!fs.existsSync(file)) return fallback;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function writeJson(file, data) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function round2(value) {
  return Math.round(value * 100) / 100;
}

const state = readJson(timeStatePath, {
  schemaVersion: 1,
  runs: 0,
  virtualBalance: 0,
  virtualHourlyRate: 1,
  bestEfficiencyScore: 0,
  totalBenchmarksRewarded: 0,
  totalSkillsRewarded: 0,
  ledger: [],
  rules: {
    realMoney: false,
    automaticTransfers: false,
    humanReviewRequired: true,
    baseBenchmarkReward: 5,
    baseSkillReward: 3,
    raisePerPassedBenchmark: 0.25,
    raisePerSkillAcquired: 0.15,
    maxVirtualHourlyRate: 100
  }
});

const verified = readJson(verifiedStatePath, { verifiedRuns: 0, learningHistory: [] });
const meta = readJson(metaStatePath, { metaRuns: 0, bestLearningScore: 0, strategyHistory: [] });
const value = readJson(valueStatePath, { loopRuns: 0, experimentHistory: [] });

const previousRuns = Number(state.runs || 0);
const verifiedRuns = Number(verified.verifiedRuns || 0);
const metaRuns = Number(meta.metaRuns || 0);
const valueRuns = Number(value.loopRuns || 0);

const lastVerified = (verified.learningHistory || [])[0] || {};
const lastMeta = (meta.strategyHistory || [])[0] || {};
const lastValue = (value.experimentHistory || [])[0] || {};

const benchmarkPassed = lastVerified.testsPassed === true && lastVerified.buildPassed === true;
const benchmarkDelta = benchmarkPassed ? 1 : 0;
const skillSignals = [
  lastMeta.learningScore > 0 ? 'meta_learning_measurement' : null,
  lastValue.id ? 'value_experiment_selection' : null,
  lastVerified.afterScore >= lastVerified.beforeScore ? 'quality_score_preserved' : null
].filter(Boolean);
const newSkillCount = skillSignals.length;

const elapsedHoursEstimate = 6;
const benchmarkReward = benchmarkDelta * Number(state.rules.baseBenchmarkReward || 5);
const skillReward = newSkillCount * Number(state.rules.baseSkillReward || 3);
const efficiencyScore = round2((benchmarkReward + skillReward) / elapsedHoursEstimate);

const raiseAmount = round2(
  benchmarkDelta * Number(state.rules.raisePerPassedBenchmark || 0.25) +
  newSkillCount * Number(state.rules.raisePerSkillAcquired || 0.15)
);

const nextRate = round2(clamp(
  Number(state.virtualHourlyRate || 1) + raiseAmount,
  0,
  Number(state.rules.maxVirtualHourlyRate || 100)
));

const payout = round2(benchmarkReward + skillReward + nextRate * 0.1);
const now = new Date().toISOString();

const ledgerEntry = {
  time: now,
  type: 'virtual_compensation_update',
  benchmarkPassed,
  benchmarkReward,
  skillSignals,
  skillReward,
  raiseAmount,
  virtualHourlyRateBefore: Number(state.virtualHourlyRate || 1),
  virtualHourlyRateAfter: nextRate,
  payout,
  efficiencyScore,
  note: 'Virtual credits only. No real payment, transfer, or financial claim.'
};

const nextState = {
  ...state,
  runs: previousRuns + 1,
  virtualBalance: round2(Number(state.virtualBalance || 0) + payout),
  virtualHourlyRate: nextRate,
  bestEfficiencyScore: Math.max(Number(state.bestEfficiencyScore || 0), efficiencyScore),
  totalBenchmarksRewarded: Number(state.totalBenchmarksRewarded || 0) + benchmarkDelta,
  totalSkillsRewarded: Number(state.totalSkillsRewarded || 0) + newSkillCount,
  lastRunAt: now,
  ledger: [ledgerEntry, ...(state.ledger || [])].slice(0, 100)
};

const report = {
  schemaVersion: 1,
  generatedAt: now,
  purpose: 'Apply a time-is-value constraint to reward verified learning progress with virtual credits and raises.',
  constraints: {
    timeIsValue: true,
    realMoney: false,
    automaticTransfers: false,
    humanReviewRequired: true,
    use: 'motivation, prioritization, and opportunity-cost scoring only'
  },
  inputs: {
    verifiedRuns,
    metaRuns,
    valueRuns,
    benchmarkPassed,
    skillSignals
  },
  rewards: ledgerEntry,
  stateAfter: {
    virtualBalance: nextState.virtualBalance,
    virtualHourlyRate: nextState.virtualHourlyRate,
    bestEfficiencyScore: nextState.bestEfficiencyScore,
    totalBenchmarksRewarded: nextState.totalBenchmarksRewarded,
    totalSkillsRewarded: nextState.totalSkillsRewarded
  },
  nextHumanStep: 'Review whether the virtual rewards match actual usefulness before changing any real-world offer, pricing, or budget.'
};

writeJson(timeStatePath, nextState);
writeJson(reportPath, report);

console.log(JSON.stringify({
  ok: true,
  virtualBalance: nextState.virtualBalance,
  virtualHourlyRate: nextState.virtualHourlyRate,
  payout,
  raiseAmount,
  benchmarkPassed,
  skillsRewarded: newSkillCount
}, null, 2));
