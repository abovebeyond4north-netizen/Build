import { projectPath, readJson, writeJson } from './lib/json-store.mjs';
import { asNumber, round2 } from './lib/number-tools.mjs';
import { prependHistory } from './lib/history-tools.mjs';

const root = process.cwd();

const paths = {
  state: projectPath(root, 'src/data/implementationPlanState.json'),
  report: projectPath(root, 'learning/implementation-plan-report.json'),
  generalReport: projectPath(root, 'learning/general-improvement-report.json'),
  efficiencyReport: projectPath(root, 'learning/efficiency-optimizer-report.json'),
  proposal: projectPath(root, 'proposals/latest-verified-proposal.json')
};

const defaultState = {
  schemaVersion: 1,
  runs: 0,
  bestPlanScore: 0,
  planHistory: [],
  planRules: {
    smallestUsefulPatch: true,
    testsBeforeMerge: true,
    buildBeforeMerge: true,
    humanReviewRequired: true,
    rollbackRequired: true
  }
};

function chooseSource({ generalReport, efficiencyReport, proposal }) {
  if (generalReport.selectedMove) {
    return {
      source: 'general-improvement-report',
      id: generalReport.selectedMove.id,
      title: generalReport.selectedMove.title,
      reason: generalReport.selectedMove.reason,
      score: asNumber(generalReport.selectedMove.score, generalReport.generalScore || 0)
    };
  }

  if (efficiencyReport.selected) {
    return {
      source: 'efficiency-optimizer-report',
      id: efficiencyReport.selected.id,
      title: efficiencyReport.selected.title,
      reason: efficiencyReport.selected.recommendation,
      score: asNumber(efficiencyReport.selected.score, 0)
    };
  }

  if (proposal.selected) {
    return {
      source: 'latest-verified-proposal',
      id: proposal.selected.id,
      title: proposal.selected.title,
      reason: proposal.selected.reason,
      score: asNumber(proposal.selected.expectedBenefit ?? proposal.selected.score, 0)
    };
  }

  return null;
}

function buildPlan(target) {
  if (!target) {
    return null;
  }

  return {
    target,
    phases: [
      {
        id: 'define-scope',
        title: 'Define minimal scope',
        objective: 'Describe the smallest useful patch that addresses the selected target.',
        doneWhen: 'The patch target, affected files, and non-goals are explicit.'
      },
      {
        id: 'add-or-confirm-tests',
        title: 'Add or confirm tests first',
        objective: 'Make sure existing checks prove the behavior that must not regress.',
        doneWhen: 'quality, architecture, library, and schema checks still cover the change.'
      },
      {
        id: 'make-small-change',
        title: 'Make one reversible change',
        objective: 'Modify the smallest set of files required for the target.',
        doneWhen: 'The change can be understood and reverted in one commit.'
      },
      {
        id: 'verify-locally',
        title: 'Verify locally',
        objective: 'Run deterministic checks and production build.',
        doneWhen: 'npm run test and npm run build pass.'
      },
      {
        id: 'write-review-notes',
        title: 'Write review notes',
        objective: 'Explain what changed, why it changed, and how rollback works.',
        doneWhen: 'Reviewer can approve or reject without guessing intent.'
      }
    ],
    acceptanceTests: [
      'npm run test passes',
      'npm run build passes',
      'state-schema-check passes',
      'architecture-check passes',
      'change remains small and reviewable'
    ],
    rollbackPlan: [
      'Revert the patch commit.',
      'Restore previous JSON state files if they changed.',
      'Re-run npm run test and npm run build after rollback.'
    ],
    riskControls: [
      'No hidden external actions.',
      'No broad rewrites unless tests already prove safety.',
      'No merge without review.',
      'Prefer adding checks before changing behavior.'
    ]
  };
}

function planScore(plan) {
  if (!plan) return 0;
  const phaseCoverage = Math.min(1, plan.phases.length / 5);
  const acceptanceCoverage = Math.min(1, plan.acceptanceTests.length / 5);
  const rollbackCoverage = Math.min(1, plan.rollbackPlan.length / 3);
  const riskCoverage = Math.min(1, plan.riskControls.length / 4);
  return round2(phaseCoverage * 0.25 + acceptanceCoverage * 0.3 + rollbackCoverage * 0.25 + riskCoverage * 0.2);
}

const state = readJson(paths.state, defaultState);
const generalReport = readJson(paths.generalReport, {});
const efficiencyReport = readJson(paths.efficiencyReport, {});
const proposal = readJson(paths.proposal, {});
const target = chooseSource({ generalReport, efficiencyReport, proposal });
const plan = buildPlan(target);
const score = planScore(plan);
const now = new Date().toISOString();

const record = {
  time: now,
  targetId: target?.id || null,
  source: target?.source || null,
  planScore: score,
  decision: plan ? 'implementation_plan_created' : 'no_plan_target_available'
};

const nextState = {
  ...state,
  schemaVersion: 1,
  runs: asNumber(state.runs, 0) + 1,
  bestPlanScore: Math.max(asNumber(state.bestPlanScore, 0), score),
  lastRunAt: now,
  lastDecision: record.decision,
  planHistory: prependHistory(record, state.planHistory, 50)
};

const report = {
  schemaVersion: 1,
  generatedAt: now,
  purpose: 'Turn the selected improvement target into a concrete, testable, reversible implementation plan.',
  selectedTarget: target,
  planScore: score,
  plan,
  stateAfter: {
    runs: nextState.runs,
    bestPlanScore: nextState.bestPlanScore,
    lastDecision: nextState.lastDecision
  },
  nextHumanStep: plan
    ? `Use the plan for ${target.id}. Start with: ${plan.phases[0].objective}`
    : 'Run improve:general or efficiency:optimize first so there is a target to plan.'
};

writeJson(paths.state, nextState);
writeJson(paths.report, report);

console.log(JSON.stringify({
  ok: true,
  target: target?.id || null,
  planScore: score,
  runs: nextState.runs,
  nextHumanStep: report.nextHumanStep
}, null, 2));
