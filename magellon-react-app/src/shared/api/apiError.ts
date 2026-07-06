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

interface ResponseLikeError {
    response?: {
        status?: number;
        data?: unknown;
    };
    message?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null;
}

function responseLikeError(error: unknown): ResponseLikeError | null {
    if (!isRecord(error) || !isRecord(error.response)) {
        return null;
    }

    return {
        response: {
            status: typeof error.response.status === 'number' ? error.response.status : undefined,
            data: error.response.data,
        },
        message: typeof error.message === 'string' ? error.message : undefined,
    };
}

function detailFromData(data: unknown): string | undefined {
    if (typeof data === 'string') {
        return data;
    }
    if (!isRecord(data)) {
        return undefined;
    }

    const detail = data.detail;
    if (typeof detail === 'string') {
        return detail;
    }
    if (Array.isArray(detail)) {
        return detail
            .map((item) => {
                if (typeof item === 'string') {
                    return item;
                }
                if (isRecord(item) && typeof item.msg === 'string') {
                    return item.msg;
                }
                return undefined;
            })
            .filter((item): item is string => item !== undefined)
            .join(', ') || undefined;
    }
    return undefined;
}

/**
 * Narrow an unknown thrown value into a structured API error.
 * Centralizes the `error.response?.status` / `error.response?.data?.detail`
 * access that would otherwise force `catch (e: any)` everywhere.
 */
export function toApiError(error: unknown): NormalizedApiError {
    if (axios.isAxiosError(error)) {
        const detail = detailFromData(error.response?.data);
        return {
            status: error.response?.status,
            detail,
            message: detail || error.message,
        };
    }
    const responseError = responseLikeError(error);
    if (responseError) {
        const detail = detailFromData(responseError.response?.data);
        return {
            status: responseError.response?.status,
            detail,
            message: detail || responseError.message || 'Request failed',
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
