/**
 * Plugin hub catalog client.
 *
 * Fetches the static `/v1/index.json` from the configured hub URL
 * (`HUB_URL` in configs.json — defaults to https://demo.magellon.org).
 * The hub is read-only public; no auth header. CORS is open on the
 * hub side (see public/_headers in the magellon-web repo) so the
 * browser can fetch directly without a CoreService proxy.
 *
 * Mirrors the response shape from
 * `magellon-web/src/pages/v1/index.json.ts`. Keep these aligned —
 * any new field on the hub side needs a matching field here before
 * the UI surfaces it.
 */
import { useQuery } from 'react-query';
import { settings } from '../../../shared/config/settings.ts';

export interface HubVersion {
    version: string;
    archive_id: string;
    /** Relative URL under the hub root, e.g. ``/assets/plugins/foo-1.0.mpn``.
     *  Prepend ``hubUrl()`` to get a fetchable absolute URL. */
    url: string;
    sha256: string;
    size_bytes: number;
    requires_sdk: string;
    published_at: string;
}

export interface HubPlugin {
    plugin_id: string;
    name: string;
    description: string;
    category: string;
    backend_id?: string;
    author: string;
    license: string;
    homepage?: string;
    tier: 'verified' | 'community';
    tags: string[];
    latest_version: string;
    versions: HubVersion[];
}

export interface HubIndex {
    schema_version: string;
    generated_at: string;
    plugins: HubPlugin[];
}

const QK_HUB_INDEX = ['hub', 'index'] as const;

/** Configured hub root URL — used to prepend relative archive URLs. */
export const hubUrl = (): string => {
    const raw = (settings.ConfigData as any).HUB_URL ?? 'https://demo.magellon.org';
    return raw.replace(/\/$/, ''); // no trailing slash so concat is clean
};

/** Build an absolute archive URL from a hub-relative path. */
export const archiveUrl = (relative: string): string =>
    relative.startsWith('http') ? relative : `${hubUrl()}${relative}`;

/**
 * GET <HUB_URL>/v1/index.json — the public catalog.
 *
 * Cached for 5 minutes (matches the hub's Cache-Control header). A
 * fresh refresh after install isn't important here — installing a
 * plugin doesn't change the hub catalog (the hub is published
 * separately via PR/CI).
 */
export const useHubIndex = () =>
    useQuery(
        QK_HUB_INDEX,
        async () => {
            const res = await fetch(`${hubUrl()}/v1/index.json`, {
                method: 'GET',
                // Don't send credentials — the hub is public read-only;
                // sending a CoreService cookie would be silly + a
                // potential leak.
                credentials: 'omit',
            });
            if (!res.ok) {
                throw new Error(`hub index fetch failed: ${res.status} ${res.statusText}`);
            }
            return (await res.json()) as HubIndex;
        },
        {
            staleTime: 5 * 60 * 1000,
        },
    );

/**
 * Download an .mpn from the hub as a File ready to upload to
 * CoreService's /admin/plugins/install endpoint. Verifies the
 * SHA256 client-side before handing the bytes back so a tampered
 * hub mirror or a wrong manifest hash surfaces immediately.
 */
export const downloadArchiveAsFile = async (
    plugin: HubPlugin,
    version: HubVersion,
): Promise<File> => {
    const url = archiveUrl(version.url);
    const res = await fetch(url, { credentials: 'omit' });
    if (!res.ok) {
        throw new Error(`archive download failed: ${res.status} ${res.statusText}`);
    }
    const buffer = await res.arrayBuffer();

    const digest = await crypto.subtle.digest('SHA-256', buffer);
    const actualSha = Array.from(new Uint8Array(digest))
        .map((b) => b.toString(16).padStart(2, '0'))
        .join('');
    if (actualSha !== version.sha256) {
        throw new Error(
            `SHA256 mismatch — hub manifest claims ${version.sha256} ` +
            `but downloaded bytes hash to ${actualSha}. Aborting.`,
        );
    }

    const filename = version.url.split('/').pop() ?? `${plugin.plugin_id}-${version.version}.mpn`;
    return new File([buffer], filename, {
        type: 'application/octet-stream',
    });
};
