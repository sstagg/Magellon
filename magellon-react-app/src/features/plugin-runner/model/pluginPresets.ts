// ---------------------------------------------------------------------------
// Plugin-specific test-bench presets. Values come from the plugin's own
// Sandbox README so "pick test image + pick templates + run" just works.

interface PluginPreset {
    defaults?: Record<string, unknown>;
    imagePixelSizesByFilename?: Array<{ match: RegExp; apix: number }>;
    templatePixelSizesByFilename?: Array<{ match: RegExp; apix: number }>;
}

const TEMPLATE_PICKER_PRESET: PluginPreset = {
    defaults: {
        diameter_angstrom: 220,
        invert_templates: true,
        bin_factor: 4,
        lowpass_resolution: 12.0,
        threshold: 0.35,
    },
    imagePixelSizesByFilename: [
        { match: /24may23b/i, apix: 1.230 },
        { match: /25may06y/i, apix: 0.830 },
    ],
    templatePixelSizesByFilename: [
        { match: /origTemplate/i, apix: 2.646 },
    ],
};

const PLUGIN_PRESETS: Record<string, PluginPreset> = {
    'pp/template-picker': TEMPLATE_PICKER_PRESET,
    'particle_picking/template picker': TEMPLATE_PICKER_PRESET,
    'particle_picking/template-picker': TEMPLATE_PICKER_PRESET,
    'particle_picking/template picker - particle picking': TEMPLATE_PICKER_PRESET,
};

function presetKey(pluginId: string): string {
    try {
        return decodeURIComponent(pluginId).toLowerCase().replace(/\s+/g, ' ').trim();
    } catch {
        return pluginId.toLowerCase().replace(/\s+/g, ' ').trim();
    }
}

function pluginPresetFor(pluginId: string): PluginPreset | undefined {
    const key = presetKey(pluginId).replace(/—/g, '-');
    return PLUGIN_PRESETS[key];
}

export function pluginTestDefaultsFor(pluginId: string): Record<string, unknown> {
    return pluginPresetFor(pluginId)?.defaults ?? {};
}

export function imagePixelSizeFor(pluginId: string, path: string): number | null {
    const preset = pluginPresetFor(pluginId);
    if (!preset?.imagePixelSizesByFilename) return null;
    const name = path.split(/[\\/]/).pop() ?? path;
    return preset.imagePixelSizesByFilename.find((r) => r.match.test(name))?.apix ?? null;
}

export function templatePixelSizeFor(pluginId: string, paths: string[]): number | null {
    const preset = pluginPresetFor(pluginId);
    if (!preset?.templatePixelSizesByFilename || paths.length === 0) return null;
    // All templates must match the same rule, otherwise don't auto-fill.
    for (const rule of preset.templatePixelSizesByFilename) {
        if (paths.every((p) => rule.match.test(p.split(/[\\/]/).pop() ?? p))) {
            return rule.apix;
        }
    }
    return null;
}
