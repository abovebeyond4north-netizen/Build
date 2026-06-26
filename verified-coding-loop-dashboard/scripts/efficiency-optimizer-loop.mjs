import { projectPath, readJson, writeJson } from './lib/json-store.mjs';
import { asNumber, clamp, round2 } from './lib/number-tools.mjs';
import { prependHistory, rankByScore } from './lib/history-tools.mjs';

const root = process.cwd();

const paths = {
  state: projectPath(root, 'src/data/efficiencyOptimizerState.json'),
  report: projectPath(root, 'learning/efficiency-optimizer-report.json'),
  processReport: projectPath(root, 'learning/process-focus-report.json'),
  computeState: projectPath(root, 'src/data/computeBudgetState.json'),
  metaState: projectPath(root, 'src/data/metaLearningState.json'),
  verifiedState: projectPath(root, 'src/data/verifiedLearningState.json')
};

const defaultState = {
  schemaVersion: 1,
  runs: 0,
  bestEfficiencyScore: 0,
  selectedHistory: [],
  weights: {
    impact: 0.32,
    lowEffort: 0.18,
    verificationStrength: 0.2,
    lowRisk: 0.15,
    creditPreservation: 0.15
  }
};

function effortForFactor(factor) {
  const table = {
    clarity: 1,
    feedback: 2,
    verification: 2,
    reversibility: 1,
    costControl: 2,
    skillGrowth: 3,
    usefulness: 3
  };
  return table[factor] || 2;
}

function riskForFactor(factor) {
  const table = {
    clarity: 0.1,
    feedback: 0.15,
    verification: 0.2,
    reversibility: 0.1,
    costControl: 0.2,
    skillGrowth: 0.25,
    usefulness: 0.3
  };
  return table[factor] ?? 0.2;
}

function verificationStrength(item) {
  const verificationFactor = asNumber(item.factors?.verification, 0);
  const feedbackFactor = asNumber(item.factors?.feedback, 0);
  return round2((verificationFactor + feedbackFactor) / 2);
}

function creditPreservationScore(computeState) {
  const balance = asNumber(computeState.creditBalance ?? computeState.balance, 1000);
  const threshold = asNumber(computeState.lowCreditThreshold ?? computeState.pauseThreshold, 100);
  const starting = asNumber(computeState.startingCredits ?? computeState.startingFloat, 1000);
  if (balance <= threshold) return 1;
  return round2(1 - clamp(balance / Math.max(starting, 1), 0, 1) * 0.25);
}

function buildCandidates(processReport, computeState, weights) {
  const weakItems = processReport.weakestSubprocesses || [];
  const recommendations = processReport.recommendations || [];
  const preservation = creditPreservationScore(computeState);

  return weakItems.map(item => {
    const recommendation = recommendations.find(candidate => candidate.subprocessId === item.id) || {};
    const impact = round2(1 - asNumber(item.experienceScore, 0));
    const effort = effortForFactor(recommendation.weakestFactor);
    const lowEffort = round2(1 / effort);
    const risk = riskForFactor(recommendation.weakestFactor);
    const lowRisk = round2(1 - risk);
    const verification = verificationStrength(item);
    const score = round2(
      impact * weights.impact +
      lowEffort * weights.lowEffort +
      verification * weights.verificationStrength +
      lowRisk * weights.lowRisk +
      preservation * weights.creditPreservation
    );

    return {
      id: `${item.processId}/${item.id}`,
      processId: item.processId,
      processTitle: item.processTitle,
      subprocessId: item.id,
      title: item.title,
      weakestFactor: recommendation.weakestFactor || 'unknown',
      experienceScore: item.experienceScore,
      impact,
      effort,
      lowEffort,
      risk,
      lowRisk,
      verificationStrength: verification,
      creditPreservation: preservation,
      score,
      recommendation: recommendation.recommendation || `Improve ${item.title} with a small measurable change.`
    };
  });
}

const state = readJson(paths.state, defaultState);
const processReport = readJson(paths.processReport, { weakestSubprocesses: [], recommendations: [] });
const computeState = readJson(paths.computeState, {});
const metaState = readJson(paths.metaState, { metaRuns: 0 });
const verifiedState = readJson(paths.verifiedState, { verifiedRuns: 0 });
const weights = { ...defaultState.weights, ...(state.weights || {}) };
const candidates = rankByScore(buildCandidates(processReport, computeState, weights));
const selected = candidates[0] || null;
const now = new Date().toISOString();
const overallScore = selected ? selected.score : 0;

const record = {
  time: now,
  selectedId: selected?.id || null,
  selectedScore: overallScore,
  metaRuns: asNumber(metaState.metaRuns, 0),
  verifiedRuns: asNumber(verifiedState.verifiedRuns, 0),
  decision: selected ? 'efficiency_focus_selected' : 'no_efficiency_candidate_available'
};

const nextState = {
  ...state,
  schemaVersion: 1,
  runs: asNumber(state.runs, 0) + 1,
  bestEfficiencyScore: Math.max(asNumber(state.bestEfficiencyScore, 0), overallScore),
  lastRunAt: now,
  lastDecision: record.decision,
  selectedHistory: prependHistory(record, state.selectedHistory, 50)
};

const report = {
  schemaVersion: 1,
  generatedAt: now,
  purpose: 'Optimize effective efficiency by ranking weak subprocesses by impact, effort, verification strength, risk, and credit preservation.',
  weights,
  selected,
  rankedCandidates: candidates,
  stateAfter: {
    runs: nextState.runs,
    bestEfficiencyScore: nextState.bestEfficiencyScore,
    lastDecision: nextState.lastDecision
  },
  nextHumanStep: selected
    ? `Focus next on ${selected.id}: ${selected.recommendation}`
    : 'Run process:focus first so the optimizer has weak subprocesses to rank.'
};

writeJson(paths.state, nextState);
writeJson(paths.report, report);

console.log(JSON.stringify({
  ok: true,
  selected: selected?.id || null,
  score: overallScore,
  runs: nextState.runs,
  nextHumanStep: report.nextHumanStep
}, null, 2));
