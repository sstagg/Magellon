import { useEffect, useState } from 'react';
import { TEMPLATE_PICKER_PATH } from '../lib/useParticleOperations.ts';
import { API_URL, schemaDefaults } from './particleSettingsCore.ts';
import type { ParamSchema, TrainedModel } from './particleSettingsTypes.ts';

interface UsePickerSchemaArgs {
    open: boolean;
    selectedBackend: string;
    onPickerParamsChange: (params: Record<string, unknown> | ((prev: Record<string, unknown>) => Record<string, unknown>)) => void;
    /** Clears any session-trained model when a fresh schema loads. */
    setTrainedModel: (model: TrainedModel | null) => void;
}

/** Input-schema fetch for the selected picker backend. */
export function usePickerSchema({ open, selectedBackend, onPickerParamsChange, setTrainedModel }: UsePickerSchemaArgs) {
    const [schema, setSchema] = useState<ParamSchema | null>(null);
    const [schemaLoading, setSchemaLoading] = useState(false);
    const [schemaError, setSchemaError] = useState<string | null>(null);

    // Fetch schema (re-fetch when backend changes)
    useEffect(() => {
        if (!open) return;
        setSchema(null);
        setSchemaLoading(true);
        setTrainedModel(null);
        const url = `${API_URL}${TEMPLATE_PICKER_PATH}/schema/input?backend=${encodeURIComponent(selectedBackend)}`;
        const token = localStorage.getItem('access_token');
        const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
        fetch(url, { headers: authHeaders })
            .then((res) => { if (!res.ok) throw new Error(`${res.status}`); return res.json(); })
            .then((data) => {
                setSchema(data);
                setSchemaError(null);
                const defaults = schemaDefaults(data);
                if (selectedBackend.replace('_', '-').toLowerCase().includes('topaz')) {
                    const topazDefaults = {
                        ...defaults,
                        model: defaults.model ?? 'resnet16',
                        threshold: defaults.threshold ?? -3.0,
                        radius: defaults.radius ?? 14,
                        scale: defaults.scale ?? 8,
                    };
                    // Merge: schema defaults fill missing fields, existing user values win.
                    onPickerParamsChange((prev) => ({ ...topazDefaults, ...prev }));
                } else {
                    // Merge: schema defaults fill missing fields, existing user values win.
                    // This preserves user-added template_paths across image navigation and
                    // panel remounts caused by setContent firing when selectedImage changes.
                    onPickerParamsChange((prev) => ({ ...defaults, ...prev }));
                }
            })
            .catch((err) => setSchemaError(`Could not load: ${err.message}`))
            .finally(() => setSchemaLoading(false));
    }, [open, selectedBackend]); // eslint-disable-line react-hooks/exhaustive-deps

    /** Hide the current schema immediately (e.g. while switching backends). */
    const resetSchema = () => setSchema(null);

    return { schema, schemaLoading, schemaError, resetSchema };
}
