# FINDINGS — shot_split / patch_refine 抓帧提速（杠杆0 归因 + 杠杆1+2 落地）

> **GT 版本**（2026-10-01 补登记，批量执行）：不适用——纯耗时归因 + 零语义逐位一致验证（整条 locate 全字段一致），不改任何判定数字。

**日期**：2026-10-01（续34）
**触发**：续33 后续把两旋钮接进生产路径，ON 臂单片 31–44min vs OFF 7–8min（旋钮自身 ~24–36min），
档案明确「未做单臂拆分归因」。用户问「关于性能有什么可以优化的地方吗」→ 拍板「都要」
（先归因拿基线，再落零语义改动，对比提速 + 验证逐位一致）。
**结论**：grab_frame（ffmpeg 逐帧 spawn）= 旋钮墙钟 **77.6%**；接抓帧缓存 + 4 线程并行批量抓帧后
**全片 test1 旋钮墙钟 1262.3s → 664.9s = 1.90×**（省 10.0 min/片），输出**三向逐位一致**、零语义。
零 `feature_version` 变更；后端 455 + API 99 全绿。

---

## 1. 归因（杠杆0）——grab 是绝对大头，历史「81%」原样平移到新路径

微探针 `mvp/scripts/probe_split_patch_timing.py`（研究侧，monkey-patch 计时，零 runtime 改动）：
不重跑整条 `locate()`，而是 `off_{case}.results.json`（旋钮前批）→ `shot_split` → `patch_refine`，
精确复现 ON 臂后半段（旋钮在 locate 末端、前段管线与开关无关）。实例级补丁 `srv.ffmpeg.grab_frame`
（线程安全 rec），两模同打点保证 A/B 公平。

**全片 test1（41 段 → 55 spans）baseline 臂（串行 / 无缓存 / 无并行 = 改动前生产接线）**：

| 阶段 | 耗时 | 调用 | s/call | %wall |
|---|---|---|---|---|
| **grab.source**（源片 ffmpeg spawn） | **822.9s** | 1860 | 0.442 | **65.2%** |
| grab.edited（编辑片） | 156.0s | 731 | 0.213 | 12.4% |
| embed.dual（DML CLS+patch forward） | 136.6s | 2130 | 0.064 | 10.8% |
| patch_score.numpy | 114.0s | 9300 | 0.012 | 9.0% |
| embed.cls（DML CLS） | 27.5s | 461 | 0.060 | 2.2% |
| residual | 5.3s | - | - | 0.4% |
| **旋钮总墙钟** | **1262.3s** | | | split 127.2 + refine 1135.1 |

**grab 合计 978.9s = 77.6% wall**。DML forward（embed.dual+cls）仅 13.0%，numpy 9.0%。
⇒ 与历史 `_patch_rerank_span` 探针「grab_frame spawn 占 81%」（TODO 续5深夜II）**同量级**，
假设证实：**瓶颈是 ffmpeg 逐帧进程 spawn，不是模型推理**。优化打法 = 减少 grab 次数（缓存）+
并行化剩余 grab（线程池），而非动 DML/numpy。

`patch_refine` 内层机制（`patch_refine.py:120-134`）：每候选 ±5s@1fps 网格（~10 帧）逐帧
`grab_frame(source) → embed_dual`，最坏 6 候选 = ~60 次源片 spawn/段，全串行、无缓存 ⇒ 成本爆炸。

---

## 2. 落地（杠杆1+2）——零语义，复用现役已上线 helper

**杠杆1（缓存）**：`locator_service.py:1105/1123` 两处旋钮接线的 `grab_frame` 从裸
`self.ffmpeg.grab_frame` 换成 `self._grab_frame_cached`（512 FIFO 进程内缓存，`:2240`）——
吃掉相邻候选窗重叠帧 + 跨段重复帧的冗余解码。

**杠杆2（并行）**：两模块新增可选 `grab_frames(path, times) -> list[frame]` 参数 + `_grab_many` helper；
生产传 `self._grab_frames_parallel`（4 线程池，`:2228`）。把「grab→embed 逐帧交错」重构为
「**先并行批量 grab 整个网格 → 再主线程串行 embed**」。

