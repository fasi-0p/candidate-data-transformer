# Frontend — Candidate Data Transformation Engine

A minimal, Apple-inspired white-themed SPA for the transformation engine.
Its only job is to make the engine's **explainability** visible: every field
traces back to its source, the conflicts that lost, and a confidence score.

## Stack

- **React 19** + **TypeScript** + **Vite**
- **Tailwind CSS v4** with Apple-minimal design tokens (`src/index.css`)
- **shadcn-style** primitives over **Radix UI** (`src/components/ui/`)
- **framer-motion** for subtle entrance motion, **lucide-react** icons

## Develop

```bash
npm install
npm run dev        # http://localhost:5173
```

The dev server proxies `/api/*` to the FastAPI engine on `http://127.0.0.1:8000`,
so both share an origin (no CORS). Start the engine first:

```bash
# from the repo root
python -m uvicorn src.api.app:app --reload
```

## Layout

| Path | Purpose |
| --- | --- |
| `src/App.tsx` | Page shell: hero, the three numbered sections, run/projection state |
| `src/components/UploadCard.tsx` | Source inputs (CSV / resume / ATS / notes / GitHub / LinkedIn-verify) |
| `src/components/StatsStrip.tsx` | Records → candidates, conflicts, per-stage timings |
| `src/components/CandidateCard.tsx` | One canonical profile |
| `src/components/FieldGroup.tsx` | A field + its provenance accordion (source, agreements, conflicts) |
| `src/components/ProjectionCard.tsx` | Re-project a run into a saved output schema |
| `src/lib/api.ts` | Typed `fetch` wrappers over the engine |
| `src/lib/types.ts` | Mirrors the engine's serialized shapes |

## Build

```bash
npm run build      # tsc -b && vite build  →  dist/
npm run lint       # oxlint
```
