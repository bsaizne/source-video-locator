import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'

// Hash history keeps the Electron file:// load happy without server rewrites.
const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: () => import('@/pages/HomePage.vue') },
  { path: '/projects', name: 'projects', component: () => import('@/pages/ProjectsPage.vue') },
  { path: '/projects/:id', name: 'project', component: () => import('@/pages/ProjectDetailPage.vue') },
  { path: '/analysis', name: 'analysis', component: () => import('@/pages/AnalysisPage.vue') },
  { path: '/results', name: 'results', component: () => import('@/pages/ResultsPage.vue') },
  { path: '/settings', name: 'settings', component: () => import('@/pages/SettingsPage.vue') },
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes,
})
