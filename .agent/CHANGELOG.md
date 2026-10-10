# CHANGELOG

## 2026-10-10（续63 补十一·第十二轮）— 真机支持档揪出剪映导出崩：极短素材撑越 material.duration

- **现场**（用户截图 + `video_locator_logs(1).zip`，Windows 支持档）：导出面板红条「无法连接后端服务…
  (fetch failed)」。先证伪字面：`/api/health` 每 20s 稳定响应 18:16→19:12 没断 ⇒ 不是连不上；真红在
  18:42:24 `POST /api/export` 抛未处理 `ValueError: 截取的素材时间范围 [start=0, end=100000] 超出了素材时长(64000)`
  （`exporters.py:923 write_jianying_draft` → `pyJianYingDraft/video_segment.py:455`）。ASGI 未处理异常 ⇒
  uvicorn 掐连接不发响应 ⇒ 前端 fetch 失败 ⇒ UI 弹误导性文案（素材《一口气看过瘾…攀岩女王…》，segments=657）。
- **根因**：`video_segment.py:452` `source = round(target×speed)`，`:454` 判 `source.end > material.duration` 就抛。
  `write_jianying_draft` 三处 `max(0.1,…)` 下限把 <0.1s 短镜头（素材 64ms）撑成 target=100000µs，再被
  「|speed-1|≤0.02 锁原速」把 source 顶到 100000µs > 64000µs ⇒ 崩。顺带暴露：同锁对「素材比 target 短 0.2%
  （重编码少一帧）」的普通 clip 也会 source=target>素材 ⇒ 潜在同类崩（本机没撞上因抽取 clip 通常 ≥ 请求宽度）。
- **修法**（行为保持）：抽纯函数 `_jianying_segment_speed(target_us, mat_us, orig_width, mat_dur)` ——
  ① 锁原速**仅当 `target_us ≤ mat_us`**；② 末尾 `round(target×speed) > mat_us` 时回压 `speed=(mat_us-1000)/target_us`。
  正常素材（mat≥target）逐字仍 1.0 原速 ⇒ 集成测试 `speed==1.0` 断言不破。
- **门禁**：后端全套 **Ran 626 tests OK (skipped=2)**（622 + 新 4）· API **128 OK**。新锁
  `JianyingSegmentSpeedTest` 四条：正常锁原速 / 真机形态（100000 vs 64000）回压不越界 / 边际短素材不越界 /
  **结构锁**（`write_jianying_draft` 必走该 helper、旧内联判据 `max(0.1, min(mat_dur` 不得复活）。
- ⚠️ **覆盖边界**：没在他机器上跑通真导出（要那份 657 段工程 + 短镜头素材）⇒ 判据 = 库源码 `:452/:454`
  确切算法 + 日志 `[0,100000] vs 64000` 确切数字 + 单测复现算术；**包内实证待下次出包**（accept 加极短素材导出锁）。
- ⚠️ **第二层未做（等裁决）**：`/api/export` 只 `except ApplicationError`（`results.py:155`），库级/磁盘级意外
  异常仍逃到 ASGI ⇒ 前端仍显示误导性 fetch failed。本轮只掐这一个具体崩；导出错误边界统一包成结构化 400 = 独立小决策，未动。
- **r20 出包（2026-10-10，口令「先出包」）**：`build-release.ps1` 一条链 `PS_EXIT=0`（资产在位走 sha 断言）；
  **未提交工作树构建**（本批未 commit）。zip `Video-Locator-win-x64-20261010r20.zip` 981,666,831B / 7,078 条目 /
  `testzip=None`；zip 内 backend.exe 77,474,898B sha16 `63987715436d5e31` == 磁盘构建（对 r19 +635B ⇒ 重建进包）。
  包内验收全绿：`accept_packaged_bundle` **FAILED=0**（DirectML 26.1s · 隔离 spawn+booted+reaped · 12 腿埋点 ·
  UI 路径导出 http=200）· `accept_packaged_render` **FAILED=0**（R1 57s · 64 段无交叠 · h264_amf · 隔离）·
  `check_export_plan_invariants` **FAILED=0**（4 片×4 通道）。**未重跑**（改动面不涉及）：三防 · Electron 启动冒烟 ·
  包体剪映产物探针。⚠️ 已知缺口：包内 accept 导出探针不带 `format` ⇒ 走 JSON 不经 `write_jianying_draft` ⇒
  剪映路径的包内锁需另加 `format=jianying`。release/ 现三档 r20/r19/r18，删 r18 等口令。本批未提交。
- **补锁（选项 B，同批）— 剪映路径升到包内常设锁**：`attr_packaged_headless.py` 追加一发 `format=jianying`
  导出（min_confidence=LOW + low_policy=backup ⇒ ≥1 clip 进 plan），`accept_packaged_bundle.py` 加两条断言
  （`jianying_http==200` + 草稿含 ≥1 segment）。对 r20 win-unpacked 重跑 bundle **FAILED=0**：实测
  `a1.loc.jy_draft` 1 段 target=src=45s speed=1.0 + 抽出 `og0-45.mp4` ⇒ write_jianying_draft 在包内真跑通、
  重构未坏正常导出。**只改 `mvp/scripts` 两脚本、不进 backend.exe ⇒ r20 zip 不变、无需重出**。边界：syn 只
  1 条常规 clip ⇒ 不专门覆盖 <0.1s 回压分支（靠单测）。两脚本改动同样未提交。

## 2026-10-10（续63 补十一·第十一轮）— mac 出包链真机结清（读 live CI 复核，档案此前停在「只差 dispatch」）

- **现场**：STATE.md 的「唯一活跃项」写的是「三份权重已重挂 `mac-alpha`、只差用户 dispatch」。
  2026-10-10 用公共 API（读 runs/jobs/annotations 无需令牌）复核 ⇒ dispatch 已执行且**全链绿**。
- **证据（primary）**：
  - run `37943554701`（head `f29e8d66`）+ run `37955484860`（head `31974f2` = checkpoint HEAD）均
    `workflow_dispatch` → `completed success`；三 job（`mps-poc` / `mvp-tests-macos` / `macos-package`）全绿。
  - `macos-package` annotations（原文）：`asset dinov2_cls_patch.onnx.data / isc_ft_v107.onnx /
    isc_ft_v107.onnx.data via A 直链+sha256 OK (…B, try=1)` 三份一发即中（走通道 A，未用 `gh` 兜底）
    + 诊断行 `curl=curl 8.7.1 gh=gh version 2.100.0 src=mac-alpha` ⇒ 第五轮「改挂 mac-alpha + step 11
    简化（删 release JSON 那一发、按仓库内 `asset.json` 的 sha 逐文件判）」这个决策被真机验证；
    第六轮登记的未证面「等值校验首次生效就在 CI 上」= 已在 CI 上验通。
  - step 15 `Accept packaged mac bundle (gate publish)` = success ⇒ step 16 `Publish (rolling tag mac-alpha)`
    = success（publish 受门槛 `if` 管）⇒ release `mac-alpha` 新增 **`Video-Locator-mac-arm64.zip`
    916,769,503 B**（`updated_at=2026-10-09T16:27:38Z`，与 run `37955484860` 时间线吻合）。
- **结论**：mac 出包链闭合。`Current Problem` / `Current Task`（补十一 顶部与第十一轮）已据此更正。
- **未做（留 H3 正式化）**：`Known Issues` 的「mac 包多带 ≈88MB 死 ONNX 资产」未本机拆包核（本机无 mac，
  不为读别人机包去取凭据）；按平台裁剪 `extraResources` 是 H3 正式化时的事。
- Windows 侧现役仍 r19；**按口令删 r17**（2026-10-10）⇒ release/ 现两档 r18 回滚 + r19 现役；
  删前 `zip_identity.py` 验回滚档 r18 `testzip=None`/7,078 条目/backend.exe sha16 `2eb651d38003d433`
  与档案逐字一致（`matches_disk_build=False` 只因磁盘现役已是 r19，属预期）。释放 ≈940MB。与 mac 线无关。

## 2026-10-09（续63 补十一·第十轮）— 真机日志揪出隔离回归：导出/渲染 no results batch；r19 出包

- **现场**（用户截图 + `video_locator_logs.zip`，Windows 支持档）：22:25 提交分析 → 22:47:22
  `locate finished segments=84 elapsed=1310.7s` → 22:48:02 `POST /api/tasks/render` 与
  22:48:07 `POST /api/export` **双双 400 `no results batch; call /api/results first`**
  （导出面板两条红条）。日志里**从没有** `POST /api/results/load` ⇒ UI 走的是"后端自己记得最近一次批"。
- **根因 = 任务级进程隔离（r16 起）留下的状态回归**：`/api/export` 与 render 的兜底是
  `ctx.current_batch or service.last_result_batch()`；locate 现在跑在**子进程**里，写的是子进程那份
  service 的 `_current_batch` ⇒ 父进程这份永远 None。`last_result_batch` 的 docstring 还承诺
  "异步 analyze 也会设置"——隔离上线后这句在父进程失效。
- **为什么验收一直绿**：包内探针（`work/r15_jianying_pkg/probe.py` 那一路）**自己先调了
  `/api/results/load`** 再导出 = 走了 UI 不走的路径 ⇒ 假绿。教训入档：**夹具必须复刻真实 UI 的
  调用序列，不能替 UI 补一步**。
- **修法**：`isolated.py` 终态信封落地处调 `_adopt_parent_batch()`（`ResultBatch.from_dict` 还原 +
  `service.adopt_result_batch()` 登记回父进程；render 批是提交时锁定的不回登记；失败只记日志不改终态）。
- **两层锁**：① `ParentBatchAdoptTest` 四条（locate 回登记 / render 不覆盖 / 失败只记日志 /
  落地处必须调用）⇒ API **128 OK**、后端全套 **622 OK**；② **包侧 UI 真实路径锁**：
  `attr_packaged_headless` 分析完成后**不先 load** 直接 `POST /api/export`，记 `export_http/export_path`，
  `accept_packaged_bundle` 断言 200（字段缺失判"未实测"不判通过）。
  r19 包内实测 **export_http=200**、产物 `a1__35e1ddf8.results.json` 落地 ⇒ 修复在包内成立。
- **r19 出包**：从干净 commit `3ef2b9e` 构建；两道验收 FAILED=0（bundle 含新锁 + render R1 60s/64 段）；
  zip = `Video-Locator-win-x64-20261009r19.zip` 981,667,323B / 7,078 条目 / `testzip()=None`；
  zip 内 backend.exe 与磁盘逐字节相等（77,474,263B，sha16=`86d2007c00cfc673`；r18 为 77,473,147B ⇒
  +1,116B，与"r18 之后 src 只有隔离回登记一处改动"相容）。
- 采坑留痕：`attr_packaged_headless.http()` 只回 body、4xx 抛 `HTTPError`，我第一版按 `(code, body)`
  解包 ⇒ 把 dict 的两个键当值（`http=path`），验收当场红给我看 ⇒ 已改成 try/except 接码。
- release/ 现三档（r17/r18/r19）；按"最新+上一档"该删 r17，**等口令**。

## 2026-10-09（续63 补十一·第九轮）— r18 出包（Windows）：把渲染 None 修复打进包

- 口令「那重新打包啊，那个日志是 windows 上的问题」。`build-release.ps1` 一条链，
  **从干净工作树 head `9eaee64` 构建**（r17 当时是未提交工作树构建；这次「包 == commit」可追溯）。
- 验收两道全绿：`accept_packaged_bundle.py` FAILED=0（资产 sha 全过 / 合成冒烟 DirectML wall=30.1s /
  隔离链 `reaped exitcode=0` / 腿埋点 12 行刻度 `[6,9,42,44,44,44,44,48,48,48,48,48]`）；
  `accept_packaged_render.py` FAILED=0（R1 completed wall=63s / 64 段无交叠 / 时长 136.366 vs 136.344 /
  隔离在位 / `h264_amf` 硬编）。
- zip：`Compress-Archive win-unpacked\*` Optimal ⇒ `Video-Locator-win-x64-20261009r18.zip`
  981,665,372B / 7,078 条目 / `testzip()=None`；**zip 内 backend.exe 与磁盘逐字节相等**
  （77,473,147B，sha256[:16]=`2eb651d38003d433`）；对 r17 尺寸 +382B（77,472,765 → 77,473,147），
  与「r17 之后 `mvp/src` 只有渲染那一处改动」相容。
- ⚠️ 如实登记：包内渲染冒烟**走不到** None 分支（整条 63s、合并段 <5s；心跳要 5s 无读数才发 None，
  他崩的是 2 小时长片）⇒ 该修复在包内无实证，锁在单测 + 「构建自干净 commit」这条链上。
- release/ 现四档并存（r15/r16/r17/r18）；删旧包仍等口令。

## 2026-10-09（续63 补十一·第八轮）— 包内日志捞出一条真缺陷：合并进度回调漏 None ⇒ 渲染 LOC-9999

- **来源**：用户递 `video_locator_logs.zip`（Windows 支持档，09-10→10-09 16:19，8.9MB）。
- **先确认三件已生效**：`backend selected=directml` ×10、`patch reranker device=dml` ×4、
  `isc refine device=dml` ×4、腿埋点 23 行 `locate leg=` + 2 行 `locate refine start`；
  `_call_connection_lost` 最后一次 10-08 18:xx（r17 之前那批）之后零出现 ⇒ 与降噪生效一致，
  但**不作铁证**（可能只是没发生客户端强关）。
- **真缺陷**：10-08 19:00 / 19:12 两次 `render failed [LOC-9999] TypeError: unsupported operand
  type(s) for *: 'float' and 'NoneType'`（素材《巅峰猎杀.1080p.HD中英双字…》）。支持档只有一行摘要
  ⇒ 用异常签名反推：`timeline_render.py` 合并两处回调 `emit(min(0.995, 0.96 + 0.035 * f), …)`，
  而 `_run_monitored` 按约定在**算不出读数**时发 `f=None`（同文件 `_seg_cb` 有这个判定、合并没抄）
  ⇒ 文案未发出即抛，整条渲染判死，用户只看到通用码。
- **修法**：抽 `merge_stage_frac(frac, base=0.96, span=0.035, cap=0.995)`，None ⇒ 读数不动只发文案；
  两处回调改走它。新增 `MergeStageFracTest` 四条：None 不抛 / 区间映射（0→0.96、0.5→0.9775、1→0.995）/
  封顶 / **结构锁**（任何 `on_frac=lambda f:` 且含 `emit(` 的行必须调用该函数，防算术写回 lambda）。
- **门禁**：后端全套 `Ran 622 tests OK (skipped=2)`、API `Ran 124 tests OK`。
- ⚠️ 覆盖边界：没在他机器上复现（要 `SVL_LOG_DEBUG=1` 重跑才有 traceback）⇒ 本次结论是
  **「异常签名 + 全仓唯一相容点」的强推断，不是实证**；LOC-9999 这种一码多因的兜底码也再次说明
  渲染失败值得有专属码（未做，登记为候选）。

## 2026-10-09（续63 补十一·第七轮）— 我自己把 workflow 改坏了：残段被 YAML 吸收进上一步，CI 报 exit 127

- **现象**：run `37813707426`（head `6fbf717`，用户 01:04 触发）红在 `Install backend build deps`，
  日志尾部 `/Users/runner/work/_temp/<uuid>.sh: line 4: note: command not found` + `exit code 127`
  ⇒ pip 安装本身全成功，是**那一步的脚本里凭空多了 49 行不属于它的 shell**。
- **根因（我的补丁脚本 bug，不是 CI 环境问题）**：`patch_step11.py` 用「第一处
  `verify_model_asset_shas.py` 行」当截断锚点，而旧正文里那行**出现两次**（元数据全灭的兜底分支里一次、
  末尾一次）⇒ 只截到第一处，剩下的旧尾巴留在原地；它缩进比 `run: |` 更深 ⇒ **被 YAML 当字面块吸收进
  上一步的 run** ⇒ 语法完全合法（`yaml.safe_load` 过、`bash -n` 过、抽出的 step 11 也正常），
  所以我那三道本地校验**全都没抓到**。
