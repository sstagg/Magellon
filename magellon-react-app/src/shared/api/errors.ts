import axios from 'axios';

export interface ApiErrorPayload {
    code?: string;
    message?: string;
    detail?: string;
    details?: unknown;
}

export class ApiError extends Error {
    readonly status?: number;
    readonly code?: string;
    readonly details?: unknown;

    constructor(message: string, options: { status?: number; code?: string; details?: unknown } = {}) {
        super(message);
        this.name = 'ApiError';
        this.status = options.status;
        this.code = options.code;
        this.details = options.details;
    }
}

export function toApiError(error: unknown): ApiError {
    if (error instanceof ApiError) return error;

    if (axios.isAxiosError<ApiErrorPayload>(error)) {
        const payload = error.response?.data;
        const message = payload?.message ?? payload?.detail ?? error.message;
        return new ApiError(message, {
            status: error.response?.status,
            code: payload?.code,
            details: payload?.details,
        });
    }

    if (error instanceof Error) return new ApiError(error.message);
    return new ApiError('An unexpected error occurred');
}

export function getApiErrorMessage(error: unknown, fallback = 'An unexpected error occurred'): string {
    const message = toApiError(error).message;
    return message || fallback;
}

