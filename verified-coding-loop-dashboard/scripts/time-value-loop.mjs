import { projectPath, readJson, writeJsonAtomic } from './lib/json-store.mjs';
import { updateRewardState, rewardReport } from './lib/reward-evidence.mjs';

const root = process.cwd();
const statePath = projectPath(root, 'src/data/timeValueState.json');
const reportPath = projectPath(root, 'learning/time-value-report.json');
const previous = readJson(statePath, {});
const verified = readJson(projectPath(root, 'src/data/verifiedLearningState.json'), {});
const state = updateRewardState(previous, verified);
writeJsonAtomic(statePath, state);
writeJsonAtomic(reportPath, rewardReport(state));
console.log(JSON.stringify({ ok: true, virtualBalance: state.virtualBalance,
  virtualHourlyRate: state.virtualHourlyRate, decision: state.lastDecision }, null, 2));
