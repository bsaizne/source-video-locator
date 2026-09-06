<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue?: string
    disabled?: boolean
    placeholder?: string
  }>(),
  { modelValue: '', disabled: false, placeholder: '' },
)
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

function onChange(ev: Event): void {
  emit('update:modelValue', (ev.target as HTMLSelectElement).value)
}
</script>

<template>
  <select class="sel" :value="modelValue" :disabled="disabled" @change="onChange">
    <option v-if="placeholder" value="" disabled hidden>{{ placeholder }}</option>
    <slot />
  </select>
</template>

<style scoped>
.sel {
  height: 32px;
  width: 100%;
  padding: 0 30px 0 12px;
  border-radius: var(--radius-s);
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  color: var(--fg);
  font-family: inherit;
  font-size: var(--fs-sm);
  appearance: none;
  cursor: pointer;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239e9e9e' stroke-width='2' stroke-linecap='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;
}
.sel:focus { border-color: var(--accent); outline: none; box-shadow: 0 0 0 1px var(--focus-ring); }
</style>
