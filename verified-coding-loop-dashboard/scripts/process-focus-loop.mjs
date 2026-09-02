import { projectPath, readJson, writeJson } from './lib/json-store.mjs';
import { asNumber } from './lib/number-tools.mjs';
import { prependHistory } from './lib/history-tools.mjs';
import { FOCUS_FACTORS, PROCESS_CATALOG } from './lib/process-catalog.mjs';
import {
  DEFAULT_EXPERIENCE_WEIGHTS,
  focusRecommendations,
  scoreProcess,
  weakestSubprocesses
} from './lib/experience-function.mjs';

const root = process.cwd();
const statePath = projectPath(root, 'src/data/processFocusState.json');
const reportPath = projectPath(root, 'learning/process-focus-report.json');

const defaultState = {
  schemaVersion: 1,
  runs: 0,
  bestOverallExperienceScore: 0,
  factorWeights: DEFAULT_EXPERIENCE_WEIGHTS,
  focusHistory: []
};

const state = readJson(statePath, defaultState);
const weights = { ...DEFAULT_EXPERIENCE_WEIGHTS, ...(state.factorWeights || {}) };
const scoredProcesses = PROCESS_CATALOG.map(process => scoreProcess(process, weights));
const overallExperienceScore = scoredProcesses.length
  ? Number((scoredProcesses.reduce((sum, process) => sum + process.experienceScore, 0) / scoredProcesses.length).toFixed(2))
  : 0;

const weakest = weakestSubprocesses(scoredProcesses, 7);
const recommendations = focusRecommendations(weakest);
const now = new Date().toISOString();

const runRecord = {
  time: now,
  overallExperienceScore,
  weakestSubprocessIds: weakest.map(item => item.id),
  weakestFactors: recommendations.map(item => item.weakestFactor),
  decision: overallExperienceScore >= asNumber(state.bestOverallExperienceScore, 0)
    ? 'experience_score_improved_or_equal'
    : 'experience_score_observed_lower'
};

const nextState = {
  ...state,
  schemaVersion: 1,
  runs: asNumber(state.runs, 0) + 1,
  bestOverallExperienceScore: Math.max(asNumber(state.bestOverallExperienceScore, 0), overallExperienceScore),
  lastRunAt: now,
  lastDecision: runRecord.decision,
  focusHistory: prependHistory(runRecord, state.focusHistory, 50)
};

const report = {
  schemaVersion: 1,
  generatedAt: now,
  purpose: 'Break the full learning system into processes and subprocesses, then focus improvement on weak factors.',
  focusFactors: FOCUS_FACTORS,
  factorWeights: weights,
  overallExperienceScore,
  scoredProcesses,
  weakestSubprocesses: weakest,
  recommendations,
  nextHumanStep: 'Review the weakest subprocesses and choose one small reversible improvement for the next proposal.'
};

writeJson(statePath, nextState);
writeJson(reportPath, report);

console.log(JSON.stringify({
  ok: true,
  overallExperienceScore,
  runs: nextState.runs,
  weakest: recommendations.map(item => `${item.processId}/${item.subprocessId}:${item.weakestFactor}`)
}, null, 2));
