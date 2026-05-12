/**
 * Hooks for the ``GET /artifacts/{oid}/workflow.json`` endpoint
 * (PE3-lite, shipped 2026-05-10).
 *
 * The backend serialises the single-parent ancestor chain plus the
 * producer plugin metadata per node. The React side here renders that
 * chain and lets the operator re-submit a node's producing job with
 * the same params (CryoSPARC-style "clone with inputs").
 */
import { useMutation, useQuery } from 'react-query';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { settings } from '../../../shared/config/settings.ts';

const api = getAxiosClient(settings.ConfigData.SERVER_API_URL);


export interface WorkflowProducer {
    plugin_id: string;
    plugin_version: string;
    category: string;
    /** Concrete params dict. Secret-keyed values are redacted server-side
     *  to ``"<redacted>"``; replaying them produces the redacted value. */
    params: Record<string, unknown>;
}

export interface WorkflowNode {
    oid: string;
    kind: string;
    producer: WorkflowProducer | null;
    /** Present only on root nodes (imported data): ``"imported"`` etc. */
    source?: string;
}

export interface WorkflowExport {
    magellon_workflow_version: number;
    exported_at: string;
    /** Honest about the current single-parent shape. Changes to ``"dag"``
     *  if multi-input lineage lands later. */
    lineage_shape: string;
    root_artifact: WorkflowNode;
    ancestors: WorkflowNode[];
    /** ``null`` when the chain fit within the depth cap. */
    truncated_at_depth: number | null;
}


export const useArtifactWorkflow = (oid: string | null | undefined) =>
    useQuery(
        ['artifact-workflow', oid],
        async (): Promise<WorkflowExport> => {
            const res = await api.get<WorkflowExport>(
                `/artifacts/${encodeURIComponent(oid!)}/workflow.json`,
            );
            return res.data;
        },
        {
            enabled: !!oid,
            // Workflow JSON is effectively immutable per artifact OID —
            // artifacts are append-only (Artifact invariant rule 6).
            staleTime: Infinity,
        },
    );


export interface ReRunRequest {
    /** Producing plugin to call. Defaults to the same plugin_id the node
     *  recorded; operator may pick a sibling backend in the same category. */
    plugin_id: string;
    /** Params override. Sent verbatim to the existing
     *  ``POST /plugins/{plugin_id}/jobs`` endpoint. */
    input: Record<string, unknown>;
    /** Optional backend pin (Wave 5 axis). */
    target_backend?: string | null;
}


/**
 * Re-submit a producing job using the params recorded in workflow.json.
 *
 * Backed by the existing ``POST /plugins/{plugin_id}/jobs`` endpoint —
 * the workflow page does the legwork of pulling the params out of the
 * workflow JSON and posting them. No new backend endpoint needed.
 */
export const useReRunFromWorkflow = () =>
    useMutation(async (req: ReRunRequest) => {
        const res = await api.post(
            `/plugins/${encodeURIComponent(req.plugin_id)}/jobs`,
            {
                input: req.input,
                target_backend: req.target_backend ?? undefined,
            },
        );
        return res.data as { job_id: string };
    });
