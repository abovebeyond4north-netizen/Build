import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { includesAll, prependHistory, rankByScore, uniqueCount } from './lib/history-tools.mjs';
import { getLearningSignals } from './lib/learning-signals.mjs';
import { asNumber, clamp, round2 } from './lib/number-tools.mjs';
import { projectPath, readJson, writeJson } from './lib/json-store.mjs';

const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'verified-loop-lib-test-'));

try {
  const nestedJson = path.join(tempRoot, 'nested/state.json');
  const fallback = { ok: false };

  assert.deepEqual(readJson(nestedJson, fallback), fallback, 'readJson should return fallback for missing files');
  writeJson(nestedJson, { ok: true, count: 2 });
  assert.deepEqual(readJson(nestedJson, fallback), { ok: true, count: 2 }, 'writeJson should create directories and persist JSON');
  assert.equal(projectPath(tempRoot, 'a/b.txt'), path.join(tempRoot, 'a/b.txt'), 'projectPath should join root and relative path');

  assert.equal(round2(1.234), 1.23, 'round2 should round down correctly');
  assert.equal(round2(1.235), 1.24, 'round2 should round up correctly');
  assert.equal(clamp(12, 0, 10), 10, 'clamp should cap high values');
  assert.equal(clamp(-1, 0, 10), 0, 'clamp should cap low values');
  assert.equal(asNumber('4.5', 0), 4.5, 'asNumber should parse valid numbers');
  assert.equal(asNumber('not-a-number', 7), 7, 'asNumber should use fallback for invalid numbers');

  assert.deepEqual(prependHistory('new', ['old'], 2), ['new', 'old'], 'prependHistory should prepend');
  assert.deepEqual(prependHistory('new', ['old1', 'old2'], 2), ['new', 'old1'], 'prependHistory should enforce limit');
  assert.equal(uniqueCount(['a', 'a', 'b', null]), 2, 'uniqueCount should count truthy unique values');
  assert.equal(includesAll('alpha beta gamma', ['alpha', 'gamma']), true, 'includesAll should detect all markers');
  assert.equal(includesAll('alpha beta gamma', ['alpha', 'delta']), false, 'includesAll should reject missing markers');
  assert.deepEqual(rankByScore([{ score: 1 }, { score: 3 }, { score: 2 }]).map(item => item.score), [3, 2, 1], 'rankByScore should sort descending');

  const signals = getLearningSignals({
    verified: {
      learningHistory: [{
        testsPassed: true,
        buildPassed: true,
        decision: 'approved',
        beforeScore: 10,
        afterScore: 12
      }]
    },
    meta: { strategyHistory: [{ learningScore: 0.5 }] },
    value: { experimentHistory: [{ id: 'portfolio-proof-page' }] }
  });

  assert.equal(signals.testsPassed, true, 'signals should preserve test pass state');
  assert.equal(signals.buildPassed, true, 'signals should preserve build pass state');
  assert.equal(signals.benchmarkPassed, true, 'signals should identify passed benchmark');
  assert.equal(signals.codeWriteSucceeded, true, 'signals should identify successful write');
  assert.deepEqual(
    signals.skillSignals,
    ['meta_learning_measurement', 'value_experiment_selection', 'quality_score_preserved'],
    'signals should detect all skill signals'
  );

  console.log(JSON.stringify({
    ok: true,
    testedModules: [
      'json-store',
      'number-tools',
      'history-tools',
      'learning-signals'
    ]
  }, null, 2));
} finally {
  fs.rmSync(tempRoot, { recursive: true, force: true });
}
