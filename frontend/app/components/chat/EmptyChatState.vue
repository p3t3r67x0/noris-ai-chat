<template>
  <section class="empty-chat" aria-labelledby="welcome-title">
    <h1 id="welcome-title">Was möchtest du heute bewegen?</h1>
    <slot>
      <div class="composer-placeholder">
        <UTextarea disabled placeholder="Frag noris AI …" aria-label="Nachricht" variant="none" :rows="2" class="w-full" />
        <div class="flex items-center justify-between">
          <UButton disabled icon="i-lucide-plus" color="neutral" variant="ghost" class="touch-control" aria-label="Anhang hinzufügen" />
          <UButton disabled icon="i-lucide-arrow-up" color="neutral" class="touch-control rounded-full" aria-label="Nachricht senden" />
        </div>
      </div>
    </slot>
    <p class="mt-4 text-center text-xs text-muted">noris AI · Dein Raum für gute Fragen.</p>
  </section>
</template>
