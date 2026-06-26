import { projectPath, readJson, writeJson } from './lib/json-store.mjs';
import { asNumber } from './lib/number-tools.mjs';
import { prependHistory, rankByScore } from './lib/history-tools.mjs';

const root = process.cwd();
const statePath = projectPath(root, 'src/data/revenueLearningState.json');
const reportPath = projectPath(root, 'revenue/revenue-learning-report.json');

const defaultState = {
  schemaVersion: 1,
  loopRuns: 0,
  bestScore: 0,
  totalRevenueRecorded: 0,
  experimentHistory: [],
  activeConstraints: [
    'zero paid tools',
    'ethical proposals only',
    'truthful claims only',
    'public information only',
    'human approval before outreach or money movement',
    'low-risk lawful work only'
  ]
};

const experiments = [
  {
    id: 'portfolio-proof-page',
    title: 'Improve the project as a portfolio proof asset',
    cost: 0,
    revenuePotential: 0.64,
    learningValue: 0.82,
    requiresHumanApproval: true,
    output: 'Create a clearer project pitch and demo checklist that a human can share with potential clients.',
    safeNextStep: 'Draft a one-page offer explaining the dashboard and invite manual review.'
  },
  {
    id: 'github-sponsors-readiness',
    title: 'Prepare GitHub Sponsors readiness checklist',
    cost: 0,
    revenuePotential: 0.52,
    learningValue: 0.65,
    requiresHumanApproval: true,
    output: 'List what the repo needs before enabling sponsorship or donations.',
    safeNextStep: 'Human reviews the checklist and enables sponsorship manually if desired.'
  },
  {
    id: 'service-offer-draft',
    title: 'Generate a reviewable service offer draft',
    cost: 0,
    revenuePotential: 0.7,
    learningValue: 0.74,
    requiresHumanApproval: true,
    output: 'Draft a manual outreach message for ethical consulting around verified automation dashboards.',
    safeNextStep: 'Human chooses recipients and sends manually only where appropriate.'
  },
  {
    id: 'open-source-issue-checklist',
    title: 'Manual opportunity research checklist',
    cost: 0,
    revenuePotential: 0.58,
    learningValue: 0.78,
    requiresHumanApproval: true,
    output: 'Create a checklist for manually finding bounties, grants, and open-source issues without automated scraping.',
    safeNextStep: 'Human searches approved platforms and pastes candidate opportunities into the repo.'
  },
  {
    id: 'template-product-roadmap',
    title: 'Turn the dashboard into a reusable template product roadmap',
    cost: 0,
    revenuePotential: 0.62,
    learningValue: 0.8,
    requiresHumanApproval: true,
    output: 'Create a product roadmap for a free starter template and optional paid customization work.',
    safeNextStep: 'Human reviews pricing, terms, and legal obligations before offering services.'
  }
];

function scoreExperiment(experiment, state) {
  const history = state.experimentHistory || [];
  const previousUses = history.filter(item => item.id === experiment.id).length;
  const novelty = Math.max(0, 1 - previousUses * 0.2);
  const feasibility = experiment.cost === 0 ? 1 : 0;
  const safety = experiment.requiresHumanApproval ? 1 : 0.4;

  return Number((
    novelty * 0.2 +
    feasibility * 0.25 +
    safety * 0.2 +
    experiment.revenuePotential * 0.2 +
    experiment.learningValue * 0.15
  ).toFixed(3));
}

const state = readJson(statePath, defaultState);
const ranked = rankByScore(experiments.map(experiment => ({
  ...experiment,
  score: scoreExperiment(experiment, state)
})));

const selected = ranked[0];
const now = new Date().toISOString();
const runRecord = {
  time: now,
  id: selected.id,
  title: selected.title,
  score: selected.score,
  cost: selected.cost,
  revenuePotential: selected.revenuePotential,
  learningValue: selected.learningValue,
  decision: 'proposed_not_executed',
  safety: 'human approval required before outreach, payments, or external actions'
};

const nextState = {
  ...state,
  loopRuns: asNumber(state.loopRuns, 0) + 1,
  bestScore: Math.max(asNumber(state.bestScore, 0), selected.score),
  lastRunAt: now,
  lastSelectedExperiment: selected.id,
  experimentHistory: prependHistory(runRecord, state.experimentHistory, 50)
};

const report = {
  schemaVersion: 2,
  generatedAt: now,
  purpose: 'Zero-cost learning loop for ethical value experiment proposals.',
  limits: {
    doesNotGuaranteeRevenue: true,
    noAutonomousPayments: true,
    noSpam: true,
    noExternalOutreach: true,
    noPaidTools: true,
    humanReviewRequired: true
  },
  selectedExperiment: selected,
  rankedExperiments: ranked,
  learningUpdate: runRecord,
  nextHumanStep: selected.safeNextStep
};

writeJson(statePath, nextState);
writeJson(reportPath, report);

console.log(JSON.stringify({
  ok: true,
  selected: selected.id,
  score: selected.score,
  loopRuns: nextState.loopRuns,
  nextHumanStep: selected.safeNextStep
}, null, 2));
