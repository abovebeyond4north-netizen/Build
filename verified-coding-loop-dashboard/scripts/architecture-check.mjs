import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const scriptDir = path.join(root, 'scripts');

const requiredLibs = [
  'scripts/lib/json-store.mjs',
  'scripts/lib/number-tools.mjs',
  'scripts/lib/history-tools.mjs',
  'scripts/lib/learning-signals.mjs',
  'scripts/lib/command-runner.mjs',
  'scripts/lib/dashboard-contract.mjs',
  'scripts/lib/quality-score.mjs'
];

const refactoredScripts = [
  'scripts/quality-check.mjs',
  'scripts/verified-improve.mjs',
  'scripts/propose-improvement.mjs',
  'scripts/revenue-learning-loop.mjs',
  'scripts/meta-learning-loop.mjs',
  'scripts/time-value-loop.mjs',
  'scripts/compute-budget-loop.mjs'
];

const forbiddenDuplicatedHelpers = [
  'function readJson',
  'function writeJson',
  'function round2',
  'function clamp(',
  'function prependHistory',
  'function uniqueCount',
  'function includesAll'
];

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8');
}

for (const lib of requiredLibs) {
  assert.ok(fs.existsSync(path.join(root, lib)), `Missing shared library: ${lib}`);
}

for (const script of refactoredScripts) {
  const content = read(script);
  assert.ok(content.includes("./lib/") || script === 'scripts/quality-check.mjs', `${script} should import shared utilities`);

  for (const helper of forbiddenDuplicatedHelpers) {
    assert.ok(!content.includes(helper), `${script} redefines shared helper: ${helper}`);
  }
}

const computeBudget = read('scripts/compute-budget-loop.mjs');
assert.ok(computeBudget.includes('normalizeBudget'), 'compute budget loop should normalize old and new budget shapes');
assert.ok(computeBudget.includes('calculateLedgerEntry'), 'compute budget loop should keep ledger calculation isolated');

const packageJson = JSON.parse(read('package.json'));
assert.ok(packageJson.scripts['architecture:check'], 'package.json should expose architecture:check');
assert.ok(packageJson.scripts.test.includes('architecture:check'), 'test script should include architecture check');

const libFiles = fs.readdirSync(path.join(scriptDir, 'lib')).filter(file => file.endsWith('.mjs'));
assert.ok(libFiles.length >= 7, 'expected at least seven shared library modules');

console.log(JSON.stringify({
  ok: true,
  requiredLibs: requiredLibs.length,
  refactoredScripts: refactoredScripts.length,
  libFiles: libFiles.length
}, null, 2));
