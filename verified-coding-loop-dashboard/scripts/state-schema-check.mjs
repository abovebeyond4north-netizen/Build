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
  'src/data/processFocusState.json',
  'src/data/efficiencyOptimizerState.json',
  'src/data/generalImprovementState.json',
  'proposals/latest-verified-proposal.json',
  'revenue/revenue-learning-report.json',
  'learning/meta-learning-report.json',
  'learning/time-score-report.json',
  'learning/compute-budget-report.json',
  'learning/process-focus-report.json',
  'learning/efficiency-optimizer-report.json',
  'learning/general-improvement-report.json'
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

const processFocus = load('src/data/processFocusState.json');
assert.equal(asNumber(processFocus.schemaVersion, 0) >= 1, true, 'process focus schemaVersion must be valid');
assert.equal(typeof processFocus.factorWeights, 'object', 'process focus should track factorWeights');
assertArray(processFocus.focusHistory, 'process focusHistory');

const efficiency = load('src/data/efficiencyOptimizerState.json');
assert.equal(asNumber(efficiency.schemaVersion, 0) >= 1, true, 'efficiency optimizer schemaVersion must be valid');
assert.equal(typeof efficiency.weights, 'object', 'efficiency optimizer should track weights');
assertArray(efficiency.selectedHistory, 'efficiency selectedHistory');

const general = load('src/data/generalImprovementState.json');
assert.equal(asNumber(general.schemaVersion, 0) >= 1, true, 'general improvement schemaVersion must be valid');
assert.equal(typeof general.weights, 'object', 'general improvement should track weights');
assertArray(general.decisionHistory, 'general decisionHistory');

const proposal = load('proposals/latest-verified-proposal.json');
assert.ok('safetyPolicy' in proposal, 'proposal should include safetyPolicy');
assert.equal(proposal.safetyPolicy?.humanReviewRequired, true, 'proposal should require review');

const valueReport = load('revenue/revenue-learning-report.json');
assert.ok('limits' in valueReport, 'value report should include limits');
assert.equal(valueReport.limits?.humanReviewRequired, true, 'value report should require review');

const processReport = load('learning/process-focus-report.json');
assertArray(processReport.focusFactors, 'process focus report focusFactors');
assertArray(processReport.scoredProcesses, 'process focus report scoredProcesses');
assertArray(processReport.recommendations, 'process focus report recommendations');

const efficiencyReport = load('learning/efficiency-optimizer-report.json');
assertArray(efficiencyReport.rankedCandidates, 'efficiency optimizer rankedCandidates');
assert.equal(typeof efficiencyReport.stateAfter, 'object', 'efficiency optimizer report should track stateAfter');

const generalReport = load('learning/general-improvement-report.json');
assertArray(generalReport.rankedMoves, 'general improvement rankedMoves');
assert.equal(typeof generalReport.stateAfter, 'object', 'general improvement report should track stateAfter');

const packageJson = load('package.json');
assert.ok(packageJson.scripts?.['schema:check'], 'package.json should expose schema:check');
assert.ok(packageJson.scripts?.test?.includes('schema:check'), 'test script should include schema:check');

console.log(JSON.stringify({
  ok: true,
  checkedFiles: requiredJsonFiles.length,
  states: ['verified', 'value', 'meta', 'timeValue', 'compute', 'processFocus', 'efficiency', 'general'],
  reports: ['proposal', 'valueReport', 'metaReport', 'timeScoreReport', 'computeBudgetReport', 'processFocusReport', 'efficiencyReport', 'generalReport']
}, null, 2));
