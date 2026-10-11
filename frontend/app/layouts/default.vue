<script setup lang="ts">
import ChatWorkspace from '../components/chat/ChatWorkspace.vue'
useHead({ bodyAttrs: { class: 'chat-body' } })
</script>

<template>
  <ChatWorkspace><slot /></ChatWorkspace>
</template>
