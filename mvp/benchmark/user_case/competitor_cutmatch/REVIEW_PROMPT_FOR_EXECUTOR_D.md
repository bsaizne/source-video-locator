# 判卷侧复核 · `PROMPT_FOR_EXECUTOR_D.md`**（v2）**　—— 并含我方记录更正

> 读者：**执行方**（`D:\claudework\cutmatch-analysis`）。你们已把 v1 复核的 **7 条 P0 + 5 条 P1** 并入 v2 —— **判卷侧确认收到并认可**。
> 本轮我方做两件事：① 对 v2 逐条回执（含一条**你们纠正了我方**的关键数字）；② 撤回并更正我方自己的错误记录。
> 日期：2026-09-26（续）｜定级：全部产出仍为**「代理复现（推断级）」**。

---

## 0. 对 v2 的总体回执

| 项 | 状态 |
|---|---|
| P0-1 每查询一行（含未匹配） | ✅ 已并入，schema 里 `matched` / `not_in_source` / `source_span: null` 齐全 |
| P0-2 `query_id` + B 段 `scene_index` 回溯 | ✅ 已并入（并固定用 **t050** 档查询单元，正确做法） |
| P0-3 时间码双写（各自 `fps_rational`） | ✅ 已并入，且写明"严禁跨文件混算" |
| P0-4 候选表落盘（top-k + channel + akaze 内点） | ✅ 已并入（k≥10，默认 20），正是我方分诊所需 |
| P0-5 `ordered_search_max_seconds` | ⚠️ **你们纠正了我方**：默认值是 **1800.0** 而非 7200 —— 我方独立字节复核**确认你们是对的**（见 §1）；风险因此**更大**（四部原片全部超限） |
| P0-6 seed + 重复跑一致性 | ✅ 已并入 |
| P0-7 原片侧索引口径明写 | ✅ 已并入 |
| P1-1～P1-5 口径混杂登记 | ✅ 已并入（且 P1-3 加了"额外跑一档 top_k≈28"的可选项，很好） |

**新增 1 条待澄清（P0-8，不阻塞开跑）**：profile v2 里 `source_sample_rate` = **2**、`commentary_sample_rate` = **2**（两者都是 `<<PREV>>` 语义，见 §2），
与 `fast_options.source_global_fps = 1.0` 并存。请说明这两个 `*_sample_rate` 的**单位与作用阶段**（帧步长？采样频率？只作用于 precise 阶段？），
并在 manifest 里写清 D 段实际用的是哪一个 —— 它直接影响"查询单元代表帧"与"源侧候选密度"。

---

## 1. 我方独立复核：`ordered_search_max_seconds = 1800.0`（**你们对，我方错**）

| 量 | 值 |
|---|---|
| profile v2 条目 | `/fast_options/ordered_search_max_seconds` = **1800.0**，`level=确证` |
| 键偏移 | `key_off 0x174bc26a` → 解码出键名 `ordered_search_max_seconds`（**名字自证通过**） |
| 值偏移 | `val_off 0x174bcc1f` → raw `66 00 00 00 00 00 20 9c 40` → 解码 **1800.0** |
| 名次配对 | 该 blob 内按 `key_off` 名次 = **17**，按 `val_off` 名次 = **17**（同序，配对成立） |
| 我方旧读数 | `verify_cutmatch_bindings_v2.py` §8.2 读 **7200.0**，来源是**键名之后的相邻字节**（`name` 后 20 字节 = `66 00 00 00 00 00 bc 40` + 下一个键名 `min_supp…`）⇒ **相邻配对假象** |

⇒ **我方撤回 7200 这条绑定**（这是同类假象的**第 3 例**：前两例是 `offset_refine_dtw_min_score` 0.1→0.55、`commentary_short_scene_min_frames` 180→8 的取值归属）。
我方已把**全部历史"相邻配对"绑定**与 profile v2 的 `val_off` 值做了一次系统对账（脚本 `mvp/scripts/reconcile_cutmatch_bindings.py`）：
**11 条中只有这 1 条真错**，其余 10 条一致（其中 `commentary_boundary_refine_max_move_frames` 的 `<<PREV>>` 解析后 = 前一条 `..._near_cut_frames = 16`，与我方读数一致）。

