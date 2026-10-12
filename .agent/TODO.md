# TODO

> **结构说明（2026-10-07 瘦身）**：本文件 = P0/P1/P2/Blocked 四容器 + 指针，目标 ≤100 行。
> 历史条目（原 43 个 ▶ 块 + 「历史记录」全节）已**逐字**迁往
> `.agent/archive/TODO_history_20261007.md`，一条未删。防复发纪律见 AGENTS.md「上下文更新约定」：
> P0 保持 ≤1 块，新增块时旧块即迁 archive。

## P0 — Current

> **▶ 2026-10-12（续63 补十六）— 真机红条定性反转：客户端 300s 头超时，不是后端掐连接【现读这条】**
> 「本轮扩面」的前提被打掉：全局 `exception_handler(Exception)` 一直有效（四臂真 uvicorn 实测 6/6 回
> 结构化 500），红条真因 = Electron 侧 Node fetch（undici）默认 headersTimeout=300s × 分钟级**同步**导出
> （真机 374s/783s 崩、571s/475s 成功却被报成失败）。修=桥接层默认 transport 改 **node:http**
> （30min 显式兜底）+ **非 2xx 透传错误体**（包内才看得到中文话术+LOC 码）。
> 门禁：UI **150 全绿** + 双 typecheck 干净 + 端到端 `PROBE PASS`；包侧新 2 锁打在 r22 上**预期红 FAILED=2**。
> 另：r19 已按口令删除（验完再删，r20 回滚档先验逐字一致）。**已提交并出 r23**
> （代码笔 `8fbd02c` + 档案笔 `a84119d`，r23 = 干净 commit `a84119d` 构建，包内四道全绿，
> zip 内 bridge.js == 磁盘逐字节相同）⇒ release/ 现**四档 r23/r22/r21/r20**，删 r20 等口令。
> 明细 = STATE Current Task 顶部「补十六」块（含「backend.exe 逐字相同」这条预期被实测推翻的订正）。

## P1 — Next

- [x] ~~r23 出包（等口令）~~ = ✅ **已出并四道全绿（2026-10-13 00:1x）**：
      `Video-Locator-win-x64-20261012r23.zip` 981,687,209B / 7,078 条目 / testzip=None /
      zip 内 backend.exe 77,493,384B sha16 `537bcca18760de77` == 磁盘（matches_disk_build=True）；
      **zip 内 `bridge.js` 与磁盘逐字节相同**（8,882B，含 node:http + httpRequester + data 透传）。
      bundle **28 PASS/0 FAIL**（两条新桥接锁由 r22 上的预期红转绿）· render **8 PASS/FAILED=0**
      （R1 wall=60s · 64 段无交叠 · h264_amf · 隔离在位）· 不变式 **FAILED=0** · 冒烟 AFTER_KILL=0。
      ⚠️ 订正：本条原写「预期 backend.exe sha16 与 r22 **逐字相同**」**被实测推翻** —— 实为同尺寸、
      仅 9 字节差（3 段各 3 字节，两处同值=归档长度字段）⇒ PyInstaller 非确定性构建；
      `git diff 36dec63..a84119d -- mvp/src mvp/api` 为空佐证没动 Python 运行面。
- [ ] **待口令：release/ 四档删 r20**（按「最新+上一档」；删前照例 `zip_identity.py` 双验 r21 可读
      且 sha16 与档案逐字一致，预计释放 ≈940MB）。
- [ ] **mac 包仍带同一缺陷**：`bridge.ts` 这份改动要经 mac CI dispatch 才进 mac 包
      （mac 出包属 2026-10-06 裁决的搁置项，是否随本批更新由用户定）。
- [ ] **导出异步化（B 方案，已向用户报过、未拍板）**：`/api/tasks/export` 进现有 tasks 框架
      （带进度 + 可取消），根治「UI 干等 6~13 分钟」。当前 A 方案只把误报修掉，不改善等待体验。

- [x] ~~导出对话框 UI 修复（2026-10-10 第十三轮）~~ = ✅ **已提交并两代进包**（2026-10-12 复核）：
      `ResultsPage.vue` 告警列表加滚动 + 输出目录「浏览…」= 代码笔 `aacfaa9`（2026-10-10 23:50，实测在 master），
      `git merge-base --is-ancestor aacfaa9 09714ab` 通过 ⇒ 已在 **r21**，r22 同链继承。本条无遗留。
