/**
 * Error-shaping helpers for plugin job submission and preview calls.
 */

export function parseFieldErrors(detail: unknown): Record<string, string> {
    if (!Array.isArray(detail)) return {};
    const out: Record<string, string> = {};
    for (const item of detail as Array<{ loc?: unknown; msg?: unknown }>) {
        if (!item?.loc || !item?.msg) continue;
        // FastAPI loc looks like ["body", "input", "threshold"] for wrapped
        // JobSubmitRequest bodies, or ["body", "threshold"] for direct
        // /preview bodies. Strip the request-envelope segments and take the
        // first remaining segment as the field key.
        const loc = Array.isArray(item.loc) ? item.loc : [];
        const segments = loc.filter((s: unknown) => s !== 'body' && s !== 'input');
        const key = segments.length > 0 ? String(segments[0]) : '';
        if (key && !out[key]) out[key] = String(item.msg);
    }
    return out;
}

export function formatSubmitError(err: unknown): string {
    const e = err as { response?: { status?: number; data?: { detail?: unknown } }; message?: string };
    const status = e?.response?.status;
    const data = e?.response?.data;
    const detail = typeof data?.detail === 'string'
        ? data.detail
        : data?.detail
            ? JSON.stringify(data.detail, null, 2)
            : null;
    if (status && detail) return `HTTP ${status}: ${detail}`;
    if (status) return `HTTP ${status}: ${e?.message ?? 'Request failed'}`;
    if (e?.message === 'Network Error') {
        return 'Network error — the server may have returned a response without CORS headers. Check the backend log for the real error.';
    }
    return e?.message || 'Submission failed';
}
