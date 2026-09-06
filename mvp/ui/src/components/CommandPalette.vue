<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseIcon from './ui/BaseIcon.vue'

interface Command {
  id: string
  label: string
  hint: string
  icon: string
  run: () => void
}

const router = useRouter()
const open = ref(false)
const query = ref('')
const activeIdx = ref(0)
const input = ref<HTMLInputElement | null>(null)

const baseCommands: Command[] = [
  { id: 'home', label: '前往首页', hint: '概览与最近项目', icon: 'home', run: () => router.push('/') },
  { id: 'projects', label: '前往项目', hint: '浏览项目', icon: 'folder', run: () => router.push('/projects') },
  { id: 'analysis', label: '开始分析', hint: '运行定位管线', icon: 'search', run: () => router.push('/analysis') },
  { id: 'results', label: '前往结果', hint: '复核匹配片段', icon: 'compare', run: () => router.push('/results') },
  { id: 'settings', label: '前往设置', hint: '应用与后端配置', icon: 'settings', run: () => router.push('/settings') },
]

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return baseCommands
  return baseCommands.filter((c) => `${c.label} ${c.hint}`.toLowerCase().includes(q))
})

watch(open, async (isOpen) => {
  if (isOpen) {
    query.value = ''
    activeIdx.value = 0
    await nextTick()
    input.value?.focus()
  }
})

function onKeydown(ev: KeyboardEvent): void {
  if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k') {
    ev.preventDefault()
    open.value = !open.value
    return
  }
  if (!open.value) return
  if (ev.key === 'Escape') {
    open.value = false
  } else if (ev.key === 'ArrowDown') {
    ev.preventDefault()
    activeIdx.value = Math.min(filtered.value.length - 1, activeIdx.value + 1)
  } else if (ev.key === 'ArrowUp') {
    ev.preventDefault()
    activeIdx.value = Math.max(0, activeIdx.value - 1)
  } else if (ev.key === 'Enter') {
    ev.preventDefault()
    const c = filtered.value[activeIdx.value]
    if (c) {
      open.value = false
      c.run()
    }
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

function run(cmd: Command): void {
  open.value = false
  cmd.run()
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="cp__mask" @click="open = false">
      <div class="cp" @click.stop>
        <div class="cp__bar">
          <BaseIcon name="search" :size="16" />
          <input ref="input" v-model="query" class="cp__input" placeholder="输入命令或搜索…" />
          <kbd class="cp__esc">ESC</kbd>
        </div>
        <ul class="cp__list">
          <li
            v-for="(c, i) in filtered"
            :key="c.id"
            class="cp__item"
            :class="{ 'cp__item--active': i === activeIdx }"
            @mouseenter="activeIdx = i"
            @click="run(c)"
          >
            <BaseIcon :name="c.icon" :size="16" />
            <span class="cp__label">{{ c.label }}</span>
            <span class="cp__hint faint">{{ c.hint }}</span>
          </li>
          <li v-if="filtered.length === 0" class="cp__empty">无匹配命令</li>
        </ul>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.cp__mask {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0, 0, 0, 0.5);
  display: flex; align-items: flex-start; justify-content: center;
  padding-top: 12vh;
  animation: fadein var(--motion-2);
}
.cp {
  width: 560px; max-width: 90vw;
  background: var(--panel);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-l);
  box-shadow: var(--shadow-l);
  overflow: hidden;
}
.cp__bar { display: flex; align-items: center; gap: 10px; padding: 14px 16px; border-bottom: 1px solid var(--divider); color: var(--fg-muted); }
.cp__input { flex: 1; border: none; background: transparent; color: var(--fg); font-size: var(--fs-md); outline: none; font-family: inherit; }
.cp__esc { font-size: 10px; color: var(--fg-faint); border: 1px solid var(--border-strong); border-radius: 4px; padding: 2px 6px; }
.cp__list { list-style: none; margin: 0; padding: 8px; max-height: 360px; overflow-y: auto; }
.cp__item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: var(--radius-s); cursor: pointer; color: var(--fg-muted); }
.cp__item--active { background: var(--accent-soft); color: var(--fg); }
.cp__label { font-size: var(--fs-sm); font-weight: 500; }
.cp__hint { font-size: var(--fs-xs); margin-left: auto; }
.cp__empty { padding: 20px; text-align: center; color: var(--fg-faint); font-size: var(--fs-sm); }
@keyframes fadein { from { opacity: 0; } to { opacity: 1; } }
</style>
