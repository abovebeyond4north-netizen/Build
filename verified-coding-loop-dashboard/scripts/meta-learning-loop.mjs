import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const metaStatePath = path.join(root, 'src/data/metaLearningState.json');
const verifiedStatePath = path.join(root, 'src/data/verifiedLearningState.json');
const valueStatePath = path.join(root, 'src/data/revenueLearningState.json');
const proposalPath = path.join(root, 'proposals/latest-verified-proposal.json');
const valueReportPath = path.join(root, 'revenue/revenue-learning-report.json');
const metaReportPath = path.join(root, 'learning/meta-learning-report.json');

function readJson(file, fallback) {
  if (!fs.existsSync(file)) return fallback;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function writeJson(file, data) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`);
}

function uniqueCount(items) {
  return new Set(items.filter(Boolean)).size;
}

function clamp01(value) {
  return Math.max(0, Math.min(1, value));
}

const meta = readJson(metaStatePath, {
  schemaVersion: 1,
  metaRuns: 0,
  bestLearningScore: 0,
  lastDecision: 'initialized',
  strategyHistory: [],
  activePrinciples: [
    'prefer verified evidence over assumptions',
    'prefer small reversible changes',
    'increase proposal diversity over time',
    'track rejected ideas instead of forgetting them',
    'require human review before external action'
  ]
});

const verified = readJson(verifiedStatePath, { verifiedRuns: 0, learningHistory: [] });
const value = readJson(valueStatePath, { loopRuns: 0, experimentHistory: [] });
const proposal = readJson(proposalPath, {});
const valueReport = readJson(valueReportPath, {});

const verifiedHistory = verified.learningHistory || [];
const valueHistory = value.experimentHistory || [];
const strategyHistory = meta.strategyHistory || [];

const proposalIds = [
  proposal?.selected?.id,
  ...verifiedHistory.map(item => item.id),
  ...valueHistory.map(item => item.id)
].filter(Boolean);

const diversity = proposalIds.length ? uniqueCount(proposalIds) / proposalIds.length : 0.5;
const evidenceDepth = clamp01((verifiedHistory.length + valueHistory.length) / 20);
const reversibility = 1;
const safetyConsistency = valueReport?.limits?.humanReviewRequired === true ? 1 : 0.7;
const cadence = clamp01((Number(verified.verifiedRuns || 0) + Number(value.loopRuns || 0)) / 20);

const learningScore = Number((
  diversity * 0.25 +
  evidenceDepth * 0.25 +
  reversibility * 0.2 +
  safetyConsistency * 0.2 +
  cadence * 0.1
).toFixed(3));

const strategies = [
  {
    id: 'increase-diversity',
    trigger: diversity < 0.55,
    recommendation: 'Rotate proposal categories so the loop does not keep selecting the same improvement type.',
    expectedEffect: 'broader search over possible value and quality improvements'
  },
  {
    id: 'increase-evidence-depth',
    trigger: evidenceDepth < 0.5,
    recommendation: 'Accumulate more verified run records before accepting stronger claims.',
    expectedEffect: 'better calibration and less overfitting to early runs'
  },
  {
    id: 'preserve-reversibility',
    trigger: true,
    recommendation: 'Keep all learning updates in small JSON and Markdown artifacts until tests prove app-level changes.',
    expectedEffect: 'safe rollback and easy human review'
  },
  {
    id: 'add-human-outcome-feedback',
    trigger: true,
    recommendation: 'Add a manual feedback field so a human can mark proposals as useful, not useful, or implemented.',
    expectedEffect: 'the loop can learn from real review outcomes instead of only static checks'
  }
];

const selectedStrategies = strategies.filter(strategy => strategy.trigger);
const now = new Date().toISOString();

const runRecord = {
  time: now,
  learningScore,
  diversity: Number(diversity.toFixed(3)),
  evidenceDepth: Number(evidenceDepth.toFixed(3)),
  safetyConsistency,
  selectedStrategyIds: selectedStrategies.map(strategy => strategy.id),
  decision: learningScore >= Number(meta.bestLearningScore || 0) ? 'learning_state_improved_or_equal' : 'learning_state_observed_lower_score'
};

const nextMeta = {
  ...meta,
  metaRuns: Number(meta.metaRuns || 0) + 1,
  bestLearningScore: Math.max(Number(meta.bestLearningScore || 0), learningScore),
  lastRunAt: now,
  lastDecision: runRecord.decision,
  strategyHistory: [runRecord, ...strategyHistory].slice(0, 50)
};

const report = {
  schemaVersion: 1,
  generatedAt: now,
  purpose: 'Measure whether the learning loop is improving its own learning process.',
  learningScore,
  dimensions: {
    diversity: runRecord.diversity,
    evidenceDepth: runRecord.evidenceDepth,
    reversibility,
    safetyConsistency,
    cadence
  },
  selectedStrategies,
  hardBoundaries: [
    'proposals are not automatically applied to core logic',
    'human review remains required',
    'external actions remain disabled',
    'income is not guaranteed or assumed'
  ],
  nextHumanStep: 'Review selected strategies and mark whether the generated proposal was useful.'
};

writeJson(metaStatePath, nextMeta);
writeJson(metaReportPath, report);

console.log(JSON.stringify({
  ok: true,
  learningScore,
  metaRuns: nextMeta.metaRuns,
  strategies: selectedStrategies.map(strategy => strategy.id)
}, null, 2));