- **修法**：`work/r17_mac_log/fix_workflow_stray.py`（断言式：残段必须以 `note "资产由直链兜底…"` 开头、
  含 `fetch()`；修完 `Install backend build deps` 恰好 2 行、`Fetch model assets` 50 行、
  macos-package 15 步、tests job 8 步、且任何步骤里都不许有游离 `note/warn/sha_ok/fetch/get` 行）。
  对 `524c9bb` 的净差异 = **只删 48 行、加 1 空行** ⇒ 确认没顺手删掉别的步骤内容。
- **防复发**：`patch_step11.py` 加两条硬断言 —— ① `assert text.count(VERIFY_TAIL) == 1`（锚点必须唯一）；
  ② 写完前跑同一套结构自检（每步 run 行数 + 游离脚本行归属）。**教训：改 YAML 字面块之后，
  `yaml.safe_load` 成功不等于内容正确，必须逐步骤打印首/末行与行数。**
- 彩排四情形（P1-P4）修完重跑仍全 PASS；step 11 的 `bash -n` 与 `extract_step11.py` 均过。
- **下一轮**：head 会是本次修复提交；`mvp-tests-macos` 与 `mps-poc` 上一轮已绿，本轮该走到 step 6 取资产。

## 2026-10-09（续63 补十一·第六轮）— 三份权重重新挂上 `mac-alpha`，CI 的资产源恢复

- **动作**：用户令「上传三个文件到 mac-alpha release」。本机 credential helper 这次**非交互返回**
  （`GIT_TERMINAL_PROMPT=0` + `timeout 20`，没弹登录窗 ⇒ 与 2026-10-07 那次不同，可以走）
  ⇒ 用 `mvp/scripts/upload_mac_model_assets.sh`（默认已指 `mac-alpha`）上传三份，全部 HTTP 201：
  `dinov2_cls_patch.onnx.data` 88,342,528B / `isc_ft_v107.onnx` 1,613,211B / `isc_ft_v107.onnx.data` 209,190,912B。
  服务端 `releases/tags/mac-alpha` 的 asset 列表**逐个字节数与本地一致**（核过三遍）。
- **端到端抽验一份**：走 CI 用的那条 API octet-stream 通道（**必须带 `-L`**，我第一遍漏了 ⇒ 拿到 0 字节，
  差点把"上传坏了"当成结论）下载回 1,613,211B，sha256 与 `asset.json` **匹配**。
  两份大文件不做本机回下（≈300MB 不值得）⇒ 由 CI step 11 的逐文件 sha256 当场判，这正是该判据的意义。
- **我自己的两次操作失误（留痕）**：① 第一次上传其实已经全绿完成，我误判它"被 TaskStop 停了没成"，
  起了第二次 detached 运行 ⇒ 脚本按「同名先删再传」把三份删了重传；② 中途我又手动 kill 掉大文件那一发，
  让 `isc_ft_v107.onnx.data` 在服务器上**缺失约 25 分钟**（第三次单发补齐）。
  错在拿 `tasklist` 里 curl 的驻留内存当进度读 ⇒ **进度判据要用服务端 asset 列表，不是本机进程表象**。
- **安全事项**：为了分辨"哪个 curl 在传哪个文件"，我用 `Get-CimInstance Win32_Process` 打了进程命令行，
  **把完整令牌写进了会话输出**一次。临时文件（`/tmp/gcm.txt` 等）已删，后续不再读进程命令行、不打印含令牌的内容；
  建议用户在 GitHub 设置里撤销该 OAuth 授权并重登（代价是重输一次凭据），由他决定。
- **下一步**：dispatch `h3-macos-mps.yml` ⇒ step 11 应绿 ⇒ 构建 → mac 包体门槛 → publish 覆盖 mac-alpha zip。

## 2026-10-08（续63 补十一·第五轮）— 真根因：`model-assets` release 被删；资产改挂 `mac-alpha`，step 11 简化
- **结案方式**：用户口述「那个 release 的 tag 被我删了」并裁决「放去 mac-alpha 呗，本来就是放进这里的，
  你非要开一个 tag」⇒ 上面「第三轮 / 第四轮」里所有**网络层定性作废**（IPv6 路由、HTTP/2 复位、
  draft 的 tags 端点行为、`api.github.com` 当下不通），那两轮的过程与观测面保留，别当结论引用。
- **我的错**：在缺「资产还在不在」这个前提时，把「同源历史绿、今天全灭」的症状归因到协议层，
  并把推测写成了结论（第四轮 STATE 原话「改判：api.github.com 这条 HTTP/2 通道当下对该 runner 不通」）。
  ⇒ 规矩：**先验被访问对象是否还存在，再谈通道**。
- **落地**：① 资产挂 `mac-alpha`（published prerelease ⇒ `releases/download` 直链公开可取、不需要令牌；
  本机实测 `releases/tags/mac-alpha` 无令牌 http=200）；② step 11 从「4 条元数据通道 + 3 条资产通道」
  简化成 **A=直链 / B=`gh release download`，完整性由仓库内 `asset.json` 的 sha256 逐文件当场判**
  （release JSON 那一发彻底不需要了，元数据 size 校验也撤了）；缺项 `::error::` 点名三份文件与字节数。
- **保住的两处真收益**：fail-fast（整步移到 `Download DINOv2 weights` 之前 ⇒ 红一轮 ≈2-3 分钟而非 ≈19 分钟）、
  annotations 自证（无令牌可读 rc/http_code/stderr 头）。
- **彩排**：`step11_harness4.sh` + `stubs4/{curl,gh,python3,sleep}` 跑 workflow 原样抽出的脚本，
  P1 直链 200→rc0(A) / P2 404+gh 失败→rc91 且文案点名 mac-alpha / P3 首发 500 二发 200→rc0 /
  P4 直链恒 404、gh 兜住→rc0(B)，全 PASS；并当场抓到一个真 bug——`echo` 里用反引号包 `$SRC_TAG`
  被 bash 当命令替换，报错文案把 tag 名吞成空串（已去掉反引号）。
- **内容就绪证明**：本机 `verify_model_asset_shas.py` 四份全 PASS（patch .onnx 78,194B /
  patch .data 88,342,528B / isc .onnx 1,613,211B / isc .data 209,190,912B）⇒ FAILED=0。
- ⚠️ **未闭合（要用户动手）**：`mac-alpha` 目前 asset 列表只有两个 zip，三份权重尚未挂上 ⇒
  下一轮 CI 仍会红，但红得明白。我本机无 GitHub 凭据（不为一个上传去弹登录）：他在网页端拖三个文件
  上 `mac-alpha`，或给一次可写令牌由我传。
- **一条要说清的事实**：`mac-alpha` 是公开 prerelease ⇒ 权重随之一同公开可下载，而 ISC 权重是 NC 许可；
  这是用户明确的选择，我不再自行改回 draft 或另开 tag（`reference-model-asset-hosting` 记忆同步更正）。

## 2026-10-08（续63 补十一）— mac CI 唯一红点：Windows 字面量断言（测试层，已修并 push）

- **现象**：用户手动 dispatch 的 run `37782689308`（head `382d3ac`）= `mvp-tests-macos` failure
  （`Ran 617 tests … FAILED (failures=1, skipped=48)`）⇒ `macos-package` **skipped** ⇒ `mac-alpha`
  没出新包。
- **取不到 job 日志**（无令牌 `/actions/jobs/<id>/logs` = 403；本机 GCM 不弹令牌不重试）⇒ 改从计数反推：
  `errors=0` 排除「构造异常对象本身抛错」，`failures=1` 只与「某条断言字面量落空」相容 ⇒ 锁定
  `test_logging.py::ProactorNoiseFilterTest::test_our_module_connection_reset_still_error` 的
  `assertIn("WinError 10054", main)`。
- **根因 = 断言把平台文案当跨平台事实**：CPython 非 Windows 平台**忽略** `OSError` 的 `winerror`
  入参（`exc.winerror` 恒 None），渲染成 `[Errno 10054]`；降噪判定本身在 mac 上走
  「winerror 缺省退 errno」分支、行为正确。
- **改动**（`d78e13a`）：`_reset()` 按平台给形态 / 新增 `_code_token()` 供 ERROR 侧断言 /
  新增常驻锁 `test_errno_only_shape_still_downgraded`（用「没有 winerror」的形态压 errno 回退分支，
  Windows 本机即可跑）。
- **验证面**：Windows `mvp.tests.test_logging` **31 OK**（30→31）；mac 侧**未本机实测**，
  判据 = 官方文档 + 现役判定分支 + run 计数相容性，最终由下一次 dispatch 定论。
- **教训 ⑮** 已写进 `STATE.md` 工程教训速查；同批更正 `Current Problem` 里「工作树仍未提交」的过期表述
  （补九/补十 已按口令提交 push）。
- ⚠️ 自伤留痕：push 时误打 `HEAD:main`（本仓默认分支 = **master**）⇒ 已补推 master 并删除远端 `main`。
- **第二轮（同批追加，依据用户递来的 mac 日志 `D:\mvp-macos-test-log.zip`）**：run `37787565939`
  （head `3349063`）= `Ran 618 tests / FAILED (errors=1, skipped=48)` ⇒ `macos-package` 仍 skip。
  ① 第一轮那处修复**真机证明有效**（`test_our_module_connection_reset_still_error` 在 mac 转 ok，
  `_code_token()` 取 `Errno` 的推断成立，旧 `failures=1` 消失）；② 红点搬到了**我新加的那条跨平台常驻锁**：
  `AttributeError: 'ConnectionResetError' object has no attribute 'winerror'`（`test_logging.py:364`）
  —— mac 上不是 `winerror=None` 而是**属性根本不存在**（文档后半句 "the attribute does not exist"
  第一次真机碰到）；产品判据一直写的是 `getattr(exc, "winerror", None)`（`logging.py:161`）⇒ 没受影响，
  **只有测试写死了「属性一定在」**。⇒ 断言改 `getattr(...)`（与判据同写法）+ `_reset`/`_code_token`/
  `logging.py` 注释按实测更正。③ 同日顺手拿到 **mac 侧腿埋点真机证据**（此前只有 Windows 包内）：
  mac 支持档 12 行 `locate leg=` 顺序与区间全对（`global_anchor 0->6/48` …
  `consecutive_resolve 44->48/48`，`patch_refine elapsed=91.1s` 走 MPS），降噪 7 条在 mac 全绿。
  ④ 教训补写进 `STATE.md` ⑮：**「另一平台的属性缺省」有两种形态（None / 属性不存在），只有真机能区分**。
- **第三轮（同批追加）— 测试门真机转绿，卡点搬到 `macos-package` 第 11 步**：run `37791429326`
  （head `b6a4a25`）= `mvp-tests-macos` **success**（618 全过 + MPS 冒烟）⇒ 前两轮改动被真机结清；
  `macos-package` 首跑红在 `Fetch model assets for mac bundle`，报
  `Run set -euo pipefail / Error: Process completed with exit code 56`（curl recv failure = 对端中途断流）。
  定性：同一步骤在 run `37471104792`（2026-10-06，head `7589659`）为 success 且此后未改 ⇒ 偶发网络，
  但**代价不对称**（抖动一次 = 19 分钟 + 后续步骤全没跑），而当时只有资产下载带 `--retry 5`，
  **取 release JSON 那一发一次重试都没有**。
  ⇒ workflow 加固（逻辑不变，只补韧性）：元数据 `curl` 补 `--retry 5 --retry-all-errors --retry-connrefused`；
  `fetch()` 外套**整发 3 次**；完成判据由「>0 字节」升级为**与 API 报的 `size` 逐字节等值**（旧口径截断成
  半体能过闸，要等 sha 校验才打死整轮）；每发失败打 `::warning::` 带 try 次与 curl rc。
  本地彩排 `work/r17_mac_log/step11_harness.sh`（桩 curl 三情形）：截断→二发齐 = rc0 恢复 /
  三发全截断 = `::error::` rc1 / 一发即齐 = 原路径 rc0；YAML 解析 + `bash -n` 过。
  ⚠️ 未证面：本机无令牌取不到 draft release 元数据 ⇒ 三资产真实 `id`/`size` 没本地核过，
  等值校验首次生效即在 CI；第四轮若仍红 56 就不再当抖动处理，改走 `gh release download`
  或 `releases/download/<tag>/<name>` 并留对照证据。
- **第四轮（同批追加）— 加固版仍红 56 ⇒ 不再押根因，改结构：多通道 + 「元数据死≠资产死」+ fail-fast**：
  run `37795700737`（head `cf4b61f`，**已含** `--retry 5` + 整发 3 次）第 11 步仍 `exit code 56`，
  `mvp-tests-macos` 继续绿。观测通道换了：**check annotations 是公共端点**
  （`GET /repos/…/check-runs/<job_id>/annotations` 无令牌 = 200），这一轮只有 3 条注解
  （Node 20 弃用 / exit 56 / arm64 排队），**我上轮加的 `::warning::` 一条没出**
  ⇒ 死在元数据那一发（`json="$(curl …)"` 在 `set -e` 下直接判死整步），6 次尝试全同码
  ⇒ **上轮「偶发网络」定性作废**。根因仍未定，候选三条（IPv6 路由 / HTTP/2 复位 /
  draft release 的 `tags` 端点行为）—— 本轮把它们变成**可读数据**，而不是押其中一个。
  ⇒ 四处改动：① 元数据四条独立入口（`api/tags` 与 `api/list?per_page=100` × `curl(-4 --http1.1)` 与
  `gh api` 独立实现）；② 资产三通道（A=api octet by id / B=gh api by id / C=`github.com` 直链），
  每发把 `rc`/`http_code`/stderr 头打进注解；③ **解耦**：元数据全灭不再整步死 ⇒ 改走
  「直链 + 仓库内 `asset.json` 的 sha256 当场判」（只字不碰 `api.github.com`；sha256 与文件名在仓里，
  与 `verify_model_asset_shas.py` 同源）；④ **fail-fast**：整步上移到 `Download DINOv2 weights` 之前
  ⇒ 红一轮从 ≈19 分钟降到 ≈2-3 分钟（已核 `build_backend_mac.py` 只 rmtree DIST/WORK/BACKEND_DIR，
  不清 `resources/models` ⇒ 先取资产安全）。
  彩排升级：不再手抄逻辑，`work/r17_mac_log/extract_step11.py` **从 workflow 原样抽出 run 块**，
  `step11_harness3.sh` + `stubs3/{curl,gh,python3,sleep}` 顶掉网络跑四情形，全 PASS：
  N1「api 双实现全挂、直链给满字节」= 本轮 CI 形态 → rc0 走直链+sha；N2「连直链也 404」→ rc90 且注解带
  `-6/-4` 路由对照；N3「tags 挂、list 成」→ rc0(ch2+A)；N4「元数据只有 gh 成、curl 资产恒截断」→ rc0(ch3+B)。
  ⚠️ 未证面（下一轮 CI 才定）：`-4`/`--http1.1` 是否命中根因、`gh api` 在 mac runner 取 draft 资产能否通、
  **直链对 draft release 是 200 还是 404**（③能否兜住的关键；本机无令牌测不了，也不为此去取凭据）。
  若直链也 404，下一步只能动资产存放位置 —— 那要用户裁决：把 `model-assets` 由 draft 改 published
  会让 NC 许可的权重公开，我不自己动。
- **档案瘦身（同批，按 2026-10-07 用户拍板的防复发纪律）**：`Current Task` ▶ 块 4 → 3，
  最旧的「续63 补八」块用带锚点断言的脚本 `work/r17_docs/migrate_state_bu8.py` **逐字**迁往
  `.agent/archive/STATE_history_20261008.md`（43 行 / 2515 字，脚本断言迁移块内含关键句 + 迁后恰 3 块）。

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

### Notes

