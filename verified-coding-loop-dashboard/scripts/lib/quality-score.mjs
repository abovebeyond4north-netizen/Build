import fs from 'node:fs';
import path from 'node:path';

export const DASHBOARD_MARKERS = [
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

export const REQUIRED_SCRIPTS = ['test', 'build', 'verify:self-improve', 'verify:full'];

export function readText(root, relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8');
}

export function computeQualityScore(root) {
  const app = readText(root, 'src/App.jsx');
  const pkg = JSON.parse(readText(root, 'package.json'));
  const markerScore = DASHBOARD_MARKERS.filter(marker => app.includes(marker)).length * 5;
  const scriptScore = REQUIRED_SCRIPTS.filter(name => Boolean(pkg.scripts?.[name])).length * 10;
  return markerScore + scriptScore;
}
