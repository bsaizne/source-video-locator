# 交接 2026-10-17（23:45）— r25 已出现役 + 竞品静态三刀收口（**未提交项：零**）

> 自包含交接件。下一会话读这一份 + `.agent/STATE.md` 顶部「续63 补十九」块即可接手。
> 上位依据：`.agent/CHANGELOG.md` 2026-10-17 的（一）~（五）节；竞品侧正文一律在
> `D:\claudework\cutmatch-analysis`（物理隔离仓，**不是 git 仓**）。

## 0. 一句话状态

Windows 现役包 = **r25**（`Video-Locator-win-x64-20261017r25.zip`，构建点 = **干净 commit `c3a17e5`**），
包内四道全绿；分发包三档 = **r25 + r24 + r23**（r22 已删）；`origin/master` = 本地 `master` = **`f59b0c5`**，
工作树在 checkpoint 前有 2 个已改文件（STATE/CHANGELOG 的时间戳与存档行）。
**本轮未执行竞品任何代码；`mvp/` 产品代码在 r25 之后零改动。**

## 1. 今天做完的四件事（读数都在 STATE，此处只给索引）

| # | 事 | 关键读数在哪 |
|---|---|---|
| 1 | 上一会话遗留三批未提交改动收口 | 代码笔 `e79d4ee`（音轨未知声道布局回退 + `clip_present` 判据收一）· `36acc50`（`material_expand_rel_cap` 2.5→**1.5**）· 档案笔 `4783594` |
| 2 | 竞品侧静态三刀（**只写文档**） | `cutmatch-analysis/FINDINGS/13`（137 模块 / 3,202 条他们自写中文 docstring）· `14`（22 个 `/api/*` + **16 键阶段词表**）· `15`（话术 341 + model lease 357） |
| 3 | 竞品采集器硬化 + 自检 | `cutmatch-analysis/scripts/{parse_runtime_log,selftest_parse_runtime_log}.py` = **17/17 PASS** |
| 4 | r25 出包 + 推 + 删 r22 | 四道包内验收 rc 全 0；zip 身份 981,693,605B / 条目 7,079 / `testzip=None` / backend.exe 与 bridge.js **zip 内 == 磁盘** / **与 r24 文件名集合差集 0/0** |

## 2. 四条被实测打掉的档案结论（**别再当事实引用**）

1. **竞品「只支持 NVIDIA」在代码层不成立** —— docstring 原文有 CUDA / **MPS** / CPU 三档设备选择 +
   `licensing/device_keys/macos.py`。该说法只对"这个 Windows 包打进 4.18GB CUDA 依赖"成立。
2. **竞品 IPC 不是「命名管道 + JSON-RPC」** —— 是**本地 Flask HTTP/WS**（`localhost:8000` +
   `/api/upload` 等真实路由字面串）。Rust 侧 `child_pipe.rs` 只是父进程读子进程 stdout。
   ⇒ 以后要"当它的 UI"不需要复刻私有握手。
3. **函数级签名静态永不可得** —— 常量块内 **C(code object) 记录 = 0**（负结果）。
   旧 `mine_nuitka_blobs.py codes` 出 0 行是"没有"，不是工具 bug。
4. **动态腿（本机直启 + 断网）判死** —— `licensing.client.legacy` 原文「**每次启动都向授权服务器校验**」+
   D4「`content_key` 由服务器下发」+ `protected_assets`「租约只在进程间内存传递、加载完即清理」
   ⇒ 断网下推理/解密链不可达。要动态只能去**已激活的真机**投放证据（`runtime_evidence/README_COLLECT.md`
   §0.5 写清了哪些件会被解析/跳过）。**本机 `runtime_evidence/` 从未投放、竞品日志路径全不存在** ⇒
   `data/runtime_params_observed.json` = `{}`（无竞品观测）。

## 3. 静态永久边界（写死，别再找）

① 函数体 / 控制流（无 code object + 指令序列线此前两次判死）；② HTTP **方法与请求体字段**（视图走
`request` 入参）；③ **权重明文 / `content_key`**（服务器下发 + 即时清理）。
⇒ 竞品侧剩余可做的只有 `alignment.offset_refiner`(99 docs) / `scene_detection.supervisor` / `models`
= **纯补全，不预期新结论类型**。

## 4. 今天我自己犯的错（三处，形态各不相同，下一个别再踩）

1. **报了没发生的读数**：打包脚本在**写包之前** `NameError`（清死代码删掉 `pre = ` 却留 `if pre:`），
   我却已经把「7,079 条目 / 981,703,678B」发出去。⇒ 教训：**后台通知的 exit code ≠ 被测脚本的 rc**；
   落档/汇报的每个数都要能指向日志行。已当场更正并 `ls` 核 `ABSENT` 才重跑。
2. **判据覆盖面写窄两次**：① zip 身份原先只比嵌套件（backend.exe/bridge.js）⇒ 缺主体也能全绿出门，
   现补三道硬断言（条目数 == 磁盘文件数 / 顶层关键件在位 / 与上一代**文件名集合差集**），不过就
   `exit 1` **不写包**；② "防记错期望值"的闸只搜 `STATE.md` ⇒ r23 的 sha16 其实在
   `archive/checkpoint-2026-10-13-0040.md:127,662`，恒判"找不到"，且第一版**没把找不到当失败拦下** = 空转。
