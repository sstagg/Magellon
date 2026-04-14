import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
    site: 'https://magellon.org',
    integrations: [
        starlight({
            title: 'Magellon',
            description: 'Software for cryo-EM data visualization and analysis — easy to install, flexible, and easily extensible.',
            logo: {
                src: './src/assets/magellon-logo.svg',
                replacesTitle: false,
            },
            favicon: '/favicon.svg',
            social: [
                { icon: 'github', label: 'GitHub', href: 'https://github.com/sstagg/Magellon' },
                { icon: 'external', label: 'CryoSift', href: 'https://www.cryosift.org' },
            ],
            sidebar: [
                {
                    label: 'Introduction',
                    items: [
                        { label: 'Welcome', link: '/' },
                        { label: 'Overview', slug: 'docs/getting-started/overview' },
                        { label: 'Demo', slug: 'docs/getting-started/demo' },
                    ],
                },
                {
                    label: 'Installation',
                    items: [
                        { label: 'Quick Start', slug: 'docs/getting-started/quick-start' },
                        { label: 'Full Install Guide', slug: 'docs/getting-started/installation' },
                        { label: 'Docker Setup', slug: 'docs/docker/setup' },
                        { label: 'Container Management', slug: 'docs/docker/containers' },
                    ],
                },
                {
                    label: 'Configuration',
                    items: [
                        { label: 'Directory Structure', slug: 'docs/configuration/directory-structure' },
                        { label: 'Environment Settings', slug: 'docs/configuration/environment' },
                        { label: 'Advanced Configuration', slug: 'docs/configuration/advanced' },
                    ],
                },
                {
                    label: 'Using Magellon',
                    items: [
                        { label: 'Data Import', slug: 'docs/usage/data-import' },
                        { label: 'Data Visualization', slug: 'docs/usage/visualization' },
                        { label: 'Plugins', slug: 'docs/usage/plugins' },
                    ],
                },
                {
                    label: 'Community',
                    items: [
                        { label: 'Community Hub', slug: 'docs/community' },
                        { label: 'Source Code', link: 'https://github.com/sstagg/Magellon', attrs: { target: '_blank', rel: 'noopener' } },
                        { label: 'Discussion Group', link: 'https://www.magellon.org/groups', attrs: { target: '_blank', rel: 'noopener' } },
                        { label: 'CryoSift', link: 'https://www.cryosift.org', attrs: { target: '_blank', rel: 'noopener' } },
                    ],
                },
            ],
            customCss: ['./src/styles/custom.css'],
            lastUpdated: true,
            editLink: {
                baseUrl: 'https://github.com/sstagg/Magellon/edit/main/website/',
            },
        }),
    ],
});
