import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://houfu.github.io/codraft',
  base: '/codraft',
  integrations: [
    starlight({
      title: 'Codraft',
      description: 'Document assembly tool for Claude Cowork',
      logo: {
        src: './src/assets/logo.svg',
        replacesTitle: false,
      },
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/houfu/codraft' },
      ],
      customCss: ['./src/styles/custom.css'],
      sidebar: [
        {
          label: 'Start Here',
          items: [
            { label: 'Introduction', slug: 'start-here/introduction' },
            { label: 'Install', slug: 'start-here/install' },
          ],
        },
        {
          label: 'Quickstarts',
          items: [
            { label: 'Feature Tour', slug: 'quickstarts/feature-tour' },
            { label: 'Your First Template', slug: 'quickstarts/your-first-template' },
          ],
        },
        {
          label: 'Guides',
          items: [
            { label: 'Template Authoring', slug: 'guides/template-authoring' },
            { label: 'Variable Naming & Type Hints', slug: 'guides/variable-naming' },
            { label: 'Configuring with config.yaml', slug: 'guides/config-yaml' },
          ],
        },
        {
          label: 'Reference',
          items: [
            { label: 'Variable Type Reference', slug: 'reference/variable-types' },
            { label: 'Project Structure', slug: 'reference/project-structure' },
            { label: 'Roadmap', slug: 'reference/roadmap' },
          ],
        },
        { label: 'Changelog', slug: 'changelog' },
      ],
    }),
  ],
});