**风险重估（比 v1 更严重）**：上限 = **1800 s = 30 min**，而本次四部原片 **全部超过**：
2.mkv **7,667 s** / test1-om **8,229 s** / test3-om **10,177 s** / test2-om **5,051 s**（v1 按 7200 估时 test2-om 被误判为"安全"）。
⇒ v2 §P0-5 的处置（**不施加该上限，或仅当"单次搜索窗"理解，并在 manifest 显式声明**）我方**完全同意**；这仍是本轮最大的假差异来源。

---

## 2. 新增待澄清（P0-8）：`source_sample_rate` / `commentary_sample_rate` = 2 的语义

profile v2（`precise_options`，blob `0x174e0158`）里：

| 键 | 值 | 值偏移 | 备注 |
|---|---|---|---|
| `source_sample_rate` | **2** | `0x174e1808` | 与 `source_global_fps=1.0`（fast_options）**并存** |
| `commentary_sample_rate` | `<<PREV>>` → 取前一条值 = **2** | `0x174e180a` | 与 `commentary_global_fps`/编辑侧重采样可能同源 |

我方关心的是：**D 段实际以哪个口径抽查询帧与源侧候选帧**。请给出单位与阶段，并写进 manifest；
若 `2` 是"帧步长/倍率"而不是"fps"，请明写。**这一条不阻塞开跑**（先跑 test1 即可），但会影响后续对照解读。

---

## 3. 口径混杂因素（v2 §P1 已并入，此处仅补一句判读纪律）

D 段产物到手后，我方对照会**固定写成**「**224 口径下的代理复现 vs 我方 518 口径（索引 1.0 fps / 编辑侧 2 fps / 候选池 28）**」，
并在结论里显式声明这 5 条混杂（P1-1～P1-5），**不得**把它们读成"竞品优劣"。

---

## 4. 我方记录更正（本文件同日追加）

| 位置 | 原记录 | 更正为 | 依据 |
|---|---|---|---|
| 本仓 `INTEL_REQUESTS_CUTMATCH.md` §8.2 / `FINDINGS_CUTMATCH_CONSTANTS_ADOPTION.md` / `.agent/STATE.md` / `.agent/TODO.md` | `ordered_search_max_seconds = 7200`（确证） | **1800.0**（确证） | profile v2 `val_off 0x174bcc1f` + 我方字节复核 + 名次配对 |

**方法论教训（写入我方档案）**：`FINDINGS/09` 式的"键名相邻字节 = 该键的值"在 Nuitka 常量块里**不可靠**（键名表与值表分离、且存在 `<<PREV>>` 复用），
已造成 **3 例**错误取值归位。我方今后的绑定复核统一走：**profile 的 `key_off`/`val_off` 字节偏移 + 名字自证 + 名表↔值表名次配对**（脚本 `verify_cutmatch_profile_pairing.py` + `reconcile_cutmatch_bindings.py`）。

---

## 5. 我方收到 D 产物后的动作（不变）

1. `import_competitor_proxy.py --loc <localization.json> --case <…>` → `work/proxy_<case>.results.json`；
2. `measure_four_results.py` 同口径对照（基线 严格 117/139 · 场景 137/139 · 负例 4/9），全程标注「代理复现（推断级），非竞品实测」；
3. 候选表到手后做"**池内选错 vs 未进池**"分诊，与我方 `work/loc_retrieval_audit.json`（HIT 117 / rank≤3 19 / rank>20 1）对照；
4. AKAZE on/off 差异单列，并标注"我方无此通道"。

> 本文件**未改动** `D:\claudework\cutmatch-analysis` 任何文件；对方取值均为只读引用。
