# CHANGELOG

## 2026-10-06（续57 夜间批二）— 计划项 1「ISC margin 门标定」= 判负关闭（两级探针 + 机制否证，已回滚）

- **立项修正**：材料复读发现 t1r08c/t1r12a 非子镜头族，而是 ISC margin 卡门（探针口径
  0.0457/0.0391 < 0.05 门）⇒ 方向改为门标定。
- **第一级（全量 0.035 臂，`probe_isc_margin35.py`）**：2mkv 2 行翻转读图裁决 =
  row23（1.5s 近场）**真增益** + row77（0.9s 窄段 HIGH 被远跳 56.6s）**真损失** ⇒
  亚门分不可作远距重锚证据。
- **第二级（近场限定 offset≤3s 才降门）**：实现+单测阶段**机制否证**——`_score_mid`
  评分窗（mid ± (w/2+1.5s)）内取 max ⇒ 近场峰必被主分吸收 ⇒ margin 恒 ≈0，无可达面；
  探针点评分口径与 runtime 窗 max 口径不可比（口径错位教训）。
- **裁决 = 判负关闭**：全量不安全 + 近场无可达面。t1r08c/t1r12a 真救回需换评分几何
  （主分排除峰侧/锚点级评分），与「扫描行为缩减」同层级立项，本轮不做。
- **处置**：isc_refine/config/locator_service 改动与单测**全部回滚**（「判负不进 runtime
  不留通道」纪律），后端 **540 OK** 复验；探针留证（`probe_isc_margin35.py` /
  `probe_isc_subgate_ab.py` + `work/isc_margin35/` 帧证据）。明细 FINDINGS_NEXT_DIRECTIONS §7。
- 按口令：**未提交 git / 未打包 r9**（工作区 = 三旋钮翻默认 + 回归锁 + pd__lib 修复 + 探针）。

## 2026-10-06（续57 夜间批次）— 三旋钮翻默认（四片联合 PASS）+ 真机复核五件 + FP16 探针判负

- **三旋钮翻默认**（用户口令「翻」，前置=补齐三片证据）：`probe_defaults_flip_ab.py` 联合双臂
  四片全 PASS（test1 0/55 · test2 **1.294×** 0/67 · test3 **1.276×** 0/103 · 2mkv **1.162×** 0/84，
  `all_identical=True`）⇒ `patch_refine_grid=True` · `rerank_grid_grab=True` · `cluster_workers=4`
  生效，三指标 136/131/138/4·9 自动成立。**新默认态 ≈ 15~31 分钟/片**
  （test1 22.0 · 2mkv 27.0 · test2 30.1 · test3 31.6，on 臂实测）。后端 540 OK。
- **真机复核（UI dev 浏览器目检）**：续57 四件全过（新建直达构建页/按钮间距/剪辑×删除/卡片
  不溢出+文件名省略），**抓修第 5 处同类溢出**（`.pd__lib` grid min-width:auto ⇒ 面板撑破），
  截图复验 scrollWidth==clientWidth；vitest 136 · 双 typecheck 绿。
- **FP16 探针（L4 销项，`probe_fp16_ab.py` 证据级）**：ISC **1.806×**（40.2→72.6fps，cos
  0.999992/max|d|=0.000956）但 DINOv2 CLS **0.845×（更慢）**、patch dual 1.014×（无肉）；
  采纳代价 = feature_version bump + 全量重建索引换 ~2.5% 全链 ⇒ **判负（有据）**。
- **方向盘点评估**（`FINDINGS_NEXT_DIRECTIONS_20261006.md`）：抓帧三桶已到解码地板（账单拟合
  实测 ≈ 固定+解码秒，管道已被网格化消掉）⇒ 纯性能侧挤干；剩余大杠杆 = 扫描行为缩减（语义
  变更需拍板）。精度首选 = **ED 子镜头切分对齐**（救 t1r08c/t1r12a part 族）；工程首选 =
  **mkv 建表异步化**。
- 按口令：**未提交 git / 未打包 r9**。工作区 = config 翻默认 + 回归锁 + pd__lib 修复 +
  3 探针（新增 defaults_flip_ab / fp16_ab，rerank_grid_ab 路径修正）。

## 2026-10-06（续57）— UI 真机反馈四件：卡片溢出 / 新建直进构建页 / 剪辑可删 / 按钮间距

- **① 首页卡片路径溢出**：`ProjectCard.vue` 根因 = grid 子项默认 `min-width:auto`，长绝对路径把
  按钮撑出网格轨道（卡内 ellipsis 失效）⇒ `.pcard` 加 `min-width:0`；顺带「剪辑」行改只显示
  文件名（basename，与源片行口径一致）。
- **② 新建项目直进构建页**：`useCreateProject.ts` 重写——删掉「先弹原生对话框选剪辑视频再跳转」
  （该流程同时是 2026-09-29 editedVideos 断链的根源），HomePage/ProjectsPage 两入口统一为
  直接创建空项目 → 跳 ProjectDetailPage，素材在构建页自选（桌面态原生对话框入口不损失）。
  `projectsMedia.test.ts` 旧流程 3 项断言合并重写为 1 项（含「桌面桥在位也不得弹对话框」锁）。
- **③ 剪辑视频可删除**：`stores/projects.ts` 新增 `removeEditedVideo(id, path)`（deep watch
  自动持久化）；`ProjectDetailPage.vue` 剪辑列表每行加与源片库同款 `pd__rm` ×按钮 + 路径
  ellipsis/title（此前只能加不能删）。
- **④ 按钮行间距**：`.pd__pickrow` 加 `display:flex; gap:10px; flex-wrap:wrap`（源片三按钮/
  合并行/手动粘贴行统一生效）。
- **门禁**：vitest **136 全绿**（净 -2：旧流程 3 项→1 项）· 双 typecheck 干净。纯展示/流程层，
  零后端/API 契约改动，零 feature_version。

## 2026-10-06（续56）— other 桶网格接线落地（新旋钮 `rerank_grid_grab`，test1 双臂 1.132× 零语义）

- **执行续55「下一刀候选」**：计时账单分桶里 `other` 294.4s=22%（locate 主循环 patch_refine
  之外的源片抓帧）＝ ① patch v2 近场池（±30s@4.0s 均匀网格，windows 账单步长 4.0s 占绝对主导、
  锚点全整数秒）② 字牌锚定源窗（每窗 4 个 `_rep_times` 均匀点）。两者等差整数秒 ⇒ 网格抽取
  最契合（现役窗解码搬全跨度 25fps 帧，4s 步长下管道量 ÷~100）。
- **落地**：新旋钮 `pipeline.rerank_grid_grab`（**默认关**，与 `patch_refine_grid` 语义解耦、
  独立 A/B 独立拍板）。开 = 两调用点走 `_grab_grid_batch`（`%.6f` 修复后的同帧契约；漏帧
  逐帧回退；`max(0,·)` 削出的重复 0.0 锚点由 dict 去重，语义不变）；关 = 逐位回
  `_grab_frames_parallel`。`config.py` 注释含证据与回退路径。
- **验证**：test1 同脚本紧邻双臂（`work/rerank_grid_ab/`，DML 断言）off **1601.0s** →
  on **1413.7s** = **1.132×**，strip(result_id) **55 段 0 差异 + 信封一致** ⇒ 端到端零语义；
  与账单预期吻合（other 桶 22% ⇒ 1.13~1.16×）。**续54~56 干净双臂最大一刀**
  （`patch_refine_grid` 1.068× / `cluster_workers` 1.071×）。
- **门禁**：单测 +7（近场池 4 + 字牌 2 + config 默认锁 1）；后端全套 **540 OK (skipped=2)**。
- **产物**：`mvp/scripts/probe_rerank_grid_ab.py`（同脚本双臂探针，支持 `--case` 四片）+
  `work/rerank_grid_ab/{off,on}.results.json, ab_summary.json`。
- **待拍板**：git 提交（续54~续56）/ 翻默认三旋钮（各需三片双臂）/ r9 出包。
  未改 GT / 未 bump feature_version / 现役默认态行为不变。

## 2026-10-05（续55）— 账单换位到「解码跨度」+ `%.6f` 真缺陷修复 + 三项提速（test1 21.5→18.0min）

- **起因（用户问「跑一片多少时间/不是用 GPU 吗/下一刀」）**：给计时探针加**阶段归因**
  （`probe_locate_stage_timing.py`：窗 spawn/抓帧/逐帧嵌入都按 `@stage` 记账 + 逐次抓帧目标清单
  `windows_*.jsonl`），并写离线复算器 `analyze_window_merge.py`（以「每段抓编辑片查询帧」为段边界）。
- **账单（test1 1332.1s，默认态 L2 on + grid on）**：窗 spawn **680 次摊在 561 次调用**（≈1.2 簇/调用）；
  拟合成本 = **~0.17s/次固定 + 0.164s/解码秒**（由 isc 0.92s@4.6s、patch 1.12s@6.3s、other 1.77s@9.75s 三点解出）
  ⇒ 续54 之后瓶颈已从「spawn 次数」换位到「解码秒数/管道搬运」。
  **CPU 抓帧 1043s = 78%；DML 推理合计 ~239s = 18%**（`embed.dinov2` 35.1 + `frame_dual` 128.8 + ISC 75.2）。
  ⚠️ **更正续54 的「GPU 仅 2.4%」**：那只数了 `backend.embed_frames` 一个入口，没枚举 patch/ISC 两个逐帧入口。
- **假读数留痕**：用 `id(frame)` 统计「重复嵌入」得 dup=1463/2130，看着支持嵌入缓存；按 `round(t,3)`
  键实测同段重复率 **0.00** ⇒ 前者是 numpy 对象释放后 id 被复用造成的假信号。**嵌入去重方向关闭（有据）**。
- **真缺陷（`%.6f` 修复）**：`FFmpegIO._grid_select_expr` 以 `%g` 打印簇起点与步长 ⇒ 三位小数被截成
  两位（3638.351 → 3638.35），select 窗口起点系统性偏离目标 ≤0.005s。后果不是「整格跳位」
  （那会被 `max_pts_lag=0.5` 护栏抓住），而是**偏差 <0.5s 的「晚一个源帧」分配被静默接受**。
  - 证据 = 跨源合成 micro（`probe_patch_grid_shape.py --mode synth`，30 窗 × 4 片 = 1200 点，
    形状 = 生产 patch 窗：三位小数起点 + 步长恰 1.0s + 10 点）：修复前 **test2 1/300 · 2mkv 6/300 ·
    test3 6/300 不同帧**（test1 0/300，那片锚点相位本就对齐，所以 test1 上看不出来）；
    改 `%.6f` 后 **四片 1200/1200 逐字节同帧**，且 grid/base = 1.86~3.29×。
  - 影响面 = 所有带小数锚点的网格调用（宽扫粗扫 `round(wlo+i*2,3)`、isc/patch 精扫、L2 建表）。
    **L2 已入库索引标签全为整数秒 ⇒ 不受截断影响，无需重建索引**（实测 times 无一小数）。
  - 端到端零语义（修复无旋钮、直接生效，故按改动前默认态产物对照）：test1 **0/55** ·
    test2 **0/67** · test3 **0/103** · 2mkv **0/84**（`work/spawn_consolidation_regress/postfix_*`，
    参照 = 续54补 的默认态臂；新臂墙钟 1384.2/2423.4/2499.9/1971.9s 与参照比 0.94~1.20× 属跨 run 噪声）。
- **三项提速**：
  1. **新旋钮 `pipeline.patch_refine_grid`（默认 False）** = patch 候选精排窗走网格抽取
     （`_grab_source_grid`，漏点逐帧回落）。micro 真实形状 2.28×、120/120 同帧 ⇒
     test1 同脚本双臂 `probe_patch_grid_ab.py`：**1384.2 → 1296.0s = 1.068×**，strip **0 差异**。
     与账单一致：patch 窗桶 172.4s÷2.28 ≈ 省 75s ≈ 全链 +6%。
  2. **`patch_refine` 段内候选窗并集（无旋钮）** = 一段所有候选窗并成一次 `grab_frames`
     请求（各窗仍按 gap/span 自然成独立簇）⇒ 目的给 (3) 提供可并发的多簇调用。
     **网格形态刻意不并集**：select 表达式按「簇起点 + 统一步长」生成，只服务单一相位，
     多相位并集会让目标落在窗口中间 ⇒ 静默拿到晚 ≤0.5s 的帧（护栏抓不到）。
     零语义验证 = test1 与并集前同代码臂（`work/patch_grid_ab/off.results.json`）**0/55 差异**。
  3. **新配置 `media.cluster_workers`（默认 1 = 现役串行逐簇）** + `FFmpegIO.grab_frames`
     簇间 `ThreadPoolExecutor` 并发（`_run_cluster` 内 MediaError ⇒ 返回 None，逐帧回退语义不变）。
     test1 同脚本双臂 `probe_perf_ab.py --knob media.cluster_workers=4`：**1155.4 → 1078.9s = 1.071×**，
     strip **0 差异**（`work/perf_ab/cl4.*`）。
- **现役耗时口径**：test1 = **18.0 分钟**（本会话开始 21.5min）。⚠️ 同代码态跨 run 实测
  1155.4 / 1287.3 / 1384.2s ⇒ **方差 ±18%**，大于既往 ±10% 口径 ⇒ 提速数字只认同脚本双臂。
- **口径同步**：`PRODUCT_INTRO.md` 高精度全片 27~43min → **21~40min**（四片实测 21.5/31.3/38.0/40.3，
  并写明同条件对照 test1 27.9→21.5 = 1.30×）。⚠️ 更正当日口头汇报两条：
  ①「打包态比实验室 +10%」不成立（r8 打包 E2E test1 24.3min 与同代码态实验室 27.9min 同量级，
  1.56× 属 r3 时代已过期）；②「test2 回归 0/67」曾在**尚未出数**时被我说成已完成 —— 已当场更正，
  档案无污染，真数据随后于 21:45 落地。
- **门禁**：后端全套 **534 OK (skipped=2)**（+8 = patch 网格 3 · 并集 2 · 簇并发 3）。
  未改 GT / 未 bump feature_version / 未 git 提交 / 新旋钮均保持默认关。
- **下一步**：① 三片回归验「并集（无旋钮）+ cluster_workers」；② d3d12va 硬解窗实测
  （`probe_hwaccel_window.py --hwaccel d3d12va`，本机 AMD 独显唯一未测入口）；
  ③ 若并行成立，接「other 桶」（逐段 patch 重排窗 294.4s=22%，跨度中位 24.8s/步长 4s，
  网格形态最契合）；④ 翻默认与 git 提交等口令。

### 续55 补 — 硬解穷尽（d3d12va / dxva2 判负）+ 簇并行双臂 PASS（2026-10-05 23:43）

- **d3d12va（本机 AMD 独显唯一未测入口）= 本 build 解不出帧**：三片各 6 窗，
  `hw 可用窗 0/6` + `md5 0/6`；单窗真实 stderr = `[hevc] hardware accelerator failed to decode picture`。
  ⇒ 探针汇总里那个 **31~148× 是空输出造成的假速度，不成立**。同批有意义的两列 = 解码地板：
  test1 sw 3.94 vs hw 5.07（**0.78×**）· 2mkv 2.20 vs 3.31（**0.66×**）· test2 4.00 vs 5.17（**0.77×**）
  ⇒ 即便出帧，硬解本身也不比软解快。
- **dxva2（同族旧版）= 同样 0/6 出帧**，地板更差：4.98 vs 9.89s（0.50×）· 2.6 vs 6.8s（0.38×）·
  4.49 vs 9.5s（0.47×）。
- **AMD 侧三条入口就此穷尽**：d3d11va 能出帧但续54 实测净 **0.42×**；d3d12va / dxva2 不出帧且地板
  更慢 ⇒ **硬解方向关闭（有据）**；要回本必须改形态（帧不回 CPU 的 GPU 前处理链，重构级）。
  macOS `videotoolbox` 仍未测（H3 机器上做）。产物 `work/hwaccel_probe/probe_hwaccel_window_{d3d12va,dxva2}.json`。
- **簇并行双臂 PASS**：`probe_perf_ab.py --case test1 --knob media.cluster_workers=4`
  ⇒ off **1155.4s** / on **1078.9s** = **1.071×**，`strip(result_id)` 逐字段 **0 差异**、
  信封一致、55 段。test1 现役（含本批并集，workers 仍默认 1）= **19.3min**，开并行 = **18.0min**。
- **并集的零语义已单独核**：`work/perf_ab/cl4.off.results.json`（并集后）vs
  `work/patch_grid_ab/off.results.json`（并集前、同代码态）= 55 段 **0 差异** + 信封一致。
  ⚠️ 并集的**速度**贡献无法与噪声分离（同代码态跨 run 实测 1155.4/1287.3/1384.2s ⇒ ±18%），
  故不报并集百分比，只报「同脚本双臂」那一对的 1.071×。
- **运行中**：段内并集三片回归（`run_union.log`，参照 = 本批 postfix 臂 2423.4/2499.9/1971.9s）。
- 未改 GT / 未 bump feature_version / 两新旋钮仍默认关 / 未 git 提交。

### 续55 补二 — 并集三片 PASS 且推翻早先判断：现役默认态 19~31 分钟（2026-10-06 00:28）

- **三片回归**（`work/spawn_consolidation_regress/union_*`；参照 = 本会话同代码态 postfix 臂，
  唯一差量 = 段内并集）：

  | 片 | 并集后 | 参照 | 比值 | strip 差异 |
  |---|---|---|---|---|
  | test2 | **1862.8s**（31.0min） | 2423.4s | **1.223×** | **0/67** |
  | test3 | **1861.6s**（31.0min） | 2499.9s | **1.298×** | **0/103** |
  | 2mkv | **1407.2s**（23.5min） | 1971.9s | **1.333×** | **0/84** |

  ⇒ `all_identical=True` ⇒ **并集零语义四片全成立**（test1 另有「与并集前臂 0/55 + 信封一致」对照）。
- ⚠️ **更正上一条里写下的判断**：「并集的速度贡献无法与噪声分离 ⇒ 不报并集百分比」是按 **test1**
  的形状统计推的（那片同段候选窗目标重复率 0.00、并集解码跨度 845→682s）。另三片候选窗
  **重叠度高** ⇒ 并集实测省 **1.22~1.33×**，是本批最大的一刀。
  **教训入档：单片窗口形状统计不能外推成成套结论；形状类判断必须跨片实测。**
