import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {
  FORBIDDEN_RUNTIME_PATTERNS,
  REQUIRED_ACTIONS,
  REQUIRED_SAFETY_CLAIMS,
  REQUIRED_SECTIONS
} from './lib/dashboard-contract.mjs';
import { readText } from './lib/quality-score.mjs';

const root = process.cwd();
const app = readText(root, 'src/App.jsx');
const pkg = JSON.parse(readText(root, 'package.json'));
const exists = file => fs.existsSync(path.join(root, file));

function assertEveryMarker(text, markers, label) {
  for (const marker of markers) {
    assert.ok(text.includes(marker), `Missing ${label}: ${marker}`);
  }
}

function scoreProject() {
  return (
    REQUIRED_SECTIONS.filter(section => app.includes(section)).length * 3 +
    REQUIRED_ACTIONS.filter(action => app.includes(action)).length * 2 +
    REQUIRED_SAFETY_CLAIMS.filter(claim => app.includes(claim)).length * 4 +
    (exists('src/data/verifiedLearningState.json') ? 10 : 0) +
    (pkg.scripts?.test ? 10 : 0) +
    (pkg.scripts?.build ? 10 : 0) +
    (pkg.scripts?.['verify:self-improve'] ? 10 : 0)
  );
}

assertEveryMarker(app, REQUIRED_SECTIONS, 'dashboard section');
assertEveryMarker(app, REQUIRED_ACTIONS, 'action button');
assertEveryMarker(app, REQUIRED_SAFETY_CLAIMS, 'safety claim');

for (const pattern of FORBIDDEN_RUNTIME_PATTERNS) {
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
  sections: REQUIRED_SECTIONS.length,
  actions: REQUIRED_ACTIONS.length,
  safetyClaims: REQUIRED_SAFETY_CLAIMS.length
}, null, 2));
