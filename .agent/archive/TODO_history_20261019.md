# TODO 历史迁移 2026-10-19

> 迁出 `.agent/TODO.md` `P0` 的「续68」块（逐字，一条未删）。
> 迁出原因：P0 防复发纪律 = P0 保持 ≤1 块。

> **▶ 2026-10-18（续68）— ✅ 出包 r27 + 五道包内验收全绿 + zip 身份双尺一致；mac dispatch 被令牌堵住【现读这条】**
> 口令「继续这个项目」。**本批只出包，`mvp/src` 零改动**（构建点 = 干净 commit `e1abea4`，与 origin/master 同步）。
> **一、为什么必须重出**：r26 的 `win-unpacked` 构建于 **2026-10-18 01:37**，而 scn3/scn4 三笔代码
> （`5bb8089` 17:42 / `b6e9113` 18:44 / `a00231c` 21:39）都在它之后 ⇒ **r26 里不含 scn3/scn4**。
> **二、包身份（两把尺子读数逐字相同）**：`Video-Locator-win-x64-20261018r27.zip` **981,703,562 B**
> （对 r26 **+5,718 B**）· 条目 **7,079**（文件 6,993 + 空目录 86）· `testzip=None` · root_form=flat ·
> zip 内 `backend.exe` **77,509,036 B / sha16 `fbba9d9870b2fcab`** == 磁盘（`matches_disk_build=True`）·
> `bridge.js` 8,882 B / sha16 `7d3e0427e3d3a4db`（与 r26 逐字同 ⇒ 本批零 JS 改动）· 与 r26 文件集合差集 **0 / 0**。
> **三、五道包内验收全绿（逐条 rc=0）**：bundle **33 PASS / FAILED=0** · render **8 PASS / FAILED=0**
> （64 段 / 136.366 vs 136.344s / `h264_amf` / 隔离在位 / wall 60s）· 导出计划不变式 **FAILED=0**
> （4 片 × 4 通道五条全绿：2mkv 70 · test1 44 · test2 46 · test3 69 段）· 启动冒烟 **FAILED=0 / AFTER_KILL=0** ·
> 合并腿 **6 PASS / FAILED=0**（包内 backend + 包内 ffmpeg 真跑）。
> **四、⚠️ mac dispatch 没做成（如实）**：非交互取令牌两条路都堵 —— `git credential fill` rc=128、
> `git credential-manager get` rc=255（`GCM_INTERACTIVE=never` 下均报 `Cannot prompt ... disabled`），
> 环境无 `GH_TOKEN`/`GITHUB_TOKEN`/token 文件。按规矩**停手不重试、不弹窗**。
> 入口 = Actions → `H3 macOS MPS POC + MVP tests` → Run workflow（ref=master，head 应为 `e1abea4`）。
> 现状硬读数（无令牌可查）：最新 mac run = `39060341032` / head `ad7cec41a` / success（2026-10-17）⇒ 现役 mac 包连 r26 都没有。
> **r24 双验已 PASS 但我没删**（`work/r27_pkg/precheck_delete_r24.py`，四档逐字一致、`testzip=None`）——删包不可逆，等你口令。
> **五、未结**：① **mac 包**（需用户给 token 或手动 dispatch）② **删 r24**（等口令，双验后删）
> ③ 真索引 `refresh_derived` 端到端仍未跑完 ④ 立项③「下游按阈值标注」未做。
> **六、⚠️ 本轮我踩的坑**：`read` 工具读长文件被截断（CHANGELOG 4017→481 行）后直接 `write` 写回，
> 抹掉 3591 行；`git checkout --` 三次恢复。**改写长文件必须先验「读到的行数 == totalLines」**（详见 CHANGELOG 续68 §坑）。

