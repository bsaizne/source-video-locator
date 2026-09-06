# Video Locator AI — UI

Vue 3 + TypeScript + Vite + Electron 桌面前端。风格为自研 Fluent 工作台（Codex
Workspace 三栏布局），通过 `ServiceAPI` 与 Python 后端通信；**默认在 Mock 适配器
上独立运行**，配置 `VITE_API_BASE` 即接入真实服务。

## 快速开始

```bash
cd mvp/ui
npm install            # npmmirror 已配（registry.npmmirror.com）
npm run dev            # 渲染层，http://localhost:5173
npm run typecheck      # vue-tsc 渲染层类型检查
npm run build          # vue-tsc + vite build → dist/
```

## 连接 Python 后端（延后）

- 前端只依赖 `ServiceAPI`（`src/services/ServiceAPI.ts`）。设置环境变量
  `VITE_API_BASE`（如 `http://127.0.0.1:8000`）后，`resolveService` 自动改用
  `HttpServiceAdapter`（HTTP + WebSocket 进度），无需改任何 UI 代码。
- 端点契约见 `../api/README.md`（FastAPI 桥，尚未实现）。

## 目录

```
src/
  components/      业务组件（ConfidenceBadge/ResultTable/VideoComparisonPlayer/…）
  components/ui/   自研基础控件（BaseButton/BaseInput/… + icons.ts）
  pages/           Home/Projects/MediaLibrary/Analysis/Results/Settings
  services/        types.ts / ServiceAPI / MockServiceAdapter / HttpServiceAdapter
  stores/          session / projects / analysis / results（Pinia）
  styles/          tokens.css / theme.css
  utils/           format.ts / reasons.ts
electron/          Electron main + preload（可选桌面壳，见 DESKTOP.md）
docs/              01-architecture / 02-design / 03-components
```

## 数据契约

`services/types.ts` 里的 TS 类型**逐字段镜像** Python `domain/models.py` 的
`to_dict()` JSON（含 `edited_segment{start,end}` 与 `original{candidate_start,
candidate_end}` 的不对称键名、`confidence` 顶层拍平、`manual_override` 门控
`auto_result`）。

## 已知限制（UI 展示层）

- `confidence_score` 为工程分非概率：UI 显示 HIGH/MEDIUM/LOW + reasons 依据，
  不显示百分比。阈值未标定。
- Mock 预览为占位（无真实片段文件）；接真实后端后由 FFmpeg 提取预览。
