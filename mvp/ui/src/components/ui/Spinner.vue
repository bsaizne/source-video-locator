<script setup lang="ts">
withDefaults(defineProps<{ size?: number; color?: string }>(), { size: 18, color: 'var(--accent-glow)' })
</script>

<template>
  <span class="spin" :style="{ width: size + 'px', height: size + 'px', borderTopColor: color }" />
</template>

<style scoped>
.spin {
  display: inline-block;
  border-radius: 50%;
  border: 2px solid transparent;
  border-top-color: var(--accent-glow);
  animation: spins 0.7s linear infinite;
}
@keyframes spins { to { transform: rotate(360deg); } }
</style>
