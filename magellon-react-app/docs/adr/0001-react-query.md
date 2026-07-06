# ADR 0001 — React Query is the data-fetching idiom

**Status:** Accepted, 2026-07-06

## Context

The codebase currently mixes three data-fetching patterns: React Query
(13 files), raw `axios` inside `useEffect` + `useState` (12+ files), and
ad-hoc manual caches (`useState<T[]>` per component). The raw patterns
have no caching, no request dedup, no consistent retry or error
handling, and each one reimplements loading/error state.

## Decision

- **All new data fetching uses React Query** (`useQuery` / `useMutation`)
  against the shared axios clients from `shared/api`.
- The shared `QueryClient` in `main.tsx` carries the default policy:
  `staleTime: 30s`, `retry: 1`, `refetchOnWindowFocus: false`. Override
  per-query only with a stated reason (e.g. live-updating job status).
- **Existing raw axios-in-useEffect code migrates opportunistically**:
  whenever a file is touched for another reason, convert its fetches.
  No big-bang migration.
- Socket-pushed state (job/step events) stays in Zustand stores — React
  Query is for request/response data, not streams.

## Consequences

- The net count of raw-fetch feature files should only go down; new
  ones are a review flag.
- Query keys follow `[domain, resource, params]`, e.g.
  `['sessions', sessionName, 'images', page]`.
