// 侧栏健康重探（续21 登记尾巴）单元测试：后端进程在首启之后消失时，侧栏不能一直挂着
// 「已连接」；断→通时要重读设备设置（重启后的后端可能换了实际设备）。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { setServiceForTest } from '@/services/inject'
import type { ConnectionStatus, DeviceSettingsJson } from '@/services/types'
import type { ServiceAPI } from '@/services/ServiceAPI'
import { useSessionStore } from '../session'

const HEALTH_POLL_MS = 20_000

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

function fakeService(health: () => ConnectionStatus) {
  const checkHealth = vi.fn(async () => health())
  const getDeviceSettings = vi.fn(async () => device())
  const svc = {
    onProgress: () => () => {},
    checkHealth,
    getDeviceSettings,
  } as unknown as ServiceAPI
  return { svc, checkHealth, getDeviceSettings }
}

describe('session 健康重探', () => {
  let current: ConnectionStatus = 'CONNECTED'
  let fake: ReturnType<typeof fakeService>

  beforeEach(() => {
    setActivePinia(createPinia())
    current = 'CONNECTED'
    fake = fakeService(() => current)
    setServiceForTest(fake.svc)
  })

  afterEach(() => {
    useSessionStore().stopHealthWatch()
    setServiceForTest(null)
    vi.useRealTimers()
  })

  it('周期重探把后端消失如实改成离线，并在恢复后重读设备设置', async () => {
    vi.useFakeTimers()
    const session = useSessionStore()
    await session.checkHealth()           // 首启门：INITIALIZING 里的初次探测
    await session.loadDeviceSettings()
    expect(session.connection).toBe('CONNECTED')

    session.startHealthWatch()
    current = 'OFFLINE'
    await vi.advanceTimersByTimeAsync(HEALTH_POLL_MS)
    expect(session.connection).toBe('OFFLINE')
    expect(fake.getDeviceSettings).toHaveBeenCalledTimes(1) // 断开不重读设备

    current = 'CONNECTED'
    await vi.advanceTimersByTimeAsync(HEALTH_POLL_MS)
    expect(session.connection).toBe('CONNECTED')
    expect(fake.getDeviceSettings).toHaveBeenCalledTimes(2) // 断→通重读一次
  })

  it('startHealthWatch 幂等，stopHealthWatch 后不再探测', async () => {
    vi.useFakeTimers()
    const session = useSessionStore()
    session.startHealthWatch()
    session.startHealthWatch()
    await vi.advanceTimersByTimeAsync(HEALTH_POLL_MS)
    expect(fake.checkHealth).toHaveBeenCalledTimes(1)

    session.stopHealthWatch()
    session.stopHealthWatch()
    await vi.advanceTimersByTimeAsync(HEALTH_POLL_MS * 3)
    expect(fake.checkHealth).toHaveBeenCalledTimes(1)
  })
})
