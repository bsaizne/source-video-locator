# 交接 2026-10-18（21:5x）— scn3 + scn4 落地完成，待出包 r27

> 自包含交接件。下一会话读这一份 + `.agent/STATE.md` 顶部「续67」块即可接手。
> 上位明细：`mvp/docs/IMPL_SCN3_20261018.md`（§1~§7 = scn3、**§8 = scn4 全记录**）；
> 计划：`mvp/docs/PLAN_BOUNDARY_ALIGNMENT_20261018.md`；判据读数：
> `mvp/docs/FINDINGS_BOUNDARY_PRECISION_20261018.md`（§9~§11）。
> 本仓 `D:\claudework\benchmark`。**代码已完成且已推送远端（`ad7cec4..a00231c`）**。

## 0. 一句话状态

**立项①（scn3）+ 立项③（侧车）+ 立项② 方案 A2（scn4）全部落地，4 片硬验收双通过，
代码已推远端。唯一剩下的是「出包 r27 + mac 另走 dispatch」——没做，等用户口令。**

## 1. 本轮做完什么（三条立项全闭环）

| 立项 | 状态 | 代码笔 | 核心读数 |
|---|---|---|---|
| ① scn3 网格精度 | ✅ 落地 | `5bb8089` | 边界时刻 1fps→10fps 原始；373/943 条边界离开网格 |
| ③ scene_strength 侧车 | ✅ 落地 | `5bb8089` | 独立性设计，不动 scenes.npy schema |
| ② CLS 腿独立门（A2） | ✅ 落地 | `b6e9113` + `a00231c` | 严格 127→135、主 span 100→131 |

**关键设计**：scn3 = 判据一格未动（`items` 仍存 `times[j]`，原始时刻走并行字典 `raw_by_snap`）；
scn4 = 像素门 **OR** 语义门（不是替换），`cls_cut_abs` 0.30→0.40（**耦合对**，注释写清了不能单独改）。

## 2. 硬验收读数（出包前的两条，都过了）

### 三指标（139 正样本 / 9 负样本，基线 `work/baseline_four_metrics_exportreal.json`）

| 指标 | 基线 | scn4 | 变化 |
|---|---|---|---|
| **严格命中** | 127 | **135** | **+8** |
| **主 span 命中** | 100 | **131** | **+31** |
| 场景命中 | 137 | **138** | +1 |
| **假阳** | 4 | **4** | **0（未恶化）** |

逐片严格：2mkv 36→**39/39** · test1 40/43 · test2 15→**19/20** · test3 36→**37/37**。

### 导出计划不变式

**`FAILED=0`**（4 片 × 4 通道五条全绿）：贴接重叠裁到 0 · 覆盖 Δ=0（133.547/80.296/71.072/115.439）·
三通道同 plan=是 · 卷轴去重逐条对上。

**导出段数未膨胀**：四片 clip **229**（70/44/46/69），基线 **234**（72/45/47/70）⇒ **反少 5 段**。

## 3. 产物与复跑

```bash
# 四片重跑（≈2h5m；索引走 refresh_derived，不重抽 CLS）
PYTHONPATH=mvp/src;mvp python work/scn3_impl_20261018/rerun_scn4_four.py
# 三指标（基线对照）
PYTHONPATH=mvp/src;mvp python mvp/scripts/measure_four_results.py --pattern "work/scn4_{case}.results.json"
# 导出计划不变式（出包前门槛，退出码 0=全绿）
PYTHONPATH=mvp/src;mvp python mvp/scripts/check_export_plan_invariants.py --pattern "work/scn4_{case}.results.json"
# 生产实现 vs 探针读数一致性（关键验收）
PYTHONPATH=mvp/src;mvp python work/scn3_impl_20261018/verify_a2b.py
```

Python = `D:\claudework\video-dedup-tool\.venv\Scripts\python.exe`；ffmpeg = `tools/ffmpeg.exe`。

## 4. 未结项（下一会话从这里接）

1. **出包 r27 + mac 另走 dispatch**（唯一剩下的主线）。`mvp/src` 已改完且验收过，可直接构建。
   构建 = `mvp/ui/scripts/build-release.ps1`；**mac 必须另 dispatch**（backend 由 CI 现编）。
2. **真索引上的 `refresh_derived` 端到端仍未跑完**：重扫 8221s@10fps 实测 >6min 且无进度输出
   （`Tee-Object` 整段结束才落盘），我当时停掉了。链路已用合成片 + `verify_equiv.py` 分头证过，
   但**「真索引整链路一次跑通」这件事没有直接证据**——若要更硬，出包前可补跑一次（留 10min+）。
3. 立项③「下游按阈值标注」未做（侧车只备好了强度数据，UI/告警口径未接）。
4. 下次出包（r27）删 r24：`work/r26_pkg/precheck_delete_r23.py` 改 `EXPECT`/`DELETE` 复用，
   删前双验、期望值从 `.agent/**.md` 文本里抓（**不要凭记忆**）。

