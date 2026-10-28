# HANDOFF — 2026-10-29 批次3 收口（自包含）

> 分支 `master`，远端 = 本地。交接时 HEAD = 本文件所在提交的父提交 `273ee8a`（+本档案笔）。
> 本轮三笔：`e2122f9`（B3-1 翻默认）· `63128eb`（smart render B 帧修正 + 批次3 findings）· `273ee8a`（STATE 收口）。

## 1. 一句话状态

批次1（三 bug + mAP@δ 尺子）、批次2（四项离线候选全不采纳）、批次3（索引并发成立并翻默认 / smart render 第二次判负关闭）
**全部结完**；产品代码面新增两处默认：`index_parallel_passes=True`、以及维持 `smart_render_enabled=False`。
**尚未出包**——现役 r29（10-25 构建）不含 XFeat、批次1 修复、批次3 并发。

## 2. 本批拿到的读数（要引用请连口径一起引）

| 项 | 结论 | 关键读数 |
|---|---|---|
| B3-1 索引两遍解码并发 | **成立，默认 True** | 2mkv 723.3→582.2s（1.24×）· test3 954.1→818.1s（1.17×）；六件产物逐字节相同；合成进度单调 |
| B3-3 smart render | **第二次判负，永久关闭** | 根因=B 帧数不匹配（已修，4513/4513）；但 copy 仅 **6.18%**、墙钟 **0.51×**、CFR 破坏 |
| 建索引成本结构（订正旧口径） | 解码两遍 ≈40% / DML 推理 ≈60% | 旧的「抓帧 78%」已过期，勿再引用 |

明细：`mvp/docs/FINDINGS_BATCH3_20261028.md`（本批）· `FINDINGS_BATCH2_20261028.md`（四项判负）·
`FINDINGS_BATCH1_20261028.md`（三 bug + 尺子）。

## 3. 别再试的清单（本轮新增，避免重复烧时间）

- **smart render**：两次判负，第二次连根因都修对了仍不成立（copy 占比 + 墙钟 + CFR 三条同时崩）⇒ 关闭。
- **Drop-DTW / 跨镜头丢弃式对齐**：帧匹配得好但位置错，丢弃机制无效（跨镜头 1.17s vs 单点 1.00s）。
- **置信三件套**（AS-Norm / k-reciprocal / Mahalanobis OOD）：AUC 0.42/0.50/0.33，无区分力。
- **VQ2D 式扩窗**：比现役差 62%（扩窗与宽搜两件事都在减分）。
- **MAGSAC 替换**：退化段中位 1.33→1.38，无增益。
- **yuv420p 管道**：仅省 ≈6%，且改像素路径 ⇒ 触发全量重建。
- 旧清单（TopK / 平 DTW / 三通道 / 子镜头重定位 / 非外观信号选子镜头）仍然有效。

## 4. 未闭合项（按优先级）

1. **bug1 生产四片 A/B**（批次1）：`text_anchor` 保留 CJK 后 OCR 字牌腿对中文素材**首次真正生效**，
   净效应未验；`text_anchor_enabled=False` 可兜底。建议并入下次出包批。
2. **出包**：Windows 下一次构建才含 XFeat/三 bug/索引并发；mac 需 dispatch（改 workflow 需授权）。
3. **批次4 立项**：MV 压缩域切点通道（PyAV `export_mvs`，机位切换=运动场翻转）是唯一「换信号源」的候选，
   直接决定「同场景多机位切点盲」这条已判负三次的线有没有第四种打法。**需口令**。
4. B3-2（单次解码双输出）：**不做**（B3-1 已达标，Windows 双管道风险高于收益）。
5. release/ 保留档（r29/r28）与删除、push 节奏：均等口令。

## 5. 环境与复现

```bash
# 门禁（改动 mvp/src 后必跑）
PYTHONPATH="mvp/src;mvp" D:/claudework/video-dedup-tool/.venv/Scripts/python.exe -m unittest discover -s mvp/tests -p "test_*.py"   # 771 OK(skipped=2)
PYTHONPATH="mvp/src;mvp" D:/claudework/video-dedup-tool/.venv/Scripts/python.exe -m unittest discover -s mvp/api/tests -p "test_*.py" # 150 OK

# 批次3 读数复现
D:/claudework/video-dedup-tool/.venv/Scripts/python.exe work/b3_20261028/eq_full/run_full.py       # 约 45 min
D:/claudework/video-dedup-tool/.venv/Scripts/python.exe work/b3_20261028/smart_render/timed.py    # 约 2 min
```

- 硬件：12 核 / RX 6750 GRE；DML 推理 batch=1 固定。
- 计时纪律：同脚本双臂、独占设备（建索引并发会显著影响其它 GPU 任务）。
- 仪表坑（本轮）：`ffprobe -count_frames` 必须把 `nb_read_frames` 写进 `-show_entries`，否则恒 0。

## 6. 回滚点

`6ff3b5b`(批次1 收口) → `b1c4403`(批次2 收口) → `7f132be`(B3-1 初版, 默认关) → `e2122f9`(B3-1 翻默认) →
`63128eb`(smart render B 帧修正) → `273ee8a`(STATE)。任一格独立可回退；B3-1 单点回退 = 把
`index_parallel_passes` 改回 False。
