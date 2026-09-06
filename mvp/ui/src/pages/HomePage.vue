<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectsStore } from '@/stores/projects'
import { useSessionStore } from '@/stores/session'
import ProjectCard from '@/components/ProjectCard.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseIcon from '@/components/ui/BaseIcon.vue'

const router = useRouter()
const projects = useProjectsStore()
const session = useSessionStore()

const recent = computed(() => projects.projects.slice(0, 6))

const backendLabel = computed(() => {
  if (session.connection === 'CONNECTED') return '已连接'
  if (session.connection === 'OFFLINE') return '离线'
  return '连接中'
})

function openProject(id: string): void {
  projects.selectProject(id)
  router.push(`/projects/${id}`)
}

function newProject(): void {
  const p = projects.addProject({ name: `未命名项目 ${projects.projects.length + 1}`, sourceVideo: 'movie.mkv' })
  router.push(`/projects/${p.id}`)
}

onMounted(() => {
  const source = projects.activeProject?.sourceVideo ?? 'Interstellar (2014).mkv'
  void session.refreshIndex(source)
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div class="hstack" style="justify-content: space-between">
        <div>
          <h1 class="page-title">首页</h1>
          <p class="page-subtitle">Video Locator AI · 在母片源中定位剪辑片段</p>
        </div>
        <BaseButton variant="primary" icon="plus" @click="newProject">新建项目</BaseButton>
      </div>
    </div>

    <div class="home__stats">
      <div class="stat">
        <span class="stat__k">后端</span>
        <span class="stat__v">{{ backendLabel }}</span>
      </div>
      <div class="stat">
        <span class="stat__k">项目</span>
        <span class="stat__v">{{ projects.projects.length }}</span>
      </div>
    </div>

    <div class="section-title" style="margin-top: 28px">最近项目</div>
    <div v-if="recent.length" class="home__grid">
      <ProjectCard v-for="p in recent" :key="p.id" :project="p" @open="openProject(p.id)" />
    </div>
    <div v-else class="home__empty">
      <BaseIcon name="folder" :size="36" />
      <p>还没有项目——创建一个吧。</p>
      <BaseButton variant="primary" @click="newProject">创建项目</BaseButton>
    </div>
  </div>
</template>

<style scoped>
.home__stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.stat {
  padding: 14px 16px; border-radius: var(--radius-m);
  background: var(--panel); border: 1px solid var(--border);
  display: flex; flex-direction: column; gap: 4px;
}
.stat__k { font-size: var(--fs-xs); color: var(--fg-faint); }
.stat__v { font-size: var(--fs-xl); font-weight: 600; }
.home__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
.home__empty { display: flex; flex-direction: column; align-items: center; gap: 14px; padding: 48px; color: var(--fg-faint); }
</style>