- [x] **mac 出包链 = ✅ 真机结清（2026-10-10 续63 补十一 第十一轮，读 live CI）**：run
      `37955484860`（head `31974f2`）三 job 全绿；`macos-package` step 11 走通道 A 直链+sha256
      三份 try=1 即中 ⇒ step 15 门槛绿 ⇒ step 16 publish 绿 ⇒ release `mac-alpha` 新增
      `Video-Locator-mac-arm64.zip` 916,769,503B（2026-10-09T16:27:38Z）。第五/六轮担心的
      「等值校验首次生效就在 CI 上」已验通。H3 正式化项（按平台裁 `extraResources` 的 ≈88MB 死资产）另计。
- [x] ~~待口令：Windows release/ 三档删 r17~~ = ✅ 已删（2026-10-10）：现两档 r19 现役 + r18 回滚；
      删前 `zip_identity.py` 验回滚档 r18 `testzip=None` / 7,078 条目 / backend.exe sha16
      `2eb651d38003d433` 与档案一致，释放 ≈940MB。与 mac 线无关。
- [x] 待用户口令：git 推送 = ✅（2026-10-07 续63 口令「按你的想法来」→ 推 `6a0ef88..aba3a21`
      实测 11 笔；档案原写 12 笔为计数过期）。
- [x] **r15 出包 = ✅（2026-10-07 12:33）**：`Video-Locator-win-x64-20261007r15.zip`
      981,659,630B / 7,078 条目 / `testzip=None` / backend.exe `sha16=d45656f585826f4a`。
      accept **FAILED=0**（新增 4 条隔离硬断言全过）· 三防 **FAILED=0** ·
      启动冒烟 Electron 4+backend 1 / AFTER_KILL=0 · 包体剪映探针
      `work/r15_jianying_pkg/probe.py` **FAILED=0**（EDL 134.12s、卷轴 64 条/56 文件/
      815.75s/531.0s 与计划层逐字对齐、包内墙钟 80.7s）。
      ⚠️ 该探针同时抓回我本批引入的回归：取材扩宽参数误透给时间线三通道（EDL 覆盖被撑到 531s）
      ⇒ 已改硬约束 + 单测锁。
- [x] ~~待裁：卷轴紧邻同素材连放~~ = ✅ 已按收窄方案实现（续63 补二，默认开 + config 旋钮 +
      3 条单测 + 守卫脚本逐条比对）。
- [x] **r16 出包 = ✅（2026-10-08 续63 补七，口令「推ci然后打包吧」）**：
      `Video-Locator-win-x64-20261008r16.zip` 981,659,900B / 7,078 条目 / `testzip=None` /
      **zip 内** backend.exe `sha16=7c9533750776a79a`。bundle · render（**R2 转绿**）· 三防 ·
      导出计划守卫 · 启动冒烟 · 包体产物探针（靶子由源码树现算）= **全部 FAILED=0**。
- [x] ~~两处新 UI 目检~~ = ✅（续63 补三，顺带修掉失效 token `--c-warn`→`--warn`）
      → **续63 补四：用户裁决删掉这两处显示**（侧栏内存行 + 黄字心跳提示），
      后端字段与 types 契约镜像保留。**别再把它当 UI 欠账重新提。**
- [x] ~~分发包保留~~ = ✅ 口令「只留r15和16」（2026-10-08）：删 r13 + r14（~1.96GB），
      留 r16 现役 + r15 回滚；删前两份均 `testzip=None` / 7,078 条目 / backend.exe 身份逐代核对。
- [ ] **续63 补十（2026-10-08）= r17 已出包并全链验收绿**：`Video-Locator-win-x64-20261008r17.zip`
      981,665,352B / 7,078 条目 / `testzip=None` / **zip 内** backend.exe 77,472,765B
      `sha16=7e3fe311bdf62b36`（== 磁盘构建；r16 = 77,469,132 / `7c9533750776a79a`）。
      bundle（含两条新包侧锁）· render · 三防 · 导出计划守卫 · 启动冒烟 AFTER_KILL=0 ·
      包体产物探针 = 全部 FAILED=0。出包时未提交，**随后同一内容已提交 `ba5bedd`**
      （构建后没再动 `mvp/src`）=> 包与该 commit 的产品源码逐字对应。
      r15 是否按「最新+上一档」保留规矩删除，等口令。
- [x] ~~待口令：本批（续63 补六~补九）git 提交~~ = ✅ 已提交 `ba5bedd`（代码/测试/脚本 8 文件）
      + 档案笔，推 origin/master。
      archive 两份 + 两个常设脚本（清单见 STATE `Next Actions` 第 1 条）。