- Created `checkpoint-2026-10-06-2317.md` checkpoint (1 modified/untracked file(s)).

## 2026-10-06（续61 补八）— 预览联动真浏览器实测：`pause`/`ended` 前提确证（补三登记的前置假设闭合）

### 做法（一次性的现役组件挂载，不留探针件）

vite dev + 临时 `probe-preview.html`/`.ts` **直接挂载现役 `VideoComparisonPlayer.vue`**
（含 `VideoPlayer.vue` + `previewCoupling.ts` 状态机本体，不是复刻逻辑），在两个 `<video>`
上挂原生监听打印 `pause` 触发瞬间的 `el.ended`。素材 = ffmpeg lavfi 现造两路不同时长
（剪辑 3.000s / 原片 6.000s）。探针页与临时素材**已删除**，事件序列留证
`work/preview_coupling_probe_20261006.md`。

### 实测四条（全过）

- **顺序是 `pause` 先于 `ended`**，但触发瞬间 `el.ended` 已 `true` ⇒ 现役实现读**元素属性**
  `v?.ended`（`VideoPlayer.vue:75`）成立。**若当时实现成「`ended` 回调置布尔标记、`pause` 读标记」，
  在这个顺序下会失效** —— 这是本轮真正的收获：前提的方向与设想相反，实现恰好走对了。
- 一路先播完不拽停另一路：ed 3.000s 自动停后，og 仍 `paused=false` 放到 4.017s（第二轮 5.110s），6.000s 才停。
- 手动暂停仍两路同停：1.5s 点暂停，两路 `pause` 内 `el.ended=false` ⇒ 走 `reportPause`，共享控制没被削弱。
- 图标真值：一路完一路放时 = 完的路 play 三角 / 放的路 pause 双条 / 中间按钮 pause 双条；
  两路都完三者全 play。播完再点播放 ⇒ 两路从 0.000 重放（`ended` 标记被清）。

### 口径边界（诚实登记）

浏览器 = Chromium（browser-use），**不是 Electron 34 自带内核**；素材是合成片，不是用户真项目。
事件顺序与 `ended` IDL 属性由 HTML 规范决定、与素材无关 ⇒ 视为前提确证；但"打包态 Electron 里
用真素材再目检一次"这一档仍未做（要用户在 r13 里顺手确认，成本一次点击）。

### 档案与提交

STATE `Current Task` 顶部新增补八块并把补七的开放项②标为闭合；TODO P0 同步。
工作区未提交内容 = 本轮档案三件 + `work/preview_coupling_probe_20261006.md`（留证）；**按口令未提交 git**。

## 2026-10-07（续62）— 成片相邻段重复画面：定位窗宽地板导致的源区间交叠，导出/渲染层去重叠

### 症状与根因

用户报「剪出的片里两个相邻片段有重合，完整视频同一画面出现两次」。探针
`work/adjacent_overlap_probe_20261006.py` 只读现役四片 results 即复现：

- 2mkv 7/83 · test1 2/54 · test2 4/66 · test3 16/102 对**编辑轴贴接**（gap=0.00）的相邻段，
  其原片窗区间交叠 0.04~2.33s，单片重复合计 0.5~10.2s。
- 根因 = **定位段源窗宽度有 `min_span_s=2.0` 地板**（`infrastructure/config.py:138`，
  `locator_service.py:1795-1801` 夹紧居中保持），而剪辑段常只有 0.7~1.5s ⇒ 两个贴接段各自
  被撑到 2s 宽，交叠量 ≈ `2s − 编辑时长`，**数学上必然发生**。典型形态
  `ed=0.86s→src 433.6-435.6` 跟 `ed=1.00s→src 434.2-436.2`（交叠 1.38s）。
- 放大项 = 导出层把段扩成"完整镜头"（`snap_clips_to_scenes`）：实测有 `ed=2.48s` 拿 `9.94s`
  源窗，一旦扩成整镜头与邻段大片重合。
- **不是最近几批引入的回归**（10-02 的 `twofed_8` 结果同样有），此前在指标口径下不可见
  （严格指标只要 span 覆盖就算 HIT）。
- 既有边界：剪映素材卷轴 `plan_jianying_assets` 早就有"严格重叠回并"去重，所以草稿不重复；
  **成片渲染 / EDL / FCP7 XML 三处完全没有去重叠**。

### 修法（用户裁决 = 中点均分）

新增纯函数 `app/exporters.py: trim_adjacent_source_overlaps(plan, *, fps, adjacency_tol_s)`：

- 只处理编辑时间轴**贴接**（gap ≤ 0.05s）的 `main`/`low` 相邻对；**非贴接的重叠 = 真实复用不裁**
  （档案既有目检结论：连续场景内切多镜头的相邻重叠 7 段里 6 段正确，几何无法区分真错配 ⇒
  不在定位层消重叠，`min_span_s` 不动）。
- **部分重叠（含源序倒挂）**：交叠区按中点切开，谁独占左半谁取左半 ⇒ 交叠区外的各自独占部分不动。
- **包含形态**（一段整个被另一段包住）：外层**挖洞**成头/尾两条 clip（同属该编辑段，记录槽按源宽
  比例分配），内层完整保留。⚠️ 首版我写成"中点裁尾"，真实四片回放暴露它会丢掉外层独占的右尾巴
  （2mkv 少 6.58s、test3 少 0.83s 画面）⇒ **丢画面比重复更糟，改判不采用**。
- 单帧守卫：切完任一侧不足 1 帧 ⇒ 跳过该对（重复量不可见），绝不产生 1 帧闪烁段。
- 链式连叠按编辑序从左到右逐对处理，新尾段插回原位后继续参与后续配对。
- 接线：`render_movie`（split 之后、拼 clips 列表之前）+ `export_project` 的 `edl`/`fcp7_xml` 分支；
  剪映卷轴保留其既有回并语义（不重复施加第二套去重）。

### 证据

- 后端 **565 OK (skipped=2)** · API **105 OK**：+16 项纯函数单测
  （`mvp/tests/test_export_adjacent_dedup.py`：中点/包含挖洞/齐平左右/倒挂保尾/链叠/守卫/
  非贴接不裁/子 span 不参与/幂等/无重叠零变化/未排序输入/fps 未知）+ 3 项渲染接线锁
  （`test_render_movie_service.py`，含"非贴接复用仍重复"这条口径边界锁）。
- 真实四片计划层回放 `work/adjacent_dedup_replay_20261006.py`：贴接重叠
  **7/2/4/16 → 0**，重复秒 **8.99/0.53/3.73/10.22 → 0**，**并集覆盖 Δ=0.00**（一块画面不丢），
  Σ段宽减少量 = 重复秒数（裁掉的正是重复那份）。
- 零语义为**构造性**：只改导出计划层的源片侧区间，不回写 `Result`；
  已核 `measure_four_results.py` 读的是 GT 匹配字段（`strict_hit/main_hit/scene_hit`）
  ⇒ 三指标不可能变，故未重跑四片（登记：这是构造论证，非实测）。

### 仍开放

- **打包态真机渲染一次目检**（源码级证据链已齐，差"在 r14 包里渲染出来亲眼看一次"）。
- 剪映卷轴的"重叠回并"与新的"中点切开/挖洞"是**两套去重语义**，是否统一待拍板。
- 源序倒挂与包含形态在真实四片里各占多少未逐条读图确证（形态由回放给出，画面正确性未逐张看）。

### r14 出包（2026-10-07 口令「推 ci 并打包，删旧包只留 r13+r14」）

- 推送：`f3396fd..6a0ef88 master -> master`（fix + docs 两笔）。
- 构建：`scripts/build-release.ps1` 四阶段全过（`work/build_r14.log`，BUILD_EXIT=0）。
- 包 = `mvp/ui/release/Video-Locator-win-x64-20261007r14.zip` = 981,639,927 B / 7,078 条目 /
  `testzip()=None`；包内 `backend.exe` 77,448,544 B `sha16=4f5631af9e4ea51f`
  （r13 = 77,445,580 / `52ca8c225bbc3683`）——尺寸+摘要逐代递增，是"修复进包"的硬证
  （包内无散装 pyc，字符串 grep 不适用，见 [[packaged-acceptance-must-run-bundle]]）。
  `Video Locator.exe`（190,557,184 B `d6001225dce0df50`）与 ISC 图（1,613,211 B `9fc9569ae4dbd8c4`）
  与 r13 逐字节同 ⇒ 未改动层符合预期。
- 验收：accept **FAILED=0**（冒烟 26.4s ≤ 75s 阈值 · DirectML 生效 · 精排与 ISC 均 GPU 未回退 ·
  定位段数 1）· 三防 **FAILED=0** · 启动冒烟 Electron 4 + backend 1 存活 25s，用完即清 AFTER_KILL=0。
- **诚实登记**：包体级"重叠被裁开"**未在包内实测**——accept 用的 `syn`/`short20` 素材只出 1 段，
  构造不出贴接重叠；本轮证据面 = 源码级 16 项纯函数单测 + 3 项渲染接线锁 + 真实四片计划层回放
  （重叠 7/2/4/16 → 0，并集覆盖 Δ=0.00）。要闭合需在 r14 里用真项目渲染或导出一次。
- 分发包保留：r10/r11 已删（~1.9GB），留 r13（回滚）+ r14（现役）。
  ⚠️ 用户口令原话是"只留 r12、r13"，但 r12 在续61 补七 已按其上一条口令删除 ⇒ 出包前列 release/ 实况
  再按「最新+上一档」执行，这次他随即确认"只留 r13 和 r14"。

## 2026-10-07（续62 补一）— 包体级判别闭合：r13 vs r14 双臂 A/B 实测，重叠在包内确实被裁开

- **缺口**：续62 出包时登记"包体级『相邻重叠被裁开』未实测"（accept 冒烟素材只出 1 段，
  构造不出贴接重叠，原本等用户真项目渲染/导出）。本批改为**自己闭合**，且做成判别性双臂：
  唯一变量 = backend.exe（r13 `52ca8c225bbc3683` = 修复前 vs r14 `4f5631af9e4ea51f` = 修复后），
  其余（ffmpeg/ffprobe/模型/SVL env/数据目录/结果输入/导出参数）逐字相同——
  r13/r14 包内 ffmpeg.exe/ffprobe.exe 先断言逐字节同，r13 臂用 zip 抽出的完整 onedir 树
  （backend.exe 是 PyInstaller onedir，单抽 exe 缺 `_internal/` 秒退，第一次踩坑留痕）。
- **驱动**：`work/r14_trim_pkg/r14_trim_pkg_probe.py` 打包态 headless 起包 →
  `POST /api/results/load` 灌真实四片结果批（`work/stable_sort_regress/*.results.json`）→
  `POST /api/export`（edl + fcp7_xml，`min_confidence=LOW + low_policy=backup` 全量超集门槛，
  两臂同参）→ 2mkv 另跑 `POST /api/tasks/render` 渲染成片。两臂均 DirectML 生效。
- **导出腿判读**（EDL 解析 `* LOCATOR orig=` 秒制区间；XML 解析 clipitem in/out）：
  - r13 臂（修复前）：贴接重叠对 EDL **4/2/4/16**（2mkv/test1/test2/test3），
    重复秒 **4.98/1.32/3.73/11.06** ⇒ **用户报的症状在修复前包内完整复现**；
  - r14 臂（修复后）：四片 EDL+XML **全部 0 对 / 0 重复秒**；
  - **并集覆盖两臂逐 case 完全相等（Δ=0.00）** ⇒ 裁掉的只是重复那份，一块画面没丢。
- **渲染腿判读**（render 结果 `clips` 只是计数不含计划 ⇒ 用成片时长做行为判别）：
  r13 成片 **166.020s**（84 clips）vs r14 **160.974s**（86 clips，+2 = 包含形态外层挖洞的头/尾条），
  **时长差 5.046s ≈ EDL 重复秒 4.98s**（差 0.066s = 逐段取帧取整）⇒ 重复画面确实从成片里消失。
  两臂均 h264_amf / mode=copy / 72.1s 完成。
- 产物：`work/r14_trim_pkg/report.json` + `probe_run.log` + 两臂 EDL/XML/成片落盘可复查。
- ⚠️ 口径说明：这是**结果批回放**（load 已有 results → 导出/渲染），不重跑定位——定位语义零改动
  由续62 构造性论证 + 565 单测承担；本批闭合的是"trim 接线在包内真实生效"这最后一环。
  剪映卷轴仍是既有回并语义（未拍板统一），jy_draft 通道未在本探针覆盖。

## 2026-10-07（续62 补二）— 剪映卷轴去重语义统一（用户拍板「先统一」）+ 旧回并大面积丢素材缺陷发现

### 统一内容（四通道一套去重）

- `locator_service.export_project` 剪映分支：在**取材扩展（`expand_material_spans`）之后、
  `plan_jianying_assets` 之前**施加 `trim_adjacent_source_overlaps(plan, fps=source_fps)`
  ——与成片渲染/EDL/FCP7 XML 完全同一函数。位置必须在扩展之后（扩展会把相邻段重新撑出
  交叠，挂在与 EDL/XML 同一处会在扩展前跑而失效）。edl/xml 处注释同步更正。
- `plan_jianying_assets` 删除内置"重叠回并"（逐 clip 一条素材、原速顺序卷轴不变）；
  新增秒级取整撞名守卫（区间不同而 `og{a}-{b}` 撞名时加 `#k` 序号，防 extract 拿错内容；
  区间逐字节相同的真实复用仍共用同名素材文件）。
- 统一后的卷轴语义：贴接对中点切开/包含挖洞（与 EDL/XML/成片一致）；**非贴接重叠 =
  真实复用保留**（卷轴会照实出现两份，与时间线三通道一致）。

### 顺带发现：旧"回并"一直在静默丢素材（真缺陷，非本次引入）

旧回并条件 `c.orig_start < cur.orig_end` **只看源区间交叠、不问编辑轴贴接** ⇒ 只要当前
素材右界够大，其后所有**源序回跳**的 clip 被吞进当前素材、画面不进卷轴。四片计划层回放
（`work/jianying_unify_replay_20261007.py`，与续62 回放同口径）：

| case | 旧素材条数 | 新素材条数 | 旧并集覆盖 | 新并集覆盖 |
|------|-----------|-----------|-----------|-----------|
| 2mkv | 5 | 85 | 4.28s | 152.12s |
| test1 | 49 | 54 | 123.01s | 129.01s |
| test2 | 22 | 65 | 37.05s | 97.15s |
| test3 | 3 | 104 | 14.61s | 167.43s |

即旧剪映卷轴对"解说式回跳剪辑"只保留了零头（2mkv 丢 ~97%）。旧卷轴唯一保证
「相邻不重复」是靠丢内容实现的。统一后贴接对 7/2/4/16 全部裁开、覆盖全额保留。

### 证据

- 后端 **569 OK (skipped=2)**（+4：`PlanJianyingAssetsTest` 重写 +3、service 剪映接线锁
  `test_jianying_branch_trims_before_planning` +1；含集成测试改为生产同款先 trim 后组卷轴，
  断言 2 段/2 素材/总时长 3s 并集保持）· API **105 OK**。
- 计划层四片回放（上表）+ **真代码端到端**（`work/jianying_unify_e2e_20261007.py`）：
  venv 真服务对 2mkv 真跑 `fmt=jianying`——日志 `export adjacent dedup (jianying): 7 对…已裁开`，
  草稿 85 段/85 素材、相邻交叠 0、总时长 155.02s、素材文件全在位、speed 全 1.0。
- 代价（如实登记）：素材条数 = 逐 clip ⇒ 抽取转码次数变多（2mkv 5→85 次抽取），
  剪映导出耗时上升；正确性优先，可接受。

### 边界

- **r14 包不含本批**（r14 出包在统一之前）——剪映语义统一只在源码树，进包需下次出包授权。
- 回放为无 scenes 的计划层口径（不含取材扩展）；服务内实际是扩展后 trim，扩展只会放大
  交叠 ⇒ 贴接对裁开结论保守成立。2mkv 真代码端到端补了真实管线的实证。

