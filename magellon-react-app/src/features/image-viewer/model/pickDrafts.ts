import type { Point } from '../lib/useParticleOperations.ts';

/**
 * Unsaved particle picks per image, kept while the page is open.
 *
 * Switching to another image used to throw away picks that weren't saved
 * yet (hand edits, or a Topaz / template preview). They are parked here
 * instead, and restored when the user comes back to the image; saving the
 * record clears its draft. Closing or reloading the page still loses them,
 * so the page warns first while any draft exists.
 */
export interface PickDraft {
    /** The picking record the picks belong to; null when none was selected. */
    recordOid: string | null;
    recordName?: string | null;
    particles: Point[];
}

const drafts = new Map<string, PickDraft>();

export const pickDrafts = {
    get: (imageOid: string | null | undefined): PickDraft | undefined =>
        imageOid ? drafts.get(imageOid) : undefined,
    set: (imageOid: string, draft: PickDraft) => { drafts.set(imageOid, draft); },
    delete: (imageOid: string | null | undefined) => { if (imageOid) drafts.delete(imageOid); },
    size: () => drafts.size,
};

/** Positions and classes only, so a reloaded copy of the same picks compares equal. */
function signature(points: Point[] | null | undefined): string {
    return JSON.stringify(
        (points ?? []).map((p) => [Math.round(p.x), Math.round(p.y), p.class ?? '1']),
    );
}

/** True when ``current`` differs from what is saved on the server. */
export function picksDiffer(current: Point[], saved: Point[] | null | undefined): boolean {
    return signature(current) !== signature(saved);
}
