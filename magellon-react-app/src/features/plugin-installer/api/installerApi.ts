/**
 * React-query hooks for the v1 admin install pipeline (`/admin/plugins/*`).
 *
 * The legacy v0 catalog/install flow lives in
 * `features/plugin-runner/api/PluginApi.ts`; this module is the
 * Administrator surface for the new `.mpn` archive pipeline (P3-P7
 * in `Documentation/PLUGIN_INSTALL_PLAN.md`). They coexist during
 * the transition; choose by intent:
 *
 *   - want to install a packed v1 `.mpn` (recommended) → here
 *   - want to push to a CoreService-local catalog of v0 archives
 *     → `useUploadCatalog` etc. in PluginApi.ts
 *
 * Backed by `controllers/admin_plugin_install_controller.py`.
 * Every call is Casbin-gated; the server returns 403 for non-Admins.
 */
import { useMutation, useQuery, useQueryClient } from 'react-query';
import getAxiosClient from '../../../shared/api/AxiosClient.ts';
import { settings } from '../../../shared/config/settings.ts';

const api = getAxiosClient(settings.ConfigData.SERVER_API_URL);

// ---------------------------------------------------------------------------
// Types — mirror the FastAPI response models in
// admin_plugin_install_controller.py.
// ---------------------------------------------------------------------------

export interface InstallResponse {
    success: boolean;
    plugin_id: string;
    install_method: string;
    install_dir: string | null;
    pid: number | null;
    error: string | null;
    /** Captured stdout+stderr from the install pipeline. Long but
     * worth surfacing in the UI when an install fails — the operator
     * shouldn't have to ssh into the box to find out why uv blew up. */
    logs: string | null;
}

export interface UninstallResponse {
    success: boolean;
    plugin_id: string;
    error: string | null;
}

export interface InstalledPlugin {
    plugin_id: string;
    install_method: string;
}

export interface InstalledListResponse {
    installed: InstalledPlugin[];
}

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

const QK_ADMIN_INSTALLED = ['admin', 'plugins', 'installed'] as const;

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * GET /admin/plugins/installed — list of installed plugins via the
 * v1 pipeline. Returned list is server-sorted (controller sorts on
 * the way out so the UI doesn't have to).
 *
 * Positional-args form for react-query v3 — same shape as the
 * project's other hooks (e.g. `usePlugins` in plugin-runner/api).
 * v4's object form silently no-ops here.
 */
export const useAdminInstalledPlugins = () =>
    useQuery(
        QK_ADMIN_INSTALLED,
        async () => {
            const res = await api.get<InstalledListResponse>('/admin/plugins/installed');
            return res.data.installed;
        },
    );

/**
 * POST /admin/plugins/install — multipart upload of a `.mpn`.
 *
 * The mutation rejects on any non-2xx response so the UI can render
 * `error.response?.data?.detail` directly. 409 = already installed
 * (suggest upgrade), 400 = archive invalid, 422 = host can't run it,
 * 500 = unexpected — the controller maps each consistently.
 */
export const useInstallMpn = () => {
    const qc = useQueryClient();
    return useMutation(
        async (file: File) => {
            const form = new FormData();
            form.append('file', file);
            const res = await api.post<InstallResponse>(
                '/admin/plugins/install',
                form,
                { headers: { 'Content-Type': 'multipart/form-data' } },
            );
            return res.data;
        },
        {
            onSuccess: () => {
                // The new install adds a row to /installed; also nudges
                // the runtime plugin list once the new plugin announces.
                qc.invalidateQueries(QK_ADMIN_INSTALLED);
                qc.invalidateQueries(['plugins']);
            },
        },
    );
};

/**
 * POST /admin/plugins/{plugin_id}/upgrade — multipart upload + force
 * flag. Default `forceDowngrade=false` matches the controller's
 * default; pass `true` to roll back across plugin boundaries.
 */
export const useUpgradeMpn = () => {
    const qc = useQueryClient();
    return useMutation(
        async (args: { pluginId: string; file: File; forceDowngrade?: boolean }) => {
            const form = new FormData();
            form.append('file', args.file);
            if (args.forceDowngrade) {
                form.append('force_downgrade', 'true');
            }
            const res = await api.post<InstallResponse>(
                `/admin/plugins/${encodeURIComponent(args.pluginId)}/upgrade`,
                form,
                { headers: { 'Content-Type': 'multipart/form-data' } },
            );
            return res.data;
        },
        {
            onSuccess: () => {
                qc.invalidateQueries(QK_ADMIN_INSTALLED);
                qc.invalidateQueries(['plugins']);
            },
        },
    );
};

/**
 * DELETE /admin/plugins/{plugin_id} — uninstall.
 *
 * No upgrade rollback here — that's a separate explicit operation
 * (operator runs upgrade with the `.bak`'s archive). Plain uninstall
 * stops the container/process and removes the install dir.
 */
export const useUninstallMpn = () => {
    const qc = useQueryClient();
    return useMutation(
        async (pluginId: string) => {
            const res = await api.delete<UninstallResponse>(
                `/admin/plugins/${encodeURIComponent(pluginId)}`,
            );
            return res.data;
        },
        {
            onSuccess: () => {
                qc.invalidateQueries(QK_ADMIN_INSTALLED);
                qc.invalidateQueries(['plugins']);
            },
        },
    );
};
