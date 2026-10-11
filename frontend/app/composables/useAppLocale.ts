import { computed, inject, onMounted, provide, ref, watch } from 'vue'
import type { InjectionKey } from 'vue'
import { resolveLanguage, translate } from '../lib/settings/messages'
import type { LanguagePreference, MessageKey } from '../lib/settings/messages'

export function createAppLocale() {
  const preference = ref<LanguagePreference>('auto')
  const browserLanguage = ref('de')
  const language = computed(() => resolveLanguage(preference.value, browserLanguage.value))
  const storageError = ref(false)
  onMounted(() => {
    browserLanguage.value = navigator.language
    try {
      const saved = localStorage.getItem('noris-ai:language')
      if (saved === 'auto' || saved === 'de' || saved === 'en') preference.value = saved
    }
    catch { storageError.value = true }
    watch(preference, value => {
      try { localStorage.setItem('noris-ai:language', value); storageError.value = false }
      catch { storageError.value = true }
    })
  })
  return { preference, language, storageError, t: (key: MessageKey) => translate(key, language.value) }
}
type AppLocale = ReturnType<typeof createAppLocale>
export const appLocaleKey: InjectionKey<AppLocale> = Symbol('app-locale')
export function provideAppLocale() {
  const locale = createAppLocale()
  provide(appLocaleKey, locale)
  return locale
}
export function useAppLocale(): AppLocale {
  // Isolated component tests and consumers outside UApp retain the German default.
  return inject(appLocaleKey) ?? { preference: ref('de'), language: computed(() => 'de'), storageError: ref(false), t: key => translate(key, 'de') }
}