## 2026-10-07（续62 补三）— 竞品 opcode 通道试采结案：字面通道判死、机器码绑定判死、blob 序通道打开

- **触发**：挂账项⑤（续61 入口层档 §4 留白「能证明有什么，不能证明先做哪个」）由用户拍板「试试」。
  全程只读（cutmatch-analysis 侧零写入），不运行竞品；零 `mvp/src` 改动。
- **字面 opcode 通道 = 判死（确证）**：解包树 0 个 `.py/.pyc`（复核），Nuitka+mypyc AOT —— 字节码从未存在。
- **机器码→常量绑定通道 = 判死（本轮三形态）**：
  ① LEA→blob 字节：blob VA 域内 tgt 仅 **2/172,604**（代码不直接引用 blob）；
  ② `MOV r64,[rip]→.data+.bss`：引用群存在（**3,922,992** 条；⚠️ v2 教训：.bss 在 VirtualSize 超出
     raw 的部分，`vs=0x7853F0` vs raw `0x60200`，扫错域只得 811 条）；
  ③ 平铺 `mod_consts` 假设（元素地址 = base+8×blob 序号）：**验证 FAIL** —— .bss 引用密度
     3.9M/916,462 槽 ≈ 4.3 引用/槽，共现签名无区分度（4 槽全中 base 前 20 万 tgt 就有 186,019 假阳性）；
     代理话术 4 元组（blob 序号 237/263/267/269）无一 base 通过检验。
  剩余理论路径 = 全量反汇编（.pdata 有 163,664 个精确函数边界）+ 模块 init 锚定数组基址 ——
  真 RE 工程量级，且精度侧已判「竞品没肉」，收益不匹配成本，**未立项**。
- **blob 序通道 = 打开（带边界条件）**：Nuitka 按模块+代码区分批序列化常量，**同批内 = 源码书写序**。
  验证 = 进度元组内嵌 pct 互证（single 模块代理链 4 条 blob 序 = 32%→35%→50%→50% 执行序 ✔，
  乱序插入的 100% 元组恰为分批边界，可用内嵌 pct/序号切分批次）。
  产出示例（`processing.progress.tracker` blob 序）：阶段词表 `['特征','候选','召回','定位']`
  （= 匹配管线拓扑注册序）、V2 流程注册序（V2 匹配→双路 offset 精排→补关键帧→DTW 精排→
  缓存校正→路径选择→长镜头局部召回，与 DEFAULT_PIPELINE_OPTIONS 的 dtw 旋钮互证并给出执行位置）、
  同义阶段名族 8 条（ETA 表 16 阶段别名素材）、`['本地素材预检','授权复核']`（授权在预检后）。
  **使用纪律**：blob 序证据一律标「强推断」，有内嵌真值时优先真值分段。
- 明细 `mvp/benchmark/user_case/competitor_cutmatch/FINDINGS_OPCODE_CHANNEL_20261007.md`；
  探针 `work/cm_opcode_probe{,2,3}_20261007.py` + 证据 `work/cm_opcode/evidence*.json`。

## 2026-10-07（续62 补四）— 六项立项（用户拍板），先入文档后动码

- **拍板范围**（从三类/四类逐条讲解中选定 6 项）：① 低内存收缩 batch+预取；② 子进程设备
  回报标记（UI-P3 根因解）；③ 阶段进度防抖+心跳（UX-P1 补强）；④ 独立 GPU 工作进程监督
  （任务级隔离先行）；⑤ 「指标 HIT ≠ 导出实得」锚点线改「导出实得」口径；⑥ 「换形态重试」
  探针族 4 条（a 置信非饱和 / b 两级采样 / c E3 换载体 / d 退化门换判据）。
- **本批产物 = 纯文档**：`mvp/docs/PLAN_HARDENING_SIX_ITEMS_20261007.md`（逐项：作用 /
  竞品形态证据 / 我方现状 / 实施要点 / 验收口径 / 边界风险 + 执行顺序建议）；
  TODO.md P1 打勾清单 + STATE Next Actions 入册。
- **执行顺序建议**：②→①→③ 小三件一批（纯增量零定位语义）→ ④ 单独批（基础设施，任务级
  进程隔离先行）→ ⑤ 口径批（建议与搁置的「性能口径三处对齐」同批处理对外数字）→
  ⑥ 研究线并行（沙盒纪律：零 runtime，PASS 才接线，门槛 = 三指标零回退 + 口袋救回 ≥1/3）。
- 零代码改动；等口令选择先跑哪批。

## 2026-10-07（续62 补五）— 六项立项小三件 ②①③ 落地（门禁全绿）

- **② 子进程设备回报标记**（UI-P3 根因解）：
  - backend：`locator_service.backend` 惰性解析点打一次性 stdout 标记行
    `BACKEND_DEVICE <actual_name> <actual_type>`（与 BACKEND_LISTEN 同风格；懒构建点 = 真实解析点
    ⇒ 必为实际值；观测行异常静默不阻断）——新增 `mvp/tests/test_device_announce.py` 2 项。
  - UI：`session.initApp` 在 READY 前 `loadDeviceSettings()` 填徽标（此前只在断→通重连时刷）；
    `buildIndex` 不再用索引 backend 标签（`IndexMeta.backend` = 建索引时冻结历史标签）覆盖徽标
    ——徽标唯一权威 = `/api/settings/device` actual 三元组。新增 `sessionDeviceBadge.test.ts` 2 项。
- **① 低内存收缩 batch+预取**：
  - 新增 `mvp/src/media/resource_budget.py`：`compute_media_budget` 纯函数三档
    （usable = available − 2GB reserve；≥6GB=ok 现役默认 / ≥2GB=tight(2 线程,64 帧/簇) /
    <2GB=critical(1 线程,16 帧/簇下限)；探针不可用 ⇒ unknown 全默认零语义）；
    `probe_memory` = GlobalMemoryStatusEx → psutil → (None,None)。
  - 接线：`_grab_frames_parallel` 线程数与档位取 min；`isc_l2_index.build_tp_index` 新参
    `max_cluster_frames`（簇切小只改批次不改帧，times/feats 逐字节一致）；
    `/api/settings/device` 响应补 `low_memory_mode/memory_tier/grab_workers/max_cluster_frames`
    （schema 同步）。新增 `mvp/tests/test_resource_budget.py` 7 项。
- **③ 阶段进度防抖+心跳**：
  - 新增 `mvp/api/tasks/debounce.py` `ProgressDebouncer`：同阶段连续帧按最小间隔（0.5s）合并
    只留最新 held；阶段切换/终态(percent≥100)立即直通；held 在下次发布前先补发（旧值先于新值，
    无信息丢失）。analyze/render 两 worker 的 on_progress 接线。新增
    `mvp/api/tests/test_progress_debounce.py` 6 项。
  - 心跳：`Task.last_event_at`（各状态变更打戳，to_dict 暴露，UI 契约同步）——轮询方据此区分
    「没消息但在动」与「真卡死」（竞品 heartbeat/progress_updated_at 同语义）。
    进度条 0.2s 宽度过渡既有，无需改 UI。
- **门禁**：后端 **578 OK (skipped=2)**（569+9 新增）· API **111 OK**（105+6）·
  vitest **144 全绿**（142+2）· 双 typecheck 干净。零定位语义（① 只在内存紧张档改变批次/
  并发，宽裕档全默认；②③ 观测与发布层）。

## 2026-10-07（续62 补六）— ④ 独立 GPU 工作进程监督：任务级进程隔离落地（门禁全绿）

- **作用**：DML 段错误/驱动崩溃不再拖垮整个后端——子进程硬崩只损失单个任务
  （task 转 failed 带退出码），主服务与其它任务存活（续6/续43 两次段错误教训的工程收口）。
- **新增 `mvp/api/tasks/isolated.py`**：
  - `run_worker_isolated`：spawn 子进程 + 监督循环（进度队列 0.5s 轮询 + 存活检查）；
    **无信封的异常退出 = 段错误/硬崩 ⇒ `mark_failed("工作进程异常退出（exitcode=…）")`**；
    取消 = 父进程 `terminate`（立即生效，绕过协作式取消）；spawn 不可用 → 返回 False
    ⇒ `run_worker` 回落线程内（`SVL_TASKS_IN_THREAD=1` 同样强制回落，调试逃生口）。
  - 子进程 `_child_main`：**自建 `SourceLocatorService()`**（SVL_* env 同源），任务主体复用
    worker 新抽的 `execute_task`（merge→locate / render 两路径父/子共用，不碰 task 状态）；
    进度/结果/错误经 multiprocessing.Queue 信封回传；`q.close()+join_thread()` 确保 feeder 冲刷。
  - 渲染批经 pickle 传参（提交时锁定的 ResultBatch，纯 dataclass 可序列化）。
  - 故障注入钩子 `_test_force_hard_exit`（payload 顶层或 render_params）：`os._exit` 硬崩模拟，
    仅供监督路径单测。
- **接线**：`TaskManager(..., isolated=)`（dependencies 生产=True，测试默认 False）；
  `run_worker/run_render_worker` 加 `isolated` 分流；`run_backend.main` 补
  `multiprocessing.freeze_support()`（打包态 Windows spawn 必需；非冻结 no-op）。
- **测试**：新增 `mvp/api/tests/test_isolated.py` 6 项——真实 spawn×3（硬崩注入 →
  failed(exitcode=123)；应用层错误信封 → failed(LOC 话术)；提交即取消 → terminate+cancelled）
  + payload 往返/pickle/环境开关。教训留痕：首轮硬崩用例失败 = 测试把注入键塞进了自己的
  payload 局部变量而监督者自建 payload——钩子改经 render_params 携带后 6/6 过。
- **边界（诚实登记）**：① 监督重启（崩溃计数+冷却）未实现——任务全为用户显式发起、
  无自动重试消费方，等批量/自动重跑形态再立项；② 打包态 spawn（freeze_support 路径）
  未在包内实测，验证挂 r15 accept；③ 隔离子进程不继承父进程内存缓存（索引/嵌入缓存
  在文件层，天然共享；嵌入 memo 首任务冷启动属预期代价）。
- **门禁**：后端 **578 OK (skipped=2)** · API **117 OK**（111+6）· vitest **144 全绿** ·
  双 typecheck 干净。零定位语义（执行位置变化，结果口径不变）。

## 2026-10-07（续62 补七）— ⑤「导出实得口径」用户裁决不做，丢回搁置区

- 六项立项中的 **⑤（指标 HIT ≠ 导出实得：锚点线改「导出实得」口径）** 用户裁决**不做**，
  与「性能口径三处对齐」「成片缺口标记」同列搁置区（重启需用户再提；两者同批处理最合适——
  都动对外数字与话术）。
- 现状不受影响：并列口径 `main_hit` 与 LOC-2003 导出告警**此前已落地**，指标/导出的差异
  已有告警可观测；本次搁置的只是"锚点线切换 + 对外数字改口径"这最后一步。
- 六项立项剩余 = **⑥ 换形态探针族**（研究线，沙盒纪律）。
- 续63 复核补注：⑥b（两级采样）的**立项理由需要重述**——档案已有「2fps vs 1fps 密度探针
  实测：生产严格净 0、建索引 ×2 耗时」，即密度↑不改落点；⑥b 是反方向（粗筛+邻域密验），
  按同一逻辑精度上限有限，真正的可兑现收益在**建索引耗时/首屏延迟**（现役 22~31 分钟/片）。
  建议门槛相应改成「三指标零回退 + 建索引耗时下降达标」，口袋救回 ≥1/3 仍作回退保险。

### Notes

- Created `checkpoint-2026-10-07-1103.md` checkpoint (1 modified/untracked file(s)).

## 2026-10-07（续63）— 导出计划层常态守卫（序列收口+不变式自检）+ 剪映逐 clip 代价实测 + r15 出包（accept 抓到 ④ 两处包内缺陷）

- 触发：用户对「推送 / r15 / ⑥」三件口令项回「按你的想法来」⇒ 按我给的排序执行：
  推送 → 计划层守卫 → 代价量化 → r15 出包。
- 已推：`6a0ef88..aba3a21 master`（实测 **11 笔**，档案写的 12 笔为计数过期）。

### 一、导出计划四通道不变式常态守卫（本批核心）

- **根因判断**：续62 两批真缺陷都不是某个函数写错，而是**同一套五步计划序列在
  `locator_service` 里抄了三遍**（成片 / EDL+XML / 剪映）——重复编排代码本身就是
  「改一处漏一处」的载体（去重叠第一次就漏了剪映）。
- **收口** = 新增纯函数 `exporters.prepare_channel_plan(batch, channel=…, …)`：
  `build_export_plan → fragment_warnings → snap_clips_to_scenes →
  split_clips_at_boundaries →〔expand_material_spans〕→ trim_adjacent_source_overlaps`
  顺序硬固定；`channel` 只进 stats 不参与分支，通道差异**只允许是参数差异**；
  stats 自带 `audit_pre_trim` / `audit` 两份体检。成片腿 + NLE 腿（含剪映分支）全部改调它，
  顺带删掉 6 个裸导入与两处重复展开。
- 新增只读函数 `exporters.audit_source_overlaps(plan)`：贴接重叠对/重复秒（=违规）、
  真实复用对/秒（=不动它）、并集覆盖、零宽。**必须扫全对**——首版只看编辑序紧邻对，
  真实复用常隔着中间段（第 1 段↔第 3 段），是自己写的锁把它逼出来后改的。
- **结构锁**（新 `mvp/tests/test_export_plan_guard.py`，19 项）：AST 扫 `mvp/src`，
  `build_export_plan` / `trim_adjacent_source_overlaps` 的产品调用点只允许存在于
  `prepare_channel_plan` 内 ⇒ 第五个出口漏接 = 测试红；另锁「扩宽在前、trim 在后」
  （顺序反过来会漏裁被扩宽重新撑出的交叠）、三时间线通道同 plan、
  三个 service 入口运行时确实经过 helper（spy）。
- **常态脚本**（入库）`mvp/scripts/check_export_plan_invariants.py`：真实四片结果批 × 四通道，
  五条判据 + 退出码（可挂出包门槛）。实测（默认门槛 MEDIUM/exclude，有索引腿）：
  贴接重叠 2/0/3/7 对 → **全 0**，并集覆盖 Δ=**0.00**（2mkv 134.094s / test1 84.346s /
  test2 74.037s / test3 119.963s），三通道同 plan=是。
- **诚实登记**：`reuse_pairs` 降级为**只报不断言**——有索引腿 2mkv/test3 首跑触发，
  机制 = 外层被挖洞后，它与第三段的共享区间让给了内层，复用对数下降而画面仍被覆盖
  （②覆盖不变式已锁住真正要防的东西）。断言它持平会把正确的去重判成违反。
- 门禁：后端 **597 OK**（578 基线 + 19 新锁）。

### 二、剪映逐 clip 代价实测（补二欠的账，计划层代理量 + 源码树双臂墙钟）

- 计划层（同一守卫脚本，唯一新增列）：2mkv 素材 **64 条 / 宽度合计 815.75s / 去重后仍需
  抽取 56 次 701s**；对照旧回并腿 2 条 / 20s —— 那是吞掉 ~96% 画面换来的，**不可比**。
  test3 = 65 条 / 895.38s / 抽取 52 次 755s。代理量与实测文件数逐字对上（56=56）。
- 源码树三臂（`work/jianying_cost_20261007.py`，同脚本、逐臂先 rmtree 防白拿别人产物，
  DirectML 断言在位）：2mkv A(扩宽)=**81.1s**/56 文件/115.8MB，B(core 不扩宽)=33.0s/64 文件
  /22.0MB，C(edl 纯文本)=0.0s ⇒ A/B=**2.46**；test2 A=**89.2s**/39 文件/256.8MB，B=29.5s ⇒ **3.02**。
