<script setup lang="ts">
import { computed } from 'vue'
import BaseIcon from './ui/BaseIcon.vue'

// Generic colored status chip for things like "Ready", "Building", "Invalid",
// "Unresolved", "Manual", "Montage", "Fallback".
type Tone = 'ok' | 'warn' | 'err' | 'info' | 'muted' | 'accent'

const props = withDefaults(defineProps<{ label: string; tone?: Tone; icon?: string }>(), {
  tone: 'muted',
  icon: undefined,
})
const toneClass = computed(() => `sb--${props.tone}`)
</script>

<template>
  <span class="sb" :class="toneClass">
    <BaseIcon v-if="icon" :name="icon" :size="12" />
    {{ label }}
  </span>
</template>

<style scoped>
.sb {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 9px;
  border-radius: var(--radius-pill);
  font-size: var(--fs-2xs);
  font-weight: 500;
  border: 1px solid currentColor;
  white-space: nowrap;
}
.sb--ok { color: var(--ok); }
.sb--warn { color: var(--warn); }
.sb--err { color: var(--err); }
.sb--info { color: var(--info); }
.sb--accent { color: var(--accent-glow); }
.sb--muted { color: var(--fg-muted); }
</style>
