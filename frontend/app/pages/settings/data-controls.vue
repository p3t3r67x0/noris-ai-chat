<script setup lang="ts">
import SettingsDialog from '../../components/settings/SettingsDialog.vue'
import { useWorkspace } from '../../composables/useWorkspace'
const { chat, importAvailable } = useWorkspace()
</script>

<template>
  <SettingsDialog :import-available="importAvailable" :import-ready="chat.backendReady.value" :import-busy="chat.importBusy.value" :import-local-chats="chat.importLocalChats" :import-feedback="chat.storageWarning.value" />
</template>
