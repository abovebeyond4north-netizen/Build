import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const proposalDir = path.join(root, 'proposals');
const proposalPath = path.join(proposalDir, 'latest-verified-proposal.json');
const statePath = path.join(root, 'src/data/verifiedLearningState.json');

function read(file) {
  return fs.readFileSync(path.join(root, file), 'utf8');
}

function readJson(file, fallback) {
  if (!fs.existsSync(file)) return fallback;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function writeJson(file, data) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`);
}

function includesAll(text, markers) {
  return markers.every(marker => text.includes(marker));
}

const app = read('src/App.jsx');
const state = readJson(statePath, {
  verifiedRuns: 0,
  bestQualityScore: 0,
  learningHistory: []
});

const existingProposal = readJson(proposalPath, null);

const candidateImprovements = [
  {
    id: 'add-calibration-history-chart',
    title: 'Add calibration history visualization',
    target: 'src/App.jsx',
    reason: 'The dashboard tracks prediction error, but does not yet visualize calibration over time.',
    expectedBenefit: 0.12,
    risk: 'low',
    requiredEvidence: ['Prediction Engine', 'Uncertainty + Calibration', 'Append-Only Event Log'],
    acceptanceTests: [
      'quality-check.mjs passes',
      'vite build passes',
      'verified improvement gate passes',
      'tests pass again after proposal state update'
    ],
    forbiddenActions: ['auto merge', 'network automation', 'unreviewed code execution', 'secret access']
  },
  {
    id: 'split-dashboard-into-components',
    title: 'Split dashboard panels into reusable components',
    target: 'src/components',
    reason: 'The main App.jsx is large. Component separation would improve maintainability without changing behavior.',
    expectedBenefit: 0.1,
    risk: 'medium',
    requiredEvidence: ['System State', 'Memory', 'Belief Tracker', 'Oracle Gate'],
    acceptanceTests: [
      'all section markers remain present',
      'all action buttons remain present',
      'build output succeeds',
      'no forbidden runtime patterns appear'
    ],
    forbiddenActions: ['behavior removal', 'unsafe runtime APIs', 'auto deployment']
  },
  {
    id: 'add-belief-contradiction-tracking',
    title: 'Add contradiction tracking to beliefs',
    target: 'belief model',
    reason: 'Truthful belief management should track evidence against a claim, not only evidence for it.',
    expectedBenefit: 0.16,
    risk: 'low',
    requiredEvidence: ['Belief Tracker', 'confidence', 'Evidence'],
    acceptanceTests: [
      'belief tracker still renders',
      'quality score does not decrease',
      'safety claims remain visible'
    ],
    forbiddenActions: ['claiming consciousness', 'self-modifying without review']
  }
];

const eligible = candidateImprovements.filter(candidate => includesAll(app, candidate.requiredEvidence));
const selected = eligible.sort((a, b) => b.expectedBenefit - a.expectedBenefit)[0];

if (!selected) {
  throw new Error('No eligible improvement proposal found. Required evidence markers were missing.');
}

const proposal = {
  schemaVersion: 1,
  generatedAt: new Date().toISOString(),
  generator: 'deterministic-safe-proposal-engine',
  selected,
  previousProposalId: existingProposal?.selected?.id || null,
  currentVerifiedRuns: state.verifiedRuns || 0,
  currentBestQualityScore: state.bestQualityScore || 0,
  safetyPolicy: {
    autoMerge: false,
    realCodeExecution: false,
    networkAutomation: false,
    humanReviewRequired: true,
    onlyProposeAfterEvidenceMarkersPresent: true
  },
  decision: 'proposal_created_not_applied',
  nextHumanStep: 'Review the proposal. If approved, implement it in a branch and let GitHub Actions prove it with tests and build.'
};

writeJson(proposalPath, proposal);

console.log(JSON.stringify({
  ok: true,
  proposal: proposal.selected.id,
  title: proposal.selected.title,
  expectedBenefit: proposal.selected.expectedBenefit,
  risk: proposal.selected.risk
}, null, 2));
