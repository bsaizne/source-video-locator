<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useProjectsStore } from '@/stores/projects'
import ProjectCard from '@/components/ProjectCard.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const router = useRouter()
const projects = useProjectsStore()

function open(id: string): void {
  projects.selectProject(id)
  router.push(`/projects/${id}`)
}

function create(): void {
  const p = projects.addProject({ name: `未命名项目 ${projects.projects.length + 1}`, sourceVideo: 'movie.mkv' })
  router.push(`/projects/${p.id}`)
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div class="hstack" style="justify-content: space-between">
        <div>
          <h1 class="page-title">项目</h1>
          <p class="page-subtitle">你的源片↔剪辑匹配项目</p>
        </div>
        <BaseButton variant="primary" icon="plus" @click="create">新建项目</BaseButton>
      </div>
    </div>
    <div class="pj__grid">
      <ProjectCard v-for="p in projects.projects" :key="p.id" :project="p" @open="open(p.id)" />
    </div>
  </div>
</template>

<style scoped>
.pj__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }
</style>
