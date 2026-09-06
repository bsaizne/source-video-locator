<script setup lang="ts">
import { computed } from 'vue'
import BaseIcon from './BaseIcon.vue'

const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'subtle' | 'ghost' | 'danger'
    size?: 'sm' | 'md' | 'lg'
    icon?: string
    loading?: boolean
    disabled?: boolean
    block?: boolean
  }>(),
  { variant: 'subtle', size: 'md', icon: undefined, loading: false, disabled: false, block: false },
)

const emit = defineEmits<{ (e: 'click', ev: MouseEvent): void }>()

const classes = computed(() => [
  `btn`,
  `btn--${props.variant}`,
  `btn--${props.size}`,
  { 'btn--block': props.block },
])

function onClick(ev: MouseEvent): void {
  if (props.disabled || props.loading) return
  emit('click', ev)
}
</script>

<template>
  <button :class="classes" :disabled="disabled || loading" @click="onClick">
    <span v-if="loading" class="btn__spinner" />
    <BaseIcon v-else-if="icon" :name="icon" :size="size === 'sm' ? 14 : 16" />
    <slot />
  </button>
</template>

<style scoped>
.btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid transparent;
  border-radius: var(--radius-s);
  font-family: inherit;
  font-weight: 500;
  color: var(--fg);
  cursor: pointer;
  transition: background var(--motion-1), border-color var(--motion-1), color var(--motion-1);
  user-select: none;
  white-space: nowrap;
}
.btn--sm { height: 28px; padding: 0 10px; font-size: var(--fs-xs); }
.btn--md { height: 32px; padding: 0 14px; font-size: var(--fs-sm); }
.btn--lg { height: 40px; padding: 0 18px; font-size: var(--fs-md); }

.btn--primary { background: var(--accent); color: var(--fg-on-accent); }
.btn--primary:hover { background: var(--accent-hover); }
.btn--primary:active { background: var(--accent-active); }
.btn--primary:disabled { background: #3a3a3a; color: var(--fg-faint); }

.btn--subtle { background: var(--panel-2); border-color: var(--border); }
.btn--subtle:hover { background: var(--card-hover); border-color: var(--border-strong); }

.btn--ghost { background: transparent; color: var(--fg-muted); }
.btn--ghost:hover { background: rgba(255, 255, 255, 0.05); color: var(--fg); }

.btn--danger { background: rgba(245, 73, 61, 0.14); color: var(--conf-low); }
.btn--danger:hover { background: rgba(245, 73, 61, 0.24); }

.btn--block { width: 100%; justify-content: center; }

.btn__spinner {
  width: 13px;
  height: 13px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: btnspin 0.6s linear infinite;
}
@keyframes btnspin { to { transform: rotate(360deg); } }
</style>