- 判读：代价主要来自**取材扩宽**（核心窗→整镜头），不是「逐 clip」本身；量级 = 分钟级，
  不是当初担心的十倍级 ⇒ r15 可以出，不需要为性能回退正确性。

### 三、r15 出包：accept/构建首跑抓到 ④ 的两处包内缺陷（都已修，且都补了硬断言）

- **第一红在构建阶段 1**：渲染层 `vue-tsc` 5 个 TS 错——`MockServiceAdapter` 三处 `TaskJson`
  缺 ③ 新增的 `last_event_at`；`sessionDeviceBadge.test.ts` 夹具写了契约里不存在的 `status`。
  ⇒ **更正登记**：续62 补五/补六 自报「双 typecheck 干净」**不实**，当时只过了
  `typecheck:desktop`，渲染层 config 一直是红的（vitest 不做跨文件类型检查，所以 144 绿掩盖了它）。
  修复后 app+desktop 双绿、vitest 144 绿。
- **第二红在包体 accept**（新加的隔离检查之一，预期红→抓到真因）：包内 stdout 缺
  `patch reranker device=dml` / `isc refine device=dml`，「精排/ISC 未回退 CPU」两条硬断言误红，
  而任务本身成功、`reaped exitcode=-15`。两层原因：
  1. 父进程拿到终态信封后立刻 `terminate` 仍在跑收尾的子进程；子进程 stdout 是管道
     （块缓冲）⇒ 日志尾巴整段被吞。修 = 正常终态先 `join(CHILD_GRACE_S=10s)` 自然退出，
     取消/硬崩路径不变（仍立即 terminate，那是隔离语义）。
  2. **真根因**：子进程不走 ASGI lifespan，而 `configure_logging()` 挂在 lifespan startup 上
     ⇒ root logger 没有 handler，INFO 记录被 `lastResort(WARNING)` 丢弃。后果不止 accept：
     包内 stdout 与支持档 `video_locator.log` **一起缺整段分析过程记录**，正是本项目当产品
     能力做的「三级日志 / 客服按日志找真因」。
  修 = `_child_main` 自行 `configure_logging()`（幂等、读 SVL_LOG_DIR 与父进程同落盘）
  + stdout/stderr 行缓冲 + 退出前 flush + 一条 `isolated child booted pid=` 的 INFO；
  顺带把 payload 带上父进程 `task_id` 并让子进程改调 `_task_from_payload`
  （父子日志可同 task_id 串联；同时消掉一份重复的 Task 构造）。
- accept 清单固化 4 条隔离断言：spawn 启动行 / 子进程 INFO 进得到包内 / `reaped exitcode=0` /
  未被误判硬崩。API 门禁 = **120 OK**（+2：宽限收割顺序、子进程日志落盘真 spawn 锁）。

### r15 出包（2026-10-07 12:25 构建 / 12:33 打包，用户口令「按你的想法来」）

- 包 = `mvp/ui/release/Video-Locator-win-x64-20261007r15.zip` = 981,659,630 B / **7,078 条目** /
  `testzip()=None`；包内 `backend.exe` 77,467,467 B **`sha16=d45656f585826f4a`**
  （r14 = 77,448,544 / `4f5631af9e4ea51f` ⇒ 尺寸+摘要硬证）。
- 验收：**accept FAILED=0**（冒烟 24.1s ≤75s · DirectML 生效 · 精排与 ISC 未回退 CPU ·
  段数 1 · **隔离子进程在跑 · 子进程 INFO 进得到包内 · 未误判硬崩**）·
  三防 **FAILED=0** · 启动冒烟 Electron 4 + backend 1 存活 30s，用完即清 `AFTER_KILL=0`。
- **包体剪映探针**（新 `work/r15_jianying_pkg/probe.py`，`FAILED=0`）：EDL 64 事件 /
  贴接重叠 0 对 / 覆盖 134.12s（计划层 134.094s）；卷轴 segments=materials=64、
  落盘素材 **56** 个（同区间复用生效）、总宽度 **815.75s** 与并集 **531.0s** 与计划层逐字相同、
  全条 speed=1.0；包内墙钟 **80.7s**（源码树 A 臂 81.1s ⇒ 包体无额外劣化）。
  探针同时是抓回「时间线通道误扩宽」回归的地方（EDL 覆盖当时读出 531s）。
- **待裁决登记**：卷轴按素材宽度首尾**重排**后，计划层故意保留的「非贴接真实复用」
  在卷轴上呈**紧邻重复**（2mkv 2 对 / 37.0s，均已被 LOC-2002 重复认领告警识别，
  且 37.0s ≤ 计划层真实复用 487.25s）。时间线三通道无此形态。探针口径改为**只报不判负**，
  要不要在卷轴也裁开这类重复 = 新决策点（未自动做）。
- 分发包现状：`release/` = r13 + r14 + r15 三份并存；按「最新+上一档」应删 r13（~0.98GB），**等口令**。

### 续63 补一 — 卷轴紧邻重复的机制确证（读图 + 计划层反查），升格为待裁决项

- 上面「待裁」那条不停留在几何量：取了 r15 包内草稿的两对重复素材各 3 帧做接触表
  （`work/r15_jianying_pkg/repeat_sheet.png`）逐张看过 = **都是真实画面**（A 组
  `og1373-1397` 掩体门/林中人物/天线塔；B 组 `og1997-2024` 女角色持械/桌上水壶/回头），
  不是黑场或冻结帧 ⇒ 重复是用户真能看见的。
- 反查计划层（同一序列、不跑 trim）拿到成因，**与"trim 漏裁"无关**：
  - A 对 = 编辑轴 `(31.17,32.28)` 与 `(33.31,34.9)` 两条 clip，**间隔 1.03s**；
  - B 对 = `(91.24,92.55)` 与 `(93.79,95.59)`，**间隔 1.24s**；
  - 两者都 > 贴接容差 0.05s ⇒ `trim_adjacent_source_overlaps` 按既定口径**故意保留**
    （档案目检结论：连续场景内切多镜头的重叠多数正确，非贴接=真实复用）。
  - 同区里另外 4 条**贴接** clip（95.59/96.48/97.45/98.9 首尾相接）确实被裁开了 ⇒ 去重叠在干活。
- **机制结论**：卷轴按素材宽度**首尾重排**（`plan_jianying_assets` 累加 placement），
  把编辑轴上"中间还夹着别的内容"的复用，变成时间线上**紧邻的同一段画面**
  （A = 同一素材文件连放两遍 24s；B = 27s 整镜头后紧跟其 13s 前缀）。
  时间线三通道无此形态（那里空隙是真的）。旧"重叠回并"恰好掩盖过它——代价是吞掉 96% 覆盖。
- **这不是回归、也不该由我自动改**：两条候选修法都要动产品语义，等用户拍板——
  (a) 卷轴内对「与前一条源区间**完全相同**的相邻素材」去重（A 型纯重复，改动最小、不碰时间线）；
  (b) 卷轴 placement 改用**真实编辑轴位置 + 保留空隙**（更贴"可溯源素材清单"原意，
      但等于给卷轴引入"空洞"，与成片 2026-09-29「未定位段跳过不填黑场」的拍板方向相反）。
  现状 = 只报数 + LOC-2002 重复认领告警已识别（2mkv 实测 2 对 / 37.0s，
  均 ≤ 计划层认定真实复用 487.25s）。

## 2026-10-07（续63 补二）— 成片包内实测升为常设验收 + 抓到渲染从未隔离 + 卷轴去紧邻同素材重复 + ①③ 的 UI 接线

- **成片通道包内实测**（`work/r15_render_pkg/probe.py`，对已发 r15）：
  `clip_ranges` 与源码树 `channel="movie"` 计划 **64 段逐字段相同**、成片时长 136.366s vs
  Σ clip 宽度 136.344s、`encoder=h264_amf mode=copy`、成片顺序里紧邻段交叠 **0 对**
  ⇒ 续63 的序列收口没有改变成片通道口径，缺口闭合。顺带把这条腿升成常设验收
  **`mvp/scripts/accept_packaged_render.py`**（真素材缺失时 skip 并登记"未实测"）。
- **该实测抓到一处真缺陷**：`TaskManager.submit_render` 调 `run_worker` 时**漏传 `isolated`**
  ⇒ 渲染任务一直在线程内跑，"崩溃只损失单任务"对成片不成立，而档案写的是"analyze/render
  子进程化"（**今天第二处自报口径与实况不符**，同族 = 同型调用点漏接）。
  修 = 传 `isolated=self._isolated`；锁 = spy 断言两条 submit 路径都传 True + AST 扫
  `manager.py` 任何 `run_worker(` 调用点必须显式带 `isolated=`。
  新常设脚本对 r15 如实报 `R2 FAIL`（修复只在源码树，需 r16 才进包）。
- **卷轴去「紧邻同素材重复」（默认开，`export.jianying_drop_adjacent_duplicates`）**：
  `plan_jianying_assets(..., drop_adjacent_duplicates=True)` 只砍**剪辑序紧邻且源区间逐字节
  相同**的后一条；嵌套前缀型（27s 整镜头后跟其 13s 前缀）与"中间隔着别条素材"一律保留。
  实测 2mkv 素材 64→**63** 条、卷轴宽度合计 815.75→**791.75s**（去掉那 24s 连放），
  **并集覆盖 531.0s 不变**（相同区间本就不增加覆盖 ⇒ 一块画面不丢）；test3 65→64 条、
  895.38→889.38s。守卫脚本判据同时从"数个数"升级为**按同一规则重算后逐条比对**
  （能抓多删/漏删/顺序错），四片 × 四通道仍 FAILED=0。
- **机制更正（比 续63 补一 的说法更准）**：紧邻重复**只在剪映卷轴**出现——成片实测 0 对、
  EDL/XML 因保留编辑轴空隙也是 0 对。根因不是"重排"本身，而是
  **「取材扩宽到整镜头」×「紧凑拼接」** 的组合：两条核心窗互不相交的 clip 扩宽后可能变成
  同一个整镜头，拼接后就成了同素材连放。⇒ 补一 里"时间线三通道无此形态"的表述对成片
  是靠实测成立的（0 对），不是靠推理；已按实况改写档案。
- **①③ 的 UI 接线（此前只到 API/契约层，用户看不见）**：
  `DeviceSettingsJson` 补 `low_memory_mode/memory_tier/grab_workers/max_cluster_frames`；
  session store 加 `lowMemory` computed（未降档或探针 `unknown` ⇒ 返回 null，宁缺毋假），
  侧栏 `BackendStatusIndicator` 多一行 warn 徽标（如"内存偏紧 · 抓帧 2 线程"）；
  analysis store 记 `lastEventAt`（提交即打点，轮询用后端 `last_event_at` 覆盖，终态清空），
  `ProgressPipeline` 在运行中且 **≥120s 无新事件** 才显示"已 X 分 X 秒没有新进展"
  ——不做"还在动"的正向噪音，只在真到可疑时长时说一句。
- 门禁：后端 **602**（+3 卷轴去重锁）· API **122**（+2 渲染隔离锁）· vitest **146**（+2）·
  app/desktop typecheck 与 renderer build 全绿。
- **未闭合登记**：两处新 UI 的**浏览器目检没做**——`evaluate_script`（注入 store 状态）与
  `take_screenshot` 被权限分类器拦下，未重试。已做到的等价证据 = 模板表达式经 vue-tsc 类型检查、
  `vite build` 编译通过、行结构与侧栏既有两行同构；**低内存行在真机上尚未亲眼见过**
  （本机内存档 = ok ⇒ 常态不显示，要看到得在真降档机器上或临时改 Mock 值）。

## 2026-10-07（续63 补三）— 两处新 UI 的真机浏览器目检（用户放行）+ 抓到并修掉一个失效的 CSS token

- 目检方式 = vite dev（Mock 适配器）+ 内置浏览器；状态用运行时注入 Pinia store 造
  （**只改页面内存态，未动任何源码/Mock 假数据**），截图两张 + 计算样式/几何量逐项读回。
- **低内存徽标行**：侧栏三行 `连接 / 后端 / 内存`，文案「内存偏紧 · 抓帧 2 线程」，
  右对齐、单行不换行；四档态逐一目检 + DOM 计数核过 ——
  `tight`=显示、`critical`=显示（「内存紧张 · 抓帧 1 线程」）、
  `low_memory_mode=false`→**不占行**、`memory_tier=unknown`→**不占行**、
  旧后端不带字段→**不占行**（宁缺毋假成立）。溢出量化：`.backend__v` scrollWidth≤clientWidth、
  `aside.side` 无横向溢出（宽 239px，徽标 129px）、`document` 无横向滚动。
- **心跳提示**：`last_event_at` 距今 183s/200s ⇒ 出「已 3 分 16 秒没有新进展」并随秒级 tick
  递增（3:16→6:16 连续观察）；30s ⇒ **不显示**（阈值 120s 生效，无正向噪音）。
  meta 行单行 24px 高、无溢出、取消按钮不被挤掉。
- **目检抓到的一处真缺陷**：`.pl__stale` 我写的是 `var(--c-warn, #d9a441)` ——
  项目 token 实际叫 **`--warn: #f2c94c`**（`src/styles/tokens.css:43`），`--c-warn` 不存在
  ⇒ 计算色静默落到兜底 `#d9a441`（读回 rgb(217,164,65) 才暴露）。改成 `var(--warn)` 后
  读回 rgb(242,201,76)，与 `StatusBadge` 的 warn 档一致。教训：**CSS 变量名不能靠印象，
  写 `var(--x, 兜底)` 时兜底会掩盖拼错的 token 名**，颜色对不对要在浏览器里读 computed style。
- 顺手排除一个假警报：截图里 "92.1%" 看着像被划了删除线，逐元素读 `text-decoration-line`
  全为 `none`、元素间距 12px 无重叠 ⇒ 是进度条边缘与文字基线对齐造成的视觉错觉，非缺陷。
- 复核后门禁不变：后端 602 · API 122 · vitest 146 · app/desktop typecheck 绿（CSS 改动不涉及类型）。
- **落盘证据**（`work/ui_accept_r15ui/`）：`mem_row_visible.png`（侧栏「内存偏紧 · 抓帧 2 线程」行）
  与 `heartbeat_stale.png`（meta 行「已 5 分 34 秒没有新进展」，色值读回 rgb(242,201,76)=`--warn`）。
  两张都逐张读回确认画面里真有被断言的那个元素——第一版截图因页面滚动把 meta 行裁掉了，
  文件名却写着 "both states"，已重拍并删掉错名文件（**证据要能自证，命名不能超出内容**）。
  造态方式 = 运行时注入 Pinia store（`low_memory_mode`/`last_event_at` 等），未改任何源码或 Mock 数据。

## 2026-10-07（续63 补四）— 用户裁决：撤掉 ①③ 的两处 UI 显示（黄字心跳提示 + 侧栏内存行）

- 口令 = 「这个黄字和后端下面那个内存就不要显示出来了，删掉吧」（附两张截图指认）。
- **删的范围（只删显示，不动契约）**：
  - `BackendStatusIndicator.vue` 的「内存」行 + `TIER_LABEL` + `lowMemory` prop；
    `AppSidebar.vue` 不再传该 prop；`session.ts` 删 `lowMemory` computed（连带不再需要的
    `computed` 导入）。
  - `ProgressPipeline.vue` 的 `.pl__stale` span + `STALE_AFTER_S`/`staleSec`/`staleLabel` +
    `heartbeatAgeSec` prop + 样式；`AnalysisPage.vue` 删 `heartbeatAgeSec` computed 与传参；
    `analysis.ts` 删 `lastEventAt`（无消费方 ⇒ 不留死代码）。
  - 两条对应 vitest 用例一并删（显示没了，锁留着就是假绿）。