- [ ] **r17 出包时（等授权）待办两件**：① accept 加包侧硬断言「真实 analyze 后支持档必须出现
      12 行 `locate leg=`」= 埋点进包的锁；② 出包后让用户自然跑一段（历史那 485 条就是这么攒的），
      再按 `review_packaged_support_log.py` C2/D 面读新档（自然攒一份真档）。
      注：降噪本身**已用真进程注入三臂闭合**（`work/r17_noise/probe_inject.py` J0-J6 全 PASS），
      这两条只是把它升级成「每次出包自动核」+ 补上「OS 真触发」那一项残留观察。
- [x] 竞品 opcode 通道可行性 = ✅ 已试采结案（2026-10-07 续62 补三）：字面通道判死（0 pyc，
      Nuitka AOT）；机器码绑定通道判死（LEA→blob / MOV→平铺数组两形态不成立，全量反汇编
      路径未立项）；**blob 序通道打开**（blob 序=源码书写序，进度 pct 互证；tracker 阶段词表
      「特征→候选→召回→定位」与 V2 流程注册序已产出）。
      明细 `competitor_cutmatch/FINDINGS_OPCODE_CHANNEL_20261007.md`。
- [ ] **六项立项已拍板（2026-10-07），先入文档后动码**——计划 =
      `mvp/docs/PLAN_HARDENING_SIX_ITEMS_20261007.md`，执行顺序建议：②设备回报 → ①低内存
      收缩 → ③防抖+心跳（小三件一批）→ ④独立进程监督（单独批）→ ⑤导出实得口径（与性能
      口径对齐联动）→ ⑥换形态探针族（研究线，沙盒纪律）。逐项完成打勾：
      - [x] ② 子进程设备回报标记 = ✅（2026-10-07：backend stdout 一次性 `BACKEND_DEVICE <name> <type>` 标记行（懒构建点=真实解析点）；UI 首启 READY 前拉 actual 三元组、buildIndex 不再用索引历史标签覆盖徽标）
      - [x] ① 低内存收缩 batch+预取 = ✅（2026-10-07：`media/resource_budget.py` 纯函数三档（unknown→全默认零语义；tight/critical 收缩），接 `_grab_frames_parallel` 线程与 `build_tp_index` 簇上限（切簇只改批次不改帧），`/api/settings/device` 补 low_memory_mode/memory_tier/grab_workers/max_cluster_frames）
      - [x] ③ 阶段进度防抖+心跳 = ✅（2026-10-07：`api/tasks/debounce.py` ProgressDebouncer（同阶段最小间隔合并、阶段切换/终态直通、held 先补发）接 analyze/render worker；Task 补 `last_event_at` 心跳并暴露 to_dict/UI 契约；进度条 0.2s 过渡既有）
      - [x] ④ 独立 GPU 工作进程监督 = ✅ 第一步任务级隔离（2026-10-07：`api/tasks/isolated.py`，analyze/render 子进程化，硬崩无信封退出 → failed(带 exitcode)，服务与其它任务存活；取消 = terminate；spawn 不可用回落线程内；`run_backend` 补 freeze_support；故障注入钩子 + 6 单测含真实 spawn。打包态 spawn 验证挂 r15 accept。监督重启（崩溃计数+冷却）暂不需要——任务全为用户显式发起，无自动重试消费方）
      - [ ] ~~⑤ 指标 HIT ≠ 导出实得~~ → **2026-10-07 用户裁决不做，丢回搁置区**（重启需用户再提；与「性能口径三处对齐」同批处理最合适）
      - [x] ⑥ 换形态探针族：**b 已实跑并判负关闭**（2026-10-08 续63 补六，`FINDINGS_TWO_STAGE_SAMPLING_20261008.md`）；a 置信非饱和 / c E3 换载体 / d 退化门换判据 **未跑**（本轮按口令只跑 b；是「未跑」不是「已证否」）。
            续63 复核建议（**待拍板，不自动开跑**）：先只跑 **b**，且判据换掉——档案已有
            「2fps vs 1fps 密度探针：生产严格净 0、建索引 ×2 耗时」，密度↑不改落点 ⇒ b 的
            精度上限有限，可兑现收益在**建索引耗时/首屏延迟**（现役 22~31min/片）。
            a 撞护栏（Confidence 公式冻结+不标定），d 的退化门默认关无生产影响 ⇒ 优先级最低。

## P2 — Later

- [x] TODO 瘦身 = ✅（2026-10-07：历史迁 `.agent/archive/TODO_history_20261007.md`，
      防复发纪律写入 AGENTS.md）。

## Blocked

- [ ] H4（Windows NVIDIA / CUDA）= `H4_GPU_RUNNER_UNAVAILABLE` —— 无可用 Windows GPU runner，
      需用户提供 NVIDIA 环境与计费权限（见 `.agent/STATE.md` H4-0 记录）。
