import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

import { assessCapabilityEvidence } from './lib/capability-evidence.mjs';

const requested = process.argv[2] || process.env.CAPABILITY_EVIDENCE_PATH || 'learning/capability-evidence.json';
const evidencePath = path.resolve(process.cwd(), requested);

if (!fs.existsSync(evidencePath)) {
  console.error(JSON.stringify({
    ok: false,
    status: 'not_measured',
    evidencePath,
    reasons: ['Capability evidence file does not exist.']
  }, null, 2));
  process.exit(2);
}

let evidence;
try {
  evidence = JSON.parse(fs.readFileSync(evidencePath, 'utf8'));
} catch (error) {
  console.error(JSON.stringify({
    ok: false,
    status: 'invalid_json',
    evidencePath,
    reasons: [error instanceof Error ? error.message : String(error)]
  }, null, 2));
  process.exit(2);
}

const assessment = assessCapabilityEvidence(evidence);
const output = {
  ok: assessment.accepted,
  evidencePath,
  capability: evidence.capability ?? null,
  scope: evidence.scope ?? null,
  ...assessment
};

console.log(JSON.stringify(output, null, 2));
if (!assessment.accepted) process.exit(1);
