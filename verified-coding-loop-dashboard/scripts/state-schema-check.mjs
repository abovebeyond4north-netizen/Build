import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

import { readJson } from './lib/json-store.mjs';
import { asNumber } from './lib/number-tools.mjs';

const root = process.cwd();

const requiredJsonFiles = [
  'src/data/verifiedLearningState.json',
  'src/data/revenueLearningState.json',
  'src/data/metaLearningState.json',
  'src/data/timeValueState.json',
  'src/data/computeBudgetState.json',
  'proposals/latest-verified-proposal.json',
  'revenue/revenue-learning-report.json',
  'learning/meta-learning-report.json',
  'learning/time-score-report.json',
  'learning/compute-budget-report.json'
];

function exists(relativePath) {
  return fs.existsSync(path.join(root, relativePath));
}

function load(relativePath) {
  assert.ok(exists(relativePath), `Missing JSON artifact: ${relativePath}`);
  return readJson(path.join(root, relativePath), null);
}

function assertArray(value, label) {
  assert.ok(Array.isArray(value), `${label} must be an array`);
}

for (const file of requiredJsonFiles) {
  const parsed = load(file);
  assert.ok(parsed && typeof parsed === 'object', `${file} must contain a JSON object`);
  assert.ok('schemaVersion' in parsed || file.includes('report'), `${file} should expose schemaVersion or be a report artifact`);
}

const verified = load('src/data/verifiedLearningState.json');
assert.equal(asNumber(verified.schemaVersion, 0) >= 1, true, 'verified schemaVersion must be valid');
assert.equal(typeof verified.lastDecision, 'string', 'verified state should track lastDecision');
assertArray(verified.learningHistory, 'verified learningHistory');

const value = load('src/data/revenueLearningState.json');
assert.equal(asNumber(value.schemaVersion, 0) >= 1, true, 'value schemaVersion must be valid');
assertArray(value.experimentHistory, 'value experimentHistory');
assertArray(value.activeConstraints, 'value activeConstraints');

const meta = load('src/data/metaLearningState.json');
assert.equal(asNumber(meta.schemaVersion, 0) >= 1, true, 'meta schemaVersion must be valid');
assertArray(meta.strategyHistory, 'meta strategyHistory');
assertArray(meta.activePrinciples, 'meta activePrinciples');

const timeValue = load('src/data/timeValueState.json');
assert.equal(asNumber(timeValue.schemaVersion, 0) >= 1, true, 'time value schemaVersion must be valid');
assert.ok('virtualBalance' in timeValue || 'virtualScoreBalance' in timeValue || 'creditBalance' in timeValue, 'time value state should track a balance-like score');
assert.ok('virtualHourlyRate' in timeValue || 'virtualRate' in timeValue, 'time value state should track a virtual rate');
assert.ok(Array.isArray(timeValue.ledger) || Array.isArray(timeValue.budgetLedger), 'time value state should track a ledger');

const compute = load('src/data/computeBudgetState.json');
assert.equal(asNumber(compute.schemaVersion, 0) >= 1, true, 'compute schemaVersion must be valid');
assert.ok('startingCredits' in compute || 'startingFloat' in compute, 'compute state should track starting credits');
assert.ok('creditBalance' in compute || 'balance' in compute, 'compute state should track current credits');
assertArray(compute.ledger, 'compute ledger');

const proposal = load('proposals/latest-verified-proposal.json');
assert.ok('safetyPolicy' in proposal, 'proposal should include safetyPolicy');
assert.equal(proposal.safetyPolicy?.humanReviewRequired, true, 'proposal should require review');

const valueReport = load('revenue/revenue-learning-report.json');
assert.ok('limits' in valueReport, 'value report should include limits');
assert.equal(valueReport.limits?.humanReviewRequired, true, 'value report should require review');

const packageJson = load('package.json');
assert.ok(packageJson.scripts?.['schema:check'], 'package.json should expose schema:check');
assert.ok(packageJson.scripts?.test?.includes('schema:check'), 'test script should include schema:check');

console.log(JSON.stringify({
  ok: true,
  checkedFiles: requiredJsonFiles.length,
  states: ['verified', 'value', 'meta', 'timeValue', 'compute'],
  reports: ['proposal', 'valueReport', 'metaReport', 'timeScoreReport', 'computeBudgetReport']
}, null, 2));