- **保留**：后端 `GET /api/settings/device` 的 `low_memory_mode`/`memory_tier`/`grab_workers`/
  `max_cluster_frames`、任务对象的 `last_event_at`、以及 `types.ts` 里对应的可选字段声明
  （= 线上契约镜像，与 Mock 适配器 `TaskJson.last_event_at` 一起是 typecheck 的必需项）。
  ⇒ ①③ 回到**"能力在后端、界面不呈现"**，这是用户裁决而非欠账，别再当缺口登记。
- 复验：vitest **144** 回到 r15 基线 · app/desktop typecheck 双绿 ·
  浏览器真机复看（注入同样的触发数据 `low_memory_mode=true` + 心跳 15 分钟）⇒
  侧栏只剩 `连接/后端` 两行、`.pl__stale` 不存在、meta 行 = 「分析中 92.1% 15:01 取消」，
  侧栏与页面无横向溢出。证据 `work/ui_accept_r15ui/after_removal.png`。
- 门禁：后端 602 · API 122 · vitest 144 · 双 typecheck 绿（本轮只动 UI 层）。

## 2026-10-07（续63 补五）— 修复链进度改加权连续 ramp（真症状：单条腿能让进度条静止几分钟）

- 起因 = 用户报「输出的时候一直卡 92.1 没反应」。核下来分两层：
  - **92.1 这个数是假的**：它来自我目检时往 Pinia 注入的道具值（`progress.current=92.1` +
    把第 4 步标 running），截图顶部那条「MOCK 模式 —— 当前显示的是界面假数据，未连接 Python
    后端」就是证据；现役发射点里 phase-less REFINE 事件**一条都没有**，92.1 算不出来
    （只有旧回归锁 `map_progress_stage(REFINE, 0, 82)` 会给出它）。
  - **但症状本身是真的**：打包日志 10-06 那次运行 shot_split 18:11:36 → patch_refine 完成
    18:20:41 → isc_refine 完成 18:29:55，**单条腿能让进度条停 9 分钟**。
- 根因 = 修复链 5 个粗步（`_FIX_STEPS=5`）把 9 条腿挤在一起，而两条重腿
  （`_apply_fast_global_anchor` / `_apply_dense_start_recheck`，每段抓密帧+嵌入）
  **腿内一条事件都不发**。
- 改法（**只改进度发射，执行顺序/开关/结果口径逐字不变**）：
  - 两条重腿加可选 `on_tick(done, total)` 参数，在各自 per-result 循环首行回报；
  - 修复链 ramp 从 5 粗步改成 **24 单位加权**：重腿占大头（锚点 1→8、密集复核 9→14），
    其余每条腿有"进入/完成"边界；`_fix_to()` 单调钳制不回退、同值不重发，
    `_fix_tick()` 把 done/total 映射进该腿区间的 90%（末 10% 留给收尾边界）。
- 锁：`FixChainTickTest` 3 项（两条腿逐段 tick 次数 = 段数、不传回调照常跑）
  + API 侧 5 个新映射点（fix/24 的 92.0/92.2/92.8/93.8/94.0）。
  门禁 = 后端 **605** · API **122**（UI 未动）。

### 续63 补五 追加 — 按实测耗时重排 92→98 区间宽度（run1 数据逼出来的第二次改）

- run1（test2 真机 21.2 分钟修复链）读数分布暴露两件事：
  1. 我给 fast_global / dense_recheck 加的逐段 tick **在这个项目上不是瓶颈**——
     锚点+密集两条腿从 91.0% 到 93.2% 只用了 6 秒（一个轮询间隔就跨过去了），
     我当初是按"哪条腿听起来重"分配权重的；
  2. 真平台期是 **字牌复核（OCR）腿 255 秒**（当时只有边界事件）⇒ 已补 `on_tick`
     并把权重从 15→15 改成 15→19；
  3. 第二个"不动"来源是**显示分辨率不是缺事件**：ISC 只分到 1 个点 ÷ 67 段
     ⇒ 每 40~58 秒才跳一个 0.1 读数。
- 改 = `_PHASE_RANGES` 宽度按实测占比重排（fix 20%→1.2 点、split 3%→0.3、
  patch 39%→2.3、ISC 38%→2.2），注释里写清依据。锁：API 映射断言按新值逐点更新（122 OK）。
- run2 中途停掉（只为验证中间状态不值 25 分钟），直接跑最终态 run3 验证。

### 续63 补五 追加二 — run3 又打脸一次，最终按"耗时占比"分配显示宽度（进度链这条线到此为止）

- run3（字牌 tick 已加、宽度仍是 fix 1.2 点）实测：**字牌腿 363 秒全程显示同一个 92.8** ——
  逐段 tick 确实发了，但 67 段挤在 `1.2 点 × 4/24 单位 = 0.2 点` 里，一位小数四舍五入后
  全被吃掉。**教训：按"腿的数量"分配显示宽度是错的，必须按耗时。**
- 最终分配（依据 run1 1274s + run3 复核的实测占比：修复链 28% / 拆分 3% / patch 38% / ISC 31%）：
  - `_PHASE_RANGES`：fix 92.0→93.7（1.7 点）、split 93.7→93.9（0.2）、
    patch 93.9→96.2（2.3）、ISC 96.2→98.0（1.8）；
  - `_FIX_UNITS` 24 → **48**，内部按耗时给：锚点 1→6、密集 7→9、**字牌 10→42（32 单位）**、
    序列 44、时序 45、冲突与歧义 47、连续重复+一致性 48。
- 跳格估算（模型 = 点数 ÷ 段数 × 每段实测秒数；该模型在 patch 上被 run3 实测验证：
  预测 28s vs 实测 18~42s 一致）：
  - 字牌 1.13 点 ÷ 67 段 × 5.4s/段 ⇒ **约 32s 一跳**（改前 363s 不动）
  - patch 2.3 点 ⇒ 实测 18~42s（改前 14~38s，读数密度 36→49）
  - ISC 1.8 点 ÷ 67 段 × 7.1s/段 ⇒ **约 27s 一跳**（改前实测 40~58s）
  ⚠️ 字牌与 ISC 两个数是**模型推算**，不是改后实测——改完没有再跑 27 分钟验证趟（用户要求收线）。
  锁里带了一条模型断言（字牌跳格 ≤40s），真机复核留给下一次自然运行。
  **[2026-10-08 续63 补八 已闭合]** 独占实测 + 包内真机轮询都做了：字牌腿均值 23.7~24.9s（**优于**预测 32s）、
  最大停留 41.4~41.6s（**超** 40s 阈值）；ISC 最大 33.8s（包内）/37.3s（源码树）。
  => 改善成立（改前 363s 冻结），但那条锁按**均值**建模、用户感知按**最大值**，口径要改（待拍板）。
- run3 中途停掉（它测的是中间态权重，继续跑只验证旧配置）。
- 门禁：后端 **606** · API **122**（映射断言按最终值逐点重写 + 一条跳格模型断言）。

## 2026-10-08（续63 补六）— ⑥b「两级采样」探针 = 判负关闭（四片同脚本成本实测 + 两片精度实测 + 逐图复核）

- **触发**：用户对三件待口令项回「3」= 只跑 ⑥b，且按 STATE 建议**换判据**
  （主 = 建索引**实测**耗时下降；硬门 = 三指标零回退；保险 = 口袋救回 ≥1/3）。
  沙盒纪律：`mvp/src` 一行未动，PASS 才接线的门槛没到 ⇒ 不接线、不 bump 生产 `feature_version`。
- **三臂**：A10 现役 1.0fps（复用生产 `.idx`，**四片全部**先断言与同脚本隔离重建
  `times`/`features` 逐字节 identical=True）· B05 = 0.5fps 粗筛（隔离根重建）·
  C05D = 粗筛 + 命中邻域 2fps 密验（窗取自 **B05 自己的候选** ±12s 合并；密帧走
  `grab_grid_times` 冻结同帧契约，不用 `iter_frames`——其合成标签比真实 pts 晚 ~0.5s，续52-C；
  合并后重建场景/事件表）。定位入口 = 生产 `srv.locate(..., index_bundle=…)`，唯一变量 = 源片网格。
- **成本实测（四片同脚本双臂）**：1fps 2477.1s=41.3min → 0.5fps 1309.6s=21.8min，
  **比值 0.529**（区间 0.481~0.609），体积 53.2→26.0MB ⇒ **主判据成立**。顺带复核前案
  13.6 帧/秒折算模型：低估 2.3%~17.1%（四片合计低估 8.3%）。
- **精度实测（两片 59 条）**：严格 58→52（−6）、**导出实得 56→44（−12）**、场景 58→56、
  负例持平，口袋 p30 回退 ⇒ **硬门崩，⑥b 判负**。
- **两片损害形态不同**（本批最有价值的发现）：test2 = **证据层**（`no_evidence` 1→9、
  编辑侧切分并段 67→65 行）⇒ 严格直接掉 5；2mkv = **导出层**（严格只掉 1，但主 span 变宽/
  位移、命中改由子 span 兜住 ⇒ 导出实得掉 6）。⇒ 10-03 的「grid2 零代价」包络**结论仍成立但
  不足以支撑决策**：它只扰动最终 span，看不见证据层与主/子归属层（正是它 §6 边界 1 自己写明
  「不覆盖、若发生损失可能更大」的那一类——现在发生了并且量出来了）。
- **密验腿（⑥b「换形态」本体）**：C05D 在 test2 上 **0 翻转、三指标与对照臂逐格相同、
  失败分布逐字相同** ⇒ 精度救得回；但命中窗并集 = 源片 **33.4%**，补帧后总嵌入预算
  5055 帧 ≈ 1fps 的 5051 帧，墙钟 265.0+395.0=660.0s > 435.0s（**1.52×**），
  locate 段还因网格变密多花 425s（1307.6→1733.0s）⇒
  **「密验救回精度」的本质就是把网格补回 1fps，所以不可能既救精度又省成本**。
  盈亏平衡：帧数要求 `cov ≤ 33.3%`；墙钟要求 `cov ≲ 12%`（密帧 seek 0.156 s/帧 vs 顺序解码 0.105）。
- **逐图复核（用户点名）**：test2 3 张 9 行 + 2mkv 4 张 10 行全部读过。
  **第一版出图取格缺陷已修并留痕**：原用「与 GT 编辑窗重叠最大的行的主 span」会取错格
  （出现过画面与 GT 完全不同却判 HIT 的格子），改成**复刻评估器匹配规则取「判档证据」那条 span**。
  读图判语：test2 的 5 条翻转里 **3 条画面级真丢/错位**（t2r02c 判无证据而 A10 精确落上同帧、
  t2r03a 整段落到 t2r02c 的航拍画面、t2r07a 跨切点错位 3s 到红衣女子镜头），2 条是短 GT 行
  ±2s 容差造成的档位变化；C05D 的救回里 2 条逐字/同镜救回（t2r06a 与对照臂**同 span**
  1628.0-1630.0）、2 条跨切点覆盖（t2r02c/t2r07a）、1 条靠信封（t2r02b）
  ⇒ 「零翻转」成立，**「逐帧等价」不成立**。
- **顺带钉住两条口径（登记，未改判卷代码）**：① 对 1 秒级超短 GT 行，`within` 通道可由
  **完全不与 GT 窗重叠**、只落在 ±2s 信封内的 span 满足 ⇒ 引用「零回退」须带这句；
  ② A10 test2 与 10-03 基线批 **逐行 mark 完全相同但 strip(result_id) 逐字节不等**
  （`isc_l2_index_enabled` 是 10-05 才翻默认，基线批跑在其前）⇒ 跨批引用 v2_* 只可用于
  三指标/mark 层，不可用于逐字节零语义断言。
- **实况发现（口径）**：源码树探针数据根 = `AppData\Local\SourceVideoLocator`，打包应用 =
  `AppData\Roaming\Video Locator AI\data`，**两套缓存**。test2 的 ISC L2 表在探针根缺失
  ⇒ A10 臂白跑一次建表（日志 `正在建立画面索引（一次性）64/5051`，不是 CLS 重建）。
  已按 `is_valid`（schema + 源片 sha256 全校验）把四片 ISC 表从打包根复制过去 ⇒
  **A10 test2 的 locate 墙钟含冷建表 ⇒ 三臂 locate 墙钟不可横向比**（只有 C05D−B05 一对干净）。
- **边界**：只测两片（test1/test3 的 B05 臂未跑）；C05D 只在 test2 测过；密验是沙盒形态
  （seek 抓帧、非均匀网格上场景表按 0.5fps 语义重建）。**⑥a/c/⑥d 未跑，保持「未跑」而非
  「已证否」**（本轮按口令只跑 b）⇒ 不得从 b 外推为探针族结案。
- **产物**：`mvp/scripts/probe_two_stage_sampling_20261008.py`（build/locate/dense/report 四腿，
  默认拒覆盖）+ `mvp/scripts/probe_two_stage_visual_20261008.py`（证据格出图）+
  `work/two_stage_20261008/`（build_account · 三臂 results · dense_bundles · compare.json ·
  visual/ · 各腿日志）+ `FINDINGS_TWO_STAGE_SAMPLING_20261008.md`。
- 门禁：`mvp/src` 零改动 ⇒ 未跑后端/API 全套（新增仅 `mvp/scripts` 探针 + 文档）。
  工作树 = 三个未跟踪新文件；**未提交 git、未出包**（r16 仍等口令）。

## 2026-10-08（续63 补七）— r16 出包：三件修复进包 + 全链包内验收绿（含 R2 由红转绿）

- **口令**：「推ci然后打包吧」⇒ 先推 `aba3a21..654dd32`（6 笔，含 ⑥b 判负批），再出 r16。
  macOS workflow 是 dispatch-only，按既有搁置裁决**未**手动触发（不烧 ~180 macOS 分钟）。
- **打包前门禁（命令输出留证 `work/r16_gates.log`）**：后端 **606 OK (skipped=2)** ·
  API **122 OK** · vitest **144 全绿** · `tsconfig.app.json` 与 `tsconfig.desktop.json`
  **分别**跑 typecheck 且 `returncode=0`。
  ⚠️ 首轮我把 `npx vue-tsc ... | tail -4` 的 `$?` 当成了编译器退出码（实为 `tail` 的）⇒
  重跑用 Python `subprocess.run().returncode` 硬取。**「双 typecheck 干净」这类自报必须有取对
  退出码的命令支撑**（同 续63 补五 被打回的那类错，只是这次自己抓到并当场修）。
- **包**：`mvp/ui/release/Video-Locator-win-x64-20261008r16.zip` = 981,659,900 B / **7,078 条目** /
  `testzip()=None`；**从 zip 里读出** backend.exe = 77,469,132 B `sha16=7c9533750776a79a`
  （r15 = 77,467,467 B / `d45656f585826f4a`）⇒ 尺寸+摘要逐代递增，且证明 zip 装的就是被验收的那份构建。
- **构建**：`build-release.ps1` 四阶段 PS_EXIT=0（模型资产 sha256 fail-fast 全过 → vite →
  electron 编译 → PyInstaller onedir + 剪枝 scipy/pandas/onnx → electron-builder dir 1053 MiB）。
- **包内验收全绿**：
  - `accept_packaged_bundle.py` **FAILED=0**：资产清单/双 sha256 · 冒烟 rc=0 **29.1s ≤75s** ·
    DirectML 生效 · 精排与 ISC 未回退 CPU · 段数 1 · **隔离子进程在跑** · **子进程 INFO 进得到包内** ·
    未误判硬崩。
  - `accept_packaged_render.py` **FAILED=0**：R1 completed（63s）· **R2 渲染确实走隔离子进程 = PASS**
    （这条对 r15 如实报红 = `submit_render` 漏传 `isolated` 的修复此前只在源码树）· R2b 未静默回落
    线程内 · R3 未误判硬崩 · R4 成片 136.366s vs Σclip 136.344s（±0.8s）· R5a 64 段紧邻 0 交叠 ·
    R6 `h264_amf`。
  - 三防冒烟 **FAILED=0**（BACKEND_LISTEN 公告 / health 200 / 受保护端点无令牌 401 /
    release 无令牌拒启 exit!=0）。
  - `check_export_plan_invariants.py` **FAILED=0**（4 片 × 4 通道五条不变式；2mkv 贴接 2 对→0、
    覆盖 Δ=0.00、三通道同 plan=是）。
  - 启动冒烟（新 `work/r16_pkg/startup_smoke.py`）**FAILED=0**：30s 时 Electron 4 + backend 1 存活、
    启动器未中途崩、按 PID 杀树后 `AFTER_KILL=0`。
