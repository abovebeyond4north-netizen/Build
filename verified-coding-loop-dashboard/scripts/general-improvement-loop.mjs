import { projectPath, readJson, writeJson } from './lib/json-store.mjs';
import { asNumber, round2 } from './lib/number-tools.mjs';
import { prependHistory, rankByScore } from './lib/history-tools.mjs';

const root = process.cwd();

const paths = {
  state: projectPath(root, 'src/data/generalImprovementState.json'),
  report: projectPath(root, 'learning/general-improvement-report.json'),
  verified: projectPath(root, 'src/data/verifiedLearningState.json'),
  meta: projectPath(root, 'src/data/metaLearningState.json'),
  compute: projectPath(root, 'src/data/computeBudgetState.json'),
  processFocus: projectPath(root, 'learning/process-focus-report.json'),
  efficiency: projectPath(root, 'learning/efficiency-optimizer-report.json'),
  proposal: projectPath(root, 'proposals/latest-verified-proposal.json')
};

const defaultState = {
  schemaVersion: 1,
  runs: 0,
  bestGeneralScore: 0,
  decisionHistory: [],
  weights: {
    provenQuality: 0.22,
    learningMomentum: 0.18,
    focusedTarget: 0.2,
    efficientNextStep: 0.2,
    reserveStrength: 0.1,
    proposalReadiness: 0.1
  }
};

function reserveStrength(compute) {
  const balance = asNumber(compute.creditBalance ?? compute.balance, 1000);
  const start = Math.max(asNumber(compute.startingCredits ?? compute.startingFloat, 1000), 1);
  return round2(Math.max(0, Math.min(1, balance / start)));
}

function scoreInputs({ verified, meta, processFocus, efficiency, compute, proposal }, weights) {
  const provenQuality = asNumber(verified.bestQualityScore, 0) > 0 ? 1 : 0.5;
  const learningMomentum = Math.min(1, (asNumber(verified.verifiedRuns, 0) + asNumber(meta.metaRuns, 0)) / 20);
  const focusedTarget = asNumber(processFocus.overallExperienceScore, 0);
  const efficientNextStep = efficiency.selected ? asNumber(efficiency.selected.score, 0) : 0;
  const reserve = reserveStrength(compute);
  const proposalReadiness = proposal.selected && proposal.safetyPolicy?.humanReviewRequired === true ? 1 : 0.4;

  const score = round2(
    provenQuality * weights.provenQuality +
    learningMomentum * weights.learningMomentum +
    focusedTarget * weights.focusedTarget +
    efficientNextStep * weights.efficientNextStep +
    reserve * weights.reserveStrength +
    proposalReadiness * weights.proposalReadiness
  );

  return {
    score,
    dimensions: {
      provenQuality: round2(provenQuality),
      learningMomentum: round2(learningMomentum),
      focusedTarget: round2(focusedTarget),
      efficientNextStep: round2(efficientNextStep),
      reserveStrength: round2(reserve),
      proposalReadiness: round2(proposalReadiness)
    }
  };
}

function buildGeneralMoves({ processFocus, efficiency, proposal }) {
  const moves = [
    {
      id: 'tighten-tests-first',
      title: 'Tighten tests before behavior changes',
      reason: 'Stronger tests make every future improvement safer.',
      impact: 0.8,
      effort: 0.35,
      risk: 0.1,
      appliesWhen: true
    },
    {
      id: 'implement-efficiency-target',
      title: 'Implement the selected efficiency target',
      reason: efficiency.selected?.recommendation || 'Efficiency report has no selected target yet.',
      impact: efficiency.selected ? asNumber(efficiency.selected.impact, 0.5) : 0.2,
      effort: efficiency.selected ? Math.min(1, asNumber(efficiency.selected.effort, 3) / 5) : 0.8,
      risk: efficiency.selected ? asNumber(efficiency.selected.risk, 0.25) : 0.4,
      appliesWhen: Boolean(efficiency.selected)
    },
    {
      id: 'improve-weakest-process-factor',
      title: 'Improve the weakest process factor',
      reason: processFocus.recommendations?.[0]?.recommendation || 'Process focus should run before this move.',
      impact: 0.7,
      effort: 0.4,
      risk: 0.15,
      appliesWhen: Array.isArray(processFocus.recommendations) && processFocus.recommendations.length > 0
    },
    {
      id: 'prepare-proposal-for-review',
      title: 'Prepare proposal for review',
      reason: proposal.selected?.reason || 'A reviewable proposal keeps progress concrete and safe.',
      impact: proposal.selected?.expectedBenefit || proposal.selected?.score || 0.45,
      effort: 0.25,
      risk: 0.1,
      appliesWhen: Boolean(proposal.selected)
    }
  ];

  return rankByScore(moves
    .filter(move => move.appliesWhen)
    .map(move => ({
      ...move,
      score: round2(move.impact * 0.45 + (1 - move.effort) * 0.3 + (1 - move.risk) * 0.25)
    })));
}

const state = readJson(paths.state, defaultState);
const weights = { ...defaultState.weights, ...(state.weights || {}) };
const verified = readJson(paths.verified, {});
const meta = readJson(paths.meta, {});
const compute = readJson(paths.compute, {});
const processFocus = readJson(paths.processFocus, {});
const efficiency = readJson(paths.efficiency, {});
const proposal = readJson(paths.proposal, {});

const scoring = scoreInputs({ verified, meta, processFocus, efficiency, compute, proposal }, weights);
const moves = buildGeneralMoves({ processFocus, efficiency, proposal });
const selectedMove = moves[0] || null;
const now = new Date().toISOString();

const record = {
  time: now,
  generalScore: scoring.score,
  selectedMoveId: selectedMove?.id || null,
  decision: selectedMove ? 'general_improvement_move_selected' : 'needs_more_signal_reports'
};

const nextState = {
  ...state,
  schemaVersion: 1,
  runs: asNumber(state.runs, 0) + 1,
  bestGeneralScore: Math.max(asNumber(state.bestGeneralScore, 0), scoring.score),
  lastRunAt: now,
  lastDecision: record.decision,
  decisionHistory: prependHistory(record, state.decisionHistory, 50)
};

const report = {
  schemaVersion: 1,
  generatedAt: now,
  purpose: 'Aggregate the system signals into one balanced general improvement decision.',
  weights,
  generalScore: scoring.score,
  dimensions: scoring.dimensions,
  selectedMove,
  rankedMoves: moves,
  stateAfter: {
    runs: nextState.runs,
    bestGeneralScore: nextState.bestGeneralScore,
    lastDecision: nextState.lastDecision
  },
  nextHumanStep: selectedMove
    ? `Next general improvement: ${selectedMove.title}. ${selectedMove.reason}`
    : 'Run process:focus and efficiency:optimize so the general optimizer has stronger inputs.'
};

writeJson(paths.state, nextState);
writeJson(paths.report, report);

console.log(JSON.stringify({
  ok: true,
  generalScore: scoring.score,
  selectedMove: selectedMove?.id || null,
  runs: nextState.runs,
  nextHumanStep: report.nextHumanStep
}, null, 2));