- **现役默认态耗时**（含 `%.6f` 修复 + 段内并集；`patch_refine_grid` / `cluster_workers` 仍默认关）：
  **test1 19.3 · 2mkv 23.5 · test2 31.0 · test3 31.0 分钟 ⇒ 19~31min**
  （本会话开始时同四片 21.5 / 31.3 / 38.0 / 40.3 ⇒ 一天内约 **1.3×**，且结果逐字段未变）。
  `PRODUCT_INTRO.md`「快」章已同步 21~40 → **19~31 分钟**。
- **口径标注（如实）**：上表三对是**跨 run** 对照（参照臂为本会话内刚测的同代码态臂；三片同向、
  幅度一致 ⇒ 方向可信，幅度按 ±18% 方差读）；严格「同脚本紧邻双臂」的干净数字仍只有
  `cluster_workers` **1.071×** 与 `patch_refine_grid` **1.068×** 两对。
- 未改 GT / 未 bump feature_version / 未 git 提交。

## 2026-10-05（续54）— 定位侧提速：窗 spawn 账单定瓶颈 + 三件合并优化（零语义 1.30×）

- **起因（用户问「首次速度/定位侧/GPU 承担 CPU」）**：计时探针（`probe_locate_stage_timing.py`
  更新：shot_split 目标修正 + 新增窗 spawn 级记账）给出精确定位账单——**窗抓帧 892s = 61%**，
  ~4600 目标摊在大量小窗，每窗 spawn 固定开销 ~1s（spawn+seek+解码 0.6s + Python 读帧等 0.4s）
  是主体；GPU 嵌入仅 2.4%。
- **路径 A（硬解）实证判负（超持续47）**：`probe_hwaccel_window.py` 实测 d3d11va 窗解码
  **反而 0.42×**（逐帧回传开销 > 解码收益；单帧模式 3× 慢 = D3D11 初始化 ~0.2-0.5s/spawn）。
  ⚠️ 探针修出关键 ffmpeg 知识：**`-copyts + -t` = 0 帧**（copyts 下 -t 按原始时间轴裁剪；
  产品用 copyts 时从不配 -t，靠目标满足后 terminate）——续54 首轮探针数据全部作废重测。
  ⚠️ 机制层好消息留档：续47 机制探针证实**统一转换链（hw 解码→format=mid→bgr24）与产品
  软解逐字节一致**（8-bit/10-bit 全过）⇒ 像素契约并非不可保，仅性能不成立。
- **三件落地（全部零语义，test1 三方 strip 逐字节全等）**：
  ① `isc_refine` 打分批量预取 `_preembed_mids`（`_mid_ts` 抽公式）——每段 6~8 个评分窗
  spawn 合并为 1~2 个；② `FFmpegIO.metadata` 实例级缓存（按路径+size+mtime，省 0.08s×~800）；
  ③ 精扫细化窗网格抽取（新旋钮 `isc_refine_grid_refine` **默认关**——fine_ts 本就是 1s 网格，
  同 first_ge 契约；实测单独收益≈0 因成本在 spawn 数，保留作管道减负基建）+4 单测。
- **验证**：后端全套 **526 OK (skipped=2)**；A/B（同脚本同条件双臂）off 1671.0s → 新 off
  **1287.3s = 1.30×**（on 1265.5s）；三方 strip（合并前基线/新 off/新 on）**逐字节全等**。
  保守口径：跨脚本运行方差 ±10%+，四片回归后方能定最终数字。产物 `work/grid_refine_ab/`
  （v1 基线存 `.v1`）+ `work/locate_timing/` + `work/hwaccel_probe/probe_hwaccel_window.json`。
- 未改 GT / 未 bump feature_version / 未提交。翻默认项：无（consolidation 无旋钮直接生效，
  grid_refine 维持默认关待用户拍板）。

### 续54 补 — 四片零语义回归 = PASS（2026-10-05 18:28，用户口令「跑三片回归」）

- **必要性**：窗 spawn 合并 + metadata 缓存**无旋钮、直接生效** ⇒ test1 之外三片必须自证零语义。
- **新脚本** `mvp/scripts/probe_spawn_consolidation_regress.py`：现役默认态直跑（`load_config()` 不
  改任何旋钮）+ `assert isinstance(srv.backend, DirectMLBackend)` 硬断言 +
  strip(`result_id`) 逐行比对 + 墙钟。参照臂 = `work/isc_l2_ab/on_<case>.results.json`
  （续52-G 常态链复验产物 = 续54 改动**之前**的现役默认态）。
- **结果**（test2 → test3 → 2mkv 顺序跑，独占 GPU ~1.9h）：

  | 片 | 新臂墙钟 | 段数 | strip 差异 | 对照参照臂（跨 run） |
  |---|---|---|---|---|
  | test2 | 2277.9s (38.0min) | 67 | **0/67** | 1.21× |
  | test3 | 2416.4s (40.3min) | 103 | **0/103** | 1.17× |
  | 2mkv | 1875.4s (31.3min) | 84 | **0/84** | 1.29× |

  启动日志逐片确证 `BACKEND=DirectMLBackend l2=True grid=True grid_refine=False`；
  索引全部命中入库目录（无重建）。
- **结论**：合并前 test1 三方全等 + 本批三片逐字节全等 ⇒ **四片逐字节全等**，故三指标
  136/131/138/4·9 **自动成立，无需重跑**。**提速口径**：干净数字只报 test1 **1.30×**（同脚本双臂）；
  本批 1.17~1.29× 系跨 run，参照臂墙钟含 GPU 争用（同批 test1 参照臂 4662.5s vs 干净 1671.0s），
  仅作物级参考。PRODUCT_INTRO 27~43min 口径仍覆盖（38.0/40.3/31.3/21.5min）。
- 产物 `work/spawn_consolidation_regress/`（`{case}.results.json` + `regress_summary.json` + `run_all.log`）；
  明细 `FINDINGS_COST_STRUCTURE_LEVERS_20261003.md` §5.7。未改 GT / 未 bump feature_version / 未提交。
- **口径同步（用户令「改吧」）**：`mvp/docs/PRODUCT_INTRO.md`「快」章高精度全片定位 27~43min →
  **21~40min**（四片实测 21.5/31.3/38.0/40.3min，标注同素材同条件 test1 27.9→21.5 = 1.30×）。
  ⚠️ **更正当日口头汇报**：我先前说「打包态比实验室 +10%」不成立——r8 打包 E2E test1 24.3min
  vs 同代码态实验室 27.9min，打包与实验室在同一量级（跨 run 方差 ±10% 内），旧 1.56× 结论属
  r3 时代（后端 DML 未生效）已过期。

## 2026-10-05（续53 补三）— E2E 抓到续52-G 潜伏崩溃（第二次分析必崩）+ 修复 + r8 重验全过

- **runtime 功能确认（r8 包内 backend，探针 `probe_pkg_runtime_features.py`）**：health/DirectML
  生效 · `/api/fs/browse`（续41）在包内可响应 · **L2 翻默认行为证据**（syn 定位中日志
  `isc l2 index build started/built` ⇒ 旋钮默认开已在包内生效）· patch/ISC 均 GPU ·
  PYZ 模块表含 isc_l2_index/isc_refine/fsbrowse · main.js 含 SVL_ISC_ONNX/SVL_PATCH_ONNX 注入。
- **E2E 抓到真崩溃**：test1 全链（打包态 headless）在 isc_refine 入口崩 LOC-9999。归因路径：
  worker 异常细节进 no-op logger（无堆栈）→ venv 复现 PASS 判打包特异 → 补堆栈留痕后拿到
  **根因 = `_isc_l2_validated` 被初始化为 `{}`（dict），`.add(ck)` 即 AttributeError**
  （续52-G 引入；只命中「**加载已存在的有效索引**」分支——续52-G 复验四片全走重建分支故漏测；
  venv 复现因索引根不同（无 SVL_DATA_DIR ⇒ Local 下无索引）走了建表分支而 PASS，双根目录对齐后矛盾解除）。
  **影响面 = 用户第二次分析同一部原片必崩**，E2E 价值确证。
- **修复**：① `set()`（+2 回归测试：有效索引加载不重建不崩 · 字段类型锁）；② worker 兜底异常
  现带 `traceback.format_exc()` 落 tasks logger（dependencies.py 传入，此前 no-op = LOC-9999 无从归因）。
- **重验**：后端全套 **523 OK (skipped=2)**；E2E 第 4 轮 **PASS**（wall=1459.4s=24.3min ·
  55 段 · `isc l2 index loaded frames=8221` 走加载分支 · DirectML）；accept **FAILED=0**；
  zip 0 缺漏 + testzip OK；Electron 启动冒烟 PASS。**r8 zip 已重打（04:36，981MB）**。
- 已知留痕：accept 首跑与刚结束的 E2E 后端进程竞态可致 syn 臂误报 rc=1（手动复跑即过，
  非包缺陷）。未改 GT / 未 bump feature_version。

## 2026-10-05（续53 补二）— git 三笔提交推送 + r8 出包验收全过；旧包只留 r7

- **git 提交推送（用户口令）**：三笔 `199c010..6fcf399 → origin/master`——
  7c6e485 feat(mvp) 续41~续53 产品代码+测试+资产（45 文件）· ee4c58a chore(research)
  探针/脚本+findings 归档 · 6fcf399 docs(agent) 交接 checkpoint。工作区清零。
- **r8 出包**：`mvp/ui/release/Video-Locator-win-x64-20261005r8.zip`（981MB，zip 条目 7078，
  testzip 无损坏，与 win-unpacked 目录逐文件比对 **0 缺漏**；win-unpacked 1.8GB）。
  `accept_packaged_bundle.py` **FAILED=0**（CLS/patch/ISC 资产 sha256 全对 + 包内 backend
  headless 冒烟 49.6s ≤75s + DirectML 生效 + 精排/ISC 均 GPU + 定位出段）；Electron 壳
  启动冒烟 PASS（backend.exe 子进程正常拉起）。
- **删旧包**：r6 zip 已删；**release 目录现役 = r7（回滚）+ r8（最新）**。
- **留痕（包格式发现）**：r7 的 `.zip` 实为 **tar 流**（文件头无 PK magic，当初 tar 打包
  后缀误用 zip）⇒ 1677MB ≈ 未压缩体积；r8 改为真 zip（Compress-Archive Optimal），
  1.8GB→981MB 系压缩率差异非内容缺失。解包 r7 用 tar、r8 用 zip 工具。
- r8 相对 r7 的内容增量 = 续42~续53 全部（ISC 第二意见+宽扫+L2 翻默认、L1 两级翻默认、
  入库层四件、建表性能结案、UI 修复、售后三件等）。未改 GT / 未 bump feature_version。

## 2026-10-05（续53 补一）— L2 源片画面索引宽扫翻默认开（用户拍板口令「1」）

- **落地**：`config.py` `isc_l2_index_enabled` False→True（注释写全证据链与回退路径）+
  回归锁翻转（`test_default_knob_on`）+ DECISIONS 2026-10-05（续53）+ PRODUCT_INTRO 口径同步
  （高精度全片定位 45~60min → **27~43min**（四片 on 臂实测 26.5/30.9/36.9/42.8min），
  新增一次性画面索引代价 5~11min/部原片）。
- **顺带修复生产健壮性**：`_ensure_isc_l2_index` 的 stat/sha256 步骤原在 try 保护外——源片
  不可读时 locate 会直接崩（翻默认后单元测试即刻暴露 3 例）；现与构建失败同语义 =
  WARNING + 回退现役宽扫（加速项失败绝不阻塞 locate）。
- 门禁：后端全套 **521 OK (skipped=2)**。未改 GT / 未 bump feature_version / 未提交。

## 2026-10-05（续53）— mkv 建表性能结案（5.01×）+「mkv 慢」错误归因更正 + builder 三缺陷修复

- **归因更正（重要）**：续52 的「test1(mkv) tp 建表 3.0 帧/s = mkv+select 解码路径本身慢」**不成立**。
  证据：2.mkv（同 mkv）15.7 帧/s；test1-om t=3600s 处 grab_grid 22.1 帧/s；三源关键帧密度同级。
  **真因** = test1-om.mkv 容器时长（8229.28s）比视频流末包 pts（8220.88s）晚 8.4s ⇒ 脚本版
  builder 尾部 8 个死目标各触发一次**整表重试**（每次全片解码 ~350s）≈ 2800s 纯浪费。
  「大簇优化无效（2.6 vs 3.0）」结论同步作废（大簇不影响死目标重试次数）。
- **修复**（`engine/localization/isc_l2_index.py`，runtime/脚本共用）：① `_capped_target_n`
  目标网格按最后视频帧 pts 截断（ffprobe `-read_intervals` 尾扫 0.15s，双级回退）；
  ② 死簇守卫（整簇不可取跳过推进，消除潜在死循环）；③ `c0 += n_c/fps`（fps≠1 簇推进修正）；
  ④ `build_isc_index.py` truepts 分支委托 build_tp_index（删除重复实现）。
- **验证**：test1-om tp 重建 **638.3s（12.9 帧/s）vs 3198.1s（2.57 帧/s）= 5.01×**，帧数 8221
  不变；与验收索引 **times/feats 逐字节相等** ⇒ 续52-F/G A/B 验收与三指标字节等价自动沿用；
  单测 +3；后端全套 **521 OK (skipped=2)**。备份 `work/isc_source_index_backup_20261005/`；
  探针 `probe_mkv_index_build_perf.py`。明细 FINDINGS §5.6.6。
- **对翻默认的影响**：建表一次性代价改写 = mp4 ~5~11min / mkv ~11min/137min 片（原「mkv +53min」
  作废）；翻默认 `isc_l2_index_enabled=True` 的性能前置**全部清除**，仍等用户拍板。
  未改 GT / 未 bump feature_version / 旋钮保持默认关 / 未提交。

## 2026-10-04（续52-G）— L2 常态链落地（入库目录 + sha 有效性 + 自动构建）+ 复验行为等价 PASS

- **新增**：`paths.isc_index_root`；模块 `engine/localization/isc_l2_index.py`
  （build_tp_index / save / load / is_valid——meta 源片 sha256 失效判定，会话缓存）；
  `locator_service._ensure_isc_l2_index`（knob 开时缺失/失效 → locate 内同步自动重建，
  INDEX_BUILD 进度，失败 WARNING 回退）。**设计变更如实**：异步构建因本进程 DML 并发
  段错误/污染风险（续6/续43）降为同步（最坏 = 首次定位多等一次建表）；异步化留待进程隔离。
- **复验抓到真 bug（已修）**：builder 初版全片网格帧攒内存（test3 ≈47GB）→ 换页拖慢 3×+
  （复验臂 2h45m）；修复 = **逐簇流式嵌入**（120s 簇）→ 重建 ~10min 级。
- **复验 PASS**：预播种 3 片被 is_valid 正确判失效（缺 schema 字段）→ 自动重建；四片新 on 臂
  与 §5.6.4 验收臂 **strip 后 0 差异**（含流式重建索引）⇒ 三指标 136/131/138/4·9 字节等价成立。
  单测 6（+1）；后端全套 **518 OK (skipped=2)**。明细 FINDINGS §5.6.5。
- **翻默认前置仅剩**：mkv 建表性能（解耦项）。未改 GT / 未 bump feature_version /
  未翻默认 / 未提交。

## 2026-10-04（续52-F）— L2 runtime 接线（默认关）+ 四片双臂 A/B = PASS（零回退 + 1.44×）

- **接线**：`pipeline.isc_l2_index_enabled`（**默认 False**，knob 关 = 逐位无操作）+ `isc_l2_index_dir`；
  `apply_isc_refine` 增 `l2_index` —— 开 = 宽扫粗排换索引 matmul（tp 特征表 × q_isc 均值分），
  top-3 真帧 ±2s 精化 / margin 门 / `-iscw` 全复用；`locator_service._load_isc_l2_index`
  （缺文件 WARNING 回退现役宽扫）。单测 +5；门禁后端全套 **517 OK (skipped=2)**。
- **四片 A/B**（off = 当前代码 fresh 批复用；on = clean GPU）：test1 **1.375×**(1/55 差异) ·
  2mkv **1.339×**(4/84) · test2 **1.630×**(4/67) · test3 **1.381×**(6/103) · 合计 **1.44×**(15/309)。
  差异行画像：9 行 ≤1.1s + 6 行 3.4~45s，置信等级 15/15 不变。
- **三指标**：严格 **136/139** · 导出实得 **131/139** · 场景 **138/139** · 负例 **4/9**
  —— **与现役基线逐项一致零回退**（支撑 1110，+2 微 churn）。**验收 PASS**。
- **待拍板**：翻默认 `isc_l2_index_enabled=True`（前置 = 索引入库常态构建链 + mkv 建表性能）。
  明细 FINDINGS §5.6.4；产物 `work/isc_l2_ab/`。未改 GT / 未 bump feature_version /
  未翻默认 / 未提交。

## 2026-10-04（续52-E）— L2 接线形态验证：l2 模式两形态实测，形态 B（top-5 ±4s）达接线可行轮廓

- **探针新增 `--mode l2`**（索引 matmul top-K → ±refine_s 局部精扫真帧，镜像生产 `_refine_topk`），
  对照 = fresh 现役臂（按 edited 坐标对齐；坑：探针 seg 是过滤后行号，直接索引全量 results 会错位）。
- **形态 A**（top-3 ±2s）：中位 0.50/1.06/0.63/1.05s，>2s 2/4/3/8（2mkv 有 30/202s 级漏峰）。
- **形态 B**（top-5 ±4s）：中位 0.50/1.06/0.56/0.53s，>2s **2/4/2/6**，2mkv 大离群全消
  （max 30.25→4.00s）；残余 = ±2~4s 粒度级 + test2 seg30 采样混叠。成本 ≈45 嵌入/段 = 现役 1/3。
- **建表性能**：mkv 大簇（600s）无效（2.6 帧/s vs 3.0）——mkv+select 解码路径本身慢，
  一次性 53min/137min 片；mp4 5~8min 可接受。接线立项材料齐（tp 索引 + 形态 B + 两遗留项）；
  接线 = runtime 改动，需四片三指标回归 + 拍板。明细 FINDINGS §5.6.3。
- 未改 runtime / 未改 GT / 未提交。