- **包体产物层探针（r16 新形态）= FAILED=0**：`work/r16_pkg/probe.py` 的靶子**不抄档案数字**，
  改由 `work/r16_pkg/expect_from_source.py` 用同一份 results 在**源码树**跑 `export_project` 现算，
  并先断言「源码树数据根 vs 包内数据根」的 2.mkv 场景表基线全等
  （`feature_version` / `preprocess_sha` / `num_frames` / `scenes.npy` 行数与求和）——
  因为两根不同名（`%LOCALAPPDATA%\SourceVideoLocator` vs `%APPDATA%\Video Locator AI\data`），
  不核这一条就无法区分「包体回归」与「吸附基线不同」。读数：EDL 134.12s / 64 事件 / 贴接 0 对；
  卷轴 **63 条 = 源码树 63**（r15 包 64）· 落盘素材 56 · 总宽度 791.75s · 并集 531.0s ·
  全原速 · 紧邻重复 1 对/13.0s ≤ 计划层认定的真实复用 487.25s · 包内墙钟 97.4s ≤140s。
  ④a 另留**行为级**证据：包内日志出现 `adjacent dedup (jianying)`。
- **卷轴 64→63 的口径含义**：r15 包是「去重只在源码树」，r16 起包内也去 ⇒ 任何引用 r15 包内
  64 条 / 815.75s 的旧读数从此失效，须改引 r16 的 63 / 791.75s（覆盖 531.0s 不变）。
- **分发包现状**：r13 + r14 + r15 + r16 四份；按「最新+上一档」应删 r13 + r14（~1.96GB），等口令。
- **未提交**：本批档案改动与 r16 探针脚本（`work/` 不入库）。候选后续 = 把
  `expect_from_source.py` + `probe.py` 提到 `mvp/scripts/` 作常设包体出口验收（与
  `accept_packaged_render.py` 同规格），待拍板。

## 2026-10-08（续63 补八）— 进度链跳格独占实测（模型口径更正）+ 支持档文件侧两条老欠账闭合

- **口令**：「先1」= 真机自然运行复核；用户裁决 **埋点下一批**（本轮零 runtime 改动）。
- **三条产物**：`mvp/scripts/review_progress_chain.py`（源码树记 `on_progress`，读数经产品自己的
  `map_progress_stage` + `ProgressDebouncer` 换算，输出与 `work/fixramp_run1_table.txt` 同列可逐行对照）、
  `mvp/scripts/review_packaged_support_log.py`（事后核真实支持档：隔离配对 / 会话账 / 腿标记 /
  ERROR 信噪比）、`work/name_probe/packaged_index_probe.py`（包内特殊文件名 + 隔离任务文件侧）。
- **进度链 test2 独占实测**（locate 全程 1476.5s = 24.6min · 67 段 · DirectML）：
  字牌腿 302.6→551.5s 共 **249s / 10 个跳格 => 均值 24.9s、最大停留 41.6s**；ISC 腿 41 格最大
  **37.3s**；92→100 全程最大停留 41.6s；读数单调不回退；防抖把 113 格合成 109 格（全是亚 0.5s
  突发）且**未放大可见停留**（raw 41.6 = debounced 41.6）。
  对照改前实测（字牌 363s 一动不动 / ISC 40~58s）=> **改善成立，量级 8.7x**；
  顺带独立复核了「现役 22~31min/片」口径（test2 实测 24.6min）。
- **模型口径更正（本批最有价值的结论）**：`mvp/api/tests/test_tasks.py:220` 那条锁
  `step_s = 0.1/(1.7*32/48/67)*(363/67) = 32s` 算的是**均匀假设下的均值**；实测均值 24.9s
  **优于**预测，但用户感知的是**最大值 41.6s**（段间成本不均，最坏单格 = 1.67x 均值）=>
  超阈值 1.6s 不代表"改善没生效"，而是**锁的口径选错了（拿均值当体验）**。
  建议（待拍板，本轮未动代码）：锁改成按实测最大值口径 + 登记 41.6s；**不**加宽字牌腿显示宽度
  （挤占 patch/ISC，且 1.6s 不构成体验问题）。
- **测量卫生（本批踩过两次，已写进脚本 docstring）**：
  ① 首跑我在重叠窗口里跑了包内探针（同一块 DML），字牌腿被抬到 52.8s => **整趟作废重跑**，
     污染趟产物已删（防后人误引）；跳格类测量对 GPU 争用极敏感，跑时不得并发任何 DML/解码活。
  ② 探针首版在任务 `completed` 后 1s 就 terminate，把父进程 `isolated child reaped` 行自己切掉
     => **假红**；改成等收割行出现（<=25s 宽限）再收。教训：任务终态 != 收割完成。
- **支持档「文件侧」两条老欠账首次实测闭合**：
  ① 打包态**子进程 INFO 真进 `video_locator.log`**：完整链
     `isolated child started(父) -> isolated child booted(子, 同 pid 同 task_id) -> 子进程 locate
     内部 INFO（patch v2 nearfield / fast_global / locate finished）-> isolated child reaped
     exitcode=0`。此前 `accept_packaged_bundle.py` 只在 **stdout** 上断言，文件侧一直未实测。
  ② 特殊文件名：从真实支持档挖出 2026-08-27 两条 `index failed: Dune (2021).mkv /
     Interstellar (2014).mkv` 的真因 = 当年 ffprobe 命令被**手工加单引号**
     （`'Dune (2021).mkv'`，Windows 不把单引号当引号 => 收到带引号的字面文件名 => rc=1）。
     现包内对 `Dune (2021) 沙丘 test.mp4` 实测：建索引 completed / 状态回读 VALID /
     索引目录 `Dune (2021) 沙丘 test__dcadb7f3.idx` / backend=directml => **历史缺陷已闭**（FAILED=0）。
- **顺带捞出的产品级欠账（未动，等排批）**：真实支持档 492 条 ERROR 里 **485 条是 asyncio
  proactor `WinError 10054` 连接重置**（客户端强关，非故障）=> 支持档信噪比仅 1.4%，
  「客服按日志找真因」会被噪声淹没。降噪（过滤该 callback 或降级为 DEBUG）与
  「修复链腿边界埋点（让进度事件落支持档）」同批做最合适 —— 后者也是本轮复核暴露的观测面缺口：
  **进度事件完全不落日志**（`mvp/api/tasks/` 无任何 `_log.info`）。
- **复核器一处自纠**：`review_packaged_support_log.py` 首版把「0 started / 0 缺」报成 A1 PASS
  —— 真实支持档早于任务隔离上线，必然没有隔离行，那是**空跑不是通过**（同 续63 补五 双 typecheck
  那类自报门禁错）。改成 `started==0 => A1/A2 判 N/A 并明写"文件侧未实测，别当已验收"`。
- 门禁：`mvp/src` 零改动；新增两个 `mvp/scripts` 复核脚本 + `work/` 探针。本批未提交、未出包。
## 追加 —— 包内真机进度链复核闭合（同批，用户「复核」口令）

- **做法**：`work/r16_pkg/packaged_cadence_probe.py` 轮询 `GET /api/tasks/{id}` 的 `progress`
  （= UI 读的同一个字段，服务端已过 `map_progress_stage` + `ProgressDebouncer`），
  在**真实包内数据根**（Roaming，索引 VALID）对 test2 跑完整 analyze，独占设备。
  => 结论：**包内 cadence 不需要等日志埋点就能测**，埋点只决定售后事后能否查。
- **实测（与源码树同口径 = 按 pct 变化折叠）**：墙钟 **1407.5s vs 源码树 1476.5s（0.95x）**；
  92→100 跳格 **54 vs 55**；全程最大停留 **41.4s vs 41.6s**；字牌腿最大 41.4s / 均值 23.7s
  （源码树 41.6 / 24.9）；ISC 腿最大 **33.8s vs 37.3s**；结果段数 67 与源码树一致；读数不回退。
  判据 C1-C6 **FAILED=0**。=> 「包内真机 cadence 未实测」这条边界**闭合**，且包体无劣化。
- **C5 支持档文件侧**：真实 25 分钟任务上隔离链四件齐全（父 `started` / 子 `booted` 同 task_id /
  子进程 `locate finished` INFO / `reaped exitcode=0`），全部落在 `video_locator.log`。
- **自纠（口径）**：探针首版按 `(pct, stage, message)` 变化折叠 —— 消息换了但读数没换会被算成
  "动了一下"，**低估**可见冻结（首跑因此报 145 格、最大停留 41.4s 看似优于真实）。
  已改成与源码树 `review_progress_chain.steps()` 一致的 **pct 变化**折叠，重出
  `work/r16_pkg/cadence/test2_packaged_dwell_pctcollapse.txt`；脚本内留注释防再犯。
- **跳格锁口径结论（不变，待拍板）**：均值实测 23.7~24.9s **优于**模型预测 32s，
  但最大值 41.4~41.6s **超** `test_tasks.py:221` 的 40s 阈值 => 该锁按均值建模、
  用户感知按最大值，建议改锁口径（登记实测最大值），**不**动显示宽度分配。



## 2026-10-08（续63 补九）— 腿边界埋点 + 支持档 proactor 降噪 + 跳格锁改按最大值口径

口令「2」= 补七/补八 实测捞出的「下一批候选三件」全做。动 `mvp/src` 两处 + 三层测试 + 两个
常设复核脚本。**未提交、未出包**（现役 r16 不含这三件）。

### ① 修复链腿边界埋点（`mvp/src/app/locator_service.py`）

- 旧缺口：进度事件**完全不落日志**（`mvp/api/tasks/` 无一处 logger 调用），售后拿到支持档只能看见
  `patch_refine:` 这类腿内自带行 ⇒ 「进度卡在哪条腿」无法按档复核（`review_packaged_support_log.py`
  C 面当初就把这条写成"已知观测面缺口"）。
- 现形态：一次 locate 落 **12 行** `locate leg=<名> elapsed=<秒> units=<a>-><b>/48 chain=<累计秒>`
  （global_anchor · dense_recheck · text_anchor · seq_rerank · temporal_repair · conflict_rerank ·
  temporal_ambiguity · consecutive_resolve · degradation_gate · shot_split · patch_refine · isc_refine）
  + 链首 **1 行** `locate refine start units=0/48 legs=<12 个开关 on/off>`。
- **口径决策（与立项原话有出入，理由登记）**：立项写的是「每腿进/出一行」，实做**每腿一行**——
  腿 k 的「进入」= 腿 k-1 的「完成」，链首开关行交代「这条腿跑没跑」⇒ 复核能力等价、行数减半；
  **腿内 tick 不落日志**（`_fix_to` 保持静默；一次真实 locate 的 tick 上百条，会把同批 ② 的降噪
  直接抵消）。
- 两条配套改动：① `_split_on/_patch_on/_isc_on` 三条旋钮判定**整体上移到修复链入口**，埋点 `legs=`
  行与腿执行同一真源（原来在下面各写一遍，改一处就谎报）；② 埋点边界放在**腿与腿的切换处**而不是
  显示刻度表的位置——旧 `_fix_to(42)` 排在序列腿**之后** ⇒ 序列腿耗时算进字牌腿，现提到之前
  （tick 上限 = `10+int(32*0.9)=38` 够不到 42 ⇒ 事件序列逐字不变、显示逐点不变）。
- 验收（后端 `mvp/tests/test_locator_service.py::LocateLegLoggingTest` 5 项）：行数恰 12 且顺序 =
  执行顺序 · 刻度与累计耗时单调 · `elapsed` 求和 = 最后一行的 `chain`（±0.3s）· 开关行 12 项 ·
  **tick 不污染**（`locate leg=` 行数 == 腿数）· **ramp 行为不变**（fix 事件电流终点仍 48、不回退）·
  **文件侧**：`configure_logging(log_dir=临时目录)`（= 打包态同一套 handler 栈，补八 已实测子进程
  INFO 进得到那份文件）跑完读回 `video_locator.log`，逐条核 12 行 + `module=app.locator_service` +
  字牌腿那条 `units=9->42/48` 必须在。

### ② 支持档 proactor 噪声降噪（`mvp/src/infrastructure/logging.py`）

- 现状实测：现役真档 19,877 条记录 / **492 条 ERROR**，其中 **485 条（98.6%）**是同一形态
  （`module=asyncio` + `_ProactorBasePipeTransport._call_connection_lost()` +
  `ConnectionResetError [WinError 10054]`，5 行/条）= 客户端（预览播放器取消 Range 请求、UI 轮询
  关连接）先挂断，**不是故障** ⇒ 信噪比 1.4%，客服按档找真因会被淹。
- 处理：`BenignConnectionNoiseFilter` 挂 **asyncio logger**（logger 级 filter 才对传播记录生效，
  挂 root 等于没挂）。判据三条**同时**成立才算噪声，宁可放过不可误杀：① 名字 `asyncio*`；
  ② 回调是 `_call_connection_lost`；③ `ConnectionResetError/BrokenPipeError` 且 `winerror`
  （缺省退 `errno`）∈ {10053,10054,10058}。**降级 DEBUG 而不是 drop** ⇒ 支持档与 stdout 不收录、
  调试档（`SVL_LOG_DEBUG=1`）逐条保留。新增 `SVL_LOG_NOISE_FILTER=off` 开关（支持人员临时看全量，
  也是双臂对照的对照臂）。顺带把 stream handler 门槛显式设 INFO（原 level=0 ⇒ 降级后的记录仍会
  以 DEBUG 刷 stderr；改后与既有「调试行只进 debug.log」分层口径一致）。
- **主证据 = 拿真实历史档做逐条判据回归**（`work/r17_noise/classify_real_log.py`）：按现役解析
  规则切记录、把 traceback 里的 `ConnectionResetError: [WinError 10054]` 还原成真实 OSError 实例、
  喂**产品代码**的 `is_benign_connection_noise()` ⇒ 噪声族 **485/485** 判可降；其它 **7 条真故障
  0 误杀**（`app.locator_service` 2 + `api` 5）。
- 单测 `mvp/tests/test_logging.py::ProactorNoiseFilterTest` 6 项：支持档不收录（stdout 同门槛）·
  调试档保留且级别是 DEBUG · 回调名不同不降 · 异常类型/错误码不同不降（10061 拒连=真问题）·
  我方模块抛同名异常照旧 ERROR（filter 只挂 asyncio）· filter 幂等安装。
- **未闭合边界（如实登记，不当验收）**：真机复现臂在本机**造不出该形态**。
  `work/r17_noise/probe.py`（uvicorn 三臂 = r16 包内 / 源码树 / 源码树+调试档，同一份客户端脚本）
  跑了四轮：一发完即 RST → 二先 recv 64KB 再 RST 并在 `preview_dir` 放 40MB 文件走 FileResponse →
  三补 `MEDIA_FFPROBE`（第二轮那 18 条「真故障」其实是探针自己缺 ffprobe 的 500，真故障样本被污染）→
  四各臂档目录先清空重跑（前三轮读数里混着上一轮尾巴）。`work/r17_noise/probe_proactor.py`（裸
  asyncio 三臂）又一轮，含按 stdlib 源码反出来的真实成因——`proactor_events.py:165` 的
  `sock.shutdown()` **没有包 try**，其上注释明写「对端还挂着 overlapped read 时关连接会以
  ERROR_NETNAME_DELETED 失败」= 10054 ⇒ 打法 = 小响应 + 挂着读 + 收 RST 后正常关。
  **五轮全部 0 条**，连**降噪之前的 r16 臂**也 0 条 ⇒ 「修复臂干净」= **空跑**。
  两脚本已改成「对照臂 0 条 ⇒ 下游一律 N/A 不判通过」，并加仪表自证行（`module=probe.arm`）
  证明落盘链路是通的（自证行三臂都在 ⇒ 确实只是没造出形态，不是没落盘）。
  同批实测通过的半边：真故障 ERROR（`POST /api/index` 指向不存在文件）在修复臂支持档里**照常可见**
  （B3 PASS）⇒ 「降噪没把信号一起降掉」这一条有真机证据。