## 5. ⚠️ 本轮我犯的六个错（**别再踩**，全留档）

| # | 错 | 正确做法 |
|---|---|---|
| ① | 只看 F1 涨（0.842→0.863）就判「有正收益」，未拆增益来源 | 必须拆 Gain/Lose + TP/FP |
| ② | 又只看 R 没涨就判「立项② 判负」 | R 不升≠没救回，要看具体条目 |
| ③ | **探针有 bug 却拿去给别人判死刑**：`blocks_cls(feats, k+1)` 把 CLS 帧索引当特征行号 | 语义门必须按**绝对时刻**取块（同生产 `gate(t)`）|
| ④ | **多模态复核是用户问了才补**，而读图直接推翻我的判负 | 判「某通道无效」前**必须先用 0.2~5fps 读到画面** |
| ⑤ | 看到「131/139」就以为退化 | 那是 `main_hit`；严格实为 **135/139**（基线 127）⇒ **报数前确认口径并对照基线** |
| ⑥ | 迁块用「块首 → `## Completed`」切片，把后续块一起覆盖，`Current Task` 3→1 块（**发生两次**） | 必须按「本块首 → **下一块首**」切片 + **写前断言块数**；靠 `git checkout` 恢复两次 |

另有两条**技术性漏接/假读数**（同族，但形态不同）：

- **生产配置注入漏接**：`cls_cut_abs`/语义门只改了 `SceneDetectConfig`，而生产走 `config.py`→`locator_service`
  逐字段注入 ⇒ **scn4 起初在真实管线里根本没生效**（第一次跑四片打印 `0.30`）。
  **教训：改判据必须验证「生产管线实际拿到的值」，光看 dataclass 默认值等于没验。**
- **旧 `long_take_ctrl` 的段内峰被段边界污染**（`[t0+0.5, t1-0.5]` 把段起点自己的峰算进去）、
  **`round(,3)` 把 0.1196 舍成 0.12 恰好等于门槛**造出假阳性分类。
  **教训：判门限必须用未舍入值；找「段内峰」要排除段边界（我改用两端各排 3s）。**

## 6. 硬读数速查（引用时注意口径）

- **scn4 尺子**：TP 109→**111**、FP **25 持平**、FN 16→**14**、F1 0.842→**0.851**
- **scn4 全片边界**（test1 8221s）：942→**912（−3.2%）**
- **A1 被否**：只在 cut.30 加语义门 ⇒ 尺子只 +3 FP 看着无害，但**全片 +10.9% 边界**（导出段数涨一成）
- **只提 cut_abs**（语义门关）⇒ 尺子 FP 25→**38**（纯亏）；`cls_cut_abs` 与语义门**是耦合对**
- **图证四处**（读图确认真切点）：test1 `5411.46`（红毛衣女子→灰衣男子）· `5415.46`（切回）·
  test2 `4573.3`（三人全景→两人近景换机位）· test3 `6682.4`（少年→中年男子换人）
- **长镜头不是「误切」是「该切没切」**：`scenes.npy` 50 段 >30s（2968s / 全片 36%）；
  干净归因 P2 32 段 / P3 11 段 / G 6 段 / 全通过 0 段

## 7. Windows / 工具坑（本轮新增）

- **`pwsh` 里 `Tee-Object` 写日志在长任务中不落盘**（整段结束才写）⇒ 想实时看进度就别用 Tee，
  直接重定向 `> file 2>&1` 并另起命令 `Get-Content -Tail`。
- **配置链路真实值必须实测**：`load_config().pipeline.xxx` + 模拟注入，两头都要打印（见 §5 的两条）。
- **test1/test2 原片扩展名不同**：`test1-om.mkv` 但 `test2-om.mp4` / `test3-om.mp4`（`os.path.exists` 逐条验过）。
- **`run_code` 写长中文用双引号数组 `join`**，不要用模板字符串（反引号会提前闭合，报误导性语法错）。
- **迁 STATE/TODO 块必须断言块数**后再写盘；切片起点用「下一块首」而不是「章节尾」。

## 8. 本轮提交（已推远端 `ad7cec4..a00231c`）

```
a00231c feat(scn4): 补生产配置注入 + 完成 4 片硬验收
5f4fe94 docs(agent): 续67 立档 — scn4 方案A2落地 + A1被否 + 四个错留档
b6e9113 feat(scn4): CLS 腿独立语义门（像素门 OR 语义门，方案 A2）
4d8fa71 docs(agent): 续66 立档 — scn3+侧车落地 + 三个实现坑 + 两次迁块事故
5bb8089 feat(scn3): 场景边界保留像素腿10fps原始时刻 + scene_strength侧车
cbf4b44 docs(plan): 边界线三项立项
643f198 docs(agent): 续65补三 — 长镜头归因+问题表述订正
e11a19e docs(agent): 未结项②改相对门结案=不做
bf35e40 docs(agent): 续65 立档 — CLS 0.718 结案=假缺陷
```
