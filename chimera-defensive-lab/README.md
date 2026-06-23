# Chimera Defensive Lab Pack

Safe defensive training material derived from a quarantined high-risk archive.

The original archive is intentionally not included. This folder contains only a harmless incident-response simulator, review notes, and tests for defensive learning.

## Contents

- Non-executing safety review
- Evidence manifest with filenames, sizes, and SHA-256 hashes
- Harmless defensive timeline simulator
- Unit tests
- CI workflow template
- Safe handling notes

## Safe local use

```bash
cd chimera-defensive-lab
python -m src.chimera_defensive_simulator
python -m pytest
```

The simulator only prints a defensive response timeline. It does not access networks, files outside its own code, credentials, processes, or system settings.

## Purpose

Use this as a clean tabletop exercise package for learning how to preserve evidence, review suspicious archives safely, document findings, and publish only safe educational material.
