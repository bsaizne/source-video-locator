# 交接 2026-10-18（03:3x）— r26 现役 + mac 包已换 + source_merge 两族修完 + cap1.5 四片收口

> 自包含交接件。下一会话读这一份 + `.agent/STATE.md` 顶部「续63 补廿四」块即可接手。
> 上位明细：`.agent/CHANGELOG.md` 2026-10-18 的（补二十 ~ 补廿四）五段。
> 本仓 `D:\claudework\benchmark`；竞品侧正文一律在 `D:\claudework\cutmatch-analysis`（物理隔离、非 git 仓）。

## 0. 一句话状态

Windows 现役包 = **r26**（`Video-Locator-win-x64-20261018r26.zip`，构建点 = 干净 commit **`ad7cec4`**，
包内**五道**验收全绿）。**mac 包也已换**（rolling tag `mac-alpha` 的
`Video-Locator-mac-arm64.zip` = **917,013,005B @ 2026-10-17T19:19:39Z**）⇒ **两端都含 r25+r26 全部后端修复**。
分发包三档 = **r26 + r25 + r24**（r23 已删，释放 ≈936MB）。
`origin/master` = **`ad7cec4`**；本地领先 **4 笔档案笔**（`f227aca`/`0ecdcd3`/`acfd16f`/`ffa06c8` + 本笔），
**未推**（刻意不推：推了 master head 就离开构建点，档案里的身份数会失配）。工作树 = 只有档案文件。

## 1. 这一夜做完的五批（读数索引，别处不重复）

| # | 事 | 关键读数在哪 |
|---|---|---|
| 补二十 | cap 1.5 观感面读图（先做 2mkv） | STATE 补二十 块（已迁 `archive/STATE_history_20261018.md`）+ `work/cap15_film_20261018/` |
| 补廿一 | `source_merge` 音频布局**两族**修复（改了产品代码） | 代码笔 `06e7a64`，`work/merge_layout_20261018/` |
| 补廿二 | 两项遗留：编码器假故障播报 + copy 判据补布局 | 代码笔 `e3d5d44`，`work/merge_layout_20261018/leftover_*` |
| 补廿三 | **出包 r26** + 新增**第五道包内合并腿实测** + 推 `e5b5d90..ad7cec4` | `work/r26_pkg/`（build/accept×5/zip/precheck） |
| 补廿四 | 删 r23 + cap1.5 结论**扩到四片**（两条自我订正）+ C 盘占用查清 | `work/{r26_pkg/precheck_delete_r23.py, cap15_film_20261018/four_case_report.json, cdisk_20261018/}` |

## 2. 七条已被实测打掉/削弱的结论（**别再当事实引用**）

1. **「双档（2.5 vs 1.5）各出一张成片再读图」= 空实验**：`material_expand` 只允许剪映通道
   （`exporters.py:433` 硬守卫 `raise`），成片通道调用 `prepare_channel_plan` 根本不传该参数
   （`locator_service.py:992-998`）⇒ **cap 对成片/EDL/XML 惰性，两档成片逐字节相同**。观感面唯一载体 = **剪映卷轴素材**。
2. **「test1/2/3 原片不在本地、不可渲染」= 错**：四片全在本地 D 盘（`D:\video\2.mkv` +
   `D:\ProjectXIXI\test{1,2,3}\*-om.*`）。错因 = 我的 `sed 's/.*: *//'` **把盘符 `D:` 吃掉**，
   输出看着像 UNC。⇒ 判存在性一律 `os.path.exists` 逐条判。
3. **「cap1.5 逐 clip == 关闭扩宽」/「1.5 档卷轴区间 == 成片通道区间」→ 只在 3/4 片成立**：
   test3 `clip62` 在 1.5 档仍扩宽（core 4.17s → 6.0s = **1.44×**，正落在 1.5 阈内）。
   口径 = **cap1.5 ≈ 关闭扩宽**（四片 234 条里 1 条）。
4. **「`mvp/ui` 零改动 ⇒ mac 不需另走 dispatch」只对一半**：mac 的 backend 由 CI 从检出 ref **现编**
   （workflow 有 `Build backend bundle`）⇒ **凡 `mvp/src` 改动 mac 就要重出**。
5. **`source_merge` 不只是"硬失败"**：混合形态（未写布局 + 已写布局）**不报错**，而**产物声道结构 =
   第一路的布局**（`[5.1,stereo]→6/5.1` vs `[stereo,5.1]→2/stereo`）= 顺序决定语义、零留痕。
