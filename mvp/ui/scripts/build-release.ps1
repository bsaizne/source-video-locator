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

# --- patch 双输出 ONNX（高精度精排 PatchReranker 用）------------------------------
# 缺它 = PatchReranker 静默回退 CPU torch，整条定位慢 2.6~3.9x（2026-10-01 打包态归因确证：
# 包内日志 patch reranker device=cpu，源码树 device=dml）。所以这里一律 fail-fast，
# 不允许「找不到就跳过」。图（78KB）入仓；外部权重与 CLS 那份字节相同，按 ORT 要求的同名复制。
$patchDir = Join-Path $ui 'resources\models\dinov2_cls_patch'
$patchOnnx = Join-Path $patchDir 'dinov2_cls_patch.onnx'
$patchData = Join-Path $patchDir 'dinov2_cls_patch.onnx.data'
if (-not (Test-Path $patchOnnx)) {
    $psrc = if ($env:SVL_PATCH_MODEL_SOURCE) { $env:SVL_PATCH_MODEL_SOURCE } else {
        Join-Path $benchmark 'work\_patch_onnx_tmp'
    }
    if (-not (Test-Path (Join-Path $psrc 'dinov2_cls_patch.onnx'))) {
        throw "patch ONNX 资产缺失: $psrc（设 SVL_PATCH_MODEL_SOURCE 指向含 dinov2_cls_patch.onnx[.data] 的目录）"
    }
    Write-Host "== -> 复制 patch ONNX 资产: $psrc ==" -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path $patchDir | Out-Null
    Copy-Item (Join-Path $psrc 'dinov2_cls_patch.onnx') $patchOnnx -Force
    Copy-Item (Join-Path $psrc 'dinov2_cls_patch.onnx.data') $patchData -Force
}
if (-not (Test-Path $patchData)) {
    $clsData = Join-Path $ui 'resources\models\dinov2_cls_384\dinov2_cls_384.onnx.data'
    if (-not (Test-Path $clsData)) {
        throw "CLS 外部权重缺失: $clsData（patch 图按同名复用这份权重）"
    }
    Copy-Item $clsData $patchData -Force
}
# 构建期摘要断言：静默降级（缺资产/资产被换）必须让打包失败，而不是让用户慢 3 倍
$patchWant = (Get-Content (Join-Path $patchDir 'asset.json') -Raw -Encoding UTF8 | ConvertFrom-Json).sha256
foreach ($f in @($patchOnnx, $patchData)) {
    $leaf = Split-Path $f -Leaf
    $exp = $patchWant.$leaf
    if (-not $exp) { continue }
    $got = (Get-FileHash $f -Algorithm SHA256).Hash.ToLower()
    if ($got -ne $exp) { throw "patch 资产 sha256 不符: $leaf 期望 $exp 实得 $got" }
}
Write-Host "== patch ONNX 资产就位（图 + 同名外部权重） ==" -ForegroundColor Green

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
