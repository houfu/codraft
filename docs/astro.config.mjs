import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
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
            { label: 'Getting Started', slug: 'getting-started' },
          ],
        },
        {
          label: 'Guides',
          items: [
            { label: 'Template Authoring', slug: 'template-authoring' },
            {
              label: 'Examples',
              items: [
                { label: 'NDA Walkthrough', slug: 'examples/nda-walkthrough' },
              ],
            },
          ],
        },
        {
          label: 'Reference',
          items: [
            { label: 'Variable Naming', slug: 'reference/variable-naming' },
            { label: 'Project Structure', slug: 'reference/project-structure' },
            { label: 'MVP Scope', slug: 'reference/mvp-scope' },
          ],
        },
        { label: 'Changelog', slug: 'changelog' },
      ],
    }),
  ],
});
