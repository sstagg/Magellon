/**
 * Schema-introspection helpers for the plugin runner — derive form
 * defaults and locate the image/template path fields from a plugin's
 * JSON input schema.
 */

export function buildDefaults(schema: unknown): Record<string, unknown> {
    const props = (schema as { properties?: Record<string, { default?: unknown }> })?.properties;
    if (!props) return {};
    const out: Record<string, unknown> = {};
    for (const [key, prop] of Object.entries(props)) {
        if (prop?.default !== undefined) out[key] = prop.default;
    }
    return out;
}

/** Pick the schema property most likely to hold a single image path. */
export function findImagePathField(schema: unknown): string | null {
    const props = (schema as { properties?: Record<string, { type?: string }> })?.properties;
    if (!props) return null;
    const stringKeys = Object.entries(props)
        .filter(([, prop]) => prop?.type === 'string')
        .map(([key]) => key);
    const imagePath = stringKeys.find((k) => /image.*path|micrograph.*path/i.test(k));
    if (imagePath) return imagePath;
    const anyPath = stringKeys.find((k) => /path$/i.test(k) || /_path/i.test(k));
    if (anyPath) return anyPath;
    const imageKey = stringKeys.find((k) => /image|micrograph/i.test(k));
    return imageKey ?? null;
}

/** Pick the schema property most likely to hold a list of template paths. */
export function findTemplatePathsField(schema: unknown): string | null {
    const props = (schema as { properties?: Record<string, { type?: string; items?: { type?: string } }> })?.properties;
    if (!props) return null;
    const arrayOfStringKeys = Object.entries(props)
        .filter(([, prop]) => prop?.type === 'array' && prop?.items?.type === 'string')
        .map(([key]) => key);
    const templateKey = arrayOfStringKeys.find((k) => /template/i.test(k));
    if (templateKey) return templateKey;
    return arrayOfStringKeys.find((k) => /path/i.test(k)) ?? null;
}
