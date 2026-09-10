import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { updateRewardState, validateRewardState, rewardReport } from './lib/reward-evidence.mjs';

const evidence = score => ({ bestQualityScore: score, learningHistory: [{
  decision: 'approved', testsPassed: true, buildPassed: true,
  beforeScore: 130, afterScore: score, elapsedSeconds: 2
}] });
const legacy = { virtualBalance: 42.72, virtualHourlyRate: 3.1, ledger: [{ payout: 14.31 }] };
const initial = updateRewardState(legacy, evidence(130), '2026-09-10T00:00:00Z');
assert.equal(initial.virtualBalance, 42.72);
assert.deepEqual(initial.legacySnapshot, legacy);
assert.equal(initial.totalSkillsRewarded, 0);
assert.deepEqual(updateRewardState(initial, evidence(130)), initial);
for (const field of ['testsPassed', 'buildPassed']) {
  const failed = evidence(135); failed.learningHistory[0][field] = false;
  assert.deepEqual(updateRewardState(initial, failed), initial);
}
const rejected = evidence(135); rejected.learningHistory[0].decision = 'rejected';
assert.deepEqual(updateRewardState(initial, rejected), initial);
for (const score of [129, NaN, Infinity, '135']) assert.deepEqual(updateRewardState(initial, evidence(score)), initial);
const improved = updateRewardState(initial, evidence(135));
assert.equal(improved.virtualBalance, 47.72);
assert.equal(improved.virtualHourlyRate, 3.35);
assert.equal(improved.totalSkillsRewarded, 0);
assert.equal(improved.ledger[0].elapsedSeconds, 2);
assert.deepEqual(updateRewardState(improved, evidence(135)), improved, 'replay awards nothing');
const timestampOnly = evidence(135); timestampOnly.learningHistory[0].time = '2099-01-01';
assert.deepEqual(updateRewardState(improved, timestampOnly), improved, 'new timestamp is not new evidence');
assert.deepEqual(updateRewardState(improved, evidence(130)), improved, 'old evidence cannot be rewarded again');
for (const mutate of [s => s.virtualBalance++, s => s.virtualHourlyRate++, s => s.ledger.push(s.ledger[0]),
  s => s.totalSkillsRewarded++, s => s.ledger[0].payout++, s => s.rewardedQualityHighWater++]) {
  const bad = structuredClone(improved); mutate(bad);
  assert.throws(() => validateRewardState(bad));
}
let many = initial;
for (let score = 131; score <= 240; score++) many = updateRewardState(many, evidence(score));
assert.equal(many.ledger.length, 110, 'evidence is retained beyond old history cap');
assert.deepEqual(updateRewardState(many, evidence(131)), many);
assert.equal(rewardReport(many).stateAfter.virtualBalance, many.virtualBalance);
const capped = structuredClone(initial); capped.rules.maxVirtualHourlyRate = 3.2;
assert.equal(updateRewardState(capped, evidence(135)).virtualHourlyRate, 3.2);

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'reward-cli-'));
try {
  fs.mkdirSync(path.join(dir, 'src/data'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'src/data/timeValueState.json'), JSON.stringify(initial));
  fs.writeFileSync(path.join(dir, 'src/data/verifiedLearningState.json'), JSON.stringify(evidence(135)));
  const cli = path.resolve('scripts/time-value-loop.mjs');
  execFileSync(process.execPath, [cli], { cwd: dir });
  const files = ['src/data/timeValueState.json', 'learning/time-value-report.json'];
  const first = files.map(file => fs.readFileSync(path.join(dir, file), 'utf8'));
  execFileSync(process.execPath, [cli], { cwd: dir });
  assert.deepEqual(files.map(file => fs.readFileSync(path.join(dir, file), 'utf8')), first, 'CLI replay is byte-identical');
  assert.deepEqual(JSON.parse(first[1]), rewardReport(JSON.parse(first[0])));
  fs.writeFileSync(path.join(dir, files[1]), '{}');
  execFileSync(process.execPath, [cli], { cwd: dir });
  assert.deepEqual(files.map(file => fs.readFileSync(path.join(dir, file), 'utf8')), first, 'report recovery awards nothing');
} finally { fs.rmSync(dir, { recursive: true, force: true }); }
console.log('Reward regression checks passed: migration, replay, failure, corruption, retention, cap, and CLI reconciliation.');
