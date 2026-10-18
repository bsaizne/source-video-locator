# 交接 2026-10-19（00:5x）— 边界线全面收敛：三方判负 + 竞品原片侧挖清 + 主线收尾

> 自包含交接件。下一会话读这一份 + `.agent/STATE.md` 顶部「续68/69/70」块即可接手。
> 本仓 `D:\claudework\benchmark`。**代码零改动**（本夜全是探针与档案）。

## 0. 一句话状态

**边界线（长镜头漏切）已用四条独立路径查到底，结论是「信号弱是素材性质，不是算法问题」。**
**竞品原片侧也挖清了：他们同样只用 TransNetV2，没有更强的方案。** 主线未结项只剩产品口径决策。

## 1. 今夜做完的事（按时间）

| # | 事 | 结论 | 落档 |
|---|---|---|---|
| ① | 出包 **r27**（首次含 scn3/scn4） | 五道包内验收全绿；zip 双尺一致 | `work/r27_pkg/` + CHANGELOG 续68 |
| ② | **扩 GT 第一轮**（25 段长镜头逐段读图） | 15 段真漏切（855s）/ 9 段单镜头 / 1 段片尾 | `FINDINGS_GT_EXPAND_20261018.md` |
| ③ | **逐帧扫描器** + CLS 腿审计 | 像素判据在这 25 段候选**全 0**；CLS **存在性 AUC 0.919** 但定位不准（最强点反是假阳） | CHANGELOG 续68补四 |
| ④ | **scn5：TN 切原片侧** | **判负**。TN 只 375 切点（我方 912），15 段只救 1 个 | `FINDINGS_SCN5_TN_ORIGINAL_20261019.md` |
| ⑤ | **真索引 `refresh_derived` 端到端** | **跑通**：398.6s / 9 项 PASS / **五表+index.json 逐字节幂等** | CHANGELOG 续70 |
| ⑥ | **竞品原片侧切分挖查** | **他们也没有独立的**，就是 TransNetV2 | `FINDINGS_COMPETITOR_SOURCE_SCENE_20261019.md` |

## 2. 核心结论（读这一节就够）

### 2.1 长镜头漏切的真相（三方交叉验证）

| 通道 | 在 15 段真漏切上的表现 | 结论 |
|---|---|---|
| **像素腿**（现役生产判据） | 段内候选 **0 个**（不是被门卡掉，是**根本没信号**） | 无解 |
| **CLS 腿** | 存在性 AUC **0.919**（真漏切中位 0.348 vs 单镜头 0.159），但**定位不准**——过语义门的 3 个点只有 1 个是真切点，且 CLS 最强的那个（0.820）反而是假阳 | 有信号，不可定位 |
| **TransNetV2** | 段内切点 8 个，但 **9/10 落在已有边界**（<3s），只救 1 个真漏切 | 高精度低召回 |

⇒ **三个通道都指向同一事实：这批切点的视觉信号本身就弱。** 不是「谁的方法不对」。

### 2.2 竞品为什么看着更准（已挖清）

**他们只在编辑侧（解说片）更准，原片侧和我们一样用 TransNetV2，没有额外方案。** 硬证据：

- `scene_detection.model = "TransNetV2"`，**全 profile 只有一份配置，不区分原片/编辑**；
- `nuitka_dict_constants` 计数：`commentary_scene` **26** 次 vs `source_scene` **3** 次（且 3 次全是阶段名/ETA，**无边界参数**）；
- ETA 表里 `source_scene` 与 `commentary_scene` **同为 220s GPU / 75s CPU** ⇒ 同一个模型跑两遍；
- 原片侧精修被限死：`source_boundary_refine_max_shift = 2` 帧（编辑侧是 16 帧）、`source_boundary_guard_frames = 0`、
  `respect_source_scene_end = false`。

⇒ **他们把功夫下在 `offset_refine_*` 全族（12 参数）+ `long_scene_*`（7 参数）** ——「切得粗，但定位对了再精修」。

## 3. 建议的下一步（按我的推荐排序，需你拍板）

1. **先裁产品口径**（唯一真正的阻塞）：**同场景内正反打/换人不换景，算不算一个镜头？**
   这个不定，任何新信息源（人脸/ReID/音频）都无法验收。
2. **立项③「下游按阈值标注」**：既然救不回来，让下游知道「这段边界不可信」是唯一诚实的做法。
   侧车 `scene_strength.npy` 数据已备好（scn3 落地），只差下游接线。
3. **不要把资源继续投在切分器上** —— 四条路（像素/CLS/TN/竞品）已全部查完。

