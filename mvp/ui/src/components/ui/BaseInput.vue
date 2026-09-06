<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue?: string
    placeholder?: string
    disabled?: boolean
    type?: string
  }>(),
  { modelValue: '', placeholder: '', disabled: false, type: 'text' },
)
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

function onInput(ev: Event): void {
  emit('update:modelValue', (ev.target as HTMLInputElement).value)
}
</script>

<template>
  <input
    class="inp"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :type="type"
    @input="onInput"
  />
</template>

<style scoped>
.inp {
  height: 32px;
  width: 100%;
  padding: 0 12px;
  border-radius: var(--radius-s);
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  color: var(--fg);
  font-family: inherit;
  font-size: var(--fs-sm);
  transition: border-color var(--motion-1), box-shadow var(--motion-1);
}
.inp::placeholder { color: var(--fg-faint); }
.inp:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--focus-ring);
  outline: none;
}
.inp:disabled { opacity: 0.5; }
</style>
