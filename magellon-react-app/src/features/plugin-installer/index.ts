/**
 * v1 admin plugin install pipeline (P3-P7 in
 * Documentation/PLUGIN_INSTALL_PLAN.md).
 *
 * Dialogs + panel for uploading `.mpn` archives, upgrading installs,
 * and uninstalling. Backed by the Administrator-gated REST endpoints
 * under `/admin/plugins/*`.
 *
 * Distinct from `features/plugin-runner/` which exposes the
 * runtime/dispatch surface (forms, schemas, browse-and-run).
 */
export { AdminInstalledPanel } from './ui/AdminInstalledPanel.tsx';
export { InstallMpnDialog } from './ui/InstallMpnDialog.tsx';
export { UpgradeMpnDialog } from './ui/UpgradeMpnDialog.tsx';
export {
    useAdminInstalledPlugins,
    useInstallMpn,
    useUninstallMpn,
    useUpgradeMpn,
} from './api/installerApi.ts';
export type {
    InstallResponse,
    InstalledListResponse,
    InstalledPlugin,
    UninstallResponse,
} from './api/installerApi.ts';
