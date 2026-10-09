export default defineNuxtConfig({
  compatibilityDate: '2026-10-08',
  devtools: { enabled: false },
  modules: ['@nuxt/eslint', '@nuxt/ui'],
  css: ['~/assets/css/main.css'],
  ui: { fonts: false },
  colorMode: { preference: 'system', fallback: 'light', storageKey: 'noris-ai-theme' },
  vite: {
    optimizeDeps: {
      // Prebundle lazy grammars too: discovering them after send would reload the dev page.
      include: [
        'markdown-it', 'shiki/core', 'shiki/engine/javascript',
        'shiki/themes/github-light.mjs', 'shiki/themes/github-dark.mjs',
        ...['python', 'javascript', 'typescript', 'json', 'bash', 'sql', 'css', 'html'].map(language => `shiki/langs/${language}.mjs`),
      ],
    },
  },
  icon: {
    provider: 'none',
    fallbackToApi: false,
    serverBundle: false,
    clientBundle: {
      scan: true,
      icons: [
        'lucide:menu', 'lucide:panel-left', 'lucide:panel-left-close', 'lucide:panel-left-open',
        'lucide:square-pen', 'lucide:search', 'lucide:chevron-down', 'lucide:chevron-up',
        'lucide:chevron-left', 'lucide:chevron-right', 'lucide:check', 'lucide:x',
        'lucide:moon', 'lucide:sun', 'lucide:monitor', 'lucide:ellipsis', 'lucide:pencil',
        'lucide:archive', 'lucide:trash-2', 'lucide:undo-2', 'lucide:settings', 'lucide:user',
        'lucide:arrow-up', 'lucide:arrow-down', 'lucide:copy', 'lucide:check-check',
        'lucide:rotate-ccw', 'lucide:square', 'lucide:plus', 'lucide:paperclip',
        'lucide:loader-circle', 'lucide:circle-alert', 'lucide:info', 'lucide:external-link',
        'lucide:sparkles', 'lucide:circle-check',
      ],
    },
  },
  app: {
    head: { title: 'noris AI', htmlAttrs: { lang: 'de' } },
  },
  typescript: {
    strict: true,
    tsConfig: {
      compilerOptions: {
        noUncheckedIndexedAccess: true,
        exactOptionalPropertyTypes: true,
      },
    },
  },
  nitro: {
    preset: 'node-server',
    devProxy: {
      '/api': {
        // Nitro removes the mount prefix before forwarding the request.
        target: new URL('/api', process.env.NORIS_DEV_API_TARGET ?? 'http://127.0.0.1:8000').href,
        changeOrigin: false,
      },
    },
  },
})
