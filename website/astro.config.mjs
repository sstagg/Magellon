import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
    site: 'https://magellon.org',
    output: 'static',
    integrations: [
        starlight({
            title: 'Magellon',
            description: 'Scientific imaging workflows — plugins, jobs, and data tools for cryo-EM pipelines.',
            logo: {
                src: './src/assets/magellon-mark.svg',
                replacesTitle: false,
            },
            social: [
                { icon: 'github', label: 'GitHub', href: 'https://github.com/sstagg/Magellon' },
            ],
            sidebar: [
                {
                    label: 'Getting Started',
                    items: [
                        { label: 'Overview', slug: 'getting-started/overview' },
                        { label: 'Installation', slug: 'getting-started/installation' },
                        { label: 'Quick Start', slug: 'getting-started/quick-start' },
                    ],
                },
                {
                    label: 'Configuration',
                    items: [
                        { label: 'Directory Structure', slug: 'configuration/directory-structure' },
                        { label: 'Environment Settings', slug: 'configuration/environment' },
                        { label: 'Advanced Configuration', slug: 'configuration/advanced' },
                    ],
                },
                {
                    label: 'Docker',
                    items: [
                        { label: 'Docker Setup', slug: 'docker/setup' },
                        { label: 'Container Management', slug: 'docker/containers' },
                    ],
                },
                {
                    label: 'Usage Guide',
                    items: [
                        { label: 'Data Import', slug: 'usage/data-import' },
                        { label: 'Data Visualization', slug: 'usage/visualization' },
                        { label: 'Plugins', slug: 'usage/plugins' },
                    ],
                },
            ],
            customCss: ['./src/styles/custom.css'],
        }),
    ],
});
