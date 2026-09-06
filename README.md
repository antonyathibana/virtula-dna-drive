# Virtual DNA Drive

A software-only DNA data storage simulator.

## Features
- Upload any file
- Convert bytes -> virtual DNA (A/C/G/T)
- Chunk DNA into strands with configurable redundancy (1-9 copies)
- Simulate substitution, insertion, deletion, and strand-dropout errors
- Recover corrupted DNA using dropout-tolerant majority voting
- Decode DNA -> original file, verified with SHA-256
- Real-time GC-content and DNA quality scoring
- Strand-by-strand viewer with per-copy diff highlighting
- Compare majority voting against a genuinely-implemented Hamming(7,4)
  bit-level error-correcting code — every number shown is measured from an
  actual run, never estimated or hard-coded
- Dashboard analytics computed live from your stored records
- Polished dark-mode browser UI

## What's simulated vs. not implemented
This models an idea from DNA-data-storage research — it does not synthesize,
store, or sequence physical DNA. Only two correction strategies are
implemented (majority voting and Hamming(7,4)); the UI will never display
numbers for a method (e.g. Reed-Solomon) that wasn't actually run.

## Run

```bash
cd virtual_dna_drive
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows
# .venv\Scripts\activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

http://127.0.0.1:8000

## Important
This is a computer simulation. It does not create, synthesize, or sequence physical DNA.
# virtula-dna-drive
