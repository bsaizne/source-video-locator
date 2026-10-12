# TODO 归档（2026-10-13）

> 从 `.agent/TODO.md` 的 P1 容器**逐字**迁出：续63 补十~补十一 期间的已结清/已被取代条目
> （r15/r16/r17 出包身份与删除登记、第十轮 mac 出包链、竞品 opcode 结案、UI 目检裁决等）。
> 迁移动机 = TODO 目标 <=100 行；开放项一律留在 P1/P2/Blocked，本文件仅作留档。

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
