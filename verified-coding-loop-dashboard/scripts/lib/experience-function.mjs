import { round2 } from './number-tools.mjs';

export const DEFAULT_EXPERIENCE_WEIGHTS = {
  clarity: 0.14,
  feedback: 0.14,
  verification: 0.18,
  reversibility: 0.14,
  costControl: 0.16,
  skillGrowth: 0.12,
  usefulness: 0.12
};

export function scoreFactors(factors, weights = DEFAULT_EXPERIENCE_WEIGHTS) {
  const weightTotal = Object.values(weights).reduce((sum, value) => sum + Number(value || 0), 0) || 1;
  const weighted = Object.entries(weights).reduce((sum, [factor, weight]) => {
    return sum + Number(factors[factor] || 0) * Number(weight || 0);
  }, 0);
  return round2(weighted / weightTotal);
}

export function scoreSubprocess(subprocess, weights = DEFAULT_EXPERIENCE_WEIGHTS) {
  return {
    ...subprocess,
    experienceScore: scoreFactors(subprocess.factors || {}, weights)
  };
}

export function scoreProcess(process, weights = DEFAULT_EXPERIENCE_WEIGHTS) {
  const scoredSubprocesses = (process.subprocesses || []).map(subprocess => scoreSubprocess(subprocess, weights));
  const processScore = scoredSubprocesses.length
    ? round2(scoredSubprocesses.reduce((sum, subprocess) => sum + subprocess.experienceScore, 0) / scoredSubprocesses.length)
    : 0;

  return {
    ...process,
    experienceScore: processScore,
    subprocesses: scoredSubprocesses
  };
}

export function weakestSubprocesses(scoredProcesses, limit = 5) {
  return scoredProcesses
    .flatMap(process => process.subprocesses.map(subprocess => ({
      processId: process.id,
      processTitle: process.title,
      ...subprocess
    })))
    .sort((a, b) => a.experienceScore - b.experienceScore)
    .slice(0, limit);
}

export function focusRecommendations(subprocesses) {
  return subprocesses.map(subprocess => {
    const sortedFactors = Object.entries(subprocess.factors || {})
      .sort((a, b) => Number(a[1]) - Number(b[1]));
    const weakestFactor = sortedFactors[0]?.[0] || 'unknown';

    return {
      processId: subprocess.processId,
      subprocessId: subprocess.id,
      title: subprocess.title,
      experienceScore: subprocess.experienceScore,
      weakestFactor,
      recommendation: `Improve ${weakestFactor} for ${subprocess.title}. Keep the change small, measurable, and reversible.`
    };
  });
}
