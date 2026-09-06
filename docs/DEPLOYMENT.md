# 部署指南（DEPLOYMENT）

Video Locator AI 桌面版的分发与安装说明（Windows）。目标：把开发版变成普通用户可安装运行的软件。

## 产物

```
mvp/ui/release/win-unpacked/Video Locator.exe      # 免安装运行版（分发给用户，双击即用）
```

> 安装器（NSIS Setup）已按用户拍板移除（2026-08-27）；只交付免安装 win-unpacked exe。

## 构建（发布者）

```powershell
cd D:\claudework\benchmark\mvp\ui
powershell -ExecutionPolicy Bypass -File scripts\build-release.ps1
```

脚本会依次：`npm run build`（渲染层）→ `compile:electron` → `build_backend.py`（PyInstaller
后端 + 剪枝）→ `electron-builder --win dir`（免安装 exe），用 npmmirror 镜像绕开 GitHub 下载限制。

## Run（运行免安装版）

1. 解压/复制 `mvp/ui/release/win-unpacked/` 整体到任意目录。
2. 双击 `Video Locator.exe` 启动（自动拉起内置 Python 后端）。

> 无需安装；未签名（`signAndEditExecutable: false`），Windows SmartScreen 可能提示「未知发布者」——
> 点「更多信息 → 仍要运行」。签名属后续阶段（需代码签证书）。

## First Launch（首次启动）

```
启动 → 初始化 AI 引擎（进度条，不要关闭）→ 检查后端 /api/health → READY → 进入首页
```

- 首次启动会**在用户数据目录**初始化 `data/`（索引/模型/预览/导出）+ `logs/`。
- 模型权重在**首次索引/分析**时按需解析（可能触发下载/导出一次），届时进度条反映任务进度。
- 失败时显示「AI 服务初始化失败」+ 重试按钮。

## Folder Structure（用户目录）

运行时**用户数据**在 Electron 用户目录——**不写入 Program Files**：

```
%APPDATA%\Video Locator AI\           # = Electron app.getPath("userData")
├── logs\                             # <SVL_LOG_DIR> 后端日志 video_locator.log
└── data\                             # <SVL_DATA_DIR>
    ├── index\                        # 特征索引（FeatureStore）
    ├── exports\                      # 导出结果批
    └── previews\                     # 预览抽取片段
```

实现：Electron 主进程设 `SVL_DATA_DIR` / `SVL_LOG_DIR` 指向上述目录（见 `electron/main.ts`），
Python 后端经 `infrastructure.paths` / `logging` 读取——**不改 mvp/src**。

**模型资产（DINOv2/DirectML ONNX）已随安装包内置**于程序目录 `resources\models\dinov2_cls_384\`，
主进程以 `SVL_DML_MODEL` 指向它（只读）——GPU（DirectML）即可用，无需把模型复制到数据目录。

## 拖拽导入

项目页的「源片库」与「剪辑视频」区支持**拖入本地视频**（Electron 经 `webUtils` 取绝对路径），
拖入后作为源片/剪辑参与分析；也可点「剪辑」区手动添加占位名。

## Troubleshooting（常见问题）

| 现象 | 处理 |
| --- | --- |
| **AI 服务启动失败** | 弹窗给出原因 + 日志位置；点击「打开日志目录」看 `logs\video_locator.log`；「重新启动」重启应用；「复制错误信息」供反馈。常见：后端文件损坏、模型初始化失败、系统资源不足。 |
| **模型加载失败** | 模型已内置在 `resources\models\dinov2_cls_384\`（`SVL_DML_MODEL` 指向）。若报缺模型，确认该目录完整（`asset.json` + `dinov2_cls_384.onnx` + `.onnx.data`）；GPU 不可用会自动回退 CPU。 |
| **视频无法读取** | 确认编码受支持（H.264/H.265/常见容器）；`ffmpeg.exe` 与 `ffprobe.exe` 在 `resources\backend\` 下；日志报 `ffmpeg`/`ffprobe` 错误时检查这两个二进制。 |
| **ffmpeg 错误** | 日志含 subprocess stderr 尾部；多为输入文件损坏/编码不支持。 |
| **首次启动一直转圈** | 看 `logs\video_locator.log` 是否在写入；后端是否成功 listen 8765。

## Uninstall（卸载，免安装版）

- 直接删除 `win-unpacked/` 文件夹即可（无注册表/启动项残留）。
- **用户数据** `%APPDATA%\Video Locator AI\` 会保留（如需彻底清理手动删除）。

## 相关命令

```bash
# 渲染层
cd mvp/ui && npm run build && npm run typecheck && npm test
# Electron
npm run typecheck:desktop && npm run compile:electron
# 后端
../video-dedup-tool/.venv/Scripts/python.exe -m unittest mvp.api.tests.test_api mvp.api.tests.test_tasks mvp.api.tests.test_progress mvp.api.tests.test_preview mvp.api.tests.test_preview_service
```

## 已知限制

- 免安装版未签名；`win-unpacked` 体积 ~900MB（含后端 bundle + 模型资产）——本地 DL 引擎 + 模型的固有成本；进度为阶段级。
