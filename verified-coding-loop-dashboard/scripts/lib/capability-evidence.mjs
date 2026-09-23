function finiteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function nonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

export function assessCapabilityEvidence(evidence) {
  if (!evidence || Object.keys(evidence).length === 0) {
    return {
      accepted: false,
      status: 'not_measured',
      reasons: ['No independent capability evidence report is present.']
    };
  }

  const reasons = [];
  const evaluator = evidence.evaluator || {};
  const holdout = evidence.holdout || {};
  const baseline = evidence.baseline || {};
  const candidate = evidence.candidate || {};
  const replication = evidence.replication || {};
  const provenance = evidence.provenance || {};

  if (evidence.schemaVersion !== 1) reasons.push('Unsupported capability evidence schema.');
  if (evaluator.independent !== true) reasons.push('Evaluator independence is not established.');
  if (evaluator.hiddenFromLearner !== true) reasons.push('Holdout visibility is not sealed from the learner.');
  if (holdout.unseen !== true) reasons.push('Tasks are not marked unseen.');
  if (!Number.isInteger(holdout.taskCount) || holdout.taskCount < 20) {
    reasons.push('At least 20 held-out tasks are required.');
  }
  if (holdout.contaminationDetected !== false) reasons.push('Contamination has not been ruled out.');
  if (!finiteNumber(baseline.score) || !finiteNumber(candidate.score)) {
    reasons.push('Baseline and candidate scores must be finite numbers.');
  } else if (candidate.score <= baseline.score) {
    reasons.push('Candidate does not outperform the baseline.');
  }
  if (replication.count < 2 || replication.consistent !== true) {
    reasons.push('Improvement must replicate consistently at least twice.');
  }
  if (evidence.unrelatedRegressionDetected !== false) {
    reasons.push('Unrelated-task non-regression is not established.');
  }
  const baselineArtifact = provenance.baselineArtifact ?? provenance.baselineCommit;
  const candidateArtifact = provenance.candidateArtifact ?? provenance.candidateCommit;
  if (!nonEmptyString(baselineArtifact)) reasons.push('Baseline artifact provenance is missing.');
  if (!nonEmptyString(candidateArtifact)) reasons.push('Candidate artifact provenance is missing.');
  if (!nonEmptyString(provenance.taskSetCommitment)) reasons.push('Task-set commitment is missing.');
  if (!nonEmptyString(provenance.receiptHash)) reasons.push('Evaluation receipt hash is missing.');

  return {
    accepted: reasons.length === 0,
    status: reasons.length === 0 ? 'independent_holdout_improvement' : 'insufficient_evidence',
    reasons,
    baselineScore: finiteNumber(baseline.score) ? baseline.score : null,
    candidateScore: finiteNumber(candidate.score) ? candidate.score : null,
    taskCount: Number.isInteger(holdout.taskCount) ? holdout.taskCount : 0,
    replicationCount: Number.isInteger(replication.count) ? replication.count : 0
  };
}