## 2026-10-04（续52-D）— L2 前置项落地：索引构建 true-pts 化（`.tp`），双时间系统归一，四片探针复跑

- **改动**（仅研究脚本，零 runtime）：`build_isc_index.py` 增 `--sampling truepts` —— L1 `grab_grid`
  select 抽取（真实 pts + first_ge，与扫描侧 grab_frame 同帧同契约），产物 `.tp.isci.npz`；片尾守卫
  （网格截断 + MediaError 渐进裁剪）。文档字符串登记 seq 标签 +0.5s 缺陷。
- **对齐验证**：tp 标签 2781.0 vs seek grab_frame **cos=1.0000**（seq 0.42）。
- **四片 tp 探针**（同 20 段）：中位 0.416/0.500/0.188/0.492（seq 0.500/0.500/0.438/0.516，
  三片改善）；>2s 条数 1/5/2/2（seq 1/4/3/5）。**插桩实证 seg18 双方在同网格点分数逐字相同
  （0.3986=0.3986）** ⇒ 时间系统贡献归零；残余 >2s 逐行裁决零「索引错」：采样混叠（索引峰更高
  seg18/2mkv seg72）· 窗扫复刻塌分（seg21/seg10，seq/tp 两轮同值 = 确定性探针伪影）· ±2.5s 粒度边缘
  （唯一索引吃亏 = test1 seg30，局部精扫按设计消化）。
- **结论**：tp 索引具备接线条件；接线前剩 ① mkv 建表性能（test1 tp 仅 3.0 帧/s，mp4 11.6~16.2）
  ② 局部精扫形态设计。明细 FINDINGS §5.6.2。未改 runtime / 未改 GT / 未提交。

## 2026-10-04（续52-C，用户令「跑终裁」）— Exp-A 证伪「v2 异实例索引」；挖出产品级新事实：双时间系统 ~0.5s 系统性错位

- **Exp-A（索引实例对比）**：隔离数据目录 + 当前代码 + 生产资产重建 test3-om CLS 索引（10177 帧/811s）
  → 与 09-05 库存**逐字节全同** ⇒ 索引构建跨进程/跨代际确定性；**「v2 异实例索引」「DML 跨实例
  非确定性」两假设证伪**（08-29 vs 09-05 差异系 fv 变更 +evt1，非抖动）。
- **Exp-B（三方对质 + 漂移测量）——新产品级发现**：
  库存索引特征 @t == `iter_frames(start=0)` 帧（cos=1.0），与 seek 抓帧 cos=0.42/0.36（看图裁决 =
  相邻镜头两幅画面）；用生产 `grab_frames` 真实 pts 密池定位：**索引标签 L 的画面实际在真实时间轴
  L+0.4~0.5s**（2781→2781.375~2781.5 cos 0.9990；3030→3030.5 cos 0.9982）⇒ **`iter_frames` 合成标签
  （`timestamp = start + i/fps`）系统性比真实 pts 晚 ~0.5s**（1s 网格半格）。镜头内无感、**切点处
  索引帧与扫描帧是两幅画面** ⇒ 解释 L2 探针 seg18 真分歧 + L2 索引 matmul 峰位系统性 +0.5s 偏移。
  **L2 接线前置项**：索引构建改 true-pts 抽帧或接线半格校正。
- **代际差最终判定（闭环）**：8 行跨代际差异 = **续46 窗解码在 test2-om/test3-ed/2.mkv 的未穷举帧差**
  （唯一自洽：test1 全片验证过窗解码 ⇒ 两代零差异 ✓；另三部只做过区域抽样）。v2 目录实例假设降级。
  精确点位穷举留待下批；「四片验收一律双新臂」口径不变。明细 FINDINGS §5.5 终裁段。
- 终裁产物 `work/exp_final_adjudication/`（重建索引 + pair PNG + 漂移脚本）。
  未改 runtime / 未改 GT / 未 bump feature_version / 未提交。

## 2026-10-04（续52-B）— ①代际差定位大步收窄（两候选证伪 + v2=异实例首候选）②L2 扩片判据原文未过（triage 后「峰不丢」大体成立）

- **① 代际差机制排查（零 GPU，止损内）**：
  - **证伪候选①**「edited_cache 重建改变切分」：test3-ed 三个代际缓存（09-06 ×2 / 10-03 ×2）与
    test2-ed 两个代际**逐字节全同** ⇒ 重建字节忠实。指纹含 `pipeline_dict`（radius 在其中）⇒ v2 臂必换键必写缓存，
    但默认目录 10-03 白天**零写入痕迹** ⇒ **v2 批几乎必然跑在另一个 SVL_DATA_DIR 实例**（首候选；
    可解释 test3 idx1 的 5488s 先验大跳）。
  - **证伪候选②**「窗解码帧字节差」：累计 **68 点**（含全部跨代际争议峰点）窗解码 vs 逐帧全部逐字节相等。
  - **新机制线索**：index↔window 复刻在多数争议行**彼此一致、共同偏离 v2 main** ⇒ 漂移在采样上游；
    粗扫网格相位随先验走（v2 偶秒网格从未采到今日峰点，如 3565.0）。fresh 三次独立进程逐位一致
    ⇒ 现状态下结果稳定。**终裁实验待口令**：默认目录复算 test3 idx1 先验（=5949 ⇒ 坐实异实例）
    + test2-om t=2781 帧级核对（index 构建 vs seek 抓帧）。明细 FINDINGS §5.5。
- **② L2 扩片（三片建表 + 探针）**：建表 test2 5051 帧/4.8MB、test3 10177 帧/9.6MB、2mkv 7668 帧/7.3MB；
  GPU 空闲 **28.8 帧/s**（反证 test1 首批 10.6 系争用；干净 ≈4~6 min/片源）。
  **原文判据（中位 ≤1s ✓ 但 >2s 条数=0 ✗）四片全未过**（1/3/4/3/5 条）；**逐行 triage**：
  离群 = 窗扫复刻塌分 3 行（index 贴生产 main）+ 1s 粒度/网格相位行（接线设计由局部精扫消化）+
  真分歧 1 行（test2 seg18，恰为跨代际行，index 站 fresh 一边）。**结论：「峰不丢」大体成立
  （index 对现役峰 15~19/20 ≤2s），判据口径应改「index vs 现役臂」；接线暂缓**，待终裁实验。
  明细 FINDINGS §5.6.1。未改 runtime / 未改 GT / 未 bump feature_version / 未提交。

## 2026-10-04（续52-A，A/B 归因线程）— 四片 fresh 双新臂全部 0 差异；3+5 行差异归因结案 = `v2_*` 跨代际（初版机制归因已更正）

- **test2 双新臂**：off 6233.7s / on 3609.3s（两臂均在并行争用下跑）→ **`strip(result_id)` 后 0/67 差异**。
- **test3 双新臂**：off 7402.8s / on 3543.9s（103 段，off 臂争用）→ **0/103 差异**。
  加上 test1（0/55）、2mkv（0/84）⇒ **四片 fresh 双新臂全部 0 差异**，网格零语义收口。
- **归因结案（2026-10-04 定稿口径，经两轮复核）**：归档批 `v2_*` vs **fresh off 臂**（旋钮关、无网格路径；
  off 调 `grab_frames(filters=None, match="first_ge", max_pts_lag=None)` 参数与改动前逐字相同 ⇒ **L1 在 off
  路径惰性**）差异 = **test2 3 行 span**（与首轮 on-vs-归档 3 行完全对应）· **test3 1 行 span + 4 段边界不一致**
  · **2mkv 1 段拆/合（84 vs 83）** ⇒ 差异全部为**归档批代际差异**，与网格无关。
  **计数口径更正**：test3 首轮「5 行」是按行号对齐虚计（段边界不同时错位也算差异行）；按编辑段键对齐
  实为 1+4。**撤回声明**：初版「= 安全网修复前的整格跳位缺陷」为**错误归因**（缺 off-arm 对照），已撤回；
  安全网证据范围 = 帧级逐字节等价 + 亚秒护栏，不覆盖这些行。**机制留白**：代际差具体机制未定位
  （候选：edited_cache 跨代际重建 / 续46 抓帧路径切换缓存时序 / 其它未登记状态差异），未做定位实验不下结论。
- **口径结论**：归档批 `v2_*` 与当前代码存在**跨代际差异**（2mkv 段数 83→84 + test2 3 行 span +
  test3 1 行 span + 4 段边界）⇒ 四片验收一律
  采用**双新臂**（fresh off vs fresh on）口径。
- **提速（口径警示）**：test2 1.727×（两臂争用）/ test3 2.089×（off 争用、on 独占）**不作头号数字**；
  干净口径 = test1 1.27× / 2mkv 1.30×；两片只说明「段数多 ⇒ 宽扫占比高 ⇒ L1 收益更大」的方向。
  明细见 FINDINGS_COST_STRUCTURE_LEVERS_20261003 §5.5。

## 2026-10-04（续52）— L2 源片 ISC 索引：test1 建表 + 对照探针 PASS（宽扫换 matmul 的精度前提成立）

- **建表**：`build_isc_index.py --source test1` → `work/isc_source_index/test1-om@1.000fps.isci.npz`
  （**8221 帧 / 7.8 MB / dim=256**，1s 网格，meta 记源片 sha256=ca870efc…、ISC onnx 路径、device=dml）。
  实测 774.2s（12.9 min，10.6 帧/s）——⚠️ 与 test2/test3 fresh 双臂**同时跑、有 GPU 争用**，
  此数不是干净口径（干净估 ~9 min/片，与续50 结构账 22.4min 相比已吃满 L1 红利）。
- **对照探针**：`probe_l2_index_replay.py --case test1 --sample 20`（同查询特征、
  索引 matmul vs 现役 ±90s 窗扫，只比「源侧候选怎么取」）：
  **Δt 绝对值中位 0.5s（≤1s 判据 ✓）· >2s 条数 0（✓）· 最大 1.375s · 20/20 段两侧均出峰**。
  分数侧索引略低于窗扫（1s 网格粗于细化 0.5s 网格，属预期），峰位全部贴住。
- **结论**：L2 把宽扫换成「索引 matmul」的**精度前提在本批 20 段上成立**；
  产物 `replay_test1.json`。test2/test3 建表 + 扩样验证待后续批次。
- 未改 runtime / 未改 GT / 未 bump feature_version / 未提交。

## 2026-10-03（续51 补一）— `grab_grid_decode` 翻默认开（用户拍板选项 B）

- **执行**：`config.py` `grab_grid_decode` **False → True**（注释内写明五条验收证据与回退路径）；
  新增默认值回归锁（`test_domain_infrastructure.test_default_config`）。
- **门禁**：后端全套 **512 OK (skipped=2)**（203s，与两条验收 job 争用 CPU）。
- **验收依据**：帧级逐字节等价（安全网后 4 组生产相位网格 0 差异）· test1 逐字段 0 差异 1.27× ·
  2mkv 双新臂逐字段 0 差异 1.30× · **四片三指标逐项一致**（136/131/138/4·9）· 亚秒步长护栏回退。
- **未归因项登记**：test2 3 行 / test3 5 行 LOW 置信 span 形状差异（不移动指标）；fresh 双新臂
  （job pwsh-51/52）在后台跑，出数后补记归因。
- **决策全文**：`.agent/DECISIONS.md` 2026-10-03（续51）。未改 GT / 未 bump feature_version / 未提交。

## 2026-10-03（续51）— 四片 A/B 抓到真缺陷：生产相位网格偶发**整格跳位** ⇒ 加安全网（拒绝 + 精确回退）

- **现象**：test1 四片回归首轮 = 逐字段 0 差异（PASS）；但 **test2 出现 3/67 段落点差**（LOW 置信，
  位移 ~23~26s）、**2mkv 段数 83→84**（一段被拆两段）。
- **排查（逐项证伪）**：① 窗解码（续46）在 1.mp4 / test1-ed **0/120、0/60 不一致**（逐字节）⇒ 排除；
  ② 帧级对照 test2-om / 2.mkv / test3-om 各 91 点 **0 不同帧** ⇒ 排除「帧不同」；
  ③ 切分可复现性：同配置跑两遍 **完全一致**、开关旋钮 **完全一致**（69=69=69）⇒ 排除「非确定性」。
- **真因**：生产网格是 `round(wlo + i*2, 3)`，步长有 0.001s 级抖动，而 `select` 抽出窗口按**统一 step**
  生成 ⇒ 窗口起点会缓慢漂到目标之前 ⇒ 个别目标被分到**下一格（+2s）**的帧（实测 t0=1285.533 的
  91 点里有 **6 个**这种点）。这直接改变了粗扫分数 ⇒ 低置信段的 argmax 翻到别处。
- **修复**：`_decode_window(..., max_pts_lag=)` 安全网 —— 网格抽取时若分配给某目标的帧 pts 比目标晚
  超过阈值（`min(step, 0.5)`）就**拒绝该分配**，交回调用方逐帧精确抓取（`grab_frame`）。
- **验证**：4 组生产相位网格（test2-om ×2 / 2.mkv / test1-om）全部 **0 不同帧**；其中抖动相位**触发 6 次**
  精确回退（即修复前会跳格的 6 个点）⇒ 成本 ~6 次/91 点，可忽略。
- **协议修正**：归档批（`v2_*`）**不能**当单变量 A/B 的 off 臂（2mkv 的段数差与旋钮无关，属跨代际差异）
  ⇒ 2mkv 必须跑**双新臂**（`--force`）；test2/test3 先按归档参照复跑，若仍不一致再补 fresh off。
- **重跑队列**：A=test2 on（带安全网）· B=2mkv 双新臂 · C=test3 on（带安全网）。**test1 结论不变**（PASS）。

## 2026-10-03（续50 补二）— L1 接线（宽扫粗扫 = 网格抽取）+ test1 整条 A/B 运行中

- **接线**（用户令「继续」；唯一变量 `pipeline.grab_grid_decode`，默认 False）：
  `isc_refine.apply_isc_refine` 增 `grab_grid` 参数 + `_embed_missing_grid` —— **只作用于宽扫粗扫**
  （`coarse_ts` 本就是 2s 均匀网格）；候选窗/细化窗相位非网格对齐，保持旧 `grab_frames`，
  把行为变更面收在「粗扫选帧」一处。`FFmpegIO.grab_grid_times`（显式时间表 + 允许带洞：
  select 抽超集 + 冻结 `first_ge` 配对）；`locator_service._grab_grid_batch`（关/无接口/超片尾三路回退，
  复用同一 512 FIFO 缓存避免重复解码）。
- **单测 +8**：isc 粗扫走网格抓帧时结果与旧路径一致（后缀/落点/子段数逐项）、缺帧逐帧回退；
  locator 旋钮开关/接口缺省/缓存命中/超片尾回退；`grab_grid` size 自动拼 scale。定向 3 文件全绿。
- **A/B 运行中**：`mvp/scripts/probe_isc_grid_ab.py --case test1`（两臂完整 `srv.locate()`，DML 硬断言，
  `strip(result_id)` 逐字段比对 + 墙钟；产物 `work/isc_grid_ab/`）。off 臂已确证 `BACKEND=DirectMLBackend`、
  `isc_radius=90`（现役默认）。**结果未出，本批不做结论**。
- **漂移修复（第三批，同日）**：初版 select 判据 `gte(t-prev_selected_t,step)` 会**逐步累积漂移**
  （1s 网格 600 点仅 121/600 逐字节同帧）⇒ 改 `_grid_select_expr(lo, step)`：锚定**每个解码簇起点**的
  绝对窗口 `[lo+k*step, lo+(k+1)*step)` 取首帧（`filters` 支持 callable 按簇生成）⇒ 修复后
  **300s@1s = 300/300、180s@2s = 90/90 逐字节同帧**，加速 2.36~2.61×，升级为「零语义」级别。
  亚秒步长（<1s）由 `MIN_GRID_STEP_S` 护栏回退旧路径（实测 0.208s 步长 3/15 同帧、cos 0.335）。
- **其它抓帧点实测后决定不接线**：shot_split（3s@4.8fps，2.10× 但 min cos 0.335 ❌）、
  patch_refine 小窗（1.08×，收益≈0.1s/次）⇒ 网格抽取只对宽扫粗扫这一形状有意义。
- **L2 建表形状实测**：test1-om 600s @1s 网格，base 123.6s → grid 49.4s（**2.50×**）⇒ 建表成本随 L1 同幅下降。

- **A/B（重跑，用户令继续后第三批）**：off 臂复用现役默认批 `work/isc_refine_arms/v2_test1.results.json`
  （续47 defaults_check 已证与当前配置逐位一致），**on 臂运行中**（`grab_grid_decode=True`，DML，radius=90）。
  首轮 A/B（旧判据）已主动中止：那份「on」臂的选帧保真只有 79/91，证据已过时。
- **test1 整条 A/B 验收 = PASS（零语义 + 1.27×）**：on 臂 **2186.1 s = 36.4 min**（55 段），
  `strip(result_id)` 后与现役默认批 **0 处差异**（主/子 span、置信、reasons、alternatives、信封全比）；
  相对续47 defaults_check（2772 s）**1.27×**、相对续45 v2 臂（2888.4 s）1.32×，**单片省 ≈9.8 min**。
  后端全套 **512 OK (skipped=2)**（100.2 s）。三片回归（2mkv/test2/test3）运行中。
- **待办**：① A/B 出数 → 四片三指标回归 → 拍板翻默认；② ~~同原语接 shot_split/patch_refine~~（已实测否定，见上）；
  ③ 后端全套（A/B 结束后跑，避免 GPU 争用）；④ L2（ISC 源片索引）立项。未改 GT、未翻默认、未提交。

## 2026-10-03（续50 补）— L1 落地：`grab_grid` 网格抽取实测 2.5×，已到「解码地板」

- **实现**（`mvp/src/media/ffmpeg/ffmpeg_io.py`，用户令「开始吧」）：新增 `grab_grid(path,t0,step,n)`
  默认滤镜 = `select='isnan(prev_selected_t)+gte(t-prev_selected_t,STEP)'` + **`-fps_mode passthrough`**
  （必带：否则 vsync 复制帧补 CFR，实测 5 帧 → 149 帧）+ 冻结规则 `first_ge` 选帧；`grab_frames` 增
  `filters / size / match / passthrough` 透传；`size` 非空时自动把 `scale=W:H` 拼进滤镜链（踩坑留痕：
  只传 size 不拼 scale ⇒ 形状不符 = 垃圾帧）。单测 +6。
