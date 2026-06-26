import fs from 'node:fs';
import path from 'node:path';
import { REQUIRED_SAFETY_CLAIMS, REQUIRED_SECTIONS } from './dashboard-contract.mjs';

export const DASHBOARD_MARKERS = [
  ...REQUIRED_SECTIONS,
  ...REQUIRED_SAFETY_CLAIMS.filter(claim => claim !== 'external side effects')
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
