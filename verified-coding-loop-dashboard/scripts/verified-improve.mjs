import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const root = process.cwd();
const statePath = path.join(root, 'src/data/verifiedLearningState.json');
const reportPath = path.join(root, 'verified-improvement-report.json');

function readJson(file, fallback) {
  if (!fs.existsSync(file)) return fallback;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function writeJson(file, data) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`);
}

function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: root,
    shell: process.platform === 'win32',
    encoding: 'utf8'
  });

  return {
    command: [command, ...args].join(' '),
    ok: result.status === 0,
    status: result.status,
    stdout: result.stdout,
    stderr: result.stderr
  };
}

function computeQualityScore() {
  const app = fs.readFileSync(path.join(root, 'src/App.jsx'), 'utf8');
  const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));

  const markers = [
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
    'Append-Only Event Log',
    'does not claim consciousness',
    'No real code execution',
    'Simulated data only'
  ];

  const markerScore = markers.filter(marker => app.includes(marker)).length * 5;
  const scriptScore = ['test', 'build', 'verify:self-improve', 'verify:full']
    .filter(name => Boolean(pkg.scripts?.[name]))
    .length * 10;

  return markerScore + scriptScore;
}

const previous = readJson(statePath, {
  schemaVersion: 1,
  verifiedRuns: 0,
  bestQualityScore: 0,
  lastDecision: 'initialized',
  learningHistory: []
});

const beforeScore = Number(previous.bestQualityScore || 0);
const qualityScore = computeQualityScore();

const test = run('npm', ['run', 'test']);
const build = run('npm', ['run', 'build']);
const provenBetterOrEqual = qualityScore >= beforeScore;
const approved = test.ok && build.ok && provenBetterOrEqual;

const decision = approved ? 'approved' : 'rejected';
const record = {
  time: new Date().toISOString(),
  decision,
  beforeScore,
  afterScore: qualityScore,
  testsPassed: test.ok,
  buildPassed: build.ok,
  rule: 'Only update learning state when tests pass, build passes, and quality score is not worse.'
};

const next = approved
  ? {
      ...previous,
      verifiedRuns: Number(previous.verifiedRuns || 0) + 1,
      bestQualityScore: Math.max(beforeScore, qualityScore),
      lastDecision: decision,
      lastVerifiedAt: record.time,
      learningHistory: [record, ...(previous.learningHistory || [])].slice(0, 25)
    }
  : {
      ...previous,
      lastDecision: decision,
      lastRejectedAt: record.time,
      learningHistory: [record, ...(previous.learningHistory || [])].slice(0, 25)
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
