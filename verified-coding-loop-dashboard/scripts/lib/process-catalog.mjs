export const FOCUS_FACTORS = [
  'clarity',
  'feedback',
  'verification',
  'reversibility',
  'costControl',
  'skillGrowth',
  'usefulness'
];

export const PROCESS_CATALOG = [
  {
    id: 'quality-verification',
    title: 'Quality Verification',
    purpose: 'Keep the dashboard behavior, safety markers, and required actions intact.',
    subprocesses: [
      { id: 'section-marker-check', title: 'Section marker check', factors: { clarity: 0.9, feedback: 0.7, verification: 1, reversibility: 0.8, costControl: 0.8, skillGrowth: 0.4, usefulness: 0.8 } },
      { id: 'action-marker-check', title: 'Action marker check', factors: { clarity: 0.85, feedback: 0.7, verification: 1, reversibility: 0.8, costControl: 0.8, skillGrowth: 0.4, usefulness: 0.8 } },
      { id: 'safety-marker-check', title: 'Safety marker check', factors: { clarity: 0.85, feedback: 0.75, verification: 1, reversibility: 0.9, costControl: 0.9, skillGrowth: 0.4, usefulness: 0.85 } }
    ]
  },
  {
    id: 'architecture-integrity',
    title: 'Architecture Integrity',
    purpose: 'Prevent duplicated helpers and keep learning scripts modular.',
    subprocesses: [
      { id: 'shared-library-presence', title: 'Shared library presence', factors: { clarity: 0.8, feedback: 0.7, verification: 0.95, reversibility: 0.9, costControl: 0.8, skillGrowth: 0.6, usefulness: 0.8 } },
      { id: 'duplication-guard', title: 'Duplication guard', factors: { clarity: 0.75, feedback: 0.8, verification: 0.95, reversibility: 0.85, costControl: 0.9, skillGrowth: 0.65, usefulness: 0.85 } },
      { id: 'modular-loop-shape', title: 'Modular loop shape', factors: { clarity: 0.75, feedback: 0.65, verification: 0.85, reversibility: 0.8, costControl: 0.75, skillGrowth: 0.7, usefulness: 0.8 } }
    ]
  },
  {
    id: 'utility-correctness',
    title: 'Utility Correctness',
    purpose: 'Prove shared helper modules behave correctly before loops depend on them.',
    subprocesses: [
      { id: 'json-store-regression', title: 'JSON store regression', factors: { clarity: 0.8, feedback: 0.85, verification: 0.95, reversibility: 0.9, costControl: 0.8, skillGrowth: 0.65, usefulness: 0.9 } },
      { id: 'number-tool-regression', title: 'Number tool regression', factors: { clarity: 0.8, feedback: 0.85, verification: 0.95, reversibility: 0.9, costControl: 0.8, skillGrowth: 0.6, usefulness: 0.85 } },
      { id: 'learning-signal-regression', title: 'Learning signal regression', factors: { clarity: 0.75, feedback: 0.85, verification: 0.9, reversibility: 0.85, costControl: 0.8, skillGrowth: 0.8, usefulness: 0.9 } }
    ]
  },
  {
    id: 'schema-integrity',
    title: 'Schema Integrity',
    purpose: 'Keep state and report artifacts machine-readable as the system evolves.',
    subprocesses: [
      { id: 'state-shape-check', title: 'State shape check', factors: { clarity: 0.8, feedback: 0.8, verification: 0.95, reversibility: 0.85, costControl: 0.8, skillGrowth: 0.55, usefulness: 0.85 } },
      { id: 'report-shape-check', title: 'Report shape check', factors: { clarity: 0.75, feedback: 0.8, verification: 0.9, reversibility: 0.85, costControl: 0.8, skillGrowth: 0.55, usefulness: 0.8 } },
      { id: 'review-gate-check', title: 'Review gate check', factors: { clarity: 0.85, feedback: 0.75, verification: 0.95, reversibility: 0.95, costControl: 0.9, skillGrowth: 0.45, usefulness: 0.9 } }
    ]
  },
  {
    id: 'proposal-generation',
    title: 'Proposal Generation',
    purpose: 'Select focused improvements only when evidence markers support them.',
    subprocesses: [
      { id: 'candidate-ranking', title: 'Candidate ranking', factors: { clarity: 0.7, feedback: 0.65, verification: 0.8, reversibility: 0.85, costControl: 0.8, skillGrowth: 0.75, usefulness: 0.85 } },
      { id: 'evidence-marker-gate', title: 'Evidence marker gate', factors: { clarity: 0.85, feedback: 0.75, verification: 0.9, reversibility: 0.9, costControl: 0.9, skillGrowth: 0.65, usefulness: 0.85 } },
      { id: 'proposal-artifact-write', title: 'Proposal artifact write', factors: { clarity: 0.8, feedback: 0.8, verification: 0.85, reversibility: 0.9, costControl: 0.85, skillGrowth: 0.6, usefulness: 0.85 } }
    ]
  },
  {
    id: 'experience-and-value-learning',
    title: 'Experience and Value Learning',
    purpose: 'Improve usefulness by selecting ethical, reviewable value experiments.',
    subprocesses: [
      { id: 'experiment-scoring', title: 'Experiment scoring', factors: { clarity: 0.7, feedback: 0.7, verification: 0.75, reversibility: 0.85, costControl: 0.9, skillGrowth: 0.8, usefulness: 0.9 } },
      { id: 'novelty-control', title: 'Novelty control', factors: { clarity: 0.65, feedback: 0.75, verification: 0.75, reversibility: 0.8, costControl: 0.8, skillGrowth: 0.85, usefulness: 0.8 } },
      { id: 'reviewable-next-step', title: 'Reviewable next step', factors: { clarity: 0.85, feedback: 0.75, verification: 0.8, reversibility: 0.95, costControl: 0.9, skillGrowth: 0.7, usefulness: 0.95 } }
    ]
  },
  {
    id: 'meta-learning',
    title: 'Meta-Learning',
    purpose: 'Measure whether the learning loop is improving its own learning process.',
    subprocesses: [
      { id: 'diversity-measurement', title: 'Diversity measurement', factors: { clarity: 0.75, feedback: 0.8, verification: 0.8, reversibility: 0.9, costControl: 0.8, skillGrowth: 0.9, usefulness: 0.85 } },
      { id: 'evidence-depth-measurement', title: 'Evidence depth measurement', factors: { clarity: 0.8, feedback: 0.8, verification: 0.85, reversibility: 0.9, costControl: 0.8, skillGrowth: 0.85, usefulness: 0.85 } },
      { id: 'strategy-selection', title: 'Strategy selection', factors: { clarity: 0.75, feedback: 0.8, verification: 0.8, reversibility: 0.85, costControl: 0.75, skillGrowth: 0.9, usefulness: 0.9 } }
    ]
  },
  {
    id: 'cost-and-credit-control',
    title: 'Cost and Credit Control',
    purpose: 'Charge internal credits for time and failures while rewarding verified progress.',
    subprocesses: [
      { id: 'time-cost-estimation', title: 'Time cost estimation', factors: { clarity: 0.75, feedback: 0.75, verification: 0.75, reversibility: 0.85, costControl: 0.95, skillGrowth: 0.6, usefulness: 0.85 } },
      { id: 'failure-penalty-calculation', title: 'Failure penalty calculation', factors: { clarity: 0.8, feedback: 0.85, verification: 0.85, reversibility: 0.85, costControl: 1, skillGrowth: 0.7, usefulness: 0.9 } },
      { id: 'success-credit-calculation', title: 'Success credit calculation', factors: { clarity: 0.75, feedback: 0.8, verification: 0.8, reversibility: 0.85, costControl: 0.9, skillGrowth: 0.75, usefulness: 0.85 } }
    ]
  }
];