6. **「每次合并白跑 nvenc+qsv」不是性能问题**：微型探测与白跑同价（死臂 ≈0.57s/条、探 7 条 2.82s）。
   真缺陷 = **向用户播报 2 条假故障**（本机无 NVIDIA/Intel 属正常态）。
7. **`ffmpeg -vf "select='gt(scene,X)',metadata=print:file=…"` 的读数不合法**（出现窗口外时间戳 +
   跨窗口复读）⇒ 边界定位改走「窗口内逐帧解码 + 自算相邻帧像素差 + 显著峰」。
   `work/merge_layout_20261018/edge_offsets.py` 只留作判废证据。

## 3. 现役硬读数（要引用就用这些）

- **包身份**：r26 = **981,697,844B**（对 r25 +4,239B）/ 条目 **7,079**（文件 6,993 + 空目录 86）/
  `testzip=None` / `root_form=flat` / `backend.exe 77,502,636B sha16 9410f2e7baa948d6` **zip 内 == 磁盘**
  （对 r25 +4,611B）/ `bridge.js 8,882B sha16 7d3e0427e3d3a4db` **与 r25 逐字同**（零 JS 改动）/
  **与 r25 文件名集合差集 0/0**。两把尺子（`make_zip_r26.py` 与 `work/r17_pkg/zip_identity.py`）读数相同。
- **五道包内验收**（串行、逐条 rc=0）：bundle **33 PASS/0** · render **0**（64 段 / 136.344 vs 136.366s /
  h264_amf / 60.1s）· 不变式 **0** · 冒烟 **AFTER_KILL=0** · **第五道合并腿 0**
  （包内 backend 打 `/api/source/merge`：两个 6ch/未写布局输入 → `mode=transcode` 且产物 **`6/5.1`**、
  两种顺序产物相同、支持档出现 `source merge plan:` 留痕）。
- **门禁**：后端 **Ran 694 OK (skipped=2)**（10-17 是 675，+19 = 补廿一 13 + 补廿二 6）·
  API **Ran 150 OK** · 导出计划不变式 **FAILED=0**。
- **cap 四片**：clips 72/45/47/70；两档不同 12/7/9/11（39）；**cap 归因 34**；
  「至少一边不在索引切点」1.5 档 151 vs 2.5 档 117；Σ素材宽 2.5/1.5/core = 499.1/421.7/419.9s；
  真剪点偏差 44 边界里 **32 有显著剪点、中位 0.249s、最大 0.917s、18 正向（2.5 素材带进邻镜头 ≤0.9s = 闪切）**。
  ⇒ **cap 既不是「过渡不流畅」的成因、也不是解药**（与 10-16 armC 反证同向）。
- **mac run**：`39060341032`，22.5min，三 job success；`macos-package` 21 步全绿含门槛与 publish。

## 4. 未结项（下一会话从这里接）

1. **第五道包内合并验收要不要升为常设**（现在住在 `work/r26_pkg/accept_packaged_merge.py`）。
   升 = 挪进 `mvp/scripts/` 并写进 AGENTS 的出包清单；不升 = 下次出包它就不会跑。
   ⚠️ 别顺手改 `mvp/ui`，那是 mac dispatch 的触发面。
2. **主线「导出过渡不流畅」**（`archive/HANDOFF_20261016_export_smoothness.md`）仍缺三样外部输入：
   他指认的**具体秒数** / 未经微信转码的原始 `movie_*.mp4` / `<解说片名>__<hash8>.results.json`。
   机械层六项已排除、armB 帧级切点判负、cap 已排除 ⇒ **别再在编码层/参数层重试**。
3. **`og720-720` 相似度自相矛盾**（0.08 vs 0.97）未定位。
4. **下次出 r27 时删 r24**：`work/r26_pkg/precheck_delete_r23.py` 改 `EXPECT`/`DELETE` 即可复用
   （删前双验留下的两档与档案逐字一致，**期望值必须从 `.agent/**.md` 文本里抓**，不要凭记忆）。
5. 档案里长期挂着但**已被裁决不做**的：C 盘清理三项、⑥a/c/d 探针族、⑤ 导出实得口径、成片缺口标记、
   mac 严格惰性再 dispatch —— **勿再提议**。

## 5. 复跑命令（绝对路径 python；bash PATH 里没有 python）

