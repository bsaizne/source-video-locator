# 交接 2026-10-18（16:3x）— 边界线：误差分型 + 索引网格损失（scn3 预演）+ B 线判负

> 自包含交接件。下一会话读这一份 + `.agent/STATE.md` 顶部「续64」块即可接手。
> 上位明细：`mvp/docs/FINDINGS_BOUNDARY_PRECISION_20261018.md`（§1 分型 / §2 网格损失 / §3 scn3 预演 /
> §4 空间通道 / §8 B 线判负与判据订正）；`.agent/CHANGELOG.md` 2026-10-18「续64」段。
> 本仓 `D:\claudework\benchmark`；口径全部**只读**（`mvp/src` 零改动、索引未重建、无新依赖）。

## 0. 一句话状态

现役包仍是 **r26**（mac 已换、与 r26 同步）。本轮**没有出包、没有提交、没有接线**；
工作树新增 = `mvp/docs/FINDINGS_BOUNDARY_PRECISION_20261018.md` + `mvp/scripts/shot_detect/probe_scn3_precision.py`
（两个 untracked）+ `.agent/{CHANGELOG,STATE}.md` 修改；`work/` 下的读数为不入库产物。

## 1. 本轮做了什么（五件，读数索引）

| # | 事 | 关键读数在哪 |
|---|---|---|
| ① | 边界误差分型（漏检/漂移/假阳） | FINDINGS §1；先复现 0.732/0.832/0.779 再拆 |
| ② | 索引网格损失（本轮核心） | FINDINGS §2；`abs_med` 0.250→0.050、`le0.12` 27.6%→77.9% |
| ③ | scn3 预演（新探针，已入库） | FINDINGS §3；A 0.250/27 · B 0.050/82 · **C 融合 0.100/80** |
| ④ | 空间结构通道判负 | FINDINGS §4（但注意 §8.1 的判据订正） |
| ⑤ | B 线（语义分格 CLS）判负 + 判据订正 | FINDINGS §8；两窗口 AUC 0.555/0.553 |

## 2. 三处我自己的错（**别再踩**）

1. **把 `abs()` 当有符号量**：`eval_shot_detector.match()` 返回的是 `|p-g|`，我拿去算有符号偏差，
   得出「104 条 100% 偏晚、中位 +0.260s」——**假读数**。手查 `419.48 → 419.0 = −0.48` 即破。
   订正后：有符号中位 **0.000**、偏早 38 / 偏晚 40（无系统偏置）。
2. **判据窗口与样本精度不匹配**：`t1_missed_attr.json` 那 52 条的时间精度是 **±2~4s**
   （`t1_long_sheets.py:33 FPS=0.25` 接触表每 4s 一格；`t1_missed_attr.py:54 WIN=2.0`），
   我第一版用 **±0.5s** 取峰 ⇒ 等于随机抽样，由此得出的「AUC 0.42~0.53 判负」**作废**。
   重算（±2s / [-4,0]）后 A 族 0.555、B 族 0.553——**结论没变但判据是干净的**。
3. **差点用「画面看着一样」下结论**：1s 采样接触表上看 4 条样本「完全没切」，0.2s 重采样后
   发现两条是**真切点**（`t=1831` 屋顶→火焰 @t+1.2s；`t=6861` 双人全景→遮挡近景 @t+0.4s）。
   ⇒ **判断「有没有切」必须 0.2s 级采样**；另外做抽帧自查（5 个远隔时刻画面全不同）排除假读数。

## 3. 硬读数（要引用就用这些）

- **分型**（尺子 44 窗 / GT conf=high 125 条，±1.0s 一一配对）：漏检 **21（16.8%）** · 漂移 **104**
  （le0.12s **26** / 0.12~0.50s **63** / >0.50s **15**）· 假阳 **38** · 有符号中位 **0.000**。
- **网格损失**（同批候选唯一变量 = 是否 snap）：`abs_med` **0.250 → 0.050**；`le0.12` **27.6% → 77.9%**；
  `le0.50` 86.7% → 98.1%；现役漂移 `p90` = **0.520s** = 1fps 吸附上限。
- **scn3 预演**（尺子 ±0.5s）：A 现役 n=93 **0.250 / le0.12 27** · B 像素10fps n=103 **0.050 / 82** ·
  **C 融合 n=105 0.100 / 80**；窗内条数 **A 142 / B 128 / C 134**（不碎）。
- **导出侧交叉验证**（`edge_offsets_v2` 11 条真剪点）：A **0.249**（le0.12 4/11）· B/C **0.000**——
  ⚠️ **同源**（真剪点也是逐帧像素差定位），只有 A 的偏差可独立引用。
- **B 线判负**：语义分格（整帧+左中右三竖条 CLS）两窗口 AUC 最好 **0.553**；A 族同批最好 **0.555**；
  判死线 0.70。旁证：GT 处整帧语义距离 **0.0869** vs 随机 **0.0857**。
