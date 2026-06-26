import { projectPath, readJson, writeJson } from './lib/json-store.mjs';
import { asNumber, clamp, round2 } from './lib/number-tools.mjs';
import { prependHistory, uniqueCount } from './lib/history-tools.mjs';

const root = process.cwd();

const paths = {
  meta: projectPath(root, 'src/data/metaLearningState.json'),
  verified: projectPath(root, 'src/data/verifiedLearningState.json'),
  value: projectPath(root, 'src/data/revenueLearningState.json'),
  proposal: projectPath(root, 'proposals/latest-verified-proposal.json'),
  valueReport: projectPath(root, 'revenue/revenue-learning-report.json'),
  report: projectPath(root, 'learning/meta-learning-report.json')
};

const defaultMeta = {
  schemaVersion: 1,
  metaRuns: 0,
  bestLearningScore: 0,
  lastDecision: 'initialized',
  strategyHistory: [],
  activePrinciples: [
    'prefer verified evidence over assumptions',
    'prefer small reversible changes',
    'increase proposal variety over time',
    'track rejected ideas for later review',
    'require human review before outside-world action'
  ]
};

const strategies = [
  {
    id: 'increase-diversity',
    recommendation: 'Rotate proposal categories so the loop does not keep selecting the same improvement type.',
    expectedEffect: 'broader search over possible value and quality improvements'
  },
  {
    id: 'increase-evidence-depth',
    recommendation: 'Accumulate more verified run records before accepting stronger claims.',
    expectedEffect: 'better calibration and less overfitting to early runs'
  },
  {
    id: 'preserve-reversibility',
    recommendation: 'Keep all learning updates in small JSON and Markdown artifacts until tests prove app-level changes.',
    expectedEffect: 'safe rollback and easy human review'
  },
  {
    id: 'add-human-outcome-feedback',
    recommendation: 'Add a manual feedback field so a human can mark proposals as useful, not useful, or implemented.',
    expectedEffect: 'the loop can learn from real review outcomes instead of only static checks'
  }
];

function computeDimensions({ verified, value, proposal, valueReport }) {
  const verifiedHistory = verified.learningHistory || [];
  const valueHistory = value.experimentHistory || [];
  const proposalIds = [
    proposal?.selected?.id,
    ...verifiedHistory.map(item => item.id),
    ...valueHistory.map(item => item.id)
  ].filter(Boolean);

  const diversity = proposalIds.length ? uniqueCount(proposalIds) / proposalIds.length : 0.5;
  const evidenceDepth = clamp((verifiedHistory.length + valueHistory.length) / 20, 0, 1);
  const reversibility = 1;
  const safetyConsistency = valueReport?.limits?.humanReviewRequired === true ? 1 : 0.7;
  const cadence = clamp((asNumber(verified.verifiedRuns, 0) + asNumber(value.loopRuns, 0)) / 20, 0, 1);

  return {
    diversity: round2(diversity),
    evidenceDepth: round2(evidenceDepth),
    reversibility,
    safetyConsistency,
    cadence: round2(cadence)
  };
}

function scoreLearning(dimensions) {
  return Number((
    dimensions.diversity * 0.25 +
    dimensions.evidenceDepth * 0.25 +
    dimensions.reversibility * 0.2 +
    dimensions.safetyConsistency * 0.2 +
    dimensions.cadence * 0.1
  ).toFixed(3));
}

function selectStrategies(dimensions) {
  return strategies.filter(strategy =>
    strategy.id === 'preserve-reversibility' ||
    strategy.id === 'add-human-outcome-feedback' ||
    (strategy.id === 'increase-diversity' && dimensions.diversity < 0.55) ||
    (strategy.id === 'increase-evidence-depth' && dimensions.evidenceDepth < 0.5)
  );
}

const meta = readJson(paths.meta, defaultMeta);
const verified = readJson(paths.verified, { verifiedRuns: 0, learningHistory: [] });
const value = readJson(paths.value, { loopRuns: 0, experimentHistory: [] });
const proposal = readJson(paths.proposal, {});
const valueReport = readJson(paths.valueReport, {});

const dimensions = computeDimensions({ verified, value, proposal, valueReport });
const learningScore = scoreLearning(dimensions);
const selectedStrategies = selectStrategies(dimensions);
const now = new Date().toISOString();
const decision = learningScore >= asNumber(meta.bestLearningScore, 0)
  ? 'learning_state_improved_or_equal'
  : 'learning_state_observed_lower_score';

const runRecord = {
  time: now,
  learningScore,
  ...dimensions,
  selectedStrategyIds: selectedStrategies.map(strategy => strategy.id),
  decision
};

const nextMeta = {
  ...meta,
  metaRuns: asNumber(meta.metaRuns, 0) + 1,
  bestLearningScore: Math.max(asNumber(meta.bestLearningScore, 0), learningScore),
  lastRunAt: now,
  lastDecision: decision,
  strategyHistory: prependHistory(runRecord, meta.strategyHistory, 50)
};

const report = {
  schemaVersion: 2,
  generatedAt: now,
  purpose: 'Measure whether the learning loop is improving its own learning process.',
  learningScore,
  dimensions,
  selectedStrategies,
  hardBoundaries: [
    'proposals are not automatically applied to core logic',
    'human review remains required',
    'external actions remain disabled',
    'income is not guaranteed or assumed'
  ],
  nextHumanStep: 'Review selected strategies and mark whether the generated proposal was useful.'
};

writeJson(paths.meta, nextMeta);
writeJson(paths.report, report);

console.log(JSON.stringify({
  ok: true,
  learningScore,
  metaRuns: nextMeta.metaRuns,
  strategies: selectedStrategies.map(strategy => strategy.id)
}, null, 2));