## 4. 未结项清单（如实）

| 项 | 状态 |
|---|---|
| mac 包 | ✅ **用户已自行 dispatch 并完成**（run `39135662432`） |
| 删 r24 | ✅ 已删（释放 936MB，三档 r27/r26/r25） |
| 真索引 `refresh_derived` | ✅ **已跑通**（本文 §1⑤） |
| 立项③「下游按阈值标注」 | ❌ 未做（侧车数据已备好，等口径） |
| 产品口径「同场景正反打算不算一个镜头」 | ❌ **未裁**（阻塞后续所有方向） |
| GT 拆条目（15 段 → 具体切点） | ❌ 未做（本轮证实**不能自动化**，需逐段 5~10fps 人工看） |
| C 盘 | ✅ 已清 9.35GB（Ghidra 6.01 + uv 3.34），剩 50.94GB |

## 5. ⚠️ 本夜我犯的五个错（全留档，别再踩）

| # | 错 | 正确做法 |
|---|---|---|
| ① | **`read` 工具读长文件被静默截断**（CHANGELOG 4017 行只返回 481 行），我据此整写回 ⇒ **抹掉 3591 行** | 改写长文件前**必须断言「读到的行数 == totalLines」**；或用 `node:fs` 整读整写 |
| ② | **8fps 降采样跑 TransNetV2**（为省时间）⇒ 得出「15 段切点全 0」的**假读数** | 预训练模型必须用它**训练时的输入规格**；TN 是原生 24~30fps |
| ③ | **`local_peaks` 返回绝对索引，我当段内偏移用** ⇒ idx45 报出 1468s（区间是 470-542s） | 凡「段内扫描」，输出第一行先自检「首个候选是否落在段内」 |
| ④ | **粗采样（8 帧）把连续跟拍长镜头误判成换景**（idx16） | 粗采样只能判「要不要细查」，**不能判「是不是切点」** |
| ⑤ | **`FeatureStore(config=cfg)` 构造报 TypeError** | 验配置链路**必须复用生产构造点**（`SourceLocatorService().store`），不要自己拼参数 |

## 6. 复跑命令速查

```powershell
$PY = 'D:\claudework\video-dedup-tool\.venv\Scripts\python.exe'
$env:PYTHONPATH='mvp/src;mvp'

# 长镜头归因（scn4 后 47 段）
& $PY work\boundary_20261018\longtake_clean.py

# 逐帧切点扫描 + 出条带
& $PY work\boundary_20261018\gt_cut_scan.py 692
& $PY work\boundary_20261018\gt_cut_scan.py --strip 692 5860.9 10 1.5

# CLS 腿审计（AUC 0.919）
& $PY work\boundary_20261018\cls_leg_audit.py

# TN 原片侧（原生 fps，正确口径）
& $PY mvp\scripts\probe_scn5_tn_native.py

# 真索引 refresh_derived（6.6 分钟）
& $PY -u work\boundary_20261018\rerun_refresh_derived_test1.py

# 后端全套（705 项）
& $PY -m unittest discover -s mvp/tests -p "test_*.py"
```

## 7. 产物索引

```
mvp/docs/FINDINGS_GT_EXPAND_20261018.md                扩 GT 第一轮（15/9/1 段判定）
mvp/docs/FINDINGS_SCN5_TN_ORIGINAL_20261019.md         TN 切原片侧判负
mvp/docs/FINDINGS_COMPETITOR_SOURCE_SCENE_20261019.md  竞品原片侧挖查
mvp/scripts/probe_scn5_tn_native.py                    scn5 探针（正确口径）
mvp/scripts/probe_scn5_tn_on_original.py               8fps 版（方法有缺陷，留档对照）
work/boundary_20261018/                                全部探针+产物（见 §6）
work/r27_pkg/                                          r27 出包全过程
mvp/ui/release/Video-Locator-win-x64-20261018r27.zip   现役包 981,703,562 B
```

## 8. Windows / 工具坑（本夜新增）

- **`Tee-Object` 在长任务中不落盘**（整段结束才写）⇒ 要实时进度用 `python -u` + `> file`。
  这条**订正了我之前「pixel_scan 无进度输出 = 卡住」的误判**。
- **`read` 工具有默认行数上限**（约 480 行），超长文件必须用 `node:fs` 读。
- ffmpeg 逐帧 seek 出条带：21 帧约 7~8 秒；151 张条带约 20 分钟。
- 改 `STATE.md`/`TODO.md` 用 `node:fs` 整读整写 + **写前断言（块首/块尾/块数）**，本夜全程零事故。