- **52 条漏切拆 verdict**：P2（低于绝对门 0.12）**45 条 = 87%**（pix 中位 0.040）·
  P3（被「3×邻域中位」否）**5 条**（pix 最高 0.684，含读图确认的 2 条真切点）· P1 1 条 ·
  **`?CLS腿应命中` 1 条（`cls_max 0.718` 远高于门 0.30 却漏 ⇒ 疑似真缺陷）**。

## 4. 未结项（下一会话从这里接）

1. **查那条 `?CLS腿应命中`（cls_max 0.718）** —— 优先级最高，疑似几行代码能定位的真缺陷：
   CLS 腿距离 0.718 远超 `cls_cut_abs=0.30`，却没产出边界。可能原因：非局部极大 / 被 gate 否 /
   被 `min_gap_s` 的 NMS 吃掉 / `_snap_index` 落到窗界外。逐条打点即可定性。
2. **接 scn3（网格精度）**：`build_scene_table` 让 `scenes.npy` 保留像素候选的 **10fps 原始时刻**
   （schema 不变、仍连续覆盖全部帧），版本位 `scn2 → scn3` 走 `FeatureStore.refresh_derived`。
   预期：边界表 `abs_med` **0.250 → 0.100**、`le0.12s` **27 → 80**、窗内条数 142 → 134。
   代价：`mvp/src` 改动 ⇒ **出包 r27 + mac 另走 dispatch**；验收须含尺子三档 + 四片导出实得 +
   导出计划不变式 + 后端/API 全套。**接线才能验「端点 0.249s 是网格造成的」这条归因假设**。
3. **改相对门**（P3 那 5 条，收益上限 5/125 = 4%）：`pixel_rel_mult=3.0` 在强运动/闪切段过严。
   属判据改动，需用户拍板值不值。
4. **B 线不要**：两窗口都判负，且只能覆盖 10% 漏检；87% 的 P2 连语义都不动。
5. **主线「过渡不流畅」**仍缺三样外部输入（他指认的具体秒数 / 未转码原始 `movie_*.mp4` /
   `<解说片名>__<hash8>.results.json`）。**别再在编码层/参数层重试**。
6. **下次出包（r27）删 r24**：`work/r26_pkg/precheck_delete_r23.py` 改 `EXPECT`/`DELETE` 复用，
   删前双验、期望值从 `.agent/**.md` 文本里抓（不要凭记忆）。
7. **已被裁决不做、勿再提议**：C 盘清理三项 · ⑤ 导出实得口径 · 成片缺口标记 · mac 严格惰性再 dispatch · ⑥a/c/d 探针族。

## 5. 复跑命令（绝对路径 python；bash PATH 里没有 python）

```bash
# 尺子三档（A 现役 / B 像素10fps / C 融合 scn3）
PYTHONPATH=mvp/src;mvp python mvp/scripts/shot_detect/probe_scn3_precision.py --save
# 导出侧真剪点交叉验证
PYTHONPATH=mvp/src;mvp python mvp/scripts/shot_detect/probe_scn3_precision.py --cuts --save
# 现役口径复现（应与档案 0.732/0.832/0.779 一致）
PYTHONPATH=mvp/src;mvp python mvp/scripts/shot_detect/eval_shot_detector.py --mode arms
```

Python = `D:\claudework\video-dedup-tool\.venv\Scripts\python.exe`；ffmpeg = `tools/ffmpeg.exe`。

## 6. 本轮产物

- 入库候选（两个 untracked）：`mvp/scripts/shot_detect/probe_scn3_precision.py`、
  `mvp/docs/FINDINGS_BOUNDARY_PRECISION_20261018.md`
- 不入库读数：`work/scn3_precision_20261018/probe_scn3_{gt,cuts}.json`、
  `work/ab_boundary_channel.json`、`work/spatial_b_probe.json`、
  `work/boundary_20261018/`（5 脚本 + `series/*.npz` ×44）
- 读图证据（在会话工作区，不在仓内）：`D:\deepseek harnees\.svlprobe\t1sheets\`
  （`t1_missed_sheets.png` 粗采样 / `fine_1831.png`、`fine_6861.png` 0.2s 细采样 / `selfcheck_times.png` 抽帧自查）

## 7. Windows / 工具坑（本轮新增）

- **`run_code` 里写长中文文本必须用双引号数组 `join`**，不要用模板字符串：模板里有反引号会提前闭合，
  报出来的是「Unexpected character '≤'」这种**误导性语法错**（我为此白跑了两轮）。
- **判断「有没有镜头切换」必须 0.2s 级采样**；1s 采样在长镜头里会漏掉瞬切（本轮实证）。
- `ffmpeg -ss` 在 `-i` 之前是快速 seek（关键帧级）；抽帧自查方法 = 抽 5 个远隔时刻拼条带，画面全不同才算生效。
