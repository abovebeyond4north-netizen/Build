import assert from 'node:assert/strict';
import { round2 } from './number-tools.mjs';

function nonnegative(value, label) {
  assert.ok(typeof value === 'number' && Number.isFinite(value) && value >= 0, label);
  return value;
}

// O(n) ledger reconciliation; reward eligibility uses an O(1) high-water mark.
// Historic credits are retained as an explicitly unverified opening balance.
export function updateRewardState(previous, verified, now = new Date().toISOString()) {
  assert.ok(previous.schemaVersion === undefined || [1, 2, 3].includes(previous.schemaVersion), 'unsupported reward schema');
  if (previous.schemaVersion !== 3) {
    const balance = nonnegative(previous.virtualBalance ?? previous.virtualScoreBalance ?? 0, 'legacy balance');
    const rate = nonnegative(previous.virtualHourlyRate ?? previous.virtualRate ?? 1, 'legacy rate');
    const score = nonnegative(verified.bestQualityScore ?? 0, 'baseline quality score');
    return {
      schemaVersion: 3, runs: 0, virtualBalance: balance, virtualHourlyRate: rate,
      bestEfficiencyScore: null, totalBenchmarksRewarded: 0, totalSkillsRewarded: 0,
      rewardedQualityHighWater: score, openingQualityHighWater: score, openingBalance: balance, openingRate: rate,
      legacySnapshot: previous, ledger: [], lastRunAt: now,
      lastDecision: 'migrated_without_reward',
      rules: { externalFinance: false, outsideActions: false, reviewRequired: true,
        baseBenchmarkReward: 5, raisePerPassedBenchmark: 0.25, maxVirtualHourlyRate: Math.max(100, rate) }
    };
  }
  validateRewardState(previous);
  const record = verified.learningHistory?.[0];
  const score = record?.afterScore;
  if (record?.decision !== 'approved' || record.testsPassed !== true || record.buildPassed !== true ||
      typeof score !== 'number' || !Number.isFinite(score) || score <= previous.rewardedQualityHighWater) return previous;
  const reward = previous.rules.baseBenchmarkReward;
  const rate = round2(Math.min(previous.rules.maxVirtualHourlyRate,
    previous.virtualHourlyRate + previous.rules.raisePerPassedBenchmark));
  const entry = { time: now, evidenceId: `quality-score:${score}`,
    qualityBefore: previous.rewardedQualityHighWater, qualityAfter: score,
    benchmarkReward: reward, payout: reward, skillReward: 0, skillSignals: [],
    virtualHourlyRateBefore: previous.virtualHourlyRate, virtualHourlyRateAfter: rate,
    elapsedSeconds: typeof record.elapsedSeconds === 'number' && Number.isFinite(record.elapsedSeconds) && record.elapsedSeconds > 0
      ? record.elapsedSeconds : null };
  const next = { ...previous, runs: previous.runs + 1,
    virtualBalance: round2(previous.virtualBalance + reward), virtualHourlyRate: rate,
    rewardedQualityHighWater: score, totalBenchmarksRewarded: previous.totalBenchmarksRewarded + 1,
    lastRunAt: now, lastDecision: 'new_quality_high_water_rewarded', ledger: [...previous.ledger, entry] };
  validateRewardState(next);
  return next;
}

export function validateRewardState(state) {
  assert.equal(state.schemaVersion, 3);
  let balance = nonnegative(state.openingBalance, 'opening balance');
  let rate = nonnegative(state.openingRate, 'opening rate');
  let lastScore = nonnegative(state.openingQualityHighWater, 'opening quality high water');
  const ids = new Set();
  for (const key of ['baseBenchmarkReward', 'raisePerPassedBenchmark', 'maxVirtualHourlyRate'])
    nonnegative(state.rules[key], key);
  for (const entry of state.ledger) {
    assert.ok(!ids.has(entry.evidenceId), 'duplicate evidence');
    ids.add(entry.evidenceId);
    nonnegative(entry.qualityBefore, 'quality before');
    nonnegative(entry.qualityAfter, 'quality after');
    assert.ok(entry.qualityAfter > entry.qualityBefore, 'quality must improve');
    assert.equal(entry.evidenceId, `quality-score:${entry.qualityAfter}`);
    assert.equal(entry.qualityBefore, lastScore);
    lastScore = entry.qualityAfter;
    assert.equal(entry.payout, state.rules.baseBenchmarkReward);
    assert.equal(entry.benchmarkReward, entry.payout);
    assert.equal(entry.skillReward, 0);
    assert.deepEqual(entry.skillSignals, []);
    assert.equal(entry.virtualHourlyRateBefore, rate);
    rate = round2(Math.min(state.rules.maxVirtualHourlyRate, rate + state.rules.raisePerPassedBenchmark));
    assert.equal(entry.virtualHourlyRateAfter, rate);
    balance = round2(balance + entry.payout);
  }
  nonnegative(state.rewardedQualityHighWater, 'quality high water');
  assert.equal(state.rewardedQualityHighWater, lastScore);
  assert.equal(state.virtualBalance, balance, 'ledger balance mismatch');
  assert.equal(state.virtualHourlyRate, rate, 'ledger rate mismatch');
  assert.equal(state.runs, state.ledger.length);
  assert.equal(state.totalBenchmarksRewarded, state.ledger.length);
  assert.equal(state.totalSkillsRewarded, 0);
  assert.equal(state.rules.externalFinance, false);
  assert.equal(state.rules.outsideActions, false);
  assert.equal(state.rules.reviewRequired, true);
}

export function rewardReport(state) {
  validateRewardState(state);
  return { schemaVersion: 3, generatedAt: state.lastRunAt,
    purpose: 'Internal credits for new verified structural-quality high-water marks; not capability or income evidence.',
    decision: state.lastDecision, constraints: { externalFinance: false, outsideActions: false, reviewRequired: true },
    legacyCredits: 'Preserved in openingBalance and legacySnapshot; not newly validated.',
    efficiencyScore: null, efficiencyNote: 'No assumed runtime or credits-per-hour claim.',
    rewards: state.ledger.at(-1) ?? null,
    stateAfter: { virtualBalance: state.virtualBalance, virtualHourlyRate: state.virtualHourlyRate,
      rewardedQualityHighWater: state.rewardedQualityHighWater,
      totalBenchmarksRewarded: state.totalBenchmarksRewarded, totalSkillsRewarded: 0 } };
}