3. **zip 目录条目规则猜错**：r24 的 85 个目录条目 = 「**无直属文件的目录**」（`diag_zip_dir_rule.py` 实测），
   我按"每目录都写"造出 1,374 条 ⇒ 跨代不可比。r25 = **7,079**（86 空目录 + 6,993 文件），
   比历代 7,078 多的那 1 个 = 本代 `resources/` 确实无直属文件。**以后条目数按 7,079 这个口径看**，
   且必须同时看「与上一代文件名差集 = 0」。

## 5. 开放项（下一会话从这里接）

1. **cap 1.5 的观感读图**（唯一真正未闭合的产品面）：⚠️ **本条建议的验收法已于 2026-10-18 判空并收口**
   （见 STATE `Current Task` 续63 补二十）——「双档各出一张成片再读图」不会有信号：`material_expand`
   只允许剪映通道（`exporters.py:433` 硬守卫），成片通道调用不传该参数 ⇒ **cap 对成片/EDL/XML 惰性**；
   改在剪映卷轴侧读完后结论 = **cap 既不是「过渡不流畅」的成因、也不是解药**（cap 归因边界变化仅 10/72 条）。
   ~~原口径如下~~：`material_expand_rel_cap=1.5` 在生产包内的语义 =
   **≈ 关闭取材扩宽**（不变式实测扩宽条数 0/0/0/1，Σ素材宽 421.7s ≈ core 419.9s）。
   四档（2.5/2.0/1.5/1.2）导出实得 131/139、严格 135/139 **逐位不变** ⇒ 只证了数据面，
   **成片接缝 / 硬切位置的读图没做**。要温和档 = 2.0（−9.4%，保留部分整镜头扩宽），
   一条数值 + 一条默认值锁 + 重跑门禁。
2. **`mvp/src/media/ffmpeg/source_merge.py::_transcode_args` 同族未改**：`concat → -c:a aac` 无布局归一
   ⇒ 同形源（6 声道 / layout=unknown）**失败更早**（`Cannot select channel layout for the link between
   filters auto_aresample_0 and Parsed_concat_6`，rc=-22、0 字节）。这是**硬失败非静默坏产物**，
   修法 = concat 前插 `aformat=channel_layouts=stereo` 或同款失败回退。需单独立批（含归因与验收）。
3. **主线「导出过渡不流畅」**（`archive/HANDOFF_20261016_export_smoothness.md`，10-16 那份）仍缺三样：
   他指认的**具体秒数** / 未经微信转码的原始 `movie_*.mp4` / `<解说片名>__<hash8>.results.json`；
   机械层六项已排除、armB 帧级切点判负；另有一笔挂账 = `og720-720` 相似度自相矛盾（0.08 vs 0.97）未查。
4. **分发包保留**：下次出 r26 时删 **r23**（删前双验 r25/r24 逐字一致，脚本
   `work/r25_pkg/precheck_delete_r22.py` 改 EXPECT 即可复用）。
5. **mac 侧**：本轮 `mvp/ui` 零改动 ⇒ r25 **不需要**另走 dispatch；
   但只要改了 JS/TS 或跨平台代码，就得主动交代「mac 要另走一发 dispatch」，否则留 Win/mac 裂口。

## 6. 复跑命令（都用绝对路径 python；bash PATH 里没有 python）

```bash
PY=D:/claudework/video-dedup-tool/.venv/Scripts/python.exe
cd /d/claudework/benchmark && export PYTHONPATH="mvp/src;mvp"
"$PY" -m unittest discover -s mvp/tests -p "test_*.py"        # 后端全套（r25 树 = Ran 675 OK, skipped=2）
"$PY" -m unittest discover -s mvp/api/tests -p "test_*.py"    # API（Ran 150 OK）
"$PY" mvp/scripts/check_export_plan_invariants.py             # 导出计划不变式（FAILED=0）
# 包内四道（串行，各自起包内后端；逐条取 rc，别用 | tail 把 rc 洗成假 0）
"$PY" mvp/scripts/accept_packaged_bundle.py && "$PY" mvp/scripts/accept_packaged_render.py
"$PY" work/r17_pkg/startup_smoke.py
"$PY" work/r25_pkg/zip_identity.py 2>/dev/null || "$PY" work/r17_pkg/zip_identity.py   # 从 zip 内读身份
"$PY" work/r25_pkg/make_zip_r25.py                             # 重打 zip（含三道结构断言，不过则 exit 1）
# 竞品侧（另一个仓，非 git）
cd /d/claudework/cutmatch-analysis
"$PY" scripts/mine_module_semantics.py                 # 全量语义清单
"$PY" scripts/mine_module_semantics.py "<模块正则>"     # 单模块抽读
"$PY" scripts/extract_http_contract.py                 # 路由 + 字段表
"$PY" scripts/extract_messages_and_lease.py            # 话术 + model lease
"$PY" scripts/selftest_parse_runtime_log.py            # 采集器自检 17/17
"$PY" scripts/parse_runtime_log.py [路径]               # 真证据进来后跑这个（默认扫 runtime_evidence/）
```

⚠️ 两个 Windows 坑（今天各撞一次）：**中文别塞进 bash heredoc 的 Python 源码**（控制台编码会打碎成
`SyntaxError` ⇒ 长中文改档一律走脚本文件）；`.agent/versions/` 下面是**目录**，按文件读会 `PermissionError`。
⚠️ 竞品仓的 `extracted/` 有 **8+GB**，禁止递归读/搜。
