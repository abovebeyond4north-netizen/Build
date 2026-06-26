export function latest(history) {
  return Array.isArray(history) && history.length > 0 ? history[0] : {};
}

export function getLearningSignals({ verified, meta, value }) {
  const lastVerified = latest(verified.learningHistory);
  const lastMeta = latest(meta.strategyHistory);
  const lastValue = latest(value.experimentHistory);

  const testsPassed = lastVerified.testsPassed === true;
  const buildPassed = lastVerified.buildPassed === true;
  const benchmarkPassed = testsPassed && buildPassed;
  const codeWriteSucceeded = benchmarkPassed && lastVerified.decision !== 'rejected';

  const skillSignals = [
    Number(lastMeta.learningScore || 0) > 0 ? 'meta_learning_measurement' : null,
    lastValue.id ? 'value_experiment_selection' : null,
    Number(lastVerified.afterScore ?? -1) >= Number(lastVerified.beforeScore ?? 0) ? 'quality_score_preserved' : null
  ].filter(Boolean);

  return {
    lastVerified,
    lastMeta,
    lastValue,
    testsPassed,
    buildPassed,
    benchmarkPassed,
    codeWriteSucceeded,
    skillSignals
  };
}
