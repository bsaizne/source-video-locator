<script setup lang="ts">
import { computed, onMounted } from 'vue'
import AppSidebar from '@/components/AppSidebar.vue'
import CommandPalette from '@/components/CommandPalette.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()

const initDone = computed(() => session.initState === 'READY')
const initFailed = computed(() => session.initState === 'FAILED')

onMounted(() => {
  // Drive the first-launch gate (backend + model) before showing Home.
  session.ensureSubscribed()
  void session.initApp()
})
</script>

<template>
  <!-- First-launch init gate (Phase 5) -->
  <div v-if="!initDone" class="gate">
    <div class="gate__card">
      <div class="gate__logo">Video Locator</div>
      <template v-if="initFailed">
        <div class="gate__title">AI 服务初始化失败</div>
        <p class="gate__msg">{{ session.initError }}</p>
        <BaseButton variant="primary" icon="refresh" @click="session.retryInit()">重试</BaseButton>
      </template>
      <template v-else>
        <div class="gate__title">
          {{ session.initState === 'CHECKING_MODEL' ? '检查 AI 模型…' : '正在初始化 AI 引擎' }}
        </div>
        <div class="gate__bar">
          <div class="gate__fill" :style="{ width: session.initProgress + '%' }" />
        </div>
        <div class="gate__pct mono">{{ session.initProgress }}%</div>
        <p class="gate__hint">请不要关闭程序</p>
      </template>
    </div>
  </div>

  <!-- Main app -->
  <div v-else class="app-shell">
    <div class="app-sidebar"><AppSidebar /></div>
    <main class="app-main"><router-view /></main>
    <CommandPalette />
  </div>
</template>

<style scoped>
.gate {
  position: fixed; inset: 0; z-index: 200;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg, #0e0e0e);
}
.gate__card {
  width: 360px; padding: 32px; border-radius: var(--radius-l);
  background: var(--panel, #161616); border: 1px solid var(--border, #242424);
  display: flex; flex-direction: column; align-items: center; gap: 14px; text-align: center;
}
.gate__logo { font-size: 20px; font-weight: 700; letter-spacing: 0.03em; }
.gate__title { font-size: var(--fs-md, 16px); font-weight: 600; }
.gate__msg { color: var(--fg-muted, #9e9e9e); font-size: var(--fs-sm, 14px); margin: 0; }
.gate__bar { width: 100%; height: 8px; border-radius: 999px; background: var(--border, #242424); overflow: hidden; }
.gate__fill { height: 100%; background: var(--accent, #4cc2ff); transition: width 0.3s ease; }
.gate__pct { color: var(--fg-muted, #9e9e9e); font-size: var(--fs-xs, 12px); }
.gate__hint { color: var(--fg-faint, #666); font-size: var(--fs-xs, 12px); margin: 0; }
</style>
