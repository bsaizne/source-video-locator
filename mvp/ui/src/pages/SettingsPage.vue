<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useService } from '@/services'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import type { DevicePreference } from '@/services'

const session = useSessionStore()
const service = useService()
const saving = ref(false)
const savedDevice = ref(false)
// 用户选的推理后端偏好；初始从后端已持久化的设置取（否则 auto）。
const devicePref = ref<DevicePreference>(session.deviceSettings?.preferred ?? 'auto')

const DEVICE_LABEL: Record<string, string> = {
  cpu: 'CPU',
  amd: 'GPU (DirectML)',
  mps: 'GPU (MPS)',
  cuda: 'GPU (CUDA)',
}
const PREF_LABEL: Record<string, string> = {
  auto: '智能（自动选 GPU/CPU）',
  directml: 'GPU (DirectML)',
  mps: 'GPU (MPS)',
  cpu: 'CPU',
}

// 下拉选项由后端 available_devices 驱动（auto 恒在，GPU 类排 CPU 前），
// 避免在 Windows 上出现 Apple/MPS 等跨平台选项。
const prefOptions = computed(() => {
  const avail = session.deviceSettings?.available_devices ?? []
  const known = avail.filter((k) => k in PREF_LABEL)
  const gpuFirst = [...known.filter((k) => k !== 'cpu'), ...known.filter((k) => k === 'cpu')]
  return ['auto', ...gpuFirst].map((k) => ({ value: k, label: PREF_LABEL[k] ?? k }))
})
const actualDevice = computed(
  () => (session.backend ? DEVICE_LABEL[session.backend.deviceType] ?? session.backend.deviceType : '—'),
)
const actualName = computed(() => session.deviceSettings?.actual_device_name ?? '—')

// ---- 导出目录（反馈 ⑭）：PR 与剪映各自独立，持久化在本地 ----
const EXPORT_DIR_KEY = 'vl.exportDir'
const JY_EXPORT_DIR_KEY = 'vl.exportDirJianying'
const exportDir = ref(localStorage.getItem(EXPORT_DIR_KEY) ?? '')
const jyExportDir = ref(localStorage.getItem(JY_EXPORT_DIR_KEY) ?? '')
const savedExport = ref(false)
const savedJyExport = ref(false)

function saveExportDir(): void {
  localStorage.setItem(EXPORT_DIR_KEY, exportDir.value.trim())
  savedExport.value = true
  setTimeout(() => (savedExport.value = false), 2000)
}

function saveJyExportDir(): void {
  localStorage.setItem(JY_EXPORT_DIR_KEY, jyExportDir.value.trim())
  savedJyExport.value = true
  setTimeout(() => (savedJyExport.value = false), 2000)
}

async function chooseExportDir(): Promise<void> {
  const p = await window.desktop?.openDirectory?.() ?? null
  if (p) {
    exportDir.value = p
    saveExportDir()
  }
}

async function chooseJyExportDir(): Promise<void> {
  const p = await window.desktop?.openDirectory?.() ?? null
  if (p) {
    jyExportDir.value = p
    saveJyExportDir()
  }
}

// ---- 日志快照（反馈 ⑮）：一键复制 / 下载压缩包 ----
const logText = ref('')
const logCopied = ref(false)
const logLoading = ref(false)

async function copyLogs(): Promise<void> {
  logLoading.value = true
  try {
    const data = await service.fetchRecentLogs()
    logText.value = data?.text ?? ''
    try {
      await navigator.clipboard.writeText(logText.value)
      logCopied.value = true
      setTimeout(() => (logCopied.value = false), 2000)
    } catch {
      // 剪贴板被拒 → 文本已加载到 state，用户可手动选择复制
    }
  } finally {
    logLoading.value = false
  }
}

async function downloadLogs(): Promise<void> {
  await service.downloadLogsArchive()
}

