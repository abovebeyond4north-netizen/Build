import { projectPath, readJson, writeJson } from './lib/json-store.mjs';
import { asNumber, clamp, round2 } from './lib/number-tools.mjs';
import { getLearningSignals } from './lib/learning-signals.mjs';
import { prependHistory } from './lib/history-tools.mjs';

const root = process.cwd();

const paths = {
  timeState: projectPath(root, 'src/data/timeValueState.json'),
  verified: projectPath(root, 'src/data/verifiedLearningState.json'),
  meta: projectPath(root, 'src/data/metaLearningState.json'),
  value: projectPath(root, 'src/data/revenueLearningState.json'),
  report: projectPath(root, 'learning/time-value-report.json')
};

const defaultState = {
  schemaVersion: 2,
  runs: 0,
  virtualBalance: 0,
  virtualHourlyRate: 1,
  bestEfficiencyScore: 0,
  totalBenchmarksRewarded: 0,
  totalSkillsRewarded: 0,
  ledger: [],
  rules: {
    externalFinance: false,
    outsideActions: false,
    reviewRequired: true,
    baseBenchmarkReward: 5,
    baseSkillReward: 3,
    raisePerPassedBenchmark: 0.25,
    raisePerSkillAcquired: 0.15,
    maxVirtualHourlyRate: 100
  }
};

function normalizeState(raw) {
  return {
    ...defaultState,
    ...raw,
    virtualBalance: asNumber(raw.virtualBalance ?? raw.virtualScoreBalance, defaultState.virtualBalance),
    virtualHourlyRate: asNumber(raw.virtualHourlyRate ?? raw.virtualRate, defaultState.virtualHourlyRate),
    ledger: raw.ledger || raw.budgetLedger || []
  };
}

function calculateReward({ state, signals }) {
  const elapsedHoursEstimate = 6;
  const benchmarkDelta = signals.benchmarkPassed ? 1 : 0;
  const newSkillCount = signals.skillSignals.length;
  const benchmarkReward = benchmarkDelta * asNumber(state.rules.baseBenchmarkReward, 5);
  const skillReward = newSkillCount * asNumber(state.rules.baseSkillReward, 3);
  const efficiencyScore = round2((benchmarkReward + skillReward) / elapsedHoursEstimate);
  const raiseAmount = round2(
    benchmarkDelta * asNumber(state.rules.raisePerPassedBenchmark, 0.25) +
    newSkillCount * asNumber(state.rules.raisePerSkillAcquired, 0.15)
  );
  const nextRate = round2(clamp(
    state.virtualHourlyRate + raiseAmount,
    0,
    asNumber(state.rules.maxVirtualHourlyRate, 100)
  ));
  const payout = round2(benchmarkReward + skillReward + nextRate * 0.1);

  return {
    elapsedHoursEstimate,
    benchmarkDelta,
    newSkillCount,
    benchmarkReward,
    skillReward,
    efficiencyScore,
    raiseAmount,
    nextRate,
    payout
  };
}

const state = normalizeState(readJson(paths.timeState, defaultState));
const verified = readJson(paths.verified, { verifiedRuns: 0, learningHistory: [] });
const meta = readJson(paths.meta, { metaRuns: 0, strategyHistory: [] });
const value = readJson(paths.value, { loopRuns: 0, experimentHistory: [] });
const signals = getLearningSignals({ verified, meta, value });
const reward = calculateReward({ state, signals });
const now = new Date().toISOString();

const ledgerEntry = {
  time: now,
  type: 'virtual_time_value_update',
  benchmarkPassed: signals.benchmarkPassed,
  benchmarkReward: reward.benchmarkReward,
  skillSignals: signals.skillSignals,
  skillReward: reward.skillReward,
  raiseAmount: reward.raiseAmount,
  virtualHourlyRateBefore: state.virtualHourlyRate,
  virtualHourlyRateAfter: reward.nextRate,
  payout: reward.payout,
  efficiencyScore: reward.efficiencyScore,
  note: 'Internal virtual credits only for prioritization.'
};

const nextState = {
  ...state,
  schemaVersion: 2,
  runs: asNumber(state.runs, 0) + 1,
  virtualBalance: round2(state.virtualBalance + reward.payout),
  virtualHourlyRate: reward.nextRate,
  bestEfficiencyScore: Math.max(asNumber(state.bestEfficiencyScore, 0), reward.efficiencyScore),
  totalBenchmarksRewarded: asNumber(state.totalBenchmarksRewarded, 0) + reward.benchmarkDelta,
  totalSkillsRewarded: asNumber(state.totalSkillsRewarded, 0) + reward.newSkillCount,
  lastRunAt: now,
  ledger: prependHistory(ledgerEntry, state.ledger, 100)
};

const report = {
  schemaVersion: 2,
  generatedAt: now,
  purpose: 'Apply a time-is-value constraint to reward verified learning progress with virtual credits and raises.',
  constraints: {
    timeIsValue: true,
    externalFinance: false,
    outsideActions: false,
    reviewRequired: true,
    use: 'motivation, prioritization, and opportunity-cost scoring only'
  },
  inputs: {
    verifiedRuns: asNumber(verified.verifiedRuns, 0),
    metaRuns: asNumber(meta.metaRuns, 0),
    valueRuns: asNumber(value.loopRuns, 0),
    benchmarkPassed: signals.benchmarkPassed,
    skillSignals: signals.skillSignals
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

writeJson(paths.timeState, nextState);
writeJson(paths.report, report);

console.log(JSON.stringify({
  ok: true,
  virtualBalance: nextState.virtualBalance,
  virtualHourlyRate: nextState.virtualHourlyRate,
  payout: reward.payout,
  raiseAmount: reward.raiseAmount,
  benchmarkPassed: signals.benchmarkPassed,
  skillsRewarded: reward.newSkillCount
}, null, 2));
