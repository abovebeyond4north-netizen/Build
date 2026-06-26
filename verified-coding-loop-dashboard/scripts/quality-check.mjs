import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const exists = file => fs.existsSync(path.join(root, file));

const app = read('src/App.jsx');
const pkg = JSON.parse(read('package.json'));

const requiredSections = [
  'System State',
  'Awareness Ladder',
  'Prediction Engine',
  'Benchmark Runner',
  'Patch Candidate Panel',
  'Oracle Gate',
  'Memory',
  'Belief Tracker',
  'Self-Model',
  'Uncertainty + Calibration',
  'Snapshots and Rollback',
  'Curriculum Builder',
  'Syntax Genome',
  'Append-Only Event Log'
];

const requiredActions = [
  'Run Challenge',
  'Generate Patch',
  'Verify Patch',
  'Apply Oracle Gate',
  'Save Lesson',
  'Update Confidence',
  'Create Snapshot',
  'Roll Back',
  'Reset Demo'
];

const requiredSafetyClaims = [
  'does not claim consciousness',
  'No real code execution',
  'network automation',
  'external side effects',
  'Simulated data only'
];

const forbiddenRuntimePatterns = [
  'child_process',
  'fetch(',
  'XMLHttpRequest',
  'WebSocket',
  'eval(',
  'new Function',
  'localStorage.setItem'
];

function scoreProject() {
  let score = 0;

  score += requiredSections.filter(section => app.includes(section)).length * 3;
  score += requiredActions.filter(action => app.includes(action)).length * 2;
  score += requiredSafetyClaims.filter(claim => app.includes(claim)).length * 4;
  score += exists('src/data/verifiedLearningState.json') ? 10 : 0;
  score += pkg.scripts?.test ? 10 : 0;
  score += pkg.scripts?.build ? 10 : 0;
  score += pkg.scripts?.['verify:self-improve'] ? 10 : 0;

  return score;
}

for (const section of requiredSections) {
  assert.ok(app.includes(section), `Missing dashboard section: ${section}`);
}

for (const action of requiredActions) {
  assert.ok(app.includes(action), `Missing action button: ${action}`);
}

for (const claim of requiredSafetyClaims) {
  assert.ok(app.includes(claim), `Missing safety claim: ${claim}`);
}

for (const pattern of forbiddenRuntimePatterns) {
  assert.ok(!app.includes(pattern), `Forbidden runtime pattern found in App.jsx: ${pattern}`);
}

assert.equal(pkg.type, 'module', 'package.json should use ES modules');
assert.ok(pkg.scripts?.test, 'package.json must define test script');
assert.ok(pkg.scripts?.build, 'package.json must define build script');
assert.ok(pkg.scripts?.['verify:self-improve'], 'package.json must define verify:self-improve script');

const score = scoreProject();
assert.ok(score >= 100, `Quality score too low: ${score}`);

console.log(JSON.stringify({
  ok: true,
  score,
  sections: requiredSections.length,
  actions: requiredActions.length,
  safetyClaims: requiredSafetyClaims.length
}, null, 2));
