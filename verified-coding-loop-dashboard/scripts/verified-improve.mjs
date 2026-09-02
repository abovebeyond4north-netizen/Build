import { projectPath, readJson, writeJson } from './lib/json-store.mjs';
import { runCommand } from './lib/command-runner.mjs';
import { computeQualityScore } from './lib/quality-score.mjs';
import { asNumber } from './lib/number-tools.mjs';
import { prependHistory } from './lib/history-tools.mjs';

const root = process.cwd();
const statePath = projectPath(root, 'src/data/verifiedLearningState.json');
const reportPath = projectPath(root, 'verified-improvement-report.json');

const previous = readJson(statePath, {
  schemaVersion: 1,
  verifiedRuns: 0,
  bestQualityScore: 0,
  lastDecision: 'initialized',
  learningHistory: []
});

const beforeScore = asNumber(previous.bestQualityScore, 0);
const afterScore = computeQualityScore(root);
const test = runCommand('npm', ['run', 'test'], { cwd: root });
const build = runCommand('npm', ['run', 'build'], { cwd: root });
const approved = test.ok && build.ok && afterScore >= beforeScore;
const decision = approved ? 'approved' : 'rejected';

const record = {
  time: new Date().toISOString(),
  decision,
  beforeScore,
  afterScore,
  testsPassed: test.ok,
  buildPassed: build.ok,
  rule: 'Only update learning state when tests pass, build passes, and quality score is not worse.'
};

const next = approved
  ? {
      ...previous,
      verifiedRuns: asNumber(previous.verifiedRuns, 0) + 1,
      bestQualityScore: Math.max(beforeScore, afterScore),
      lastDecision: decision,
      lastVerifiedAt: record.time,
      learningHistory: prependHistory(record, previous.learningHistory, 25)
    }
  : {
      ...previous,
      lastDecision: decision,
      lastRejectedAt: record.time,
      learningHistory: prependHistory(record, previous.learningHistory, 25)
    };

writeJson(reportPath, {
  ...record,
  testCommand: test.command,
  buildCommand: build.command,
  testStatus: test.status,
  buildStatus: build.status
});

if (!approved) {
  console.error(JSON.stringify({ ok: false, record }, null, 2));
  process.exit(1);
}

writeJson(statePath, next);
console.log(JSON.stringify({ ok: true, record }, null, 2));
