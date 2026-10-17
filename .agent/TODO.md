# TODO

> **结构说明（2026-10-07 瘦身）**：本文件 = P0/P1/P2/Blocked 四容器 + 指针，目标 ≤100 行。
> 历史条目（原 43 个 ▶ 块 + 「历史记录」全节）已**逐字**迁往
> `.agent/archive/TODO_history_20261007.md`，一条未删。防复发纪律见 AGENTS.md「上下文更新约定」：
> P0 保持 ≤1 块，新增块时旧块即迁 archive。**续迁**：P1 里已结清/已被取代的历史条目（r15~r17 出包身份、
> 第十轮 mac 出包链、竞品 opcode 结案等 49 行）于 2026-10-13 逐字迁 `archive/TODO_history_20261013.md`。

## P0 — Current

> **▶ 2026-10-17（续63 补十九）— 竞品三刀（只写文档）+ r25 出包【现读这条】**
> 竞品侧四条承重前提被实测打掉 ⇒ 没按原选项执行，改为静态语义重组（未执行竞品任何代码）：
> 「只拉模块」不成立（0 个 app `.py`/`.pyd`）；常量块 **code object 记录 = 0**（函数签名静态永不可得）；
> IPC 是**本地 Flask HTTP/WS**不是命名管道 JSON-RPC；其代码有 **CUDA/MPS/CPU 三档**（"只支持 NVIDIA"
> 仅指其 Windows 包依赖）。产出 `FINDINGS/13`（137 模块 / 3,202 条他们自写中文 docstring）、
> `FINDINGS/14`（22 个 `/api/*` + **16 键阶段词表** + batch 12 键 + 授权 18 码）、
> `FINDINGS/15`（话术 341 + model lease 357）。对我方最有用三条：**其原片侧 1fps 索引且不切镜头**
> （独立印证 cap 1.5 是同侧口径）／**时长守恒靠变速补齐 90–110% 而非 0.1s 下限撑宽**／
> **渲染失败仍交付 XML**（挂着的未决口径当场闭合）。
> **动态腿判死（确证）**：「每次启动都向授权服务器校验」+ `content_key` 服务器下发 + 租约只在内存传递
> ⇒ 本机直启且断网下推理/解密链不可达。静态三条永久边界写死（函数体控制流 / HTTP 方法与请求体 / 权重明文）。
> **采集器修 7 处**（含我自己上轮引入的回归：白名单收窄把 `draft_content.json`/CSV/XML 一起跳过；
> CSV-TSV 无行判据；XML 属性名抢匹配吞内层键值；UTF-16 静默零命中；排除件在报表里凭空消失）
> + 新自检 `scripts/selftest_parse_runtime_log.py` **17/17 PASS**。
> 本机 `runtime_evidence/` 从未投放 ⇒ `runtime_params_observed.json` = **{}（无竞品观测，自检只证链路可用）**。
> **r25 已出**（构建点 = 干净 commit `c3a17e5`；推之前远端有用户自己的一笔网页改动 10-16 11:41 删 README 一行
> ⇒ 不覆盖，本地 4 笔 **rebase** 到它之上再推）：四道包内验收对 `win-unpacked` 取、逐条 rc=0
> （bundle **33 PASS/0** 且上批 4 条导出通道锁仍真绿 · render **0** · 不变式 **0**（扩宽 0/0/0/1）·
> 冒烟 `AFTER_KILL=0`）。zip `Video-Locator-win-x64-20261017r25.zip` = **981,693,605B**（对 r24 **+1,417B**）
> / 条目 **7,079**（文件 6,993 + 空目录 86，r24 是 85 ⇒ 差的那个 = 本代 `resources/` 无直属文件）/
> `testzip=None` / backend.exe 77,498,025B sha16 `ae04274989342708` 与 bridge.js **zip 内 == 磁盘** /
> **与 r24 文件名集合差集 = 0/0**。`mvp/ui` 零改动 ⇒ **mac 不需另走 dispatch**。
> ⚠️ **两处我自己的错**：① 打包脚本目录条目规则先写错（每目录都写 ⇒ 1,374 条，跨代不可比）；
> ② 清死代码时删掉 `pre = ` 留 `if pre:` ⇒ 脚本在写包前 NameError，**而我已把「7,079 / 981,703,678B」
> 一组没有读数支撑的数报了出去** ⇒ 当场更正、核磁盘 `ABSENT` 才重跑。⇒ 判据补三道硬断言
> （条目数==磁盘文件数 / 顶层关键件在位 / 与上一代文件名差集），不过就 `exit 1` 不写包。
> **未结**：cap 1.5 的**观感读图仍未做**（四档指标不变只证数据面）· ✅ **删 r22 已执行**（留 r25/r24/r23，
> 删前双验）· `source_merge::_transcode_args` 同族未改 · 动态要补只剩 HTTP 方法/请求体（需已激活真机）。
> 明细 = STATE Current Task 顶部「补十九」块；竞品正文一律在 `D:\claudework\cutmatch-analysis`。

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
- [x] ~~待口令：release/ 四档删 r20~~ = ✅ **已删（2026-10-13 00:2x）**：删前 `zip_identity.py` 验回滚档
      r21 `testzip=None` / 7,078 条目 / backend.exe 77,493,043B / sha16 `fa3c394567cc17d2` 与档案逐字一致；
      r20 自身本批早先亦验过（`63987715436d5e31` 一致）。⇒ 现三档 r23/r22/r21。
- [x] ~~mac 包仍带同一缺陷，待用户定是否跟更~~ = ✅ **已 dispatch（2026-10-13 00:3x）**：run
      `38277827813`（ref=master，head `4fe0d96a5`，HTTP 204）。机制已读 workflow 本体验明：门槛绿 ⇒
      `gh release upload mac-alpha --clobber` **自动就地覆盖**，无需人工；门槛红 ⇒ publish 不跑、留旧包。
      用户明确「mac zip 不用你确认」⇒ **不再自行追读该 run**（watcher 日志留 `work/watch_mac_run.log`）。
- [x] ~~导出异步化（B 方案）~~ = ✅ **已落地（2026-10-13 续63 补十七）**：
      `POST /api/tasks/export` 进现有 tasks 框架（进度 0→99 + 可取消），UI 已切任务通道；
      同步 `/api/export` 保留未删。⚠️ 未提交、未出包 ⇒ 用户手上还没有；进包 = r24（mac 另 dispatch）。

- [x] ~~导出对话框 UI 修复（2026-10-10 第十三轮）~~ = ✅ **已提交并两代进包**（2026-10-12 复核）：
      `ResultsPage.vue` 告警列表加滚动 + 输出目录「浏览…」= 代码笔 `aacfaa9`（2026-10-10 23:50，实测在 master），
      `git merge-base --is-ancestor aacfaa9 09714ab` 通过 ⇒ 已在 **r21**，r22 同链继承。本条无遗留。
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
