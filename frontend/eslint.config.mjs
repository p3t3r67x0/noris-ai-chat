import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt({
  ignores: ['app/types/generated/**', 'playwright-report/**', 'test-results/**'],
}, {
  rules: {
    '@typescript-eslint/no-explicit-any': 'error',
  },
})
