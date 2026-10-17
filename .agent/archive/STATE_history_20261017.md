# STATE 迁移存档（2026-10-17 续63 补十八立档同批）

> `Current Task` 退休块**逐字**迁移。本批迁出：续63 补十五（真机 SegmentOverlap 崩修复
> + 导出第二层错误边界 + derived_stale 真机实证）。现役块见 `.agent/STATE.md`。

> **▶ 2026-10-12（续63 补十五）— 真机 SegmentOverlap 崩修复 + 导出第二层错误边界 + derived_stale 真机实证【现读这条】**
> 用户递来截图（导出框红条「无法连接后端服务 (fetch failed)」）+ `video_locator_logs(2).zip`。
> **① 版本定性**：日志 19:54 `rebuild index: derived table version changed (…scn1 → …scn2)` +
> 19:56 `index derived refreshed`（**109s**）⇒ 他跑的正是 r21/scn2 代，且
> **derived_stale 老用户首触重刷路径首获真机实证**（补十三 ⑥(e) / 补十四登记的「未实测」项闭合；
> 随后 locate 3.8h 完成 657 段，重刷未引入异常）。
> **② 新崩法 ≠ 第十二轮**：`pyJianYingDraft.SegmentOverlap: New segment overlaps with existing
> segment [start: 728326000, end: 730242000]`（`exporters.py write_jianying_draft → track.add_segment`；
> 库判据 `overlaps = not(end<=start or other.end<=start)` = 严格相交、贴边合法）。
> **根因链（算术逐格对上）**：贴接裁开 64 对 → 产出 **<0.1s 窄素材**（上一条槽宽恰 0.084s）→
> 碎片门槛 `min_clip_s=0.15` **只告警不裁** → 卷轴按真实宽度排槽 → `write_jianying_draft` 的
> `rec_w=max(0.1,…)` 把 target 撑出槽位 0.016s → 与下一条严格相交 ⇒ 整导出打死 →
> 意外异常逃 ASGI 掐连接 ⇒ UI 又弹误导文案。**与第十二轮同族（0.1 下限），这次越的是目标轴**
> （十二轮越的是素材时长轴）。
> **③ 修复两处**：A=`plan_jianying_assets` 卷轴**槽位与累加**都吃 `max(0.1, w)`，与 write 同口径
> ⇒ 结构性无重叠（窄素材占 0.1s 槽、speed 走十二轮回压腿，不越素材时长）；
> B=`routes/results.py` 第二层错误边界（第十二轮「等裁决」项被真机裁决）：意外异常 →
> 结构化 400（message 带真实异常名 + 「请把日志发给支持人员」，traceback 落支持档）。
> **④ 门禁**：后端 **Ran 670 OK (skipped=2)**（+2：窄素材槽位锁 + 结构锁「累加必须用下限后宽度」）·
> API **Ran 130 OK**（+2：意外异常→400 / ApplicationError 分支不被吞）·
> `check_export_plan_invariants.py` **FAILED=0** · 日志提取采坑：`accept_bundle_r21.log` 混编码，
> 提取脚本一律 `stdout.reconfigure(utf-8)`（教训 ⑮ 同族再犯，已在补十四 CHANGELOG 登记）。
> **⑤ 覆盖边界（如实）**：没在他那台机器复现真导出（判据=日志数字与算术相容 + 单测复现该形态）；
> 第二层边界**只加了 /api/export 一条路由**，其它路由意外异常仍会穿 ASGI（未扩面）；
> 窄素材被撑到 0.1s 槽 = 0.83× 慢放观感，属最保守默认（不丢画面），未做「<0.1s 直接丢」变体。
> ✅ **定性订正（续63 补十六 实测）**：本块 ②「意外异常逃 ASGI ⇒ 掐连接」与 ⑤「其它路由仍会穿 ASGI」
> **均不成立** —— `app.py:86` 的全局 `exception_handler(Exception)` 一直在跑并发结构化 500
> （四臂真 uvicorn 实测 6/6 收到 500）；红条真因 = Electron 侧 Node fetch 的 undici 默认
> **headersTimeout=300s** 先放弃，而那发导出实际跑了 374s/783s。判据与修法见顶部「补十六」块与
> `Known Issues` 教训 ⑳。
> **⑥ r22 已出（2026-10-12 口令「立档 → 提交 → 出 r22」）**：代码笔 `a506df4` + 档案笔 `36dec63`
> 已推 ⇒ **r22 = 干净 commit `36dec63` 构建**；包内三道验收全绿（bundle FAILED=0 · render FAILED=0 ·
> 不变式 FAILED=0）；zip `Video-Locator-win-x64-20261012r22.zip` 981,686,020B / 7,078 条目 /
> testzip=None / **zip 内 backend.exe 77,493,384B sha16 `f0d00f10c4123813` == 磁盘**（对 r21 +341B，
> 与本批两处小改动相容）。release/ 现四档 r22/r21/r20/r19，按「最新+上一档」应删 r19，等口令。
> **口径更正（用户澄清）**：「推 release」= **更新 mac-alpha 上的 mac 包**（走 mac CI dispatch），
> **Windows zip 不挂 GitHub**（继续本地分发）。我先前把「挂r22即可」理解成上传 Windows zip，
> 并因 helper 挂死停在待传——该动作作废，Windows zip 不传。
> **⑦ mac 更新已结清（2026-10-12 22:5x 实测公开 API）**：用户 dispatch 的 run `38262048171`
> （head `686b178`，含 SegmentOverlap 修复）三 job 全绿 = mps-poc 5.8min / mvp-tests-macos 14.9min /
> macos-package 11.4min，全程 27min（远快于档案写的 ≈180 macOS 分钟——该口径过期，留待下次核）；
> `mac-alpha` 的 `Video-Locator-mac-arm64.zip` 已覆盖 = **916,823,896B / updated_at 2026-10-12T14:45:51Z**
> （对旧版 916,769,503B +54KB，与本批代码改动量相容）。
> 产物：`mvp/src/app/exporters.py` · `mvp/api/routes/results.py` · `mvp/tests/test_exporters.py` ·
> `mvp/api/tests/test_api.py`；真机日志与解包在 `work/support_20261011b/`（不入库）。

