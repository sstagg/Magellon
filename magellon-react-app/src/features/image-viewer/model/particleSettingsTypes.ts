import type { ComponentProps } from 'react';
import type { SchemaForm } from '../../../shared/ui/SchemaForm.tsx';
import type { PickDispatchResponse, Point } from '../lib/useParticleOperations.ts';

// ---------------------------------------------------------------------------
// Types shared by the particle-settings panel, its sub-components and hooks
// ---------------------------------------------------------------------------

export interface BackendInfo {
    backend_id: string;
    plugin_id: string;
    label: string;
    capabilities: string[];
    has_preview: boolean;
    has_sync: boolean;
    http_endpoint: string | null;
    status: string;
    enabled: boolean;
}

export type DrawerState = 'configure' | 'previewing' | 'preview' | 'running' | 'dispatched' | 'results';

/** The JSON-schema shape consumed by the embedded SchemaForm. */
export type ParamSchema = ComponentProps<typeof SchemaForm>['schema'];

/** A single particle as returned by a picker backend. */
export interface BackendPick {
    x: number;
    y: number;
    score?: number;
    radius?: number;
}

/** Session model returned by the train endpoint. */
export interface TrainedModel {
    engine_opts?: Record<string, unknown>;
    preview_id?: string | null;
}

export interface ParticleSettingsDrawerProps {
    open: boolean;
    pickerParams: Record<string, unknown>;
    onPickerParamsChange: (params: Record<string, unknown>) => void;
    onRun: () => void;
    /** Dispatch a picking task via RMQ for the given backend and IPP name. */
    onDispatch: (targetBackend: string, ippName: string) => Promise<PickDispatchResponse | null>;
    /** Opens the batch-run modal so the user can pick the cohort of images. */
    onRunBatch?: () => void;
    isRunning: boolean;
    onPreviewParticles: (particles: Point[]) => void;
    onAcceptParticles: () => void;
    onDiscardParticles: () => void;
    imageName: string | null;
    /** Session of the selected image — lets the backend resolve the MRC path. */
    sessionName?: string;
    autoPickingProgress: number;
    resultCount: number | null;
    /** Optional IPP name for the run — used as the RMQ task label. */
    ippName?: string;
    /** Current count of particles loaded on the canvas. Used to populate
     *  the dispatch-flow results card. */
    currentParticleCount?: number;
    /** Current canvas particles, used as session-local Topaz annotations. */
    currentParticles?: Point[];
}
