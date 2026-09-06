<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import BaseIcon from './ui/BaseIcon.vue'
import BackendStatusIndicator from './BackendStatusIndicator.vue'

const route = useRoute()
const session = useSessionStore()

const NAV = [
  { to: '/', label: '首页', icon: 'home' },
  { to: '/projects', label: '项目', icon: 'folder' },
  { to: '/analysis', label: '分析', icon: 'search' },
  { to: '/results', label: '结果', icon: 'compare' },
  { to: '/settings', label: '设置', icon: 'settings' },
]

function isActive(to: string): boolean {
  if (to === '/') return route.path === '/'
  return route.path.startsWith(to)
}
</script>

<template>
  <aside class="side">
    <div class="side__brand">
      <span class="side__logo"><BaseIcon name="layers" :size="18" /></span>
      <div class="side__brandtext">
        <div class="side__name">Video Locator</div>
        <div class="side__tag">AI</div>
      </div>
    </div>

    <nav class="side__nav">
      <button
        v-for="n in NAV"
        :key="n.to"
        class="side__item"
        :class="{ 'side__item--active': isActive(n.to) }"
        @click="$router.push(n.to)"
      >
        <BaseIcon :name="n.icon" :size="16" />
        <span>{{ n.label }}</span>
      </button>
    </nav>

    <div class="side__spacer" />
    <BackendStatusIndicator :backend="session.backend" :index-status="session.indexStatus" :connection="session.connection" />
  </aside>
</template>

<style scoped>
.side { display: flex; flex-direction: column; height: 100%; }
.side__brand { display: flex; align-items: center; gap: 10px; padding: 16px 18px; }
.side__logo {
  width: 34px; height: 34px; border-radius: var(--radius-m);
  background: linear-gradient(135deg, var(--accent), #2b74b8);
  color: #fff; display: flex; align-items: center; justify-content: center;
}
.side__brandtext { display: flex; align-items: baseline; gap: 5px; }
.side__name { font-size: var(--fs-md); font-weight: 600; }
.side__tag { font-size: var(--fs-2xs); color: var(--accent-glow); font-weight: 600; }
.side__nav { display: flex; flex-direction: column; gap: 2px; padding: 8px; }
.side__item {
  display: flex; align-items: center; gap: 11px;
  padding: 9px 12px; border: none; border-radius: var(--radius-s);
  background: transparent; color: var(--fg-muted); font-size: var(--fs-sm);
  font-family: inherit; cursor: pointer; text-align: left;
  transition: background var(--motion-1), color var(--motion-1);
}
.side__item:hover { background: var(--card); color: var(--fg); }
.side__item--active { background: var(--accent-soft); color: var(--accent-glow); }
.side__spacer { flex: 1; }
</style>
