<script setup lang="ts">
interface TabItem {
  key: string
  label: string
}

const props = defineProps<{ items: TabItem[]; modelValue: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()
</script>

<template>
  <div class="tabs" role="tablist">
    <button
      v-for="t in props.items"
      :key="t.key"
      class="tabs__item"
      :class="{ 'tabs__item--active': t.key === props.modelValue }"
      role="tab"
      :aria-selected="t.key === props.modelValue"
      @click="emit('update:modelValue', t.key)"
    >
      {{ t.label }}
    </button>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: 2px;
  border-bottom: 1px solid var(--divider);
}
.tabs__item {
  padding: 8px 14px;
  border: none;
  background: transparent;
  color: var(--fg-muted);
  font-family: inherit;
  font-size: var(--fs-sm);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color var(--motion-1), border-color var(--motion-1);
}
.tabs__item:hover { color: var(--fg); }
.tabs__item--active {
  color: var(--accent-glow);
  border-bottom-color: var(--accent);
}
</style>
