export const REQUIRED_SECTIONS = [
  'System State',
  'Awareness Ladder',
  'Prediction Engine',
  'Benchmark Runner',
  'Patch Candidate Panel',
  'Oracle Gate',
  'Memory',
  'Belief Tracker',
  'Self-Model',
  'Uncertainty + Calibration',
  'Snapshots and Rollback',
  'Curriculum Builder',
  'Syntax Genome',
  'Append-Only Event Log'
];

export const REQUIRED_ACTIONS = [
  'Run Challenge',
  'Generate Patch',
  'Verify Patch',
  'Apply Oracle Gate',
  'Save Lesson',
  'Update Confidence',
  'Create Snapshot',
  'Roll Back',
  'Reset Demo'
];

export const REQUIRED_SAFETY_CLAIMS = [
  'does not claim consciousness',
  'No real code execution',
  'network automation',
  'external side effects',
  'Simulated data only'
];

export const FORBIDDEN_RUNTIME_PATTERNS = [
  'child_process',
  'fetch(',
  'XMLHttpRequest',
  'WebSocket',
  'eval(',
  'new Function',
  'localStorage.setItem'
];
