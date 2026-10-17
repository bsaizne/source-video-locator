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