- **反例留痕**：`fps=1/N` 滤波会**重定时间轴**（实测帧落到 +0.5 s，ISC cos 均值仅 0.785）⇒ 弃用，改用 `select`。
- **生产形状 A/B**（test1-om，t0=1382.5，180 s 窗 / 2 s 网格 / 91 点）：base **27.9 s** →
  **grid 11.1 s（2.51×）** / grid512 10.7 s（2.61×）；79/91 **逐字节同帧**、其余 12 点 ≤1 源帧；
  ISC 余弦 mean **0.997**（min 0.922）/ grid512 mean 0.996。
- **新关键事实（解码地板）**：同窗 `ffmpeg -f null -` = **8.5 s（21× 实时；顺序解码 26~27×）** ⇒
  grid 的 11.1 s 中 ≈8.5 s 是解码，L1 把「管道搬运」（~20 s）压到 ~2.4 s。**继续降本只剩两条路**：
  L2（源片索引 = 全片一次顺序解码 + 每段零解码）与硬解（对扫描路径做 ISC cos A/B，不照搬续47 判负）。
- **门禁**：后端全套 **505 OK (skipped=2)**（95.8 s；本批改 `mvp/src` ⇒ 已跑全套）。
- **未做**：接线（宽扫仍走旧 `grab_frames`）、四片回归、未改 GT/feature_version/默认值、未 git 提交。
- **产物**：`mvp/scripts/probe_grab_pipe_modes.py`、`work/grab_pipe_ab/ab_test1_1382p5_s2.json`、
  FINDINGS_COST_STRUCTURE_LEVERS_20261003 **§5**。

## 2026-10-03（续50）— 定位成本结构实测：抓帧=管道 I/O 瓶颈（4× 推理）⇒ L1 网格抽取为首选杠杆

- **触发**：用户「性能侧还可以怎么优化，必须先把成本打下了我们才好继续优化算法」。新探针
  `mvp/scripts/probe_isc_cost_levers.py`（`main-score` / `index-pilot`），**零 runtime 改动**。
- **成本单元（实测）**：ISC 推理 **0.0328 s/帧（30.4 fps）**；窗解码抓帧 **0.1308 s/帧（7.65 帧/s）
  = 推理的 **4×****；原始帧 2.64/5.53/5.97/4.61 MB（2mkv/test1/test2/test3）；推算管道 ≈676 MB/s。
  根因 = `_decode_window` 对窗内每帧都读原始 BGR（只取 1/25~1/30）⇒ 抓帧成本正比「解码秒数」而非「目标帧数」。
  **更正续47 的定性**（「宽扫大头在 embed 而非抓帧」）。
- **L1（首选）**：网格抽取 `-vf fps=1/N` + 消费者侧 `-s` ⇒ 管道 ÷25~60（再 ÷9）⇒ 宽扫 18~24 s/段 → 3~6 s/段，
  并同幅作用于 shot_split/patch_refine（续34 实测 grab 占两旋钮段 77.6%）。零 feature_version 风险
  （扫描帧不进索引）；验证 = 抽样逐字节/max|Δpixel| + 同 t ISC 余弦 + 四片回归。
- **L2**：ISC 源片索引 pilot 实测（test1-om 600s / 1s 网格）= grab 78.5s + embed 19.7s ⇒ 整片外推
  **22.4 min / 8.4 MB**；收益在母片复用（N≥2 起每片省 ~22 min）+ 扫描范围扩到全片。先 L1 再 L2（建表同样吃管道）。
- **L3（判弱）**：宽扫 main-agreement 门——301 合格段仅 **15 段（5.0%）**被切换；`main_score` 两族大幅重叠
  （切换段中位 0.509 vs 未切换 0.771；真增益行 0.509/0.598/0.674）⇒ θ=0.70 跳 67.1% 才保住三条增益且误跳 3 段；
  θ=0.80 误跳 0 但只跳 33.2%。**不建议单独上**，仅作兜底。
- **L4**：FP16 ONNX 未测（正交、便宜）。已判负不再碰：硬解 / ISC 批量推理 / 索引密度 ÷2 / 宽扫阶梯。
- **边界**：676 MB/s 为推算（按 8 簇 × ~1,200 解码帧）；宽扫 s/段 取自续45 四片增量口径，未单段插桩；
  `main_score` 以 ON 臂主 span 近似「宽扫前主」。未改 GT/runtime/feature_version/默认值，未 git 提交。
- **产物**：`FINDINGS_COST_STRUCTURE_LEVERS_20261003.md`；`work/isc_cost_levers/{main_score.json,index_pilot.json}`；
  `mvp/scripts/probe_isc_cost_levers.py`。**待拍板**：开 L1？L2 立项？L4 并行？git（续41~续50）/ r8 重打。

## 2026-10-03（续49）— TODO ④「两级采样索引探针」结构账 + 精度敏感度实测 = 建议不立项

- **触发与纪律**：用户令「继续这个项目」（无新指令）⇒ 取 P0 ④（性能侧队列末项，用户新增）。
  按续48 教训「提前收工类优化先做结构账再决定实跑」，本批**不烧 3~4 小时四片回归**，先做
  零 runtime、零 GPU 的结构账 + 一个便宜探针。
- **新探针**：`mvp/scripts/probe_index_fps_sensitivity.py`（纯 JSON+GT，零 GPU）——把现役默认批
  `work/isc_refine_arms/v2_*` 的**原片侧 span**做 4 类扰动（grid2 / shrink1 / shift∓1s），
  用同一评估器 `measure_shot_recall.evaluate` 重算三指标 + 翻转清单 + 索引成本账。
- **实测（四片合计）**：base **136 / 131 / 138 / 4·9**（与档案读数一致 = sanity pass）；
  **grid2（吸附 2s 网格，偏差 ≤1s）= 137 (+1) / 131 / 138 / 4·9**（唯一翻转 t1r12a part→HIT）；
  shift_minus1 = 132 (−4) / 124 (−7) / 138 / 4·9；shift_plus1 = 135 (−1) / 130 (−1) / 138 / 4·9；
  shrink1（两端各缩 1s，最坏上界）= 118 (−18) / 83 (−48) / 128 (−10) / 4·9。
  ⇒ **量化零代价**；大损失只出现在「系统性缩短」形态，而它是「span 变短」不是「网格变粗」
  （现役端点来自 patch/ISC 细化，实测 0.25s 步长，非索引网格）。
- **成本账（真实元数据）**：四片 1.0fps 索引 31,117 帧 / 8.65h 源片 / 53.2MB / 建索引折算
  38.1min（13.6fps，续17 口径）⇒ ÷2 省 **19.1min + 26.6MB**，**且只省一次**；每次定位
  （test1 实测 46.2min，现役 radius=90 + 窗解码）**不受影响**：`isc_refine.apply_isc_refine`
  用 `_grab_many(source_path, coarse_ts)` 按任意时刻抓帧，粗扫点由 `scan_radius_s`/`WIDE_COARSE_STEP`
  决定，与索引网格无关（续34 同结论：grab 占两旋钮段 77.6%）。
- **检索保真度复算（当前 GT，DML 206s）**：`audit_retrieval_ceiling.py --coarse-stride "2,10"` →
  stride2(0.5fps) 粗池 **139/139**、rank p99 **11.0**（≪ 我方 `retrieval_top_k=28`）；
  stride10(0.1fps) 130/139、p99 448.6。**口径更正留痕**：2026-09-26 档案记 p99=25.3 / 命中 127，
  差异来源 = 2026-10-01 GT r1 修订（17 条）与结果批口径，非算法变化；方向不变。
- **裁决建议**：**(a) 不立项**（收益与「每次定位」痛点错配）/ (b) 降级为新装机可选档 /
  (c) 若仍要实跑，方案已备（隔离 `SVL_DATA_DIR` + `sampling_fps=0.5` 重建四片 ≈19min +
  现役配置四片全跑 ≈3h）。**替代杠杆**：ISC 宽扫粗步长 2.0s→4.0s（−42% 宽扫 embeds）——
  现役宽扫**已是两级**（2.0s 粗 + top-3 峰 ±2.0s@1s），需先落盘小样本 ISC 粗曲线（runtime 不落盘）
  算峰值保持率，提案 = 20~30 段 ×±90s @1s 曲线探针（≈5~10min GPU），门槛 ≥95%。
- **门禁**：后端全套 `python -m unittest discover -s mvp/tests` = **499 OK (skipped=2)**，91.9s；
  本批**零 `mvp/src` 改动**（只新增 `mvp/scripts` 探针一份），无 API/vitest/typecheck 影响面。
- **边界**：§3 是**最终 span 的敏感度包络**，非 0.5fps 链路模拟（不覆盖「提案整体换地方」与
  「聚簇/覆盖判据内部行为改变」）；建索引耗时是折算值（本批未重建索引）；未改 GT、未改 runtime、
  未 bump `feature_version`、未翻任何默认值、未 git 提交。
- **产物**：`mvp/benchmark/user_case/competitor_cutmatch/FINDINGS_INDEX_DENSITY_DIV2_20261003.md`；
  `work/index_fps_probe/{sensitivity_20261003.json, audit_stride2_10_20261003.json}`；
  `mvp/scripts/probe_index_fps_sensitivity.py`。

## 2026-10-03（续48）— v3 阶梯宽扫验收（ladder=30）= FAIL（计时判负）：3/3 片更慢，`isc_refine_ladder_s` 维持 0.0

- **动机与设计**：v2 宽扫 +88min/四片的成本大头 = DML 逐帧 embed × 设计假设「多数歧义段在
  内圈（±30s）就有过 margin 门（0.05）的峰」→ 内圈收工省外圈粗扫。新增旋钮
  `pipeline.isc_refine_ladder_s`（默认 0.0 = 现役全域扫）。
- **实跑**：`rerun_isc_refine.py ladder`（radius=90 + ladder=30），2mkv/test1/test2 三片自然
  完成；**test3 主动中止**（REFINE ~42/103，前三片计时已一致更慢；stdout PY_EXIT=127 中止
  留痕，非脚本崩溃）。
- **计时（判负依据，3/3 片全部更慢）**：2mkv 3167.7s vs 2923.8s（**+8.3%**）/ test1 2928.0s
  vs 2888.4s（**+1.4%**）/ test2 3738.0s vs 3302.3s（**+13.2%**）；3 片合计 164.0min vs
  151.9min = **+7.9%（节省为负）**。test3 中止未完成、不参与计时判定。
- **精度（无损但无意义）**：3 片硬门零回退——严格 99/102 · 导出实得 95/102 · 场景 101/102 ·
  负例 3/6 逐片持平 vs v2 臂；**mark/main_hit 双口径翻转 0 行**；生死线 **p20/p34/p14 保持
  HIT 且落点与 v2 臂逐位同**；t1r08c/t1r12a 仍 part、t2r03b 仍 MISS、自信错点名 t1r30a/
  t2r04a 保持 HIT 落点同。churn 4 行（p12/p13/t1r20/t1r26）拼图读毕全部同景内选位差、
  无真损失；切换段 21 vs v2 19。
- **机制复盘（设计错误非实现错误）**：内圈收工前提 = 多数段内圈有过门峰，但过门峰 ≈ 最终
  切换段仅 ~10%（21/206，3 片口径）⇒ ~90% 段注定「内圈无过门峰 → 白付内圈粗扫（31 pts）
  + top-3 细化（~15 embeds）→ 扩展外圈」；收工段省 ~75 embeds vs 非收工段付 ~46 embeds，
  10%:90% 比例结构性净亏。**教训：「提前收工」类优化必须先证明目标事件在多数段发生——
  用续45 验收数据（切换率 10%）一页纸结构账即可判负，不必实跑 2.7 小时。**
- **裁决 = FAIL，维持 `isc_refine_ladder_s=0.0`**（阶梯分支代码保留树内但不激活）；未改 GT、
  未 bump feature_version、未 git 提交、未翻任何默认值。
- 归档：FINDINGS_ORTHOGONAL_BACKBONE_PROBE_20261002 **§12**；产物
  `work/isc_refine_arms/ladder_{2mkv,test1,test2}.results.json` + 分析
  `work/isc_refine_arms/analysis_ladder/`（对照脚本 `compare_iscladder_flips.py` + metrics/
  flip/fine/churn/inner_hit + 拼图 7 张全读毕；既有 `analysis/`、`analysis_v2/` 零覆盖）。
  内圈命中率从产物不可直接区分（日志无逐段留痕），近似上界 = `-iscw` 切换段胜出峰在 ±30s 内
  5/6，如实标注口径。
- **待拍板不变**：git 提交（续41~续48）/ r8 重打。性能侧队列：③ 宽扫自适应降本（阶梯形态）
  **判负关闭**；下一杠杆 = ④ 两级采样索引探针。

## 2026-10-03（续47）— 性能侧①②闭卷：ISC 批量推理判负 / 硬解判负；defaults_check 实测 46.2min 回填

- **defaults_check（现役默认 = radius 90 + 窗解码）**：test1 全片 **46.2min（55 段）**，vs v2 验收批
  **逐位一致** ✓（两个零语义改动合成无漂移）。PRODUCT_INTRO 口径定为 **45~60 分钟/片**
  （快速档 7~8min）——46.2 略超预估区间的原因 = 宽扫成本大头在 DML 逐帧 embed 而非抓帧。
- **① ISC@512 批量推理 = 判负**（`probe_isc_batch.py`，动态 batch ONNX + DML）：batch1 **33.2fps**
  > batch16 26.6 > batch8 23.0 > batch4 16.9——与 DINOv2@518 同结论（RX 6750 GRE DML 栈
  batch=1 最佳）；批量 vs 单帧数值一致（max|d|=3.5e-7）⇒ 宽扫 embed 成本本机无法用 batch 压缩。
  产物 `work/probe_isc_batch.json` + 动态 ONNX。
- **② ffmpeg 硬解（-hwaccel d3d11va/auto）= 判负不进特征路径**：a1.mp4 实测像素差
  mean|d|≈1.05（色度转换路径不同），2.mkv 逐字节一致但无法对任意用户素材保证 ⇒ 与冻结帧契约
  （BGR uint8 逐位）冲突。留档 `work/` 无独立产物（探针为内联验证，结论本条即档案）。
- 队列剩余：③ 宽扫自适应降本（行为变更需四片回归）/ ④ 两级采样索引探针（0.5fps 档先行，
  feature_version bump + 四片回归）——均为更大批次，等用户拍板排期。
- **待拍板不变**：git 提交（续41~续47）/ r8 重打。

## 2026-10-03（续46 补）— ISC v2 宽幅扫描翻默认 radius=90（用户拍板）：严格 136 / 导出实得 131 生效

- `pipeline.isc_refine_scan_radius_s` **0.0→90.0**（用户拍板「1」）；config 注释改写为续45 验收
  PASS 依据（严格 134→136 p20/p34 获救 · 导出 128→131 · 翻转全真增益 · churn 无损失）+
  代价登记（宽扫 ~150 embeds/歧义段，四片 +88min 无窗解码口径）。
- PRODUCT_INTRO 高精度时间口径 **18min→30~45min**（18min 是 radius=0 旧口径，继续不诚实；
  精确数字 = 现役默认（radius 90 + 窗解码）实测中，`work/defaults_check/test1` 跑完回填，
  同时交叉验证 vs `v2_test1` 批逐位一致）。
- 门禁：后端全套 **496 全绿**（85s，radius 翻默认后）。
- **待拍板不变**：git 提交（续41~续46）/ r8 重打。
- **事故留痕（已修复）**：本条与续46 条目最初归档时把章节标题写进了插入块，导致 TODO/STATE
  各出现一个重复 `## P0 — Current` / `## Current Task` 标题（违反章节结构纪律）——已去重修复
  并做结构校验（11 章节无重复无缺失）。教训：**插入块的文本不得包含锚点标题本身**。

## 2026-10-03（续46）— 窗批量抓帧解码：test1 全片 21.5→16.0min = 1.34×（逐位一致），翻默认开

用户令「做 ffmpeg 解码侧」。落地 = `FFmpegIO.grab_frames`（每时间簇一次 spawn：`-ss lo` 窗解码
+ `showinfo` 逐帧 pts + **`-copyts`** 保原始轴，取每 t 首个 pts≥t 帧；聚类 gap≤4s/跨度≤40s；
失败逐帧回退）+ `locator_service._grab_frames_window`（缓存查漏→批量→回填，键与旧缓存一致；
假体无批量接口鸭子回退）+ 旋钮 `pipeline.grab_window_decode`（**已翻默认 True**）。

- **两个真 bug 当场抓掉**：① BASE_ARGS `-loglevel error` 吞 showinfo 输出 ⇒ 等(pts) 死等
  （显式覆盖 loglevel + 无 pts 早退整簇回退）；② **无 `-copyts` 时输出时间轴被重置且首帧受
  seek 舍入影响 ⇒ 选帧差一帧**（实测批量帧 = 单帧的 -1/30s 且像素差 2.37）——`-copyts` 后
  逐字节相等。两条都写进代码注释防回退。
- **零语义证据链**：单测（synthetic a1.mp4 6 时刻 array_equal）→ 真实 2.mkv 132 帧微基准
  **17.7s→10.2s = 1.73× 逐字节一致** → test1 全片 A/B（唯一变量=flag）：
  **1291.6s→961.4s = 1.34×，strip(result_id) 55 段逐位一致 + 信封一致**（`work/grab_window_ab/`）。
- 门禁：后端全套 **496 全绿**（+2 窗解码测试）；翻默认后 4 处假体报错由鸭子回退修复复绿。
- 边界：ON 臂耗时口径为本会话同轮配对（续44 的 26.6min 是另一轮，机器状态有漂移）；
  硬解（-hwaccel）未做（像素格式链有变数，留作下一杠杆）；Mac/NVIDIA 同享本优化。
- **待拍板不变**：① v2 `isc_refine_scan_radius_s=90`（严格 136/导出 131 PASS 在手，代价 +88min/四片——
  本优化可吃回一部分）；② git 提交（续41~续46）；③ r8 重打。

## 2026-10-03（续45）— ISC 门控 v2 宽幅扫描四片验收 PASS：严格 134→136 / 导出实得 128→131 / p20+p34 获救，radius 待拍板

