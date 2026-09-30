# RUNBOOK —— 竞品本机实测的采集清单（给用户/另一个对话执行）

> 目的：拿到 **CutMatch V7.1.0 的真实运行输出**，与我方四片基准逐条对标。
> 我方四片基线（生产两级切分+白闪守卫）：严格 **117/139**、场景 137/139、负例 4/9；
> 各片查询单元数：2mkv 69 / test1 41 / test2 54 / test3 67；TN shot 数：71 / 33 / 66 / 87。

## 0. 风险与更安全的替代（先读）

本项目既定约束（\`cutmatch-analysis/.agent/STATE.md\`）：**禁止在主力机安装**——安装器未签名、
安装期提权 + PowerShell 联网静默装 WebView2；MSI 表显示会写 4 个 Registry 项、5 个 CustomAction、
并用 \`_wmi\` 指纹 + TPM/CNG 设备密钥（\`licensing.device_keys\`）做**设备绑定**。

替代方案（按推荐顺序）：
1. **先试"零安装直跑"**：解包产物已在 \`D:\claudework\cutmatch-analysis\extracted\app\`（5.69 GB / 207 文件）。
   直接运行其中的 \`cutmatch-desktop.exe\`（或 \`cutmatch-sidecar.exe\`）——不写注册表、不提权、不联网装 WebView2。
2. **Windows Sandbox / Hyper-V VM**（可抛弃环境）。
3. 若坚持本机安装：**先建还原点** → **断网**（或防火墙全阻）→ 用**独立本地账户** → 安装 → 不登录任何账号/浏览器。

> 已知硬边界：a01/a02 模型是 **AEAD 加密 + 服务器 model lease**（P-256 ECDH + HKDF + AES-256-GCM）。
> 没有合法 lease，程序很可能**卡在"加载模型"**——这本身就是一条结论，请如实记录现象。

## 1. 素材（必须与 benchmark 完全一致）

| 案例 | 编辑片（输入） | 原片（源） |
|---|---|---|
| 2mkv | \`D:\video\1.mp4\` | \`D:\video\2.mkv\` |
| test1 | \`D:\ProjectXIXI\test1\test1-ed.mp4\` | \`D:\ProjectXIXI\test1\test1-om.mkv\` |
| test2 | \`D:\ProjectXIXI\test2\tset2-ed.mp4\` | \`D:\ProjectXIXI\test2\test2-om.mp4\` |
| test3 | \`D:\ProjectXIXI\test3\test3-ed.mp4\` | \`D:\ProjectXIXI\test3\test3-om.mp4\` |

建议顺序：**test2（最短，69.4 s）→ test1 → test3 → 2mkv**。记录每一步是否成功/耗时。

## 2. 要采集的 5 类产物（这是重点）

存放位置建议：\`D:\claudework\cutmatch-analysis\runtime_evidence\<YYYYMMDD>\`（新目录，不动既有产物）。

| # | 产物 | 位置/怎么拿 | 用途 |
|---|---|---|---|
| 1 | **导出文件** | 剪映草稿目录、PR XML / FCPXML、任何"导出片段"文件，原样打包 | 直接得到他们的**片段边界与时间码**（对标第一优先） |
| 2 | **结果页片段清单** | 结果界面里每段的起止时间码；导出 CSV 最好，**截图也接受**（一张全量/分段多张） | 片段数、时长分布 |
| 3 | **数据目录快照** | 他们的 app data 目录整包（字符串显示含 \`scenes_file\`、\`*scene_split_cache\`、\`frame_patches_offsets_path\`、\`sample_offsets_path\`） | 他们的**原片侧场景切分**与 offset/patch 中间结果 |
| 4 | **日志（一次完整运行）** | 程序的 log 文件；若 UI 有"诊断/导出日志"入口优先用 | 日志里通常直接打印 \`offset_refine_*\`、\`dtw_*\`、\`topk_*\`、\`commentary_scene_*\` 的**实际取值**（能补上 FINDINGS/08 待定的 name→value） |
| 5 | **环境与设置** | GPU/驱动、是否启用 CUDA、UI 里所有可见设置项及其取值（尤其"场景灵敏度/scene_sensitivity"类） | 排除口径差异；判断它是否 NVIDIA-only 才能跑 |

## 3. 我会怎么用这些产物（对标表）

1. **片段级对标**：他们的编辑侧片段数/时长分布 vs 我方 twopass（69/41/54/67）与 TN shot（71/33/66/87）——
   一眼看出他们输出的是 **shot 粒度**还是**场景粒度**（多镜头合并）。
2. **边界级对标**：把他们的片段边界与我方边界、TN 切点做最近邻距离分布（±0.5 s 命中率、位移中位数）。
3. **原片侧对标**：他们的 source scene split 与我方 \`scenes.npy\`（1 fps 特征聚合）比粒度与数量。
4. **参数反推**：从日志把 P0/P1 的常量真实取值填上（回应 \`FINDINGS/08\` §3 待办）。
5. **端到端（能跑通就做）**：用同样四片跑他们的**定位**，与我方 117/139 同口径比（需他们的输出中含原片位置）。

## 4. 若跑不通：如实记录现象即可

- 卡在模型加载/激活 → 说明 lease 依赖（写进结论，不必绕过）。
- 报 CUDA/驱动错误 → 验证"D5 NVIDIA-only"推断。
- 界面能开但功能灰 → 记录哪个功能需要许可。

> 采集完把目录路径告诉我（或直接说"放好了"），我从 benchmark 侧**只读**分析，不动你们项目任何文件。