**关键设计约束（遵守续6 教训）**：`embed_dual`/`embed`（DML forward）**保持主线程串行**——
DirectML EP 多线程并发 Run 同一 ONNX session 会原生段错误（续6 实测）。**只并行化 grab**
（纯 IO+解码，无 DML）。`_grab_frames_parallel` 用 `ex.map` **保序** ⇒ 帧内容与顺序不变。

改动文件：
- `engine/localization/patch_refine.py`：签名 +`grab_frames=None`；`_grab_many`；查询帧 5 连抓 +
  候选网格批量抓两处循环重构。
- `engine/localization/shot_split.py`：同上（编辑窗采样帧批量抓）。
- `app/locator_service.py:1105-1106 / 1123-1124`：两处旋钮接线传 `grab_frame=_grab_frame_cached`
  + `grab_frames=_grab_frames_parallel`。

**向后兼容**：`grab_frames=None` 默认 ⇒ 回退逐帧 `grab_frame`。离线验证器
（`validate_patch_refine.py:85`、`validate_split_patch_refine.py:91/96`）与单测
（`test_patch_refine.py`、`test_shot_split.py`）均不传 `grab_frames`，命中回退路径 ⇒ 研究工具零回归。

---

## 3. 验证——三向逐位一致 + 全尺度 A/B + 缓存驱逐路径经验覆盖

### 3.1 零语义（三向逐位一致，最强证明）
`span_of` 规范化（`ed`/`og`/`segs` 排序/`conf`/`nis`，排除 shot_split 的 `uuid4` result_id）后：

```
baseline_full == optimized_full : True   (串行 vs 并行/缓存，同 harness)
baseline_full == ref(on_test1)  : True   (微探针 vs 生产整条 locate 产物)
optimized_full == ref(on_test1) : True
>>> THREE-WAY BIT-IDENTICAL: True        (各 55 spans)
```

参照 `ref_on_test1.spans.json` = 续33 生产验收产物 `work/spl_patch_arms/on_test1.results.json`
（原始串行代码、双旋钮全开、整条 `locate()` 输出，已逐张读图验证过）规范化而来。
三臂全等 ⇒ **既证明改后代码零语义，又证明微探针忠实复现生产旋钮段**。

### 3.2 全尺度 A/B 提速（同 harness 干净跑，无 CPU 争用）
| 臂 | 旋钮墙钟 | split | refine |
|---|---|---|---|
| baseline_full（串行/无缓存/无并行） | **1262.3s** | 127.2 | 1135.1 |
| optimized_full（缓存+4线程并行） | **664.9s** | 66.8 | 598.1 |
| **SPEEDUP** | **1.90×**（省 597.4s = 10.0 min） | 1.90× | 1.90× |

机制分解：缓存把 raw grab **2591 → 1691 次（省 900 = 35%）**；并行把剩余 grab 摊到 4 线程
（optimized 下 grab 聚合 thread-time 1295.4s > 墙钟，因 4 线程并发，墙钟才是判据）。
8 段子集先行 A/B = 362.4s → 173.5s = **2.09×**（子集缓存命中率高于全片，故略高于全片 1.90×）。

### 3.3 缓存驱逐路径（全片额外覆盖，8 段子集没触到）
全片 optimized 做 1691 次 raw grab，`_grab_frame_cached` 上限 512 即 `clear()` ⇒ 整轮触发 ~3 次清空。
多线程 check-then-clear 竞争下输出**仍逐位一致** ⇒ 驱逐+并发最坏只导致冗余重抓，不影响正确性。

### 3.4 回归门
- 后端全套 `python -m unittest discover -s mvp/tests`：**455 OK (skipped=2)**（与基线逐字匹配）。
- API 套件 `mvp/api/tests`：**99 OK**。
- 零 `mvp/src` 行为改动（仅抓帧调度）；零 `feature_version` 变更；生产三指标不变（旋钮默认仍关）。