`mvp/scripts/rerun_isc_refine.py v2` 四片实跑（完整 `srv.locate()` 生产路径，唯一变量
`pipeline.isc_refine_scan_radius_s` 0→90；`isc_refine_enabled=True` 双臂同开；ALL_DONE/PY_EXIT=0，
2mkv 2923.8s / test1 2888.4s / test2 3302.3s / test3 3631.1s，总 212.4min vs 续44 ON 臂 124min，
宽扫开销 ≈+88min）。对照臂 = `work/isc_refine_arms/on_{case}`（radius 0 现役行为）。

- **三指标硬门全过（零回退全升）**：严格 134→**136**（+2）· 导出实得 128→**131**（+3）·
  场景 138 持平 · 负例误报 4/9 持平（分片 3/0/0/1 逐片持平）· 支撑 span 1094→1103。
- **翻转 3 条全真增益、零真损失**（拼图逐张读毕，`work/isc_refine_arms/analysis_v2/isc45_*_sheet12.png`）：
  - 2mkv/p20 part→HIT：ON 同景 7.5s 后（直身行走）→ V2 窗内同款劳作动作（续43 探针
    margin +0.11 兑现）；
  - 2mkv/p34 part→HIT：ON 错场景（男子举牌 "I'M A PRETTY GOOD SHOT"，偏 82s）→ V2 窗内
    同女子同景（margin +0.33 兑现）——**CLS 真盲族两例全救，v2 立项动机直接兑现，MISS6 缺口 6→4**；
  - test2/t2r06c main F→T：ON 5.1s span 起点在窗后 2.4s 且漂过切点 → V2 窗内同内容。
- **churn 3 行**（判据行口径 >1s 位移共 5 行，除翻转外 2 行无指标影响：t2r04b 同隧道镜头内
  2.2s / t3r22 同战斗蒙太奇 1.4s，读毕无隐藏损失），远低于 >20 预警线；ISC 切换段 31（v1 21），
  `-iscw` 宽扫虚拟候选胜出 14 段 ⇒ margin 门 0.05 + 先粗后细 + 距主≥2s 三重约束压住 churn。
- **MISS6 逐条**：p20/p34 获救；p14 保持 HIT（落点逐位同）；t1r08c/t1r12a 仍 part（落点逐位
  同，宽扫峰未过门，如实记录）；t2r03b 仍 MISS（0s 占位段 width≤0.01 按模块边界跳过，
  「无候选段兜底重扫」仍是独立未立项形态）。**自信错点名 t1r30a/t2r04a 双臂一致 HIT、
  落点逐位同，无恶化**。
- **裁决 PASS** ⇒ 可进用户拍板翻 `isc_refine_scan_radius_s=90`；**radius 保持 0.0 未翻**
  （未改 GT、未 bump feature_version、未 git 提交）。
- 产物：`work/isc_refine_arms/v2_{case}.results.json` + stdout `work/rerun_iscv2_stdout.log` +
  分析 `work/isc_refine_arms/analysis_v2/`（`compare_iscv2_flips.py` + metrics/flip/fine/churn
  + 拼图 8 张全读毕；既有 `analysis/` 产物零覆盖）。归档
  `FINDINGS_ORTHOGONAL_BACKBONE_PROBE_20261002.md` §11。
  边界：radius 单值 90 未扫其它半径（护栏禁 sweep）；t1r08c/t1r12a 宽扫峰未过门未逐段归因；
  宽扫代价 +88min/四片进拍板考量。

## 2026-10-03（续44 补）— ISC 第二意见翻默认开（用户拍板）：config True + 打包接线三件套 + 再生成链

- **`pipeline.isc_refine_enabled` False→True**（margin 0.05 不变）；config 注释改写为验收 PASS 依据 +
  已知上限登记（候选提案来自 CLS 聚簇 ⇒ p20/p34 型真盲救不到 ⇒ 门控 v2 = 提案放宽检索 top-N；
  t2r03b 无候选不救）。
- **打包接线三件套**：① 资产入册 `mvp/ui/resources/models/isc_ft_v107/`（asset.json 含 sha256 入 git；
  图 1.6MB + 权重 209MB **二进制 gitignore**，构建时从 `work/isc21_weights_ortho_probe/` 拷入）；
  ② `build-release.ps1` 加 ISC 段（缺资产 fail-fast + sha256 断言，`SVL_ISC_MODEL_SOURCE` 可覆写源目录）；
  ③ `main.ts` 注入 `SVL_ISC_ONNX` + `accept_packaged_bundle.py` 加 ISC 资产/断言/冒烟日志
  `isc refine device=dml` 检查（SMOKE_WALL_S 45→75s）；`locator_service` 加设备留痕日志。
- **再生成链**：`mvp/scripts/export_isc_onnx.py`（实测：新导出 vs 仓内参考 cos=1.000000、max|d|=0、
  权重 sha256 相同；图字节随导出器版本可变——数值等价即有效，替换资产须同步 asset.json sha256）。
- **门禁**：后端全套 **492 全绿**（88s）· vitest **138** · vue/desktop 双 typecheck · compile:electron 全绿。
  零 GT / 零 feature_version。**r8 重打未做（等口令）**。

## 2026-10-02（续44）— ISC 第二意见局部重排生产验收 PASS：严格 133→134 / 导出实得 125→128 / 负例持平，待拍板翻默认

`mvp/scripts/rerun_isc_refine.py on` 四片实跑 ON 臂（完整 `srv.locate()` 生产路径，唯一变量
`pipeline.isc_refine_enabled`；ALL_DONE/PY_EXIT=0，2mkv 1879s / test1 1595s / test2 2009s /
test3 1958s，总 ≈124min）。OFF 臂 = 现役默认批 `work/spl_patch_arms/on_{case}.results.json`
直接复用（配置断言 + 续39 同 GT r1 重计 133/125/138/4 逐位一致旁证等价性；**口径勘误：现行 GT
下「导出实得」基线 = 125，119 为续39 修订前旧数**）。

- **三指标硬门全过（零回退）**：严格 133→**134**（+1）· 导出实得 125→**128**（+3）·
  场景 138 持平 · 负例误报 4/9 持平 · 支撑 1078→1094。
- **翻转 3 条全真增益、零真损失**（拼图逐张读毕，`work/isc_refine_arms/analysis/isc44_*_sheet12.png`）：
  - 2mkv/p14 part→HIT：OFF 落错误场景（地堡庭院 1392-1396）→ ON 落 GT 窗内（1379.5-1380.6，
    天线场景与 ED 同内容）——MISS6 唯一获救例；
  - test2/t2r07c main F→T：同主持镜头命中，span 端点距 GT 窗 0.35s（±2s 容差记账/子镜头粒度；
    OFF span 超窗 5s 漂入切镜）；
  - test3/t3r02c main F→T：同燃烧城垒镜头命中，端点距 GT 窗 0.48s（OFF 落 17s 外错场景）。
- **churn 9/139 无指标影响**：逐条核验 mark/main_hit 双臂一致（t1r02 cov 0→1.0、t3r19
  0.52→0.75 反升；t1r26/t2r04b/t2r06b 覆盖略降仍 ±2s 内；t3r02a 双臂 main F 无影响）⇒ 无隐藏损失。
- **MISS6/t2r03b 逐条**：p14 获救；p20/p34/t1r08c/t1r12a 仍 part（逐位同）；t2r03b 双臂均
  0s 占位（v1 门控不救无候选段，符合预期；ISC 证据链可救但需先有候选，留门控 v2）。
- **旋钮观察**（不改默认）：翻转 3/139、aligned 噪声区零翻转 ⇒ margin 门不松不紧；3 条增益
  落点全部紧贴 GT 窗（span 收缩偏保守，观察点=span 端点贴窗而非 margin 本身）。
- **裁决 = PASS（机械执行预定门）⇒ 可进用户拍板翻默认；`isc_refine_enabled` 保持 False**。
  未翻默认 / 未改 GT / 未 bump feature_version / 未 git 提交。
- 产物：`work/isc_refine_arms/on_*.results.json`（4）+ stdout `work/rerun_isc_refine_stdout.log`
  + 分析 `work/isc_refine_arms/analysis/`（双臂 metrics、翻转清单 `isc44_flip_list_20261003.txt`、
  细粒度 diff `isc44_fine_diff_20261003.txt`、出图脚本 `make_isc44_flip_sheets.py`、拼图 3 张）。
  归档 `FINDINGS_ORTHOGONAL_BACKBONE_PROBE_20261002.md` §10。**没验**：OFF 臂同轮复跑（等价性
  靠旁证）、ON 臂增量耗时单测、合成集、margin 敏感性扫描（护栏禁 sweep）。

## 2026-10-02（续43）— 方案B 正交 backbone 探针 = 正判：ISC21 在 MISS6 上 6/6 gt_is_peak，通过可行性门槛

**用户拍板方案B**（续42 收口后的算法侧唯一候选）。探针 `mvp/scripts/probe_orthogonal_backbone.py`，
与方案A 同扫描协议/判据（margin>0.02、gt_is_peak ±1.5s、门槛 MISS+POCKET ≥1/3 且对照零反噬）/案例集
（MISS6+POCKET8 去重+CONTROL8=20 案例），产物 `work/orthogonal_backbone/`。

- **四臂**：**ISC21**（`isc_ft_v107`，EfficientNetV2-M@512→GeM→256-d，copy-detection 专用、与 DINOv2
  完全异族；权重自 tier2 trash 恢复 `work/isc21_weights_ortho_probe/` 离线加载；ONNX 导出时把
  gem(p=1) 重写为 ReduceMean 后 **DML 可授权**，生效）/ **CLIP** ViT-B/32 视觉塔（openaipublic 权重，
  HF 不可达绕开；**CPU 回退**——DML 授权失败且失败路径有毒，见工程留痕①）/ **dino**（现役 CLS-384，
  sanity 基线）/ **ens**（三臂逐位置 z-score 均值 = 方案B 集成形态）。
- **结果**：ISC = MISS **5/6 gt>main、6/6 gt_is_peak**（p14 +0.074 / p20 +0.110 / p34 +0.326 /
  t1r08c +0.046 / t1r12a +0.039 / t2r03b 峰落 GT±0.4s），MISS+POCKET 7/12 ✓；对照 7/8 peak，
  唯一 t1r27 = margin −0.0217 边界翻转（峰在 GT end+1.2s，非灾难反噬）。CLIP 弱信号（MISS 3/6、
  曲线近水平）不单独采纳；dino sanity 2/6 = 已知基线行为（harness 无 GT 泄漏旁证）；ens 与 ISC 持平。
- **铁律复核**：逐张读曲线 9 张（p14/p20/p34/t1r08c/t1r12a/t2r03b/t1r27/t2r06c/t3r02c/p04）——
  MISS 的峰为孤立真峰或罩住 GT 的清晰高区，非方案A 那种噪声台地；帧拼图 3 张（t2r03b/p34/p20）
  GT 帧与 ED 查询同内容、主定位帧不同内容（p34/p20 = 同场景另一时刻）⇒ **ISC 补的正是 DINOv2 缺的
  「同场景内时刻判别力」**。独立证据：dino sanity 对照 + Phase 12 ISC+TransVCL 曾是旧 GT v1 时代
  唯一产出视觉确认真定位的特征链。
- **结论改写**：t2r03b 续42「不可救」限定为 **DINOv2 证据链上不可救；ISC 证据链能救** ⇒ 列为
  采纳门控设计必验收样本。
- **工程留痕**：① **CLIP 图 DML 授权失败（E_INVALIDARG 80070057）会污染进程**——之后同进程任何
  DML session Run 段错误（EXIT=139；"同序列去 CLIP"对照复现归因）⇒ 未来多模型 runtime 的 DML
  授权失败必须 fail-fast 隔离（预检/子进程）；② t2r03b 主定位=0s 占位把扫描窗炸成全片 3580 位置
  （CPU 3834s"忙而不死"；方案A 同窗逻辑同踩）⇒ 已修：窗 >150s 钳 GT 邻域 ±15s + main_in_window 标记。
- 边界：探针=位置扫描 oracle 形态，**未进 runtime**；零 `mvp/src`/零 GT/零 feature_version；
  ISC@DML 全片扫描成本 ~2min/案例（runtime 只需歧义段 ±5s 局部窗，成本可控但须实测）。
- 归档 `FINDINGS_ORTHOGONAL_BACKBONE_PROBE_20261002.md`。**待拍板**：采纳门控设计 vs 先扩验证
  （139 正例峰位分布）；git 提交（续41+续42+续43，等口令）。

### 续43 扩验证（同日拍板选项②）：全 139 正例 ISC 峰位分布 = 信号真实、分层清晰

- `probe_ortho_full139.py`（同协议双臂 ISC+dino，35min）：**核心判别桶（drift+far+nowin，63 例）
  ISC 峰命中 44/63 (70%) vs dino 37/63**，配对仅ISC中 15 vs 仅dino中 8 ⇒ 非小样本运气，但强度分层：
  drift(2–15s) 73% / far(>15s) 43% / nowin 8/8；MISS6 全部 peak✓；aligned 基线两臂一致（71/76）。
