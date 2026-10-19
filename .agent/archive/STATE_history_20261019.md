# STATE 历史块归档 2026-10-19（续80）

> 逐字迁入，一字未改。来源 `.agent/STATE.md` `## Current Task`。

> **▶ 2026-10-18（续68）— 出包 r27：五道包内验收全绿 + zip 身份双尺一致；mac dispatch 被令牌堵住【已退休，见上】**
> 口令「继续这个项目」。**本批只出包，`mvp/src` 零改动**（构建点 = 干净 commit `e1abea4`，与 origin/master 同步 `0 0`）。
> **一、为什么必须重出（硬前提，不是例行）**：r26 的 `win-unpacked` 构建于 **2026-10-18 01:37**，
> 而 scn3/scn4 三笔代码（`5bb8089` 17:42 · `b6e9113` 18:44 · `a00231c` 21:39）**都在它之后**
> ⇒ **r26 里根本不含 scn3/scn4**，用户手上那版边界时刻仍是 1fps 网格 + 旧 CLS 像素门。
> **二、包身份（`work/r27_pkg/make_zip_r27.py` 与独立 `work/r17_pkg/zip_identity.py` 两把尺子读数逐字相同）**：
> `Video-Locator-win-x64-20261018r27.zip` · **981,703,562 B**（对 r26 **+5,718 B**）· 条目 **7,079**（文件 6,993 + 空目录 86）·
> `testzip=None` · root_form=flat · zip 内 `backend.exe` **77,509,036 B / sha16 `fbba9d9870b2fcab`** == 磁盘（`matches_disk_build=True`）·
> `bridge.js` 8,882 B / sha16 `7d3e0427e3d3a4db`（与 r26 逐字同 ⇒ 本批零 JS 改动）· 与 r26 文件集合差集 **0 / 0**。
> **三、五道包内验收全绿（串行逐条取 rc，全部 rc=0）**：
> ① `accept_packaged_bundle.py` **33 PASS / FAILED=0**（12 行 `locate leg=` 齐、`legs` 刻度 `[6,9,42,44,44,44,44,48,48,48,48,48]`、DirectML 生效、冒烟 **35.2s ≤ 75s**、导出任务通道 completed）；
> ② `accept_packaged_render.py` **8 PASS / FAILED=0**（64 段 / 成片 136.366 vs Σclip 136.344s / `h264_amf` / 渲染走隔离子进程 / wall 60s）；
> ③ `check_export_plan_invariants.py` **FAILED=0**（4 片 × 4 通道五条不变式全绿；2mkv 70 · test1 44 · test2 46 · test3 69 段）；
> ④ `work/r17_pkg/startup_smoke.py` **FAILED=0**（Electron 4 进程 + backend 1 个、30s 存活、`AFTER_KILL=0` 无残留）；
> ⑤ `work/r26_pkg/accept_packaged_merge.py` **6 PASS / FAILED=0**（包内 `backend.exe` + 包内 ffmpeg 真跑合并腿：`(6,'unknown')` 夹具、产物 `6/5.1`、两种顺序同布局、留痕命中）。
> **四、⚠️ mac dispatch 没做成（如实交代，不是遗漏）**：非交互取令牌两条路都堵 ——
> `git credential fill` rc=128 与 `git credential-manager get` rc=255，在 `GCM_INTERACTIVE=never` 下均报
> `Cannot prompt because user interactivity has been disabled`；环境里也无 `GH_TOKEN` / `GITHUB_TOKEN` / 任何 token 文件。
> 按既定规矩**停手不重试、不弹窗**。入口 = Actions → `H3 macOS MPS POC + MVP tests` → Run workflow（ref=master，head 应为 `e1abea4`）。
> 判据（补廿三 1b 已订正）：**`mvp/src` 或 `mvp/ui` 任一有改动 ⇒ mac 必须另走 dispatch**，因为 mac 包的后端由 CI 现编。
> **mac 包的硬读数（无令牌也能查）**：`GET /repos/bsaizne/source-video-locator/actions/workflows/h3-macos-mps.yml/runs` http=200，
> 最新一次 = run `39060341032` / head **`ad7cec41a`** / `workflow_dispatch` / completed success（2026-10-17T18:57Z）⇒
> **现役 mac 包停在 10-17，连 r26 那两笔都没有**，更不含 scn3/scn4。
> **r24 双验已 PASS、但我没删**：`work/r27_pkg/precheck_delete_r24.py`（期望值从 255 份 `.agent/**/*.md` 文本里抓、读数从 zip 里取）
> 四档 r27/r26/r25/r24 全部与档案逐字一致、`testzip=None`。删包不可逆 ⇒ **等你的口令**。
> **五、⚠️ 本轮我自己踩的一个坑（留档防复发）**：用 `read` 工具读 `CHANGELOG.md`（4017 行）只拿回 **481 行**（工具默认上限），
> 我据此整文件 `write` 写回 ⇒ **4021 → 234 行，后 3,591 行被静默抹掉**；`STATE.md`/`TODO.md` 同批也被截断。
> 三次 `git checkout --` 恢复，改用 `node:fs` 整读整写（已验证 fs 读到完整 4017 行）。
> **教训：改写长文件前必须先断言「读到的行数 == totalLines」，否则一律不许写回。**
> **六、未结**：① **mac 包**（需用户给 token 或手动 dispatch）② **删 r24**（等口令，双验后删）
> ③ 真索引 `refresh_derived` 端到端仍未跑完 ④ 立项③「下游按阈值标注」未做。
> 明细：`work/r27_pkg/{build_r27.log,accept_bundle_r27.log,accept_render_r27.log,invariants_r27.log,startup_r27.log,accept_merge_r27.log,make_zip_r27.log,zip_identity_r27.log,make_zip_r27.py}`。