### 3.5 整条 locate() 验证（最强证明：完整生产路径，非微探针）
`mvp/scripts/time_full_locate_optimized.py`（优化后代码、双旋钮开、走完整 `srv.locate()`，test1 全片）：
- **实测用户侧墙钟 = 1052.4s = 17.54 min**（55 段；直接测量，非推导）。
- **FULL-LOCATE BIT-IDENTICAL: True** —— 整条 locate 输出 == 续33 原始串行生产产物
  `work/spl_patch_arms/on_test1.results.json`。且不止 span 级：`strip(result_id)` 后**全部确定性字段逐一比对**
  （`confidence_score`/`candidate_rank`/`alternatives`/`reasons`/`original_segments`/信封字段
  `schema_version`/`original_video`/`edited_video`）**差异段数 = 0**。产物字节数 99953 == 参照 99953。
  ⇒ 零语义证明从「旋钮段微探针」升级到「完整生产 locate 路径的全字段级」。
- **常量 P 反推**（pre-knob 管线，与旋钮无关）：P = opt_full − opt_knob = 1052.4 − 664.9 = **387.5s = 6.5 min**
  （吻合档案 OFF 臂 7–8 min）。serial_full = P + serial_knob = 387.5 + 1262.3 = **1649.8s = 27.5 min**。
- **full-locate 提速 = 1649.8 / 1052.4 = 1.57×**（稳健：只依赖实测 opt_full + 实测旋钮省 597.4s +
  「P 与旋钮无关」结构事实，P 在双臂相消，不受 P 测量误差影响）。
- **ON/OFF 开销比**：串行 1649.8/387.5 = **4.26×**（吻合档案「4~5×」）→ 优化 1052.4/387.5 = **2.72×**
  （**实测确认**了 §4 此前标注为推导的「2.4~3×」）。
- ⚠️ 交叉核对留痕：档案续33 直测 test1 ON 臂 ≈31min（串行），本次推导 serial_full = 27.5min，差 ~3.5min
  ——推测源于档案那次 A4 编辑缓存冷/机器态差异；不影响 1.57× 结论（该式 P 相消，不依赖 serial_full 绝对值）。

---

## 4. 边界与诚实标注
- **两个提速口径分清**：① **旋钮段墙钟 1.90×**（微探针 off 批 → 两旋钮，同 harness 双臂直测）；
  ② **整条 locate 墙钟 1.57×**（用户实际体验；因 pre-knob 管线 P≈6.5min 未被本次优化触碰，
  按 Amdahl 稀释，1.57× < 1.90×）。引用时须标明是哪个口径。
- **只验了 test1 全片**：2mkv/test2/test3 未跑全片 A/B（成本考量）；但零语义由「整条 locate 全字段逐位一致 +
  三向 span 一致 + 回退路径兼容 + 455/99 全绿」保证，提速机制（grab 占比 77.6%）与片子无关，可外推。
- **未做杠杆3**（改 REFINE_FPS/收窄窗口/CLS 预筛）：那类会改结果、需三指标回归，本轮只做零语义的 1+2。
- **旋钮默认值仍关**：本批只提速，不翻默认。**ON/OFF 开销比已从 4.26× 降到 2.72×（实测）**，
  续33 后续「三选一」拍板的时间口径据此更新：高精度模式全片 locate = **17.54 min（test1 实测）**，
  不再是原「30–45 分钟/片」——(c) 选项的 `PRODUCT_INTRO` 文案可下修到「高精度 ≈18 min/片（test1 实测，
  片子长度相关）」。默认值翻转仍待用户拍板 + r3 真机复核。

## 5. 产物
- 探针 `mvp/scripts/probe_split_patch_timing.py`（baseline/optimized 双模，实例级打点，span dump；旋钮段 A/B）。
- `mvp/scripts/time_full_locate_optimized.py`（整条 locate 优化后墙钟 + 全字段逐位一致验证）。
- `work/spl_patch_timing/`：`baseline_test1.spans.json`（8段）· `optimized_test1.spans.json`（8段）·
  `baseline_full_test1.spans.json`（41段）· `optimized_full_test1.spans.json`（41段）·
  `ref_on_test1.spans.json`（生产参照规范化）· `baseline_origcode_test1.spans.json`（改前原始代码 8 段）·
  `fulllocate_on_test1.results.json`（整条 locate 优化后产物，99953 bytes == 参照）·
  `baseline_full_run.log` / `fulllocate_optimized_run.log`（运行日志）。
