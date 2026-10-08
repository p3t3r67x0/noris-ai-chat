import tailwindcss from '@tailwindcss/vite'

export default defineNuxtConfig({
  compatibilityDate: '2026-10-08',
  devtools: { enabled: false },
  modules: ['@nuxt/eslint'],
  css: ['~/assets/css/main.css'],
  vite: { plugins: [tailwindcss()] },
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