```bash
PY=D:/claudework/video-dedup-tool/.venv/Scripts/python.exe
cd /d/claudework/benchmark && export PYTHONPATH="mvp/src;mvp"
"$PY" -m unittest discover -s mvp/tests -p "test_*.py"        # 后端全套（r26 树 = Ran 694 OK, skipped=2）
"$PY" -m unittest discover -s mvp/api/tests -p "test_*.py"    # API（Ran 150 OK）
"$PY" mvp/scripts/check_export_plan_invariants.py             # 导出计划不变式（FAILED=0）
# 包内五道（串行，各自起包内后端；逐条取 rc，别用 | tail 把 rc 洗成假 0）
"$PY" mvp/scripts/accept_packaged_bundle.py && "$PY" mvp/scripts/accept_packaged_render.py
"$PY" work/r17_pkg/startup_smoke.py
"$PY" work/r26_pkg/accept_packaged_merge.py                   # 第五道：合并腿（真起包内 backend）
"$PY" work/r17_pkg/zip_identity.py "D:/claudework/benchmark/mvp/ui/release/Video-Locator-win-x64-20261018r26.zip"
"$PY" work/r26_pkg/make_zip_r26.py                            # 重打 zip（三道结构断言，不过则 exit 1 不写包）
# 出包链（改了 mvp/ui 或 mvp/src 之后）
cd mvp/ui && powershell -ExecutionPolicy Bypass -File scripts/build-release.ps1
# cap1.5 四片复测（只读，不写 runtime）
"$PY" work/cap15_film_20261018/four_cases.py                  # → four_case_report.json
"$PY" work/cap15_film_20261018/sheets_four.py                 # → sheets4/×7（读图用）
# mac 侧状态（公开 API，**不需要令牌**；curl 输出务必写到仓内路径，python 读不到 git-bash 的 /tmp）
timeout 40 curl -sL "https://api.github.com/repos/bsaizne/source-video-locator/actions/runs/<RUN_ID>/jobs" -o work/r26_pkg/jobs.json
timeout 40 curl -sL "https://api.github.com/repos/bsaizne/source-video-locator/releases/tags/mac-alpha" -o work/r26_pkg/rel.json
```

## 6. 这一夜我自己犯的错（形态各不相同，下一个别再踩）

1. **shell 文本处理造出假读数**：`sed 's/.*: *//'` 把 `D:` 一起吃掉 ⇒ 判成"UNC 不可达"，
   还先报给用户、又写进档案（同一份假读数被复用两次）。⇒ 否定判断（"拿不到/不存在"）必须
   `os.path.exists` 逐条判 + 打印**完整原值**。
2. **探针夹具自身失败没查 rc ⇒ 矩阵全空跑**：`pan=6 channels|…` 造的"无名 6 声道"源被 aac **拒收**，
   产物**根本没有音轨**，六臂全"通过"其实没进场；同轮目录名带 `:` `/` 又触发 WinError 123。
   ⇒ 每条外部命令 `assert rc==0 and 产物在`，并给夹具本身加锁（`test_fixture_is_actually_unnamed`）。
3. **档案原话的修法不能照抄**：`aformat=channel_layouts=stereo` 会把 5.1 永久下混；
   「双档各出一张成片」是空实验；「白跑 = 性能问题」方向错。⇒ 动手前把**每条**前提重新测一遍。
4. **判据覆盖面写窄**（历史教训 ⑦⑲ 同族）：`declared_layout` 只认 json 缺字段、不认 csv 的字面
   `unknown` ⇒ 换种取数方式整套归因会**静默失效**，已加固并加锁。

## 7. Windows 坑（本仓反复踩）

- **中文别塞进 bash heredoc 的 Python 源码**（控制台编码打碎成 `SyntaxError`）；长中文改档一律走脚本文件。
- **脚本 `print` 中文前先 `sys.stdout.reconfigure(encoding='utf-8', errors='replace')`**，否则 GBK 崩在末尾装饰行。
- **`curl` 输出写到 `/tmp` 后 python 读不到**（git-bash 与 Windows python 的 `/tmp` 不同路）⇒ 写仓内路径。
- `.agent/versions/` 下面是**目录**，按文件读会 `PermissionError`（迁移/搜索脚本要跳过不可读者）。
- 竞品仓 `extracted/` 有 **8+GB**，禁止递归读/搜。
- 编辑工具报"失败"时补丁可能已落盘 ⇒ 重发前先 `grep` 判定实际状态；批量改档用带断言的脚本。