### ③ 跳格锁改按最大值口径（`mvp/api/tests/test_tasks.py`）

- 旧锁 = `round(0.1/(1.7*32/48/67)*(363/67)) = 32 ≤ 40`：算的是**均匀假设下的均值**，且输入 363s
  是修复**前**的腿耗时。补八 两趟实测：均值 20.5~24.7s 一直优于该预测，而**最大单格** 41.4~41.6s
  超那条 40s ⇒ 不是「改善没生效」（改前形态 = 字牌腿 363s 一动不动），是**锁的口径选错了**。
- 新锁拆两条：**锁 A** 可见读数数由现役宽度表**现算**（`_visible_steps()` 在
  `map_progress_stage` 上取值，宽度一改就红，不抄档案）+ 腿墙钟 ÷ 读数数 ≤30s；
  **锁 B** 登记两趟实测**最大停留** ≤45s（45 = 承认现状 41.6 并要求别继续变差；
  **不**加宽字牌腿显示宽度——会挤占 patch/ISC 的预算）。
  另加 `test_width_collapse_would_trip_the_lock` **反向验证**：把宽度压回 run3 那种「按腿数量平分」
  形态（0.2 点）⇒ 读数 12→3、均值 82s 超阈值 ⇒ 证明锁 A 真会抓到那类回归。
- **更正 续63 补八 的腿归因（说错主动更正留痕）**：档案写「ISC 腿 41 格 最大 37.3s（源码树）/
  33.8s（包内）」—— patch 与 ISC 两条腿的 UI 消息文本**一模一样**，旧 `review_progress_chain.py`
  按消息子串归因 ⇒ 两条腿混成一条（那个「41 格」就是 23+18 的和）。按事件 `phase` + **墙钟区间
  裁剪**重算两趟原始数据：

  | 腿 | 腿墙钟 源码树/包内 | 最大停留 源码树/包内 | 代码可见读数数 |
  |---|---|---|---|
  | 字牌 OCR | 245.9 / 236.6 s | **41.6 / 41.4 s** | 12 |
  | 切镜拆分 | 33.8 / 31.7 s | 33.8 / 31.7 s | 2 |
  | patch 精排 | 470.9 / 423.1 s | **37.3** / 28.3 s | 24 |
  | ISC 第二意见 | 419.7 / 408.9 s | **33.9** / 33.8 s | 19 |

  ⇒ 37.3s 属 **patch 腿**，ISC 腿 = 33.9s；全程最坏单格仍是字牌腿（41.6/41.4）⇒ 补八 的
  「改善 8.7x、按最大值超旧阈值 1.4~1.6s、不加宽宽度」三条结论**不受影响**。
  （注：显示停留的折叠口径在两腿边界上会把尾巴算进上一条腿——93.9 那个读数既是拆分末端又是
  patch 开头 ⇒ 统计一律按原始事件流的腿区间裁剪，`leg_dwells()` 写了这条原因。）

### ④ 两个常设复核脚本同批改口径

- `mvp/scripts/review_progress_chain.py`：判据换成 ①逐腿最大 ≤45 ②逐腿均值 ≤30（切镜拆分不判均值，
  整腿只 2 个读数）③全程 ≤60 ④读数单调 ⑤与登记值对照（**只报数不判负**）
  ⑥**埋点自证**（⑥a 档内腿行数 == 12；⑥b 逐腿 `elapsed` 与事件流墙钟对账，差 ≤max(8s,12%)；
  **0 行判 N/A 不判通过**）。归因函数用已录 `work/progress_chain_review/test2.events.json`
  **离线回放**校验过（那趟早于埋点 ⇒ ⑥a 正确地报 N/A，而逐腿统计与上表逐格一致）。
- `mvp/scripts/review_packaged_support_log.py`：新增 **C2 腿边界埋点面**（行数/腿顺序/刻度与累计
  单调/「腿耗时合计 ≤ 会话 `locate finished` elapsed」；无腿行 ⇒ 判 **N/A** 并明写「档早于埋点或
  跑的是 <=r16 包，别当已实测」）；D 面写明降噪已上线（老档里的 10054 = 历史，非回归）。
  对现役真实档重跑 FAILED=0（C2 如实报 N/A）：`work/support_log_review/report_r17_c2.json`。

### 附带

- `locate()` 里 ISC 那条「默认关」注释过期：`config.py:350 isc_refine_enabled = True`（随「ISC L2
  画面索引宽扫」在提交 7c6e485 一起翻的默认）⇒ 就地更正注释，**未动行为**。
- 门禁 = 后端 **617** OK(skipped=2) · API **124** OK · vitest **144** · app/desktop 两个 config
  分别 typecheck **RC=0**（`work/r17_gates/gates_final.log` + `gates.json`；退出码由
  `subprocess.returncode` 硬取）。门禁 runner 自身修了两处本机坑：Windows 上 `npx` 必须
  `shutil.which` 解析（否则 FileNotFoundError）；vitest 输出里的 U+2713 会打断 cp936 控制台的
  `print`（RC=0 已拿到却挂在打印尾巴）⇒ runner 里 `sys.stdout.reconfigure(utf-8, replace)`。
- 教训入 `Known Issues` 速查：**⑫ 按 UI 文本标签分组统计会串腿**（要用结构化 `phase` + 墙钟裁剪）、
  **⑬ 降噪/复现类探针必须自带仪表自证行 + 对照臂 0 条 ⇒ 下游判 N/A**（这条今天挡掉了三轮假绿）。

### 追加 —— 复现臂七轮全 0，改「借 asyncio 自己的记录路径」闭合（同批，用户「怎么解决，你想想」→「可以」）

- **七轮客户端强关都没造出该形态**（`work/r17_noise/`）：
  `probe.py`（uvicorn 三臂 = **r16 未修复包内** / 源码树 / 源码树+调试档）四轮 ——
  ①发完即 RST；②先 recv 64KB 再 RST 并在 `preview_dir` 放 40MB 文件走 FileResponse；
  ③补 `MEDIA_FFPROBE`（第二轮那 18 条"真故障"其实是探针自己缺 ffprobe 的 500，真故障样本被污染）；
  ④各臂目录先清空重跑（前三轮读数里混着上一轮尾巴，我差点把陈旧样本当新证据）。
  `probe_proactor.py`（裸 asyncio 三臂）两轮 —— 慢写法（40×64KB + drain）与按 stdlib 源码反出来的
  「挂着读再正常关」写法（`proactor_events.py:165` 那句**没包 try** 的 `sock.shutdown()` 才是
  历史 traceback 的行号；慢写法失败是因为 drain 先抛 ⇒ `fatal_error` 置位 `_called_connection_lost`
  ⇒ 后面 close 直接短路，永远走不到那句 shutdown）。
  `probe_keepalive.py`（真服务栈 + keep-alive 超时当扳机：客户端只收响应头就 RST、晾服务端 6.5s
  让它自己回收这条挂着读的废连接）一轮。⇒ **七轮全 0 条**，连 r16 未修复对照臂也 0 条。
  三个脚本都改成「对照臂 0 条 ⇒ 下游一律 N/A 不判通过」并加仪表自证行（`module=probe.*`，
  实测三臂都在 ⇒ 确实只是没造出来，不是落盘链路没通）。
- **闭合办法 = 不再赌 OS 时序，改借框架自己的记录路径**（`work/r17_noise/probe_inject.py`，
  `FAILED=0 / VERDICT=CLOSED`）：在跑着**真实产品服务栈**的进程里调
  `loop.call_exception_handler({message, handle, exception})`，由 **asyncio 默认异常处理器**落到
  logger `"asyncio"` —— 真 `create_app()`、真 `uvicorn.Server(Config(..., log_level="info",
  access_log=False))`（参数同 `api/launcher.py:build_server`）、真 ProactorEventLoop、
  lifespan 里真产品的 `configure_logging()`、真 `ConnectionResetError(10054,…)` 带真 traceback；
  剩下唯一变量就是「我们的 filter 在不在」。**代打的只有一处并写明**：抛它的回调不是
  `_call_connection_lost` 本尊，message/handle 按历史档逐字复制 ⇒ 「OS 会不会真报这个错」
  不由本脚本证明。
- **三臂七判据全 PASS**：J1 不过滤臂 10/10 条该形态进支持档（含 WinError 10054）= 不过滤就会淹档 ·
  J2 过滤臂同一注入 0 条 · J3 过滤+调试档：支持档仍 0 条，`debug.log` 以 **DEBUG** 留满 10 条
  （降噪≠丢信息）· J4 不误杀：同批注入的 `ValueError` callback 形态 + 产品自己的真故障
  （POST /api/index 指向不存在文件）在三臂**都**照旧进档 · J0 装配锁（off 未装 / on 已装）·
  J5 仪表自证 · J6 确认注入跑在 ProactorEventLoop 上。
- **②的证据链定型**：判据对不对 = 历史真档 485 条逐条回归（485/485 + 真故障 7 条 0 误杀）；
  链路生不生效 = 真进程注入三臂双臂对照；不误杀 = 单测 6 项 + J4。**残留一项**如实登记：
  本机没有「OS 真报错」的直接观察。r17 出包时建议把这套三臂升成包侧常设断言
  （在 `backend.exe` 里注入 ⇒ 支持档 0 条 / 调试档留满），另加一条
  「真实 analyze 后支持档必须 12 行 `locate leg=`」= 埋点进包的锁。
- **两个 stdlib 坑**（首两版读数全错分类的原因，已写进脚本注释与 `Known Issues` ⑭）：
  ① `create_app` 用**自定义 lifespan** ⇒ 往 `app.router.on_startup` 挂东西根本不执行
  （表现为 `INJECT_NOT_DONE`，服务其实活着）；② 3.13 的 `default_exception_handler` 要的是
  **异常对象**，传 `(type, val, tb)` 三元组会让处理器自己抛
  `AttributeError: 'tuple' object has no attribute '__traceback__'`，档里整片变成
  "Exception in default exception handler"。
- 本追加不改 `mvp/src`（只动 `work/` 探针与档案）⇒ 不重跑门禁；三件主体修复的门禁数仍按上方
  「附带」段（后端 617 · API 124 · vitest 144 · 双 typecheck RC=0）。仍未提交、未出包。

## 2026-10-08（续63 补十）— r17 出包：补九 三件进包 + 包侧两条新锁（腿埋点已实测落支持档）

口令「先出包吧」。包体与验收全部实测，未抄上一代数字。

- **构建**：`mvp/ui/scripts/build-release.ps1`（vite + `vue-tsc` → compile:electron →
  PyInstaller 后端 → electron-builder dir）一条链 `PS_EXIT=0`；出包前查过 tasklist 无形态残留。
  zip = `Compress-Archive -Path win-unpacked\* -CompressionLevel Optimal`（与 r15/r16 同形态，
  根=散装内容、7,078 条目）。
- **包** = `mvp/ui/release/Video-Locator-win-x64-20261008r17.zip`：
  **981,665,352B / 7,078 条目 / `testzip()=None`**；**从 zip 内读出**的
  `resources/backend/backend.exe` = 77,472,765B `sha256[:16]=7e3fe311bdf62b36`
  ⇒ 与磁盘构建产物逐字节一致（`matches_disk_build=True`）；r16 = 77,469,132 / `7c9533750776a79a`
  ⇒ 尺寸 **+3,633B**，正对应本批埋点 + 降噪的代码量；r15 = 77,467,467 / `d45656f585826f4a` 未动。
  核验工具新写 `work/r17_pkg/zip_identity.py`（一次列全部代次、从 zip 里读、顺带核 root 形态）。
- **代次性质（两段如实记）**：出包当时 补九 三件**尚未提交**（git 时机由用户掌握），所以先按
  「工作树构建」登记；出包后随即提交为 `ba5bedd`，且**构建之后没有再改 `mvp/src`**（只改了
  `.agent` 档案与 `accept_packaged_bundle.py` 里一条判据自身的 bug）⇒ 包内 backend.exe 与该
  commit 的产品源码逐字对应；那条判据修正不进包（脚本不在包内）。
  · `accept_packaged_bundle.py` **FAILED=0** — 资产清单/图/外部权重 sha 全对；合成素材冒烟
    30.2s ≤ 75s、`backend selected=directml`、`patch reranker device=dml`、`isc refine device=dml`
    （未静默回退 CPU）、`segments=1`、隔离链 `started`+`booted` 齐、无 `DIED without envelope`；
  · `accept_packaged_render.py` **FAILED=0** — R1 completed wall=63s · R2/R2b 渲染走隔离子进程
    且未回落线程内 · R4 136.366s vs Σ136.344s · R5a 64 段紧邻 0 交叠 · R6 `h264_amf`；
  · 三防冒烟 **FAILED=0**（含 release 通道无令牌拒启、越权请求 401）；
  · `check_export_plan_invariants.py` **FAILED=0**（4 片 × 4 通道五条不变式）；
  · 启动冒烟 `work/r17_pkg/startup_smoke.py` **FAILED=0** — 30s 时 Electron 4 进程 + backend 1
    仍存活、用完即清 `AFTER_KILL=0`；
  · 包体产物探针 `work/r17_pkg/probe.py` **FAILED=0** — 靶子由 `work/r17_pkg/expect_from_source.py`
    **在源码树现算**（卷轴 63 条 / 56 个素材文件 / 791.75s / 531.0s、EDL 134.12s、贴接 0 对），
    包内实测同值、包内墙钟 99.7s ≤ 140s、全原速。
- **两条新包侧锁（进 `accept_packaged_bundle.py`，r17 起常设）**：
  ① **腿边界埋点进包并落支持档** = 读 `work/pkg_attr/logs/video_locator.log` 里
  **最后一次 locate 的窗口**（该档是追加式，全文计数会假绿，所以必须切窗口）断言
  `locate leg=` 的名字与**顺序**逐条等于 `EXPECT_LEGS`（12 条）· `units=` 右端只增不减 ·
  链首 `locate refine start units=0/48 legs=…` 在位。包内实测原文（合成素材 a1.mp4，1 段）：
  `text_anchor elapsed=0.4s units=9->42/48` · `shot_split 2.0s` · `patch_refine 10.1s` ·
  `isc_refine 7.5s` · `chain=20.0s` ⇒ 「进度卡在哪条腿」第一次在**打包态支持档文件**里可读。
  ② `EXPECT_LEGS` 与单测 `LocateLegLoggingTest.LEGS` 同源，注释写明必须同改（否则一边假绿）。
- **首跑一条假红 = 判据自己的 bug**：`legs == EXPECT_LEGS` 是 list 比 tuple ⇒ 恒 False，
  而失败明细里 12 个名字逐字正确 ⇒ `list(EXPECT_LEGS)` 修掉后重跑 FAILED=0。
  按「验收脚本首跑预期红」的规矩先分清是包的问题还是判据的问题：**这次是判据**，
  没动包、也没放宽阈值。
- 本批（补十）未重跑门禁：只改 `mvp/scripts/accept_packaged_bundle.py`（两条新包侧锁 + 修自己
  那条 list/tuple 比较 bug）、`work/` 与档案；`mvp/src` 与测试未动，
## 2026-10-08

### Added

- None.

### Modified

- Updated `.agent/STATE.md` last-updated timestamp.

### Fixed

- None.

### Removed

- None.

### Notes

- Created `checkpoint-2026-10-08-0109.md` checkpoint (1 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-10-08-1704.md` checkpoint (7 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-10-09-2351.md` checkpoint (1 modified/untracked file(s)).
