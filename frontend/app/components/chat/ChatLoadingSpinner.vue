<template>
  <div class="chat-loading-region" role="status" aria-label="Chat wird geladen">
    <span class="chat-loading-spinner" aria-hidden="true">
      <svg class="chat-loading-ring" viewBox="0 0 20 20" fill="none">
        <circle class="chat-loading-track" cx="10" cy="10" r="8.75" />
        <circle class="chat-loading-arc" cx="10" cy="10" r="8.75" pathLength="100" stroke-dasharray="75 25" transform="rotate(-180 10 10)" />
      </svg>
    </span>
  </div>
</template>

<style scoped>
.chat-loading-region {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  pointer-events: none;
}
.chat-loading-spinner { display: block; width: 20px; height: 20px; }
.chat-loading-ring {
  display: block;
  width: 100%;
  height: 100%;
  stroke-width: 2.5px;
  animation: chat-loading-rotate 900ms linear infinite;
}
.chat-loading-track { stroke: #ccc; }
.chat-loading-arc { stroke: #5d5d5d; }
:global(.dark) .chat-loading-track { stroke: rgb(255 255 255 / 20%); }
:global(.dark) .chat-loading-arc { stroke: #bdbdbd; }
@keyframes chat-loading-rotate { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
  .chat-loading-ring { animation: none; }
}
</style>
