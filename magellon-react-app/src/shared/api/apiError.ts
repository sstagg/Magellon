import axios from 'axios';

/** Structured view of a thrown value, normalized from Axios/Error/unknown. */
export interface NormalizedApiError {
    /** HTTP status code, when the error came from an HTTP response. */
    status?: number;
    /** Server-provided `detail` (or raw string body), when present. */
    detail?: string;
    /** Best human-readable message: server detail, else the Error message. */
    message: string;
}

/**
 * Narrow an unknown thrown value into a structured API error.
 * Centralizes the `error.response?.status` / `error.response?.data?.detail`
 * access that would otherwise force `catch (e: any)` everywhere.
 */
export function toApiError(error: unknown): NormalizedApiError {
    if (axios.isAxiosError(error)) {
        const data = error.response?.data as { detail?: string } | string | undefined;
        const detail = typeof data === 'string' ? data : data?.detail;
        return {
            status: error.response?.status,
            detail,
            message: detail || error.message,
        };
    }
    if (error instanceof Error) {
        return { message: error.message };
    }
    return { message: String(error) };
}

/** Convenience: the best message for an unknown error, with a fallback. */
export function apiErrorMessage(error: unknown, fallback: string): string {
    const { detail, message } = toApiError(error);
    return detail || message || fallback;
}
