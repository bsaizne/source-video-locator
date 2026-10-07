// ② 子进程设备回报标记（2026-10-07 立项）store 侧单测：
// 徽标的唯一权威来源 = /api/settings/device 的 actual 三元组；
// buildIndex 的索引 backend 标签（IndexMeta.backend = 建索引时的冻结历史标签）
// 不得覆盖侧栏徽标（UI-P3 误标残余的根因）。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { setServiceForTest } from '@/services/inject'
import type { DeviceSettingsJson, IndexStatus } from '@/services/types'
import type { ServiceAPI } from '@/services/ServiceAPI'
import { useSessionStore } from '../session'

function device(overrides: Partial<DeviceSettingsJson> = {}): DeviceSettingsJson {
  return {
    preferred: 'directml',
    actual_device_name: 'directml',
    actual_device_type: 'amd',
    is_accelerator: true,
    fallback: false,
    available_devices: ['cpu', 'directml'],
    ...overrides,
  }
}

describe('session 设备回报徽标', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    setServiceForTest(null)
  })

  it('initApp 在 READY 前拉一次 actual 设备填徽标', async () => {
    const getDeviceSettings = vi.fn(async () => device())
    const svc = {
      onProgress: () => () => {},
      checkHealth: vi.fn(async () => 'CONNECTED' as const),
      getDeviceSettings,
    } as unknown as ServiceAPI
    setServiceForTest(svc)
    const session = useSessionStore()
    await session.initApp()
    expect(session.initState).toBe('READY')
    expect(getDeviceSettings).toHaveBeenCalledTimes(1)
    expect(session.backend?.deviceName).toBe('directml')
    expect(session.backend?.deviceType).toBe('amd')
    setServiceForTest(null)
  })

  it('buildIndex 的索引历史 backend 标签不覆盖徽标（actual 保持权威）', async () => {
    const getDeviceSettings = vi.fn(async () => device())
    const stale: IndexStatus = {
      indexMeta: null,
      validation: { status: 'VALID', reason: null },
      backend: { deviceName: 'cpu', deviceType: 'cpu', isAccelerator: false, fallback: false },
    }
    const buildIndex = vi.fn(async () => stale)
    const svc = {
      onProgress: () => () => {},
      checkHealth: vi.fn(async () => 'CONNECTED' as const),
      getDeviceSettings,
      buildIndex,
    } as unknown as ServiceAPI
    setServiceForTest(svc)
    const session = useSessionStore()
    await session.loadDeviceSettings()
    expect(session.backend?.deviceType).toBe('amd')
    await session.buildIndex('D:/m/source.mkv')
    expect(session.indexStatus?.validation.status).toBe('VALID')   // 索引状态照常更新
    expect(session.backend?.deviceType).toBe('amd')     // 徽标不被历史标签拉成 cpu
    setServiceForTest(null)
  })
})