---

> **同批（续63 补十九立档）再迁出**：续63 补十六（真机红条定性反转 = 客户端 300s 头超时，非后端掐连接）。

> **▶ 2026-10-12（续63 补十六）— 真机红条定性反转：不是「后端掐连接」，是客户端 300s 头超时【现读这条】**
> 口令两件：① release/ 删 r19（验完再删）② 「补十五 ⑤ 的未扩面项」本轮扩面。**② 的前提被实测打掉**，
> 扩面改打到真因上。
> **① 定性反转（连错两次的档案断言已订正）**：补十五/第十二轮都写「意外异常逃 ASGI ⇒ uvicorn 不发响应
> ⇒ UI fetch failed」。三条反证：(a) `mvp/api/app.py:86` **早装了**全局 `exception_handler(Exception)`，
> 真机日志那行 `unhandled error on POST /api/export` 就是它的落盘行；(b) 四臂真 uvicorn 实测
> （A 裸 / B +2×BaseHTTPMiddleware / C +CORS / **D 复刻生产栈**，同 starlette 1.6.0 + uvicorn 0.52.4）
> = **6/6 客户端收到结构化 500 JSON、服务存活、零连接失败**；(c) Starlette `ServerErrorMiddleware`
> 源码在 re-raise 前先 `await response(...)`。**真因 = 客户端不等**：Electron 主进程用 Node 全局 fetch
> （undici）默认 headersTimeout=300s，探针实测 `{message:"fetch failed", causeName:"HeadersTimeoutError",
> reject_after_ms:300504}`；而真机那两发崩的导出请求实际跑了 **374s / 783s**（从 locator_service 的
> `material expand` 行到崩溃行卡 Δ），同档另有 **571s / 475s 的成功导出** ⇒ 草稿已写完、UI 报「连不上后端」。
> **② 修（全在 Electron 主进程，`mvp/src`/`mvp/api` 零改动）**：A=桥接层默认 transport
> `globalThis.fetch` → **`httpRequester`（node:http，无隐式头超时）**，显式兜底
> `BRIDGE_REQUEST_TIMEOUT_MS=30min`（取值=实测最坏 783s 留 ~2× 余量；挂死仍会断，不静默永久转圈）；
> B=**非 2xx 把错误体当 `data` 带回**——旧写法只给 error/detail ⇒ 渲染层读不到 `body.message/code`，
> 包内把后端写好的中文话术+LOC 码降级成英文技术串（dev 态走 fetchTransport 有 data ⇒ **只有包内暴露**）。
> **③ 门禁**：UI **150 项全绿**（146→150，bridge.test.ts +6：node:http 真 socket 往返/查询串转发/
> 默认 transport 结构锁/显式超时断连→network:true/服务端断连→network:true/非 JSON 兜底/非 2xx 透传）
> + **双 typecheck 干净**（app + desktop）。包侧新锁 2 条进 `accept_packaged_bundle.py`，
> 打在 **r22 现役包上首跑 = FAILED=2（预期红，证锁真咬）**，其余 26 项全绿（DirectML wall=27.1s、
> 剪映通道 http=200、12 行腿埋点齐）。端到端 `work/probe_bridge_long_request.cjs`（跑**编译产物**
> `out/electron/backend/bridge.js`，两臂并发打同一 330s 慢服务器）= **PROBE PASS**：
> node:http 臂 `ok=true status=200 waited=330065ms`，旧 undici 臂 `network=true waited=307099ms`。
> **④ r19 已删**（口令「删（验完再删）」）：先验回滚档 r20（testzip=None · 7,078 条目 · backend.exe
> 77,474,898B · sha16 `63987715436d5e31`）**与档案逐字一致**，再验 r19 自身（testzip=None · 7,078 条目 ·
> 77,474,263B · sha16 `86d2007c00cfc673`）一致 ⇒ 删（释放 ≈936MB）。release/ 现**三档 r22/r21/r20**。
> **⑤ 覆盖边界（如实）**：改动不进 `backend.exe` ⇒ **r22 zip 不含本批修复**，需重出（r23 = 见 ⑥）。
> 超过 300s 的证据来自「编译产物 + 真 socket + 330s 慢**夹具**」，**不是真机真导出**；夹具侧显式关了 Node
> 服务端 `requestTimeout/headersTimeout`（真后端 uvicorn 无此限制——真机 571s/475s 都回过响应）。
> ~~undici 默认值实测在 Node v24.18.0，Electron 34 内嵌 Node 20.x 的同值未单独实测（同族 300s，登记为边界）~~
> → **已在 Electron 内实测关闭**（`work/probe_electron_fetch_default.cjs`，Electron **34.5.8 / Node 20.19.1**）：
> global fetch 臂 **306,602ms** 抛 `fetch failed`(cause `HeadersTimeoutError`)、node:http 臂
> **330,006ms 真拿到 200** ⇒ `PROBE PASS`，定性在产品实际运行环境里同样成立。
> dev 态浏览器 fetch 路径未动（分发不走它）。导出 >30min 仍会被切断回 network:true（取「有界等待」）。
> **其它路由不加 per-route try/except**（前提已证伪，全局 handler 继续作 500）；`/api/export` 的第二层
> 边界**保留**（<300s 的意外异常仍给 400+人话），但其档案理由以本块为准。本批未重跑后端/API 全套（无 Python 改动面）。
> **⑥ r23 已出（2026-10-13 00:1x，口令「先提交再打r23」）**：代码笔 `8fbd02c` + 档案笔 `a84119d`
> ⇒ **r23 = 干净 commit `a84119d` 构建**（构建时工作树干净）。`build-release.ps1` 四步 PS_EXIT=0。
> 包内四道全绿：**bundle 28 PASS / 0 FAIL**（含两条新桥接层锁——它们在 r22 包上**首跑预期红 FAILED=2**，
> 现在转绿）· **render 8 PASS / FAILED=0**（R1 completed wall=60s · 64 段无交叠 · 136.366 vs 136.344s ·
> h264_amf · 隔离子进程在位）· **导出计划不变式 FAILED=0**（4 片 × 4 通道）· **启动冒烟**
> Electron 4 + backend 1 / 30s 存活 / AFTER_KILL=0。
> zip `Video-Locator-win-x64-20261012r23.zip` = **981,687,209B / 7,078 条目 / testzip=None / flat**
> （对 r22 +1,189B，与「只改一份主进程 JS」相容）；**zip 内 bridge.js 与磁盘逐字节相同**（8,882B，
> 含 `require("node:http")` + `fetchImpl = httpRequester` + `data: bodyData`）= 修复确实在分发包里，
> 不只是在 win-unpacked 里。
> ⚠️ **一处预登记预期被推翻并订正**：本块原写「预期 r23 的 backend.exe sha16 与 r22 逐字相同」——
> 实测**不等**（r23 `537bcca18760de77` vs r22 `f0d00f10c4123813`，**同尺寸 77,493,384B**）。字节级 diff
> = **仅 9 字节、3 段各 3 字节**（偏移 264 / 344 / 253492，其中 264 与 253492 两处同值 ⇒ 归档长度/偏移类字段），
> 形态符合 PyInstaller「.pyc 内嵌构建时间戳 ⇒ 压缩后位移」的**非确定性构建**；佐证 =
> `git diff 36dec63..a84119d -- mvp/src mvp/api` **为空**（本批没动 Python 运行面）。⇒ 正确口径是
> 「同尺寸 + 差异只在归档长度/时间戳字段」，**不是**「逐字相同」；`zip 内 == 磁盘构建`
> （matches_disk_build=True）这条仍然成立且是有效闸。
> ~~⚠️ mac 侧未跟新：同一份 `bridge.ts` 缺陷在 mac 包里同样存在，要经 mac CI dispatch 才到用户手上~~
> → **已随本批 dispatch（见 ⑦）**：mac 包与 Windows 共用同一份 `bridge.ts`，改 JS/跨平台代码后
> **必须主动交代「mac 要另走一发 dispatch」**，否则会默默留下「Win 已修、mac 仍崩」的裂口。
> **⑦ 收口三件（2026-10-13 00:2x–00:3x，口令「1.删r20，2.动，动完之后就走ci更新mac平台」）**：
> ① **r20 已删**——按规矩先验回滚档 r21（`testzip=None` · 7,078 条目 · backend.exe 77,493,043B ·
> sha16 `fa3c394567cc17d2` **与档案逐字一致**）；r20 自身本批早先也验过（`63987715436d5e31` 一致）。
> ⇒ release/ 现**三档 = r23 现役 + r22 + r21**（本块 ⑥ 原写「四档、删 r20 等口令」已执行，口径以此处为准）。
> ② **已 push `1a05aba..4fe0d96`（4 笔）**（含代码笔 `8fbd02c` 与 r23 构建点 `a84119d`）。
> ③ **mac 已 dispatch**：`h3-macos-mps.yml`（ref=master）HTTP **204** ⇒ run **38277827813**，
> head_sha `4fe0d96a5`（= 最新 master，故构建面含桥接层修复）。**话术口径钉一次**：
> **push ≠ 走工作流**——该 workflow 是 `workflow_dispatch` 专用（push 不触发，为省 macOS 分钟），
> push 只是**前置**（dispatch 取默认分支 head）。要「更 mac 包」得单独说 dispatch。
> **自动换包机制**（读 `.github/workflows/h3-macos-mps.yml` 本体，非回忆）：`macos-package`
> `needs: mvp-tests-macos`(:103) ⇒ 「Accept packaged mac bundle (gate publish)」(:278) ⇒
> 「Publish to GitHub Releases (rolling tag mac-alpha)」(:281) 对已存在 tag 执行
> `gh release upload mac-alpha "$Z" --clobber`(:288) ⇒ **门槛绿就同名资产就地覆盖，无需人工步骤**；
> **门槛红则 publish 整步不跑，mac-alpha 留旧包**（= 历史「两轮红第三轮绿」那几轮没换包的原因）。
> 收口读数（run 三 job 结论 + `mac-alpha` 资产字节数/`updated_at` 对旧值 916,823,896B @
> 2026-10-12T14:45:51Z）另笔登记；用户 00:3x 明确「mac zip 不用我确认」，此项**不再自行追读**。
> **未结**：**B 方案=导出异步化**（`/api/tasks/export` 进现有 tasks 框架，带进度+可取消，根治
> 「UI 干等 6~13 分钟」）已向用户报过、未拍板未开工。
> 产物：`mvp/ui/electron/backend/bridge.ts` · `mvp/ui/electron/backend/tests/bridge.test.ts` ·
> `mvp/scripts/accept_packaged_bundle.py`；探针/日志在 `work/`（不入库）：`probe_global_handler.py` ·
> `probe_node_fetch_timeout.js` · `probe_bridge_long_request.cjs` · `probe_electron_fetch_default.cjs` ·
> `bridge_long_request.log` · `electron_fetch_timeout.log` · `node_fetch_timeout.log` ·
> `accept_{bundle,render}_r23.log` · `invariants_r23.log` · `startup_r23.log` · `r23_id.log` ·
> `backend_diff.txt` · `r19_id.log`/`r20_id.log`。