async function saveDevice(): Promise<void> {
  if (saving.value) return
  saving.value = true
  try {
    await session.setDevicePreference(devicePref.value)
    savedDevice.value = true
    setTimeout(() => (savedDevice.value = false), 2000)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void session.loadDeviceSettings().then(() => {
    if (session.deviceSettings) devicePref.value = session.deviceSettings.preferred
  })
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">设置</h1>
      <p class="page-subtitle">后端与导出配置</p>
    </div>

    <div class="st__grid">
      <section class="st__card">
        <div class="section-title">设备</div>
        <label class="st__field">
          <span>推理后端偏好</span>
          <BaseSelect v-model="devicePref">
            <option v-for="opt in prefOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </BaseSelect>
        </label>
        <label class="st__field">
          <span>当前实际后端</span>
          <span class="st__device mono">{{ actualDevice }}<template v-if="session.deviceSettings">（{{ actualName }}）</template></span>
        </label>
        <p v-if="session.deviceSettings?.fallback" class="st__hint st__warn">
          已回退到 CPU：请求了 GPU 但 DirectML 不可用（模型资产缺失或驱动不支持）。
        </p>
        <p class="st__hint">
          智能档会在 GPU 可用时自动选它；分析视频时自动启用，无需手动构建。
        </p>
        <div class="st__actions">
          <BaseButton :loading="saving" @click="saveDevice">保存设备</BaseButton>
          <span v-if="savedDevice" class="st__saved mono">已保存</span>
        </div>
      </section>

      <section class="st__card">
        <div class="section-title">导出目录</div>
        <label class="st__field">
          <span>PR (Premiere) 导出目录 —— FCP7 XML / EDL / JSON 输出到这里</span>
          <BaseInput v-model="exportDir" placeholder="留空 = 默认导出目录" />
        </label>
        <div class="st__actions" style="margin: 4px 0">
          <BaseButton icon="folder" @click="chooseExportDir">选择目录</BaseButton>
          <BaseButton variant="primary" @click="saveExportDir">保存</BaseButton>
          <span v-if="savedExport" class="st__saved mono">已保存</span>
        </div>
        <p class="st__hint">PR 工程文件（FCP7 XML / EDL / JSON）导出到此目录；留空时使用系统默认导出目录。</p>

        <label class="st__field" style="margin-top: 16px">
          <span>剪映导出目录</span>
          <BaseInput v-model="jyExportDir" placeholder="留空 = 默认导出目录" />
        </label>
        <div class="st__actions" style="margin: 4px 0">
          <BaseButton icon="folder" @click="chooseJyExportDir">选择目录</BaseButton>
          <BaseButton variant="primary" @click="saveJyExportDir">保存</BaseButton>
          <span v-if="savedJyExport" class="st__saved mono">已保存</span>
        </div>
        <p class="st__hint">
          建议直接选择剪映的草稿文件夹（通常是 <span class="mono">D:\JianyingPro Drafts</span>）——
          导出的草稿会直接出现在剪映首页列表里，点开就是排好时间线的工程。
        </p>
      </section>

      <section class="st__card">
        <div class="section-title">日志</div>
        <div class="st__actions" style="margin: 4px 0">
          <BaseButton :loading="logLoading" icon="copy" @click="copyLogs">复制日志</BaseButton>
          <BaseButton icon="download" @click="downloadLogs">下载日志压缩包</BaseButton>
        </div>
        <p v-if="logCopied" class="st__saved mono">日志已复制到剪贴板</p>
        <p class="st__hint">复制最近一次运行的运行日志，或打包下载全部日志文件。</p>
      </section>

      <section class="st__card">
        <div class="section-title">置信度</div>
        <p class="st__hint">
          该分数是工程置信值，<strong>不是概率</strong>。界面以高 / 中 / 低三档并附原因展示，而非百分比。
        </p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.st__grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
.st__card { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius-m); padding: 18px; }
.st__field { display: flex; flex-direction: column; gap: 6px; font-size: var(--fs-xs); color: var(--fg-muted); margin-bottom: 14px; }
.st__hint { font-size: var(--fs-xs); color: var(--fg-faint); margin: 4px 0 0; }
.st__warn { color: var(--warn); }
.st__device { font-size: var(--fs-md); color: var(--fg); }
.st__actions { display: flex; align-items: center; gap: 12px; margin: 20px 0; }
.st__saved { color: var(--ok); font-size: var(--fs-xs); }
</style>
