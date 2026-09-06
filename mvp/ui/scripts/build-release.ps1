# build-release.ps1 — 完整发布构建（渲染层 + Electron 主进程 + Python 后端 + 免安装 exe）
#
# 流程：npm build → compile:electron → build backend(PyInstaller) → electron-builder(dir)
# 产物：mvp/ui/release/win-unpacked/Video Locator.exe（免安装运行版；不产 NSIS 安装器）
#
# 用法（PowerShell）：
#   cd D:\claudework\benchmark\mvp\ui
#   powershell -ExecutionPolicy Bypass -File scripts\build-release.ps1
#
# 说明：
#   - 用 npmmirror 镜像下载 electron / electron-builder 二进制，绕开 GitHub 443 被拦。
#   - Python 后端用 venv python（可经 $env:BENCHMARK_VENV_PY 覆盖）。
$ErrorActionPreference = 'Stop'

$ui = Split-Path -Parent $PSScriptRoot                 # mvp/ui
$benchmark = Split-Path -Parent (Split-Path -Parent $ui)  # benchmark root(mvp/ui -> benchmark)
$venvPy = if ($env:BENCHMARK_VENV_PY) { $env:BENCHMARK_VENV_PY } else {
    'D:\claudework\video-dedup-tool\.venv\Scripts\python.exe'
}

Set-Location $ui

# --- 模型资产（DirectML/CPU ONNX）：确保已就位，否则从模型源复制 ------------------
$modelDir = Join-Path $ui 'resources\models\dinov2_cls_384'
if (-not (Test-Path (Join-Path $modelDir 'dinov2_cls_384.onnx'))) {
    $src = if ($env:SVL_MODEL_SOURCE) { $env:SVL_MODEL_SOURCE } else {
        Join-Path $env:LOCALAPPDATA 'SourceVideoLocator\models\dinov2_cls_384'
    }
    Write-Host "== -> 复制模型资产: $src ==" -ForegroundColor Cyan
    if (-not (Test-Path (Join-Path $src 'dinov2_cls_384.onnx'))) {
        throw "模型资产缺失: $src（请先运行 mvp/scripts/export_dml_model.py 导出，或设 SVL_MODEL_SOURCE）"
    }
    New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
    Copy-Item (Join-Path $src '*') $modelDir -Recurse -Force
}

Write-Host "== [1/4] 渲染层构建 (vite) ==" -ForegroundColor Cyan
npm run build
if ($LASTEXITCODE -ne 0) { throw "renderer build failed" }

Write-Host "== [2/4] Electron 主进程编译 ==" -ForegroundColor Cyan
npm run compile:electron
if ($LASTEXITCODE -ne 0) { throw "electron compile failed" }

Write-Host "== [3/4] Python 后端打包 (PyInstaller onedir + 剪枝) ==" -ForegroundColor Cyan
& $venvPy (Join-Path $benchmark 'mvp\scripts\build_backend.py')
if ($LASTEXITCODE -ne 0) { throw "backend build failed" }

Write-Host "== [4/4] electron-builder (dir, 免安装 exe) ==" -ForegroundColor Cyan
$env:ELECTRON_MIRROR = 'https://npmmirror.com/mirrors/electron/'
$env:ELECTRON_BUILDER_BINARIES_MIRROR = 'https://npmmirror.com/mirrors/electron-builder-binaries/'
npx electron-builder --win dir
if ($LASTEXITCODE -ne 0) { throw "electron-builder failed" }

Write-Host "== 完成：$ui\release\win-unpacked\Video Locator.exe ==" -ForegroundColor Green
