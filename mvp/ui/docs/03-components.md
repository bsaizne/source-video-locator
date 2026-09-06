# Video Locator AI — Vue3 组件结构（阶段三）

> 组件全部自研（无第三方 UI 库）。基础控件见 `src/components/ui/`，业务组件见
> `src/components/`，页面见 `src/pages/`。

## 1. 组件树

```
App.vue
└── .app-shell（grid: sidebar 1fr inspector）
    ├── AppSidebar.vue
    │   └── BackendStatusIndicator.vue  ← session.backend + session.indexStatus
    ├── <router-view>
    │   ├── HomePage.vue            → ProjectCard[]
    │   ├── ProjectsPage.vue        → ProjectCard[]
    │   ├── ProjectDetailPage.vue
    │   ├── MediaLibraryPage.vue
    │   ├── AnalysisPage.vue        → ProgressPipeline
    │   ├── ResultsPage.vue         → ResultTable + VideoComparisonPlayer
    │   └── SettingsPage.vue
    └── InspectorPanel.vue          ← results.selected / analysis / session
└── CommandPalette.vue（Ctrl+K 浮层）
```

## 2. 基础控件（`components/ui/`）

| 组件 | 关键 props | 说明 |
|---|---|---|
| `BaseButton.vue` | `variant(primary/subtle/ghost/danger)` `size(sm/md/lg)` `icon` `loading` `disabled` `block` | Fluent 风格按钮；emit `click` |
| `BaseInput.vue` | `modelValue` `placeholder` `disabled` | `update:modelValue` |
| `BaseSelect.vue` | `modelValue` `placeholder` | `update:modelValue`（自绘下拉箭头） |
| `BaseTabs.vue` | `items[{key,label}]` `modelValue` | `update:modelValue` |
| `BaseProgress.vue` | `current/total` 或 `value(0..100)` `indeterminate` `label` | 进度条 |
| `Spinner.vue` | `size` `color` | 旋转指示 |
| `BaseIcon.vue` | `name` `size` `strokeWidth` | 内联 SVG 图标集（`icons.ts`） |

## 3. 业务组件（`components/`）

| 组件 | 关键 props / emits | 职责与复用点 |
|---|---|---|
| `ConfidenceBadge.vue` | `{level, score?, reasons?, showScore?}` | 三档彩色徽章 + 可选分数；**显示分数数字，绝不显示百分比**；hover 显示 reasons 工具提示 |
| `StatusBadge.vue` | `{label, tone(ok/warn/err/info/muted/accent), icon?}` | 通用状态 chip：Ready/Invalid/Unresolved/Manual/Montage/Fallback |
| `ProgressPipeline.vue` | `{steps: PipelineStep[]}` | 6 步任务轴；消费 analysis store 的 steps（idle/running/done/error） |
| `Timeline.vue` | `{duration, value, markers[], interactive?, selectedId?}` + `seek/select` | 时间尺 + 区间条 + 游标；支持点击 seek、命中 marker 选中 |
| `VideoPlayer.vue` | `{src?, poster?, label?, currentTime?, playing?}` + `tick/playingChange/seek/duration` | HTML5 video + 自定义传输控件；src 为空时显示占位 |
| `VideoComparisonPlayer.vue` | `{result, editedSrc?, originalSrc?}` | 上 Edited / 下 Original + 同步时间轴；play/pause/seek/reset；Edited 时间↔Original 区间映射 |
| `ResultTable.vue` | `{results, selectedId?}` + `select(id)` | 结果列表：Clip#/Edited/Original/Confidence/Score + Montage/Manual/Unresolved 标识 |
| `ProjectCard.vue` | `{project}` + `open` | Home/Projects 网格卡片 |
| `InspectorPanel.vue` | （无 props，读 store） | 右侧细节：选中结果详情 / reasons 依据 / alternatives / 手动区间修正 / failure 提示 |
| `CommandPalette.vue` | （无 props） | Ctrl+K 浮层，导航+动作搜索 |
| `BackendStatusIndicator.vue` | `{backend, indexStatus}` | Model/Backend/Index 状态；`deviceName` 仅展示不作分支；`AMD_GPU_BACKEND_BLOCKED` 专门态 |

## 4. 数据流（Pinia store → 组件）

| store | 状态 | 消费组件 |
|---|---|---|
| `stores/session.ts` | `backend` `indexStatus` `lastStage`；action `refreshIndex/buildIndex` | AppSidebar/BackendStatusIndicator、Inspector、Home |
| `stores/projects.ts` | `projects[]` `activeProjectId` `activeProject`；action `addProject/selectProject` | Home/Projects/ProjectDetail/MediaLibrary/Analysis |
| `stores/analysis.ts` | `steps[]` `segments` `running` `error` `progress`；action `runLocate/reset` | AnalysisPage、Inspector |
| `stores/results.ts` | `batch` `selectedId` `selected` `counts`；action `setBatch/select/markManualOverride/clear` | ResultsPage、Inspector |

Service 单例经 `useService()` 获取（`services/inject.ts` 懒加载单例），页面与 store
共用同一 `ServiceAPI` 实例；默认 `MockServiceAdapter`，配置 `VITE_API_BASE` 后切
`HttpServiceAdapter`（同一接口，UI 无改动）。

## 5. props/emits 契约要点

- 所有 `v-model` 均为 `modelValue: string` + `update:modelValue`（除 BaseTabs 用 key
  字符串，BaseProgress 无 v-model）。
- 所有组件不直接读后端 JSON 之外的字段；页面把 `ResultBatchJson` 交 `ResultTable`，
  把 `ResultJson` 交 `VideoComparisonPlayer` / `InspectorPanel`。
- 组件无副作用（不发起网络），持久化/进度/取消全部在 store 与 service 层。
