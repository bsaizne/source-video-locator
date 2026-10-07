import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useService } from '@/services'
import type { BackendInfoJson, ConnectionStatus, DevicePreference, DeviceSettingsJson, IndexStatus } from '@/services'

// First-launch init lifecycle (Phase 5): the app shows a blocking init screen
// until the backend is reachable (and its model path validated), then enters Home.
export type InitState = 'INITIALIZING' | 'CHECKING_MODEL' | 'READY' | 'FAILED'

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

// Global session state: which backend is in use, how the index looks, and the
// latest progress event (subscribed once to the service). Shared by the
// sidebar (BackendStatusIndicator + index status) and the Inspector.
export const useSessionStore = defineStore('session', () => {
  const service = useService()

  const backend = ref<BackendInfoJson | null>(null)
  const indexStatus = ref<IndexStatus | null>(null)
  const lastStage = ref<string | null>(null)
  // Device backend settings (GET/POST /api/settings/device). null until first load.
  const deviceSettings = ref<DeviceSettingsJson | null>(null)
  // Backend reachability (GET /api/health). CONNECTED means the FastAPI bridge
  // answered ok; the Mock adapter always reports CONNECTED.
  const connection = ref<ConnectionStatus>('CONNECTING')
  const initState = ref<InitState>('INITIALIZING')
  const initProgress = ref(0)
  const initError = ref<string | null>(null)

  let subscribed = false
  function ensureSubscribed(): void {
    if (subscribed) return
    subscribed = true
    service.onProgress((ev) => {
      lastStage.value = ev.stage
    })
  }

  async function checkHealth(): Promise<void> {
    connection.value = 'CONNECTING'
    connection.value = await service.checkHealth()
  }

  // Drive the first-launch init screen: wait for backend reachability, mark the
  // model check, then READY. On persistent offline → FAILED (with retry).
  async function initApp(): Promise<void> {
    initState.value = 'INITIALIZING'
    initProgress.value = 5
    initError.value = null
    let ok = false
    const tries = 60
    for (let i = 0; i < tries; i++) {
      connection.value = 'CONNECTING'
      connection.value = await service.checkHealth()
      if (connection.value === 'CONNECTED') { ok = true; break }
      initProgress.value = Math.min(90, 5 + Math.round((i + 1) / tries * 85))
      await sleep(600)
    }
    if (!ok) {
      initState.value = 'FAILED'
      initProgress.value = 0
      initError.value = '无法连接到本地 AI 服务。请检查后端是否可启动，或点击重试。'
      return
    }
    // CHECKING_MODEL is a read-only phase here: the model resolves lazily on first
    // index build; for first-launch we just confirm the bridge answers and the
    // data dir is writable (the backend does the real download on first use).
    initState.value = 'CHECKING_MODEL'
    initProgress.value = 70
    // ② 设备回报（2026-10-07 立项）：首启即拉一次 actual 设备三元组填徽标——
    // 此前只在断→通重连时刷新，首启徽标可能空挂或被索引历史标签占位。
    await loadDeviceSettings()
    await sleep(400)
    initState.value = 'READY'
    initProgress.value = 100
  }

  async function retryInit(): Promise<void> {
    await initApp()
  }

  // 侧栏健康重探（续21 登记尾巴）：initApp 只在首启探测一次，后端进程随 Electron
  // 崩溃/被杀之后侧栏会一直挂着「已连接」+ 旧设备徽标。READY 之后按固定间隔复查，
  // 断→通时顺带重读设备设置（后端可能已重启并换了实际设备）。
  const HEALTH_POLL_MS = 20_000
  let healthTimer: ReturnType<typeof setInterval> | null = null

  async function probeHealth(): Promise<void> {
    const prev = connection.value
    const next = await service.checkHealth()
    connection.value = next
    if (prev !== 'CONNECTED' && next === 'CONNECTED') await loadDeviceSettings()
  }

  function startHealthWatch(): void {
    if (healthTimer) return
    healthTimer = setInterval(() => void probeHealth(), HEALTH_POLL_MS)
  }

  function stopHealthWatch(): void {
    if (!healthTimer) return
    clearInterval(healthTimer)
    healthTimer = null
  }

  async function refreshIndex(originalPath: string): Promise<void> {
    try {
      const st = await service.getIndexStatus(originalPath)
      indexStatus.value = st
      // 状态查询不带设备信息（backend=null）时保留既有值——不把侧栏徽标误标成 CPU
      // （2026-10-01 E2E 发现：打包态启动即显示 CPU，实际后端是 directml/amd）。
      backend.value = st.backend ?? backend.value
    } catch {
      // No status query (Http mode) — leave index/backend unknown rather than crash.
      indexStatus.value = null
      backend.value = null
    }
  }

  async function buildIndex(originalPath: string): Promise<void> {
    const st = await service.buildIndex(originalPath)
    indexStatus.value = st
    // ② 设备回报（2026-10-07 立项）：不用索引的 backend 标签覆盖侧栏徽标——
    // 那是「建这条索引时」的冻结历史标签（IndexMeta.backend），不是当前实际设备；
    // 徽标的唯一权威来源 = /api/settings/device 的 actual 三元组（loadDeviceSettings）。
  }

  function setBackendFromDeviceSettings(ds: DeviceSettingsJson): void {
    backend.value = {
      deviceName: ds.actual_device_name,
      deviceType: ds.actual_device_type,
      isAccelerator: ds.is_accelerator,
      fallback: ds.fallback,
    }
  }

  async function loadDeviceSettings(): Promise<void> {
    try {
      const ds = await service.getDeviceSettings()
      deviceSettings.value = ds
      setBackendFromDeviceSettings(ds)
    } catch {
      // Device settings unavailable (Http mode offline) — leave unknown rather than crash.
      deviceSettings.value = null
    }
  }

  async function setDevicePreference(pref: DevicePreference): Promise<DeviceSettingsJson> {
    const ds = await service.setDeviceSettings(pref)
    deviceSettings.value = ds
    setBackendFromDeviceSettings(ds)
    return ds
  }

  function clear(): void {
    backend.value = null
    indexStatus.value = null
    lastStage.value = null
    connection.value = 'CONNECTING'
    initState.value = 'INITIALIZING'
    initProgress.value = 0
    initError.value = null
  }

  return {
    backend, indexStatus, lastStage, connection, deviceSettings,
    initState, initProgress, initError,
    ensureSubscribed, initApp, retryInit, refreshIndex, buildIndex,
    loadDeviceSettings, setDevicePreference, checkHealth, clear,
    startHealthWatch, stopHealthWatch, probeHealth,
  }
})
