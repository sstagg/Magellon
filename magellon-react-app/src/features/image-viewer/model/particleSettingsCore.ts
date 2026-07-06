import { settings as appSettings } from '../../../shared/config/settings.ts';
import type { Point } from '../lib/useParticleOperations.ts';
import { confidenceFromScore } from '../lib/useParticleOperations.ts';
import type { BackendPick } from './particleSettingsTypes.ts';

export const API_URL = appSettings.ConfigData.SERVER_API_URL;

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

export function validateParams(schema: unknown, params: Record<string, unknown>, imageName: string | null): string[] {
    const s = schema as {
        properties?: Record<string, {
            title?: string;
            ui_hidden?: boolean;
            ui_required_message?: string;
            minItems?: number;
            minimum?: number;
            maximum?: number;
            exclusiveMinimum?: number;
        }>;
        required?: string[];
    } | null;
    if (!s?.properties) return [];
    const errors: string[] = [];
    const required = new Set<string>(s.required || []);

    if (!imageName) {
        errors.push('No image selected — select a micrograph first.');
    }

    for (const [key, field] of Object.entries(s.properties)) {
        if (field.ui_hidden) continue;
        const value = params[key];
        const label = field.title || key;

        if (required.has(key)) {
            if (value === undefined || value === null || value === '') {
                errors.push(field.ui_required_message || `${label} is required.`);
                continue;
            }
            if (Array.isArray(value) && field.minItems && value.length < field.minItems) {
                errors.push(field.ui_required_message || `${label} needs at least ${field.minItems} item(s).`);
                continue;
            }
        }

        if (value !== null && value !== undefined && typeof value === 'number') {
            if (field.minimum !== undefined && value < field.minimum)
                errors.push(`${label} must be at least ${field.minimum}.`);
            if (field.maximum !== undefined && value > field.maximum)
                errors.push(`${label} must be at most ${field.maximum}.`);
            if (field.exclusiveMinimum !== undefined && value <= field.exclusiveMinimum)
                errors.push(`${label} must be greater than ${field.exclusiveMinimum}.`);
        }
    }
    return errors;
}

export function schemaDefaults(schema: unknown): Record<string, unknown> {
    const props = (schema as { properties?: Record<string, { default?: unknown }> })?.properties;
    if (!props) return {};
    const defaults: Record<string, unknown> = {};
    for (const [key, field] of Object.entries(props)) {
        if (field?.default !== undefined) defaults[key] = field.default;
    }
    return defaults;
}

export function pointFromBackendPick(
    p: BackendPick,
    idPrefix: string,
    idx: number,
    threshold: number,
    isTopaz: boolean,
): Point {
    const score = Number(p.score ?? 0);
    const radius = Number(p.radius);
    return {
        x: p.x,
        y: p.y,
        id: `${idPrefix}-${Date.now()}-${idx}`,
        type: 'auto',
        confidence: confidenceFromScore(score, isTopaz),
        score,
        radius: Number.isFinite(radius) && radius > 0 ? radius : undefined,
        class: score >= threshold ? '1' : '4',
        timestamp: Date.now(),
    };
}
