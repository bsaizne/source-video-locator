# Video Locator AI — 视觉设计（阶段二）

> 高保真 UI 以**可运行组件**呈现（`src/pages/HomePage|AnalysisPage|ResultsPage` 用
> mock 数据渲染），本文件给出视觉规范。主题 token 见 `src/styles/tokens.css`。

## 1. 设计语言

Microsoft Fluent 启发的**专业工作台**风格：克制、高对比、扁平、小圆角、轻阴影、
克制的动效。**不炫技**，保持专业软件质感。所有组件自研，无第三方 UI 库。

## 2. 主题：Dark Mode

| Token | 值 | 用途 |
|---|---|---|
| `--bg` | `#111111` | 主背景 / Main 区 |
| `--panel` | `#1E1E1E` | Sidebar / Inspector / 卡片面板 |
| `--panel-2` | `#232323` | 控件 / 轨道底 |
| `--card` | `#252525` | 卡片 |
| `--card-hover` | `#2C2C2C` | 卡片 hover |
| `--border` | `#2F2F2F` | 描边 |
| `--accent` | `#0078D4` | Fluent 蓝主色（按钮/选中/进度） |
| `--accent-glow` | `#4CC2FF` | 高亮文本 / active 导航 |
| `--fg` | `#F3F3F3` | 主文本 |
| `--fg-muted` | `#9E9E9E` | 次级文本 |
| `--fg-faint` | `#6E6E6E` | 弱文本 |

### 置信三档（`ConfidenceBadge`）

| 档位 | 颜色 | 底 |
|---|---|---|
| HIGH | `#6CCB5F` | `rgba(108,203,95,.14)` |
| MEDIUM | `#F2C94C` | `rgba(242,201,76,.14)` |
| LOW | `#F5493D` | `rgba(245,73,61,.14)` |

## 3. 排版与圆角

- 字体：`'Segoe UI Variable Text', 'Segoe UI', system-ui`；等宽 `'Cascadia Code', Consolas`。
- 字号：11 / 12 / 13 / 14 / 16 / 20 / 26。正文 14。
- 圆角：`--radius-s/m/l = 6 / 8 / 12px`；药丸 `999px`（徽章/状态）。
- 阴影：`--shadow-s/m/l`（下拉命令面板用大阴影）。

## 4. 布局

- `.app-shell`：`240px / 1fr / 320px` 三栏 grid。Sidebar 与 Inspector 各自
  border 分隔，背景 `--panel`；Main 背景 `--bg` 可滚动。
- `.page`：Main 内 `max-width:1280px; margin:auto; padding:24px`。
- 卡片网格：`repeat(auto-fill, minmax(260px,1fr))`（Home/Projects）；
  Results 页 `minmax(340px,.9fr) / 1.1fr` 双栏。

## 5. 动效（Windows Fluent Motion，克制）

- `--motion-1/2/3 = 80/120/180ms cubic-bezier(.4,0,.2,1)`。
- hover 升高卡片 `translateY(-1px)`（180ms）；按钮背景色过渡（80ms）；
  进度条宽度过渡（180ms）。命令面板淡入（120ms）。
- 不加入场大动效 / 弹簧 / 夸张位移。

## 6. 关键页面组件视觉

- **Home**：统计条（4 个 stat 卡）+ Recent Projects 卡片网格。卡片 icon 用
  `--accent-soft` 底 + `--accent-glow` 图标，右上角 status chip。
- **Analysis**：两张信息卡（Source / Edited）+ 主次按钮 + 6 步 Pipeline
  （每步圆形节点：idle 数字 / running spinner / done 勾 / error 叉，连线轨道）。
- **Results**：左 ResultTable（表头大写淡色 + 行 hover/active 左侧 accent 条），
  右视频对比播放器（上方 Edited / 下方 Original，两行同步时间轴），
  右上角三档统计 chip。
