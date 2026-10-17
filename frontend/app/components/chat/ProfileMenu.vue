<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import type { DropdownMenuItem } from '@nuxt/ui'
import { useAppLocale } from '../../composables/useAppLocale'
import { helpMenuItems } from '../../lib/settings/profileMenu'

const props = withDefaults(defineProps<{ demo?: boolean, compact?: boolean }>(), { demo: true, compact: true })
const { t } = useAppLocale()
const open = ref(false)
const helpScreen = ref(false)
const smallScreen = ref(false)
const trigger = ref<{ $el: HTMLElement } | null>(null)
const alignOffset = ref(0)
let media: MediaQueryList | undefined
let navigationMedia: MediaQueryList | undefined
let navigating = false
const menuElements = new Map<boolean, HTMLElement>()
function resize(): void { smallScreen.value = media?.matches ?? false; updateOpen(false) }
function closeAtBreakpoint(): void { updateOpen(false) }
onMounted(() => {
  media = window.matchMedia('(max-width: 639px)'); resize(); media.addEventListener('change', resize)
  navigationMedia = window.matchMedia('(max-width: 1023px)'); navigationMedia.addEventListener('change', closeAtBreakpoint)
})
onUnmounted(() => {
  media?.removeEventListener('change', resize); navigationMedia?.removeEventListener('change', closeAtBreakpoint)
  for (const element of menuElements.values()) element.removeEventListener('keydown', onMenuKeydown, true)
})
const identity = computed(() => props.demo ? t('demo') : t('singleOwner'))
const items = computed<DropdownMenuItem[][]>(() => {
  const help = helpMenuItems(t).map(item => ({ ...item, ...(!item.target ? { onSelect: () => { navigating = true } } : {}) }))
  if (smallScreen.value && helpScreen.value) return [[{
    label: t('back'), icon: 'i-lucide-arrow-left', onSelect: event => { event.preventDefault(); helpScreen.value = false; void focusFirst() },
  }], help]
  return [[{ label: t('settings'), icon: 'i-lucide-settings', to: '/settings/general', onSelect: () => { navigating = true } }], [{
    label: t('help'), icon: 'i-lucide-circle-help',
    ...(smallScreen.value ? { onSelect: (event: Event) => { event.preventDefault(); helpScreen.value = true; void focusFirst() } }
      : { children: help, content: submenuContent, ui: { content: 'profile-help-menu' } }),
  }]]
})
async function focusFirst(): Promise<void> {
  await nextTick()
  document.querySelector<HTMLElement>('.profile-menu:not(.profile-help-menu) [role="menuitem"]')?.focus()
}
function updateOpen(value: boolean): void {
  if (value) {
    navigating = false
    const button = trigger.value?.$el
    const rail = button?.closest('.chat-rail')
    alignOffset.value = rail && button ? Math.max(0, rail.getBoundingClientRect().right - button.getBoundingClientRect().left + 2) : 0
  }
  open.value = value
  if (!value) helpScreen.value = false
}
function onMenuKeydown(event: KeyboardEvent): void {
  if (event.key === 'Tab') { event.preventDefault(); event.stopPropagation(); updateOpen(false) }
  else if (smallScreen.value && helpScreen.value && event.key === 'ArrowLeft') {
    event.preventDefault(); helpScreen.value = false; void focusFirst()
  }
}
// Nuxt UI 4.11 forwards declared content events, but not native keydown attrs.
// Bind only the two owned portal elements; Reka keeps its arrow/hover handling.
function bindMenu(value: unknown, sub: boolean): void {
  menuElements.get(sub)?.removeEventListener('keydown', onMenuKeydown, true)
  menuElements.delete(sub)
  const element = value instanceof HTMLElement ? value.parentElement : null
  if (element) { element.addEventListener('keydown', onMenuKeydown, true); menuElements.set(sub, element) }
}
function closeAutoFocus(event: Event): void {
  event.preventDefault()
  if (navigating) requestAnimationFrame(() => document.getElementById('settings-heading')?.focus())
  else trigger.value?.$el.focus()
}
const content = computed(() => ({ side: 'top' as const, align: 'start' as const, alignOffset: alignOffset.value, sideOffset: 8, collisionPadding: 8, avoidCollisions: true, onCloseAutoFocus: closeAutoFocus }))
const submenuContent = { side: 'right' as const, sideOffset: 6, collisionPadding: 8, avoidCollisions: true }
</script>

<template>
  <UDropdownMenu
    :open="open" :items="items" :external-icon="false"
    :content="content"
    :ui="{ content: 'profile-menu', viewport: 'profile-menu-viewport', group: 'profile-menu-group', item: 'profile-menu-item', itemLeadingIcon: 'profile-menu-icon', itemTrailingIcon: 'profile-menu-icon', itemLabel: 'profile-menu-label' }"
    @update:open="updateOpen"
  >
    <UTooltip :text="demo ? t('localAccount') : t('account')" :disabled="!compact">
      <UButton ref="trigger" color="neutral" variant="ghost" :class="compact ? 'profile-trigger touch-control' : 'profile-trigger profile-trigger-wide'" :aria-label="demo ? t('localAccount') : t('account')">
        <UAvatar text="N" size="sm" class="profile-avatar" />
        <span v-if="!compact" class="profile-trigger-copy"><span>Noris AI</span><small>{{ identity }}</small></span>
      </UButton>
    </UTooltip>
    <template #content-top="{ sub }">
      <span v-if="sub" :ref="element => bindMenu(element, true)" class="sr-only" aria-hidden="true" />
      <div v-else :ref="element => bindMenu(element, false)" class="profile-menu-identity">
        <template v-if="helpScreen"><span>{{ t('help') }}</span></template>
        <template v-else>
          <UAvatar text="N" size="sm" class="profile-avatar" />
          <div><p>Noris AI</p><small>{{ identity }}</small></div>
        </template>
      </div>
    </template>
  </UDropdownMenu>
</template>
