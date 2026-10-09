<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Conversation } from '../../lib/chat/conversations'

const props = defineProps<{
  conversation: Conversation | null
  removeConversation: (id: string) => void | Promise<void>
  returnFocus?: HTMLElement | null
}>()
const open = defineModel<boolean>('open', { required: true })
const pending = ref(false)
const error = ref<string | null>(null)
const cancel = ref<{ $el: HTMLButtonElement } | null>(null)
const description = computed(() => `Dadurch wird ${props.conversation?.title ?? ''} endgültig gelöscht. Dieser Vorgang kann nicht rückgängig gemacht werden.`)

watch(open, () => { error.value = null })

function initialFocus(event: Event): void {
  event.preventDefault()
  cancel.value?.$el.focus()
}

function restoreFocus(event: Event): void {
  event.preventDefault()
  // Mobile drawers and deleted rows can remove the original menu trigger.
  const trigger = props.returnFocus
  if (trigger?.isConnected && !trigger.closest('[inert]')) trigger.focus()
  else document.querySelector<HTMLElement>('#chat-main')?.focus()
}

// Reka supplies the title/description IDs and focus trap; this pinned version
// does not add aria-modal to DialogContent itself.
const modalContent = { 'aria-modal': true, onOpenAutoFocus: initialFocus, onCloseAutoFocus: restoreFocus }

function updateOpen(value: boolean): void {
  if (!pending.value) open.value = value
}

async function confirmDelete(): Promise<void> {
  const id = props.conversation?.id
  if (!open.value || !id || pending.value) return
  pending.value = true
  error.value = null
  try {
    await props.removeConversation(id)
    open.value = false
  }
  catch {
    error.value = 'Der Chat konnte nicht gelöscht werden. Bitte versuche es erneut.'
  }
  finally {
    pending.value = false
  }
}
</script>

<template>
  <UModal
    :open="open" title="Chat löschen?" :description="description"
    :dismissible="!pending" :close="{ disabled: pending }"
    :content="modalContent"
    :ui="{
      overlay: () => 'delete-dialog-overlay', content: () => 'delete-dialog',
      header: () => 'delete-dialog-header', wrapper: () => 'delete-dialog-copy',
      title: () => 'delete-dialog-title', description: () => 'delete-dialog-description',
      close: () => 'delete-dialog-close', body: () => 'delete-dialog-body', footer: () => 'delete-dialog-footer',
    }"
    @update:open="updateOpen"
  >
    <template #close>
      <UButton icon="i-lucide-x" color="neutral" variant="ghost" aria-label="Dialog schließen" class="delete-dialog-close" :disabled="pending" />
    </template>
    <template v-if="error" #body>
      <p role="alert" class="delete-dialog-error">{{ error }}</p>
    </template>
    <template #footer="{ close }">
      <UButton ref="cancel" color="neutral" variant="soft" label="Abbrechen" class="delete-dialog-button delete-dialog-cancel" :disabled="pending" @click="close" />
      <UButton color="error" variant="soft" label="Chat löschen" class="delete-dialog-button delete-dialog-confirm" :loading="pending" :disabled="pending || !conversation" @click="confirmDelete" />
    </template>
  </UModal>
</template>

<style>
/* Dialog-only theme tokens: no changes to the shell or its global tokens. */
.delete-dialog {
  --delete-surface: #fff;
  --delete-cancel-bg: #f4f4f4;
  --delete-cancel-hover: #eaeaea;
  --delete-danger-bg: #fce8e8;
  --delete-danger-hover: #fae0e0;
  --delete-danger-text: #c52222;
  position: fixed;
  z-index: 70;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: min(485px, calc(100vw - 32px - 2 * max(env(safe-area-inset-left), env(safe-area-inset-right))));
  max-height: calc(100dvh - 32px - 2 * max(env(safe-area-inset-top), env(safe-area-inset-bottom)));
  overflow-y: auto;
  padding: 24px;
  border: 0;
  border-radius: 26px;
  background: var(--delete-surface);
  color: var(--noris-text-primary);
  box-shadow: 0 8px 32px #00000014;
}
.dark .delete-dialog {
  --delete-surface: #303030;
  --delete-cancel-bg: #3d3d3d;
  --delete-cancel-hover: #484848;
  --delete-danger-bg: #512c2c;
  --delete-danger-hover: #613131;
  --delete-danger-text: #ffaaaa;
}
.delete-dialog-overlay { position: fixed; inset: 0; z-index: 60; background: #00000059; }
.delete-dialog-header, .delete-dialog-copy { display: block; }
.delete-dialog-title { margin: 0 36px 14px 0; font-size: 24px; line-height: 30px; font-weight: 600; }
.delete-dialog-description { margin: 0; color: var(--noris-text-secondary); font-size: 18px; line-height: 26px; overflow-wrap: anywhere; }
.delete-dialog-close { position: absolute; top: 12px; right: 12px; display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; padding: 0; border-radius: 50%; color: var(--noris-text-primary); background: transparent; }
.delete-dialog-close:hover:not(:disabled) { background: var(--delete-cancel-bg); }
.delete-dialog-close > span { width: 20px; height: 20px; }
.delete-dialog-body { margin-top: 16px; }
.delete-dialog-error { margin: 0; font-size: 14px; line-height: 20px; color: var(--delete-danger-text); }
.delete-dialog-footer { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; margin-top: 24px; }
.delete-dialog-button { display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; min-height: 44px; padding: 10px 18px; border: 1px solid transparent; border-radius: 9999px; font-size: 14px; line-height: 22px; font-weight: 500; transition: background-color 100ms, opacity 100ms; }
.delete-dialog-cancel { border-color: var(--noris-border); color: var(--noris-text-primary); background: var(--delete-cancel-bg); }
.delete-dialog-cancel:hover:not(:disabled) { background: var(--delete-cancel-hover); }
.delete-dialog-confirm { color: var(--delete-danger-text); background: var(--delete-danger-bg); }
.delete-dialog-confirm:hover:not(:disabled) { background: var(--delete-danger-hover); }
.delete-dialog-button:active:not(:disabled) { filter: brightness(0.96); }
.delete-dialog-button:focus-visible, .delete-dialog-close:focus-visible { outline: 2px solid var(--noris-text-primary); outline-offset: 3px; }
.delete-dialog-button:disabled, .delete-dialog-close:disabled { opacity: 0.5; cursor: not-allowed; }
@media (prefers-reduced-motion: no-preference) {
  .delete-dialog[data-state="open"], .delete-dialog-overlay[data-state="open"] { animation: delete-dialog-fade 140ms ease-out; }
  .delete-dialog[data-state="closed"], .delete-dialog-overlay[data-state="closed"] { animation: delete-dialog-fade 100ms ease-in reverse; }
}
@keyframes delete-dialog-fade { from { opacity: 0; } to { opacity: 1; } }
</style>