- **ISC 独家增量 12 例**（仅 ISC 中，margin 至 0.37，10/12 在 drift+far，与 MISS6 高度重叠）。
- 失败 19 例两族：**近位移边界翻转 9 例**（disp≤5s、gap ≤0.1 噪声级）/**远位移一致错 10 例**
  （点名读图 t1r30a/t2r04a：ISC 与 dino 同峰同错、gap 可达 +0.6 ⇒ 两族特征共同上限，非 ISC 抖动）；
  t1r18 点名确证 ISC 真独家判别（ISC 峰在 GT 窗内、dino 峰窗外）。
- **门控设计约束**：ISC 只能做歧义段「第二意见 tiebreaker」（margin 绝对门 + 候选窗约束 + 两臂
  分歧才介入），全局重排必 churn（形态5 同构教训）；收益期望 = MISS6（6/6 peak✓）+ drift 独家
  增量 ~7 例，风险 = aligned 5 例峰不中 + 边界翻转 churn ⇒ 三指标零回退仍为硬门。
- 扩验证产物 `work/orthogonal_backbone_full139/`；归档同 FINDINGS §9。
  **待拍板**：是否按上述约束立项采纳门控设计；git 提交（等口令）。

### 续43 补：立项前多模态复核（用户问「多模态复核没」）= 独家增量 12 例全读毕：11 干净 + 1 边界

- 扩验证阶段只点名读了 3 张；本批补出 6 例曲线+内容拼图（p28/p09/t1r08a/t2r07b/t2r07c/t3r02a），
  连同探针阶段已读的 p14/p20/p34/t1r12a/t2r06c/t1r18/t1r30a/t2r04a，独家增量与失败代表全部读毕。
- **干净确证 11/12**（p28 举牌人/p09 Levi 特写/t1r08a 强喂/t2r07c 国旗马甲演讲/t3r02a 瞭望塔火景——
  ED/GT/ISC峰 三帧同内容，DINO 峰均在我方错误位置）；**边界 1/12 = t2r07b**：ISC 峰内容真但锚到
  GT 窗前 2.2s 的相邻子镜头（ED 段含切点）= 多镜段子单元族，不算干净命中。
- **记账修订**：ISC 独家增量 = 干净 11 例；**门控新增约束**：ED 段含切点/多子镜头时，ISC 峰允许
  锚到相邻子镜头（±2~3s），采纳判据须容忍子镜头粒度或结合 ED 子镜头切分对齐。
- 立项（选项①）已拍板 ⇒ 下批 = 采纳门控设计实现（歧义段 top-K ±5s ISC 重扫 + margin 绝对门 +
  候选窗/子镜头粒度约束 + 融合判据 + 三指标回归 + MISS6/t2r03b 必验收）。git 提交继续等口令。

## 2026-10-02（续41 后续）— r7 出包：入库层四件 + 快/精双模式进分发包（真机快验含一处显示修复）

**用户令「进 r7」**。`Video-Locator-win-x64-20261002r7.zip`（1.68GB / 8364 条目）。

- 首建 exit 0 → `accept_packaged_bundle.py` FAILED=0（22.2s）→ 三防冒烟全过
  （`work/pkg_attr/three_defense_smoke_r7.py`）→ 启动冒烟 PASS（Electron 4 + backend 1）。
- **包体真机快验（CDP，原生态）**：FileBrowser 走真实盘——「此电脑」列 C:(系统)/D:(软件)
  + 真实剩余容量 ✓；导航 `D:\ProjectXIXI\test2` 白名单只列 2 个 mp4 ✓；分析页「模式」单选
  可切快速 ✓；合成素材快速档跑通：日志 **`locate started ... refine=fast`** →
  7s 完成、该 session **「拆分多镜头段」消息 0 条**（快速档确实跳过）✓。
- **抓到并修掉显示缺陷**：小文件在浏览面板显示「0.0 GB」（155MB 级剪辑片看起来像坏）→
  `fmtSize` <1GB 改 MB 显示；复跑 vitest 138 + typecheck → **重建 r7** → 复验显示
  `test2-om.mp4 1.4 GB / tset2-ed.mp4 11 MB` ✓。zip 为修复后重建产物。
- **现役包 = r7**（= r6 + 续41 两批）。r5/r6 zip 处置未拍板（默认保留）。
- 续41 全部改动**仍未提交 git**（等口令）。

## 2026-10-02（续41）— 入库层四件 + 快/精双模式（一批两做，未打包）

**用户令「先入库，然后双模式」**。两块全部落地：

### A. 入库层四件（竞品 web.file_api.browser 移植，D#238/#239）
- **后端** `mvp/src/infrastructure/fsbrowse.py`（纯函数）：Windows 盘符枚举（含卷标，
  GetLogicalDrives+GetVolumeInformationW，失败逐级降级）/ **自然排序**（数字段按值比较）/
  **视频扩展名白名单**（13 容器）/ 磁盘剩余（shutil.disk_usage）；隐藏文件与无权限条目跳过不炸列表。
  路由薄壳 `GET /api/fs/browse`（detail 只回名字不回完整路径，与日志脱敏同立场）。
- **磁盘预检**：新 `DiskSpaceError` = **LOC-1108**（errors.py + SUPPORT_ERROR_CODES.md 同步，
  防漂移测试绿）；挂点 = `merge_originals`（输入总和+256MB）与 `render_movie`
  （~7.2Mbps 估体积+512MB 头寸，含逐段中间 MOV）——动手前失败，不留半截产物。
- **前端** `FileBrowser.vue`：此电脑→盘符（剩 xx GB）→目录（自然排序、只视频+文件夹）、
  多选按点选顺序=合并顺序、单选模式（剪辑片）、错误内联显示；ProjectDetailPage 源片库 +
  剪辑片区各挂一个「浏览选择」入口（原生对话框/粘贴入口保留）。
- **实测（dev+Mock，浏览器）**：D: 盘列 clip2 在 clip10 前 ✓；txt 不出现 ✓；
  点选顺序进原片库 ✓；盘符剩余容量显示 ✓。

### B. 快/精双模式
- `locate(..., refine: bool|None=None)`：None=config 默认（高精度，两旋钮默认开不变）；
  False=快速档跳过切镜拆分+画面深度复核。落日志 `locate started ... refine=on/fast/default`。
- 全链透传：`AnalyzeTaskRequest.refine` → `Task.refine` → worker → locate；
  UI 分析页「模式：高精度（默认）/ 快速（省时约六成）」单选，档位记 localStorage；
  body 只在显式选择时携带 refine（不传=逐字与旧形态一致）。
- 测试：service 级 3 条（默认发拆分消息 / fast 不发 / 显式 precise=默认）+
  API 透传 1 条 + vitest body 3 分支。

**门禁**：后端 **485** · API **104** · vitest **138** · 双 typecheck · `test:mock` 全绿。
零 `feature_version`（模式只动后处理开关，索引/查询语义不变）。
**未提交、未打包**——两批（续41 全部）建议随 **r7** 一起进包（需授权）；git 等口令。

## 2026-10-02（续40 后续三）— r6 出包：UI 三修复 + 售后三件进分发包（包体真机全验）

**用户拍板「出包吧」**。`Video-Locator-win-x64-20261002r6.zip`（1.68GB / 8364 条目，
win-unpacked 01:38 全新构建，BUILD_EXIT=0）。

- **包体装配验收** `accept_packaged_bundle.py` = **FAILED=0**（syn 冒烟 22.3s、device=dml）。
- **三防冒烟**（`work/pkg_attr/three_defense_smoke_r6.py`）= 全过（LISTEN/health200/401/无令牌拒启 rc=1）。
- **调试档包内冒烟（新）**：包内 backend.exe + `SVL_LOG_DEBUG=1` → 日志目录出现
  `debug.log` + `video_locator.log` 双档，health 200 = PASS。
- **启动冒烟**：Electron 4 进程 + backend.exe 子进程 = PASS。
- **包体真机快验（合成素材，CDP 驱动 r6 exe）**：首页卡徽标「**未分析**」✓；分析实时文案
  「复用已有母片索引：source.mp4 / 镜头边界粗扫 / 逐段定位 1/1」✓；进度**一位小数 92.0%** +
  计时器走动 ✓；跑完 1 结果 HIGH 0.99 + 自动预览；包内日志 `backend selected=directml` +
  `patch reranker device=dml`（01:45:24）✓。
- **r6 内容 = r5 全部 + 续40 后续（UI 三修复）+ 续40 后续二（售后三件）**。
  渲染层修复入包经 grep 产物确证（ProjectCard chunk 含「未分析」、AnalysisPage 含 toFixed(1)）。
- **数据留存裁决（用户 2026-10-02）**：应用数据目录残留（merged 1.9GB / edited_cache /
  index 等，PROJECT_AUDIT §9）**不删、待办不再挂档案**；本次新查项（data_fresh_probe、
  Electron 缓存、.idx.stale、mvp/logs）同样不删不登记。§9 仅作审计事实留档。
- **现役包 = r6**；r5 zip 处置未拍板（默认保留）。

## 2026-10-02（续40 后续二）— 售后可诊断性三件：脱敏补强 + 三级日志 + 客服编号对照表

**用户拍板「按推荐顺序，先启动脱敏三件」**（差集 TOP8 第 5 项，续17 登记）。
先纠档：路径脱敏主体**续19 T1-2 已落地**（`redact_text` + `RedactingFilter`，msg/traceback/URL/token 全覆盖），
本批 = 补漏 + 补齐另两件：

- **① 脱敏补强**：a) `launcher.make_server` 关 uvicorn `access_log`（访问行带**原始 query**
  如 `video_path=D%3A%5C...` 且走 uvicorn 自己的 logger 不过我方过滤器；`module=api` 请求日志已覆盖可诊断性）；
  b) 新规则 `_PCT_WIN_PATH`（百分号编码盘符路径 → `<PATH:文件名>`，保留文件名利于客服对单）；
  c) `_API_PATH_QUERY`（`/api/...?*path=` 参数值打码，负向前瞻避免二次吞 `<PATH:>`）。
- **② 三级日志**（对齐竞品 wp.diagnostics 客户/支持/调试分层，不抄 .cmlog 加密形态）：
  客户档 = UI 话术 + LOC 码（已有）；支持档 = `video_locator.log`（INFO+，脱敏，「下载日志」即此）；
  **调试档（新）**= `debug.log`（DEBUG 全量、同样脱敏、20MB×3，默认**关**，
  env `SVL_LOG_DEBUG=1` 由支持人员指导开启；主文件 handler 钉 INFO 两档互不重复）。
- **③ 客服编号对照表** `mvp/docs/SUPPORT_ERROR_CODES.md`：全部 **13 个对外码**
  （LOC-1000/1101/1102/1103/1104/1105/1106/1107/1109/1201/2001/2002/9999）× 含义/用户话术/
  常见触发/客服处置 + 竞品 11 族归口参照；AUTH/DISK/MEM 三类**预留占位**（对应功能未做）。
  防漂移 = 新测试 `test_support_codes_doc.py`：源码码集 ⇔ 表码集双向相等 + 核心异常类码唯一。
- **验证**：后端 **469（+9）** · API **100** 全绿；前端零改动。规则次序教训：整段 query 打码
  会吞掉既有 `session=<REDACTED>` 断言语义 ⇒ 收窄为只打 `*path=` 值；百分号正则懒惰匹配只吃到
  前缀 ⇒ 改贪婪到 `&`/空白分隔符（两条均有回归锁）。
- **r6 重打累计内容** = 续40 后续（UI 三修复）+ 本批三件（launcher/logging/errors 文档）。

## 2026-10-02（续40 后续）— 真机 UI 三问题修复：REFINE 进度区间 + 一位小数 + 全量中文话术

**用户真机反馈三条**：① 项目卡「empty」英文技术值漏到界面 + 长文件名逐字换行 + 徽标与邻卡挤；
② 进度条一直卡 92、要精确到小数点后一位；③ 「高精度精修：patch 局部精排」暴露技术点，全部进度文案重写。

- **① ProjectCard**：`STATUS_LABEL.empty='未分析'`（原样漏英文的根因=标签表缺键直显枚举值）；
  图标+徽标成组靠左（原 space-between 把徽标推到右缘与邻卡图标贴一起）；`.pcard__meta` 单行省略号
  （长合并文件名不再「合 并」逐字折行）。
- **② 进度逻辑**：新增 `ProgressStage.REFINE`，worker 映射 92→98 逐事件插值（EXPORT 挪 98→99.5）——
  段循环后的全局修复/拆分/精排链不再把进度钳死 92；`Task.progress` 改 float、
  `map_progress_stage` 输出**一位小数**、`ProgressPipeline` 显示 `toFixed(1)`。
- **③ 话术全量重写（locator_service 21 条消息）**：`patch 局部精排`→「画面深度复核 i/n」、
  `segment i/n: text card/retrieval/localize/confidence`→「逐段定位 i/n」、`reuse index`→
  「复用已有母片索引」、`特征提取`→「分析剪辑画面」、`twopass coarse sampling/segmentation`→
  「镜头边界粗扫/精修」、`exporting/exported`→「正在导出/已导出」等；REFINE 链入口补发首条消息
  覆盖此前 ~6.5min 静默空窗（text anchor 批处理段）。
- **验证**：后端 **460** · API **100（+1 REFINE 区间测试；2 处期望随小数更新）** · vitest **132** ·
  双 typecheck · `test:mock` 全绿；浏览器 dev + 源码树后端（DML 生效）合成素材实跑：
  「母片索引已完成（共 90 帧）/镜头边界粗扫/画面深度复核 1/1/**98.0%**」逐条目检 ✓；
  首页卡「未分析」徽标 + 长名单行截断 ✓。
- **登记**：dev 浏览器态侧栏徽标显示「CPU 回退」而实测 backend selected=directml（打包态 r5 显示
  正确 = GPU (DirectML)）——dev 专属形态，未修；本次改动**未进 r5 包**，需 r6 重打才到用户手上。

## 2026-10-02（续40）— r5 重打 + 包体验收全过：打包态 62.6→27.0 min，续36 修复真机确证

**用户拍板 = r5 重打 + 包体验收**。全部通过：

- **构建**：`build-release.ps1` 四阶段全过 → `release/Video-Locator-win-x64-20261001r5.zip`
  （1.68GB / 8364 条目，含 patch 资产 4 条目增量；r4 zip 保留未删，删旧包需另行授权）。
- **首跑抓到一个构建缺陷**：续36 新增的 patch 资产 sha256 断言用 `Get-Content -Raw`（ANSI/GBK）
  读 UTF-8 `asset.json` ⇒ `ConvertFrom-Json` 崩（该断言 r5 前从未实跑）。修 = 加 `-Encoding UTF8`。
- **包体装配验收** `accept_packaged_bundle.py` = **FAILED=0**（r4 实测 FAILED=5）：资产在位 +
  sha256 双对 + 包内 backend.exe 合成冒烟 23.2s ≤45s、`backend selected=directml`、
  **`patch reranker device=dml`**。
- **三防冒烟**（新 `work/pkg_attr/three_defense_smoke_r5.py`，产物只落 work/）= 全过：
  BACKEND_LISTEN 公告 / health 200 / 受保护端点无令牌 401 / release 无令牌拒启 rc=1。
  ⚠️ 注：`/api/health` 属放行路径不能当门禁负例（首版误用已改）。
- **真机 E2E（test2 全链，CDP 驱动整包）**：
  ① **续36 根因修复真机确证**：包内日志 `patch reranker device=dml`（r3/r4 同位置 = cpu）；
  ② **打包态 locate elapsed = 1622.0s = 27.0 min**（r3/r4 = 3756.7s 62.6 min；实验室 1396.7s）
    ⇒ 「打包态应回到 ~23min 级」达成（残余 1.16× 为段循环前 P 段）；
  ③ 结果与 r3 E2E 逐字段一致：67 段 / 31高 9中 25低 2未定位 / shot_split 54→67（split 9, 14 shots）/
    patch_refine refined 65 switched 11 ⇒ 零语义漂移；
  ④ **r4 尾巴一 = 精修进度文案落地**：UI 实测「高精度精修：patch 局部精排 10/67」逐段推进；
  ⑤ **r4 尾巴二 = 导出默认项**：置信门槛默认选中「全部（低置信也作为主片段导出）」。
- **新登记（非阻塞）**：a) 段循环结束→shot_split 开始之间约 6.5 min（sequence/temporal/conflict
  修复 + 置信）无任何进度消息且百分比单调钳死 92%，用户观感仍像卡住——候选 UX 尾巴；
  b) 包内 CLS `dinov2_cls_384/asset.json` 无 sha256 ⇒ 每次启动 WARNING
  「asset integrity skipped」（既有，非 r5 回归）；c) 本次真机跑未做渲染成片（r3 已验）。
- **git 仍未提交（等口令）**：续33后续~续40 全部，含本次 `build-release.ps1` 编码修复。

## 2026-10-01（续39）— GT 20条工单结案：17修订/3保留，同批重计133/125/138

> **▶ 2026-10-01（续39）— 20 条 GT 缺口核对及写回完成**
> 用户令「那你去完成啊」：原生帧节奏解码、切点/动作图证与源帧辅助匹配完成；**17 条修订、3 条保留**。
> 10 条原片窗修订 + 7 条仅 ED 锚点收紧；139 个 ID、其余119正例、9负例保留，未扩充蒙太奇标签。
> 四份 GT 版本追加 `gt-gap-review-20261001-r1`；备份 `work/gt_backup_pre_gap_review_20261001/`；MD5 manifest 已更新。
> 原 ON 结果批不变，同评估器重计 **严格 133/139 · 主片段 125/139 · 场景 138/139 · 负例误报 4/9**。
> 相对旧GT读数132/119/137：这是**标注修订导致重计，不是算法提升**。p34 HIT→part 如实保留。
> t1r08c 零时长已改一帧锚点，但严格仍未命中（MISS→part）；续38“实际覆盖该点”过强，现撤回。
> t2r03b 旧“同源重复”已追加取代说明；t1r22/t1r25/t2r06c 原标注成立。
> **范围/精度**：本轮核对20工单，非全139条重标；源窗为图证帧时间包络，不声称亚帧精度；执行者Codex，非用户逐条亲审。
> 报告 `mvp/benchmark/user_case/semantic_signal/FINDINGS_GT_GAP_REVIEW_20261001.md`；最终图证 `work/gap_gt_review_final_20261001/`。
> 校验通过：输入8哈希、备份逐字节、结果4哈希不变、未选119正例/9负例不变、ID保留。GT工单结案，算法仍有6条严格未命中。

## 2026-10-04（续53，A/B 归因线程收口）— 四片**双新臂全 PASS**：逐字段 0 差异 × 4

协议：**fresh off（`grab_grid_decode=False`） vs fresh on（True）**，同代码/同配置/唯一变量=旋钮，
两臂都是完整 `srv.locate()`，比对 `strip(result_id)` 后逐字段；归档批 `v2_*` 只作 history、不作 off 臂
（跨代际差异已实测：2mkv 归档 83 段 vs 同配置 fresh 84 段、共有段落点 0 差异）。

| 片 | off | on | 段数 | 逐字段 | 加速比 | 口径 |
|---|---|---|---|---|---|---|
| test1 | 2772 s（续47 defaults_check，已证与当前配置逐位一致） | 2186.1 s | 55/55 | **0 差异** | **1.27×** | 干净 |
| 2mkv | 3225.9 s | 2479.2 s | 84/84 | **0 差异** | **1.30×** | 干净（双新臂） |
| test2 | 6233.7 s | 3609.3 s | 67/67 | **0 差异** | 1.727× | 两臂均与 test3 并行争用⇒仅参考 |
| test3 | 7402.8 s | 3543.9 s | 103/103 | **0 差异** | 2.089× | off 臂受争用、on 臂独占⇒偏高 |

- **结论一（缺陷已闭合）**：test2 先前对归档参照的 3 行、test3 的 5 行落点差，经双新臂复跑**全部消失**
  ⇒ 它们是**安全网修复前**的「整格跳位」缺陷，不是网格路径的固有代价。
- **结论二（口径纪律）**：跨代际的归档批不可作单变量 A/B 的 off 臂；四片验收一律**双新臂**。
- **结论三（指标）**：四片三指标逐项一致（严格 136/139 · 导出实得 131 · 场景 138 · 负例 4/9；支撑 1103→1108）。
- **产物**：`work/isc_grid_ab/{ab,off,on}_{test1,2mkv,test2,test3}.*`；明细 FINDINGS_COST_STRUCTURE_LEVERS_20261003 §5.5。
- **未做**：未改 GT / 未 bump feature_version / 未翻任何其它默认值 / 未 git 提交（等口令）/ r8 重打（等口令）。

### Notes

- Created `checkpoint-2026-10-04-2350.md` checkpoint (86 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-10-04-2353.md` checkpoint (87 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-10-04-2354.md` checkpoint (88 modified/untracked file(s)).

## 2026-10-05

### Added

- None.

### Modified

- Updated `.agent/STATE.md` last-updated timestamp.

### Fixed

- None.

### Removed

- None.

### Notes

- Created `checkpoint-2026-10-05-0012.md` checkpoint (90 modified/untracked file(s)).

- Created `checkpoint-2026-10-05-0012.md` checkpoint (89 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-10-05-1625.md` checkpoint (11 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-10-05-1628.md` checkpoint (12 modified/untracked file(s)).

## 2026-10-06

### Added

- None.

### Modified

- Updated `.agent/STATE.md` last-updated timestamp.

### Fixed

- None.

### Removed

- None.

### Notes

- Created `checkpoint-2026-10-06-0118.md` checkpoint (26 modified/untracked file(s)).

- Created `checkpoint-2026-10-06-0118.md` checkpoint (25 modified/untracked file(s)).

- Created `checkpoint-2026-10-06-0114.md` checkpoint (24 modified/untracked file(s)).

## 2026-10-06（续58）— r9 出包 + 全链验收 PASS（口令「出包」）

- **构建**：`build-release.ps1` 四步全过（首跑败于旧 win-unpacked 文件被占用 `Access is denied`
  → 清进程删目录重跑即过）；产物 `mvp/ui/release/win-unpacked/Video Locator.exe`。
- **包内容**（工作区未提交态构建）：三旋钮新默认（`patch_refine_grid` / `rerank_grid_grab` /
  `cluster_workers=4`）+ UI 五件修复（卡片溢出/新建直进构建页/剪辑×删除/按钮间距/pd__lib
  面板溢出）+ 续54~57 全部提速与修复。
- **验收**：`accept_packaged_bundle.py` **FAILED=0**（backend.exe/patch/ISC 资产 sha256 全过 ·
  包内冒烟 33.9s ≤75s · DirectML 生效 · 精排 GPU 未回退 · ISC GPU）+ **启动冒烟 PASS**
  （进程 25s 存活）+ zip 抽验（`Video-Locator-win-x64-20261006r9.zip` 936MB / 7078 条目 /
  CRC OK / main.js+preload+渲染层+三模型资产全在；asar 禁用形态 = `resources/app/out/electron/`）。
- release 现役 = r8（回滚）+ **r9（最新）**；r7 已删（2026-10-06 用户口令「留r8删r7」）。
- ⚠️ 包 = 未提交工作区构建 ⇒ **git 提交应先于任何对工作区的再修改**（保持包↔提交一致）。

## 2026-10-06（续58 补一）— r9 包真机全链复核 = PASS（口令「跑吧」）

- **跑法**：`attr_packaged_headless.py test1`（包内 backend.exe headless，与 Electron 打包态
  同 env）。**补齐脚本落后项**：r3 时代的 env 注入缺 `SVL_PATCH_ONNX`/`SVL_ISC_ONNX`
  （r5+ main.ts 才有），不补会复现「精排静默回退 CPU」事故——已对齐 main.ts 打包态注入。
- **结果**：wall **1196.9s = 19.9min**（实验室同代码态 1320.5s，headless 无 UI 观察侧，方差内）
  · 55 段 · task completed 零错误 · DirectML 生效（directml/amd 无回退）· 索引复用（VALID）·
  轮询延迟 p50 4.7ms / p95 17.4ms（进度通道健康）。
- **语义核验（最硬一条）**：包内结果 vs 实验室 `defaults_flip_ab/test1/on` 臂
  strip(result_id) 后**逐字节 identical = True**（55 段 + 信封）⇒ r9 包 = 实验室同语义，
  三旋钮新默认在包内正确生效。
- 阶段观感：逐段定位 ~7s/段 → REFINE（拆分+精排）~10min，进度通道全程有消息（续40 修复生效）。
  ⚠️ 脚本 summary 的 "package" 字段是硬编码 r4 旧串（化妆品级，未改）。
- ⚠️ 包 = 未提交工作区构建 ⇒ git 提交前不要再改工作区。r8 删除仍待授权。

## 2026-10-06（续58 补二）— 算法下一刀立项完成（口令「3」），待拍板三选一

- **影响面量化（离线，新默认批 136/131/138/4·9）**：路线 A 导出选择器 oracle = **导出实得
  131→136（+5）、零损失行**（t1r22/t1r25/t2r02b/t2r06a/t3r02a 五行全有命中子 span）。
- **信号面新发现（推翻朴素选优）**：命中子 span 的 score 全为 null（基础链降子老主，5 行里
  仅 1 行有 refine 改写后缀）；alternatives 近乎空；池子 span 只有检索级分 ⇒ 同源信号重选
  大概率同错，选优需异源信号（patch/ISC 导出时打分）或口径变更。
- 路线 B 扫描缩减（解码地板，radius 90 不可砍）、路线 C mkv 异步化（缺产品口径）——均列
  暂缓理由。提案档 `semantic_signal/RESEARCH_PROPOSAL_NEXT_CUT_20261006.md`：
  A1 降子补记分（半天，零行为）→ A2 异源选优（1 天，主形态）∥ A3 导出含子（产品选项），
  统一验收门 = 严格/场景/负例零回退 + 导出 +5 全兑现 + 5 行读图。

### Notes

- Created `checkpoint-2026-10-06-1320.md` checkpoint (1 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-10-06-1431.md` checkpoint (1 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-10-06-1432.md` checkpoint (1 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-10-06-1435.md` checkpoint (1 modified/untracked file(s)).

## 2026-10-06（续59 补记）— macOS CI 5 失败根因修复（跨平台平局确定性）

> 本条为补记：续59 当时只写了 STATE/TODO，**CHANGELOG 漏落**（STATE 里「明细 CHANGELOG 续59」
> 指向不存在的条目），2026-10-06 续60 会话核对时发现并补齐。

- **现象**：CI（macOS runner）全套抓到 **5 失败**（`patch_refine`×2 + `isc_l2_index`×3），Windows 全绿。
- **根因**：numpy SIMD 快排（quicksort）对**精确平局**的返回顺序跨架构不同 ⇒ `_clusters` 选出的候选
  代表帧不同 ⇒ 下游精扫窗 / 宽扫排除集漂移。生产真实 sims 是连续浮点、无精确平局，产品语义不受影响；
  踩中者是合成夹具的退化平局。
- **修复（提交 `3230fad`，已推 origin/master）**：判据排序加 `kind="stable"` **两处**（`git show --stat` 核过）
  —— `engine/localization/patch_refine.py:58`（`_patch_score` 的 `_clusters` 代表帧序）与
  `engine/localization/isc_refine.py:302`（L2 宽扫排除集序）；平局按索引序 ⇒ 全平台逐位一致。
  另两处 `clustering.py:80` / `segment.py:204` 的 `kind="stable"` **本次未动**（先前已在位）。
  测试侧随确定性收敛更新两断言/一夹具（patch E2 代表帧 112 ⇒ child start 110；isc_l2 真峰 139-141
  移到 CLS 库外延区，使 `-iscw` 采纳与平局顺序无关）。
- **门禁**：Windows 后端全套 **540 OK**；未改 GT、未 bump `feature_version`、未动任何旋钮/阈值/采样。

## 2026-10-06（续60）— stable 修复双链验证 PASS：四片逐字节零差异 + macOS CI 全绿

- **① 四片零差异回归（生产不变性证明）= PASS**：`probe_stable_sort_regress.py`（defaults-only、
  `assert DirectMLBackend`）续59 会话启动后**未断**，本会话按日志实测接管监控至 `ALL_DONE`。
  `work/stable_sort_regress/summary.json`：2mkv `wall=1584.3s` / test1 `1202.5s` / test2 `1642.6s` /
  test3 `1548.5s`，四片 **`strip_identical=true`、`n_diff_rows=0`**（对照臂 =
  `work/defaults_flip_ab/<case>/on.results.json`，同代码态默认旋钮）。
  ⇒ **stable 排序对生产行为零影响，无需回滚、无需改纯夹具方案重推**。
- **② macOS CI = 全绿**：run **37425131410**（#23，head `eded658` 含 `3230fad`）三 job success
  （`mvp-tests-macos` / `mps-poc` / `macos-package`）。`mvp-tests-macos` 日志实测
  **`Ran 540 tests in 412.938s` → `OK (skipped=45)`** ⇒ 续59 的 5 个失败确认修复；
  Windows 540 / macOS 540 计数齐平（skip 数差异 = 平台资产与 DML 用例守护）。
- **更正留痕（两条，均为交接文本里的错记）**：
  ① **「push `3230fad` 自动触发 CI」是错的**——`.github/workflows/h3-macos-mps.yml` 的 `on:`
  **只有 `workflow_dispatch`**（文件注释写明为省 macOS runner 刻意手动）。GitHub API 实测最新 run
  停在 3d1b580（修复的父提交），3230fad 之后**没有任何新 run** ⇒ CI 验证必须手动 dispatch；
  本会话经用户口令后 dispatch。② STATE「明细 CHANGELOG 续59」指向空条目（见上「续59 补记」）。
- **未动的平局敏感点（将来跨平台再漂移时从这里查）**：`app/locator_service.py:1863`、
  `engine/localization/evidence_localize.py:168/198/493`、`montage_localize.py:57`、
  `offset_vote_prior.py:123`、`retrieval.py:50`（本轮 CI 已全绿，未改；这些点含真实连续 sims
  上理论平局面，改动须重走四片零差异验收）。
- **销项**：续59 三项待办（① 回归 ② CI ③ 全过归档）全部结案，无阻塞、无遗留。
- **待拍板延续**：本会话仅改档案文档（STATE/TODO/CHANGELOG），git 提交等口令；
  下一刀（A1 降子补记分 → A2 异源选优 ∥ A3 导出含子）仍未拍板。

## 2026-10-06（续61）— LOC-1107 片尾越界真缺陷修复 + 竞品入口/资源层整值读完（精度仍无肉，工程出 9 条）

### 一、LOC-1107 片尾越界（打包态 r9 真机撞出，源码已改未提交）

- **现象**：r9 打包态跑 `work/e2e_r3/src_part1.mp4`（63.000s / 1827 帧 @29fps）整条 locate 失败，
  UI 只见通用话术「视频读取/剪辑处理失败，请确认文件未损坏、未被其它程序占用」；日志真因 =
  `MediaError: grab_frame returned no frame at t=63.500: src_part1.mp4`，链路
  `locate:1172 → apply_patch_refine:164 → _grab_source_grid:100 → _grab_grid_batch:2512 →
  grab_grid_times:323 → grab_frames:252 → grab_frame:177`。
- **根因（两条叠加）**：① 精扫窗 `g1 = mid + REFINE_WIN_S(5s)` 无片尾边界（修复前
  `patch_refine.py` 内 `grep duration` 零命中），落在片尾的候选会向**不存在的帧**要网格点；
  ② `grab_frames` docstring 承诺的「超片尾逐帧回退 `grab_frame`（健壮性优先）」不成立——
  `grab_frame` 取不到帧即抛（`ffmpeg_io.py:177`），于是**单点越界 = 整条任务失败**。
- **修法（上游钳制）**：`apply_patch_refine` 新增 `source_duration_s`，窗尾
  `g1 = min(g1, source_duration_s)`，钳后 `g1 <= g0` 的候选跳过（该段原样返回，走既有 None 守卫）；
  `locator_service` 生产传 `bundle.meta.duration`（**容器时长而非索引末点**——末点比片尾早约 1s，
  用它钳制会削掉原本能成功的窗，属语义变更）。两处假承诺注释同步改正。
- **为什么不必重跑四片（构造性零语义）**：钳制仅在窗尾越过容器时长时生效，而这类目标过去必然走到
  抛错路径 ⇒ **任何过去能跑完的 run，请求时间集合与帧逐位不变**；且网格按 `(g1-g0)` 等分，
  一旦钳制整窗点位都变，所以"会不会变"等价于"钳制有没有触发"，而触发即意味着过去会崩。
- **验证**：后端 **543 OK (skipped=2)**（原 540 + 3 新锁：窗尾钳制 / `dur=None` 旧行为不变 /
  窗整体越界→段原样返回）· API **104 OK** · 真素材 A/B `work/fix_eof_ab_probe.py`：
  未钳制臂复现 `MediaError @ t=63.000`，钳制臂 OK（51 个请求点，最大 t=62.48，结果段数 1）。
- **登记盲区（诚实）**：四片回归母片都是 ~2h，「短原片 + 段落落片尾」从未进验收集 ⇒ 零语义 harness
  覆盖不到越界输入这类边界；残留下界 = [视频流末点, 容器末点) 的一帧缝（本例 0.019s，既有行为未扩大）。
- **顺带**：竞品把这类失败单列 `MEDIA-002 素材无法正常读取` 并配建议话术，而我方一个 LOC-1107
  覆盖全部 ffmpeg/ffprobe 失败 ⇒ 「是否拆码」列为待拍板（触 `errors.py` 只增不改规则）。

### 二、竞品入口/资源层整值读完（只读常量池，零 `mvp/src` 改动）

- **触发**：`work/cm_redig/inventory_prefixes.py` 清点实测 = 续37 只挖 9,850 / 37,041 值（26.6%），
  分桶为 已挖 26.6% / **未挖第一方 10,721 值 74 模块（28.9%）** / 三方噪声 16,470（44.5%）；
  `cutmatch.matching` 整族 58 模块 9,733 值**已全覆盖** ⇒ 续37「精度已挖干净」在其范围内成立，
  「竞品侧已空」不成立。
- **本次读**：`dump_entry.py` → 17 模块 3,634 值（`processing.video.{processor,concat}`、
  `processing.jobs.batch`、`processing.progress.tracker`、`processing.resources.{device_events,
  memory_safety}`、`web.processing_api.{single,batch,state,routes,diagnostics}`、`runtime.{resources,tools}`）。
- **结论**：精度侧无新机制（与总账一致）；**工程/UX/售后侧 9 条形态**，4 条直接回答我方挂着待办
  （720p 代理 + `is_proxy_frame_accurate` 帧精确门禁 → CFR 代理；按可用内存收缩 batch/预取 +
  `low_memory_mode` 上报 → memmap；`CUTMATCH_DEVICE_CONFIRM=` 子进程回报真实设备 → UI-P3 徽标误标；
  阶段延迟发布 + `heartbeat` → UX-P1 卡感）。另 `xml_only` 是**入口开关不是失败兜底** ⇒ 竞品
  「渲染失败仍出 XML」的未决口径要重问；`runtime.tools` 明文 macOS Finder 启动 locale 非 UTF-8 会
  炸中文路径 ⇒ 对刚出的 mac artifact 直接相关；口径收益 = 竞品默认 `matching_mode=standard`
  从反推升级为直证（view:308/861/930/933）。
- **两处更正留痕**：① 会话内先前提的「27% 已读 ⇒ 精度结论不稳」被清点数据削弱，已按实测改口；
  ② `model_lease` 口头猜「GPU 模型占用治理」**错**，入口层证据 = 授权租约
  （`verified_model_lease` / `reason=missing_model_lease` / 话术「V2 模型授权租约缺失，无法开始处理」）。
- **未穷尽**：竞品是 Nuitka 产物，本层证据全来自常量池 ⇒ 能证"有什么旗标"，不能证"先做哪个"；
  opcode 通道可行性仍未探。
- **明细档**：`mvp/benchmark/user_case/competitor_cutmatch/FINDINGS_CUTMATCH_ENTRY_LAYER_20261006.md`
  + `work/cm_redig/inventory_20261006.md` / `entry_view_20261006.md` / `entry/*.txt`。

## 2026-10-06（续61 补一）— r10 出包（含 LOC-1107 修复）+ 五道包体验收

- **构建**：`mvp/ui/scripts/build-release.ps1` 四步全过（vite → compile:electron → PyInstaller
  onedir 后端 1053 MiB → electron-builder --win dir），PS_EXIT=0，产物
  `release/win-unpacked/Video Locator.exe`（11:27 的 r9 被**原位覆盖**，非空目录重打）。
  ⚠️ 过程记录：`release/win-unpacked` 目录级 rename 被拒（某进程把它当 CWD），但目录内文件
  可写可改名 ⇒ 放弃改名、原位构建；r9 解包内容改从 **r9 zip 解出**留作对照臂。
- **包内容验收**：`accept_packaged_bundle.py` **FAILED=0**（patch/ISC 图+外部权重 sha256 全过 ·
  包内冒烟 30.3s ≤ 75s · DirectML 生效 · 精排 GPU 未回退 CPU · ISC GPU）。
  `work/pkg_attr/three_defense_smoke_r7.py` **FAILED=0**（backend 在位 · BACKEND_LISTEN 公告 ·
  health 200 · 拒绝无令牌 · release 无令牌拒启 exit!=0）。
- **启动冒烟**：`Video Locator.exe` 起后 25s 存活 = Electron 4 + backend 1（与 r9 同形态）。
- **zip**：`mvp/ui/release/Video-Locator-win-x64-20261006r10.zip` = 981,634,169 B / **7,078 条目**；
  抽验 `Video Locator.exe`、`resources\backend\backend.exe`、`resources\app\out\electron\main.js`、
  patch/ISC `.onnx.data` 均可打开读取（CRC 过）。
  **包内含修复的硬证**：包内 backend.exe = 77,441,843 B，r9 同文件 = 77,440,920 B（差 923 B），
  且包内无散装 pyc（模块在 CArchive 内，故字符串 grep 不适用，改用尺寸+行为证据）。
- **macOS CI run #24**（head `137866f`，含本次修复与 3 个新测试；**用户手动 dispatch**）=
  三 job success，`mvp-tests-macos` 日志 **Ran 543 tests in 362.3s → OK (skipped=45)**
  ⇒ 修复跨平台不回归（Windows 543 / macOS 543 齐平）。
- **片尾形态的包体复现 = 未成立（如实登记）**：新造两条素材
  （`eof_tail_ed6.mp4` 原片末 6s；`eof_ed126.mp4` part1+part2 拼接 126.8s 只给 part1 作原片，
  66 段定位 + 82 段精排）在 **r9 包**上跑：eof63 22.1s 过、eof126 455.0s 过，**都没崩**
  ⇒ 这两条不是判别性用例，包体级"修复前必崩"仍未实证；源码级 A/B（真 FFmpegIO，未钳制臂复现
  `MediaError @ t=63.000`）与 543 单测才是本次修复的证据面。
  ⇒ **待用户用 16:34 那次失败的同项目（31 段解说 vs `src_part1.mp4`）在 r10 上重跑一次**，
  那才是包体级判别测试。跑手已备：`attr_packaged_headless.py` 新增 `eof63` / `eof126` 两用例。

## 2026-10-06（续61 补二）— 进度条 92% 卡死 + 计时显示 00:00 两个 UI 缺陷修复

- **用户报**：打包态分析跑到「镜头分析 92.1% 00:00」长时间不动，且计时不像在走。
- **根因 1（百分比）**：`_STAGE_RANGES` 里 REFINE = (RETRIEVAL, 92, 6) 被**修复链 / 切镜拆分 /
  patch 逐段精排 / ISC 逐段**四条子链共用同一条 0→1 ramp，而修复链整段只发一条
  `current=0, total=len(results)` 的事件 ⇒ UI 停在 92.0~92.1 数分钟；随后逐段精排的分数
  又被 `run_worker` 的单调钳制挡住（它的 frac 从 0 重起）。
- **根因 2（计时）**：`AnalysisPage.vue` 的 elapsed 是**组件本地** `setInterval` 计数器，
  只有 `run()` 会 `startElapsed()` ⇒ 换页/组件重挂即归零且不再走（显示 00:00）。
- **修法**：① `ProgressEvent` 加 `phase`（默认空 = 旧行为逐位不变，`to_dict` 同步）；
  ② `worker._PHASE_RANGES` 把 92→98 切成互不重叠四段：`fix` 92-94 / `split` 94-95 /
  `patch` 95-97 / `isc` 97-98，带 phase 的事件 current 一律按**已完成数**解释（`current/total`）；
  ③ 修复链补 5 个粗步事件（全局锚点 → 字牌与序列 → 时序与冲突 → 连续重复 → 整体一致性），
  `locator_service._notify` 透传 phase；④ 起点时刻改存 store `taskStartedAt`，
  页面按 `Date.now() - taskStartedAt` 现算，`running` 驱动 tick，终态/`reset()` 清空。
- **门禁**：后端 **543 OK (skipped=2)** · API **105 OK**（+1 phase 切片测，含"无 phase = 92.1
  旧行为"回归锁）· vitest **137 全绿**（+1 store 起点测）· `typecheck` + `typecheck:desktop` 干净。
- **口径**：纯展示层与事件 schema，**未动任何定位语义**（无新旋钮、无 GT 变更、无 feature_version）；
  修复链事件插在既有步骤块之后，不改步骤顺序。
- **注意**：现役 **r10 包不含本修复**（r10 = 17:31 构建，只含 LOC-1107）⇒ 要让打包态进度动起来需 r11。

## 2026-10-06（续61 补三）— 预览双播放器联动暂停 + 时长显示 00:00 修复（UI）

- **用户报**：结果页预览里「上面的（剪辑）播完后，下面的（原片）没播完也跟着暂停」；截图同时显示
  剪辑播放器左右时间都是 `00:00`。
- **根因 1（联动暂停）**：`VideoPlayer.onPause` 把 `<video>` 的 `pause` 事件**一律**上报成
  `playingChange(false)`，而浏览器在**播到末尾时同样会 fire `pause`** ⇒ 剪辑片段放完 ⇒
  `VideoComparisonPlayer` 的共享 `playing` 被置 false ⇒ 另一路经 `watch(props.playing)` 被暂停。
  佐证症状是单向的：原片那路**当时根本没接** `@playing-change`（只有剪辑接了），
  所以"上停拽下"成立、反向不成立。
- **根因 2（00:00）**：`duration` 只在 `@timeupdate` 里更新，且 `preload="metadata"` 下未开播就没有
  timeupdate ⇒ 右侧总时长一直显示 00:00。
- **修法**：① `VideoPlayer` 用元素自身的 `ended` 标志区分两种 pause —— 播完改发新事件 `ended`
  （不再冒泡成"用户暂停"），并补 `@loadedmetadata` 设时长；按钮图标改用本地 `showPlaying`
  （= 共享 playing 且本路未播完），使先播完那路显示 ▶ 而另一路继续；
  ② 联动判定抽成纯函数 `src/utils/previewCoupling.ts`（`reportPause` 手动暂停=两路都停；
  `reportEnded` 单路播完=另一路继续，两路都完才置停；`reportPlay` 重播清标记；`resetSyncState`），
  父组件按该状态机走，两路都接上 `@playing-change` + `@ended`。
- **门禁**：`typecheck` 干净 · vitest **142 全绿**（+5 条状态机测，含"一路播完另一路不停"与
  "两路都完才停"两条判别锁；未装 `@vue/test-utils`，故以纯函数锁行为）。
- **未验证面（如实）**：`pause` 与 `ended` 的先后（规范上 ended 标志先置 true 再排队 pause）
  是本次判定的前提，**没在真浏览器里跑过**；起 dev 前端用真实素材目检，或等 r11 由用户实测。

## 2026-10-06（续61 补四）— r11 出包（三项修复入包）+ 包内进度分级实测

- **内容**：`db0d86d` 三笔 = LOC-1107 片尾钳制（`3a6aa4c`，r10 已含）+ 进度条 92% 切片（`13e18e2`）
  + 预览联动与时长 00:00（`dba7c00`）+ 档案。构建 PS_EXIT=0，产物 18:45
  （`Video Locator.exe` / `backend.exe` 77,442,958 B，逐代递增 r9 77,440,920 → r10 77,441,843 → r11 77,442,958）。
- **包体验收**：`accept_packaged_bundle.py` **FAILED=0**（资产 sha256 · 冒烟 26.5s ≤75s · DML 生效 ·
  精排/ISC GPU 未回退）· 三防冒烟 **FAILED=0** · 启动冒烟 25s 存活 Electron 4 + backend 1 ·
  zip `Video-Locator-win-x64-20261006r11.zip` = 981,635,025 B / 7,078 条目，抽验
  `Video Locator.exe`、`resources\backend\backend.exe`、`resources\app\dist\assets\ResultsPage-xeWnraUr.js`、
  ISC 权重均可开读。
- **包内进度分级的硬证**（不只看单测）：包内 backend headless `syn` 事件流的进度值序列 =
  **92.0 → 94.0 → 95.0 → 97.0 → 100**，正好落在新切的四段（fix 92-94 / split 94-95 /
  patch 95-97 / isc 97-98）边界上；旧代码这一段会整片停在 92.x。
- **渲染层进包证明**：包内 `resources/app/dist/assets/ResultsPage-xeWnraUr.js` 与 vite 产物同名哈希，
  内含压缩后的 `ed:!1,og:!1`（= `initialSyncState` 的 `{ed:false, og:false}`）⇒ 预览联动修复在包里。
- **仍未闭合**：① 预览"一路播完另一路继续"的 **pause/ended 事件顺序前提**没在真浏览器目检过
  （包内只有静态与状态机证据）；② LOC-1107 的包体级判别复现仍缺用户那条 16:34 真项目重跑；
  ③ macOS CI run #25（head `db0d86d`）结果待收。
- **release 现状**：现役 = **r11**；r10 / r9 / r8 全部留在 `mvp/ui/release/`（三个 981MB zip + 一个 982MB，
  磁盘 303GB 富余，未做删除授权）。zip 形态沿用 r9/r10 的"根=win-unpacked 内容"（与档案里 r4/r5 的
  带 `win-unpacked/` 目录层口径不一致，未擅自改）。

## 2026-10-06（续61 补五）— mac 包体内容验收脚本 + publish 门槛（CI）

- **动因**：mac 包过去只验到「构建成功 + 静态库依赖 + ad-hoc 签名可验」，从未做包体实测
  （违反我方纪律"打包验收必须实测包体"）；且 `macos-package` 最后一步是
  **构建成功即 `gh release upload --clobber` 到公开 rolling tag `mac-alpha`**（实测该 release
  现有两资产：今日 `Video-Locator-mac-arm64.zip` 640,187,762 B dl=0 + 旧
  `Video.Locator-0.1.0-arm64-mac.zip` 571,967,939 B **dl=12**）。
- **新脚本** `mvp/scripts/accept_packaged_bundle_mac.py`（Windows 版 `accept_packaged_bundle.py`
  的 mac 同口径版；后者绑死 `win-unpacked`/`backend.exe`/三条 DML 判据，mac 上必然红，不可复用）：
  A 结构（app/backend/ffmpeg/ffprobe/DINOv2 权重随包，记 sha256）·
  B **patch/ISC 精排资产在位**（缺失=FAIL，可用 `SVL_MAC_ALLOW_MISSING_REFINE_ASSETS=1` 显式豁免并留痕）·
  C 起包（release 通道 + 随机端口 + 临时 SVL_DATA_DIR/LOG_DIR，stdout 必须排空否则管道写满阻塞后端）·
  D 门禁负例（无令牌打 `/api/settings/device` 应 401；`/api/health` 属放行路径不能当负例）·
  E 端到端（包内 ffmpeg lavfi 现造 20s 原片 + 6s 剪辑 + **中文名副本**，建索引 → analyze → 轮询到终态）·
  F 设备判据 = 日志出现 `backend selected=mps`（stdout 与 SVL_LOG_DIR 两处都扫，防"读错地方"假红）。
- **CI 接线**：`macos-package` 在 upload-artifact 之后、publish 之前插入
  `Accept packaged mac bundle (gate publish)` ⇒ **FAILED>0 则 publish 不执行**，
  mac-alpha 不再"构建成功即对外发布"。
- **预期第一次会红**（如实预告，不是脚本 bug）：mac 构建目前**只装 DINOv2 .pth**，
  `build_backend_mac.py` 从未复制 patch 双输出 ONNX 与 ISC ONNX ⇒ B 判据必 FAIL。
  这正是当年 Windows 上"精排静默回退 CPU、整条慢 2.6~3.9×"瞒两周的同型缺口，
  在 mac 上至今未收。收口办法 = 把两资产随包（ONNX session 的 provider 列表本就含
  CPU 兜底，mac 上可用 CPU 跑精排，比"静默跳过精排/ISC"更接近 Windows 行为）。
- **未验证面**：本脚本**从未在真 macOS 上执行过**（本机 Windows+AMD），只过了
  `py_compile` + 平台守卫（非 darwin 退出码 2）+ 接口契约核到源码
  （`BACKEND_LISTEN <host> <port>`、task `to_dict` 含 `result`、`/api/index` 返回 `IndexResponse`、
  设备行文本 `backend selected=mps`）。首次真跑即在 CI 里。
- 本地门禁：workflow YAML 可解析（三 job）· 脚本 py_compile 通过。

## 2026-10-06（续61 补六）— mac 包体门槛三轮转正 + LOC-1107 第二处（ISC 片尾越界）收口到解码层

### 门槛三轮 dispatch 的实录（#26 / #27 / #28，全在真 macOS runner 上）

- **#26 红**（step15）：`FileNotFoundError: .../Contents/Resources/backend/backend` —— 门槛脚本自己的 bug：
  给 `Popen` 同时传**相对** argv[0] 与**相对** `cwd`，POSIX 先切 cwd 再解析路径 ⇒ 前面 `is_file()`
  全 True 却死在启动。已 `resolve()` 绝对化，并把 Popen 包成 FAIL 而非裸 traceback。
- **#27 红**（step15）：两条 locate 终态 **LOC-1107**，进度停在 97.0（= ISC 精扫段）。
  这轮不是脚本问题：本地用**同款合成素材**（20s lavfi 原片 + 末 6s 剪辑）在 Windows+DML 复现，
  traceback = `isc_refine.py:314 → 231 → 206 → 154 → grab_frames:255 → grab_frame:177`，
  `grab_frame returned no frame at t=20.500`（原片 20.0s）⇒ **跨平台真缺陷**。
- **#28 绿**：`FAILED=0` 全项 PASS（图+`.data` 双 sha · BACKEND_LISTEN · health 200 ·
  无令牌 401 · 建索引 `device=mps frames=20` · locate 完成结果段=1 · **中文路径**同样完成 ·
  `backend selected=mps`），step16 publish 才放行 ⇒ `mac-alpha` 上的包从"构建成功即发布"
  变成"过包体功能验收才发布"。mac zip 现 913,591,283 B（含 patch/ISC 权重）。

### 我上一轮的判断错在哪（更正留痕）

补第一处（patch_refine）时我在 commit/档案里写过"其他网格调用方按构造在界内"——**错**：
`isc_refine` 的 `rhi = t0 + WIDE_REFINE_S(2s)` 与粗扫窗同样无片尾边界，近场池(±radius)、
字牌锚定同理。教训 = 修掉一处同类缺陷后不得宣称"其余界内"，必须枚举同型调用点。

### 修法（第一版：解码层预钳制 —— 已被下面的严格惰性版替换）

- `FFmpegIO._decodable_cap(info)` = 容器时长 − 1 帧（元数据不可信 ⇒ None ⇒ 不兜底）；
- `grab_frame`：`t > cap` 钳到 cap（不再抛）；
- `grab_frames`：目标先钳制再聚类，返回时**按原始请求值补别名键**；
- 测试 +2（真实 `a1.mp4`）：越界 `grab_frame` 不抛；批量口保留原始键且片内逐位不变。

### ⚠️ 更正留痕（同轮内两次自我修正）

**① 我把 r11 的读数读错过一次**：`work/r11_arm/run_arm.py` 双臂跑完只打
`[done] ... segments=0`，而 `segments` 取的是 `result.results` 长度 —— 任务 **failed** 时它同样是 0。
我据此写成"r11 = completed 但 0 段 ⇒ 说明预钳制改了本来能成功的请求"，**错**。实测
`work/pkg_attr/headless_short20.summary.json`：r11 = `task_status=failed`、
`task_error=…LOC-1107`。⇒ r11/r12 的 0↔1 差异就是**兜底救活了过去会抛的请求**，与我最初的
"构造性零语义"推理**不冲突**；预钳制版本的实际风险是另一件事（下条）。
脚本已改：`[done]` 同时打 `status`/`err`，`package` 字段不再硬编码 "r4" 而是按实测
backend.exe 的 `sha256[:16] + size + mtime` 生成（双臂归因必须有包身份抓手）。

**② 预钳制仍有实质风险，故改成严格惰性**：`cap = 时长 − 1/fps` 只是末帧 pts 的**下界估计**，
真实末帧常更靠后 ⇒ `t ∈ (cap, 时长]` 本来**能取到正确帧**的请求会被先钳到 cap 处的另一帧
（换帧→换分→可能换段）。本机 20s 素材上没观测到这种替换，但它不可证伪 ⇒ 不该留在生产里。

### 修法（现役 = 严格惰性）

- 删掉 `grab_frame`/`grab_frames` 里一切**预先**钳制：目标一律按原始 t 解码，簇划分与帧选择逐位不变；
- 只在 `grab_frame` 的「stdout 不足一帧」分支（过去 = 直接抛 `MediaError`）里兜底：
  若 `t > cap` ⇒ 调 `_grab_last_frame()` 解片尾 ~2 帧区间取**最后一帧**（管道流式读，内存有界；
  不做第四种选帧语义），仍取不到才抛；
- `cap` 的角色从"钳制值"降级为"判据"：只有**片尾形状**的失败才被救，中段子流损坏照样抛（不误吞）；
- `_grab_last_frame` 按 (路径, size, mtime_ns, scale) 记忆（上限 8 条）：短原片一次 locate
  **实测命中 11 次**，不记忆就是 11 次片尾重解；
- 测试：`test_grab_frame_beyond_end_rescues_not_raises`（兜底帧 = `_grab_last_frame` 且非黑帧）、
  `test_grab_frame_in_bounds_untouched_by_rescue`（界内点与批量口逐字节同）、
  `test_grab_frames_beyond_end_keeps_original_keys`（批量键仍为原始请求值）。

### 资产侧收口（同轮）

`model-assets` 内部 tag 挂三份（88,342,528 / 1,613,211 / 209,190,912 B），CI 第 11 步下载 +
`verify_model_asset_shas.py` 校验；`releases/download` 本机不通 ⇒ 改走 API assets 端点。
mac 侧"精排静默回退 CPU torch / ISC 第二意见缺席"的缺口正式关闭（此前该缺口会让 mac 包
与 Windows 包不同档，且完全静默）。

### 门禁与遗留

- 后端 **545 OK (skipped=2)** · API **105 OK** · FFmpegIO 单测 20 OK；提交 `7589659`（修复）
  + `1c07cea`（脚本路径修复）+ `137c724`/`edfa5ac`（资产管线）已推送。
  ⚠️ 本节所述"预钳制"实现**已被补七的严格惰性版替换**（测试也随之改名/加条，现役 21 OK）。
- **r11 不含第二处修复** ⇒ 短原片在 Windows 包上照样会崩 ⇒ 由 r12 收口（见下一节）。
- 仍开放：预览"一路播完另一路继续"的真浏览器目检；LOC-1107 用户 16:34 真项目的包体判别重跑；
  竞品 opcode 通道可行性。

## 2026-10-06（续61 补七）— EOF 兜底改严格惰性 + test1 实测判决 + r13 出包验收

### 代码最终态（替代补六的"预钳制"版）

- `grab_frame`：**单次 spawn 按原始 t**；仅当 `stdout` 不足一帧**且** `t > cap` 时调
  `_grab_last_frame()`（`-ss 时长−tail` 起流式解到 EOF，只留最后一帧，管道逐帧读；
  按 (路径, size, mtime_ns, scale) 记忆，上限 8 条）。仍取不到才抛，异常文本不变。
- `grab_frames`：**取消**预钳制与"原始请求值别名键"，簇目标一律原始 t。
- `cap` 的角色 = 判据（区分"片尾越界"与"中段流损坏"，后者照旧抛），不再是钳制值。
- 短原片实测兜底一次 locate **命中 11 次** ⇒ 记忆化把 11 次片尾重解压成 1 次。

### 实测判决（两条，都是本轮新证据）

- **真实片 test1 零语义**（`work/eof_inert_check/run_instr.py test1`，同旋钮
  patch_refine_grid/rerank_grid_grab=True + cluster_workers=4，对照修复前基线
  `work/defaults_flip_ab/test1/on.results.json`）：
  **segments 55/55 · strip 后 identical=True · n_diff=0 · 兜底命中 0 次**。
  wall=1238.2s 含并行 typecheck 争用 ⇒ **不作性能口径**（见 [[assert-backend-in-measurements]] ⑧）。
  ⇒ 补六 免跑四片的推理这轮**有实测背书**（test1 直接同帧同结果），其余三片仍是构造性论证。
- **包体级判别闭合**（同一 `short20` 素材 = 20s 原片 + 其 6–12s 剪辑，三个代际各实测一次）：
  r11 包 = `task_status=failed` + LOC-1107；r12 包（预钳制）= completed 1 段；
  **r13 包（严格惰性）= completed 1 段**（wall 18.1s，进度 92→94→95→100）。
  源码树同素材 = `src 5.5–7.5`、HIGH 0.9957、frame_precision=true（构造真值 6–12s）。
  ⇒ LOC-1107 的包体级"修复前必崩/修复后不崩"这一课，从补一至今挂着的状态**已闭合**。

### 判卷抓手修复（我自己踩的坑，见补六更正）

`mvp/scripts/attr_packaged_headless.py`：`[done]` 现在同时打 `status`/`err`；
`package` 字段不再硬编码 "r4"，改为按实测 `backend.exe` 的 `sha256[:16] + size + mtime` 生成
（r13 = `sha16=52ca8c225bbc3683 77445580B mtime=2026-10-06 23:02`）。

### 门禁与 r13 出包

- 后端 **546 OK (skipped=2)** · API **105 OK** · FFmpegIO 单测 **21 OK** · vitest **142** ·
  `vue-tsc` 与 electron `tsc` 均干净。
- r13 = `mvp/ui/release/Video-Locator-win-x64-20261006r13.zip`（981,636,653 B / 7,078 条目 /
  `testzip()` 无坏件，backend.exe·主 exe·ISC 图三条目抽读可开）。
  accept **FAILED=0**（冒烟 27.0s · DirectML 生效 · 精排与 ISC 未回退 CPU · 定位段数 1）·
  三防 **FAILED=0** · 启动冒烟 25s 存活 Electron 4 + backend 1（用完即清，AFTER_KILL=0）。
- backend.exe 尺寸逐代：r10 77,441,843 → r11 77,442,958 → r12 77,443,992 → **r13 77,445,580**。
- **分发包保留**（用户口令"只留 r10、r11、最新包"）：r8/r9 已删，r13 过验收后 r12 已删。

### 仍开放

- 预览"一路播完另一路继续"的真浏览器目检（`pause`/`ended` 先后仍是前提）。
- mac 现役资产 = **预钳制版**（CI #28 绿、`mac-alpha` 已发布）；是否为严格惰性再 dispatch 一次
  （≈180 macOS 分钟）待拍板。
- LOC-1107 是否拆码 · 下一刀 A1→A2 ∥ A3 · 性能口径三处对齐（PRODUCT_INTRO 19~31 vs 现役）·
  竞品 opcode 通道可行性。

### Notes

- Created `checkpoint-2026-10-06-2315.md` checkpoint (0 modified/untracked file(s)).
