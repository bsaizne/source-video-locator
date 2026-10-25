# HANDOFF — 续96/97 性能与调研批（2026-10-26，写于关机前）

> 自包含交接件。上一份有效交接 = STATE `Next Actions` 续97 指针（`41ef170`）。
> 读这份 + `mvp/docs/FINDINGS_PERF_HARDPROBLEMS_SURVEY_20261026.md` + `mvp/docs/PLAN_SMART_RENDER_20261026.md` 就够。

## 1. 本批做了什么（续95 → 续97 全链）

- **续95（口令「开始吧/开始」）**：① dense_recheck 默认开（146→147 零退化）+ 修掉 trim 包含形态
  亚帧丢画面缺口（test2 −16ms 违反覆盖门；亚帧余量改内层吸收）；② `degenerate_warning` 旁路标注
  落地（gate 拒因降级，不拒行；E2E test2 触发 1 行 = A/B gate 拒识同行；test3 六条被拒行逐图
  = 3 拒对 + 2 误伤 + 1 NEAR）；④ ③④⑤ 三轮 A/B 补跑完**全部维持默认关**；⑤ **r29 已出包**
  （`Video-Locator-win-x64-20261025r29.zip` 1,018,084,363B / backend.exe sha16 `cc212c6029ba700e`
  / 五道验收全绿 / face_identity 资产接包 + numba 排除 -120MB）。
- **续96（三口令）**：conf_v2 拍板默认关；r27 已删（删前三档双验，释放 936MB，现两档 r29+r28）；
  mac dispatch 用户待定。
- **续97（口令「可以，9点前花完token」）**：渲染 **workers 2→6 = 2.3x**（60.1s→26.3s 实测，
  `379c1fd`）；dense_recheck 分级复核**判负**（test1 严格 42→41；细窗仅占 locate 5-10%，
  调研估计已订正；代码 opt-in 默认关）；三路业界调研落档（XFeat / ArcFace / FFmpeg MV 第三腿 /
  DML 陷阱清单）。

## 2. 现役状态

- HEAD = `41ef170`，工作树干净，**领先 origin/master 26 笔未 push**（push 时机归用户）。
- Windows 现役包 = **r29**（含 dense_recheck 默认开 + degenerate_warning + face_identity 资产）；
  `release/` 两档 r29+r28。workers=6 渲染提速**尚未进包**（r30 生效）。
- 后端 **742**（+4）/ API **150** / UI 166 全绿；四片 GT 150 行：严格 147 / 导出实得 142 / 场景 149。

## 3. 待办（按优先级，都需口令/用户动作）

1. **mac dispatch**（用户待定）：r29 起代码+资产+main.ts 都变了，mac 包必须重出。
2. **smart render 两决策点**（PLAN_SMART_RENDER §4）：① 实现「仅 H.264 源」条件快路径；
   ② HEVC 源（3/4 素材）是否改输出契约（成片 HEVC 10-bit + hevc_amf）。
3. **XFeat 起点精修**（1.8k★ Apache-2.0，CPU 实时；旁路字段形态攻「时刻三成对」）——下一批首选。
4. **SFace→ArcFace**（yakhyo/face-reidentification MIT；须重标 cos 阈值——需扩样本对）。
5. 低成本探针批：DINOv2 ONNX batch 静态化重导出、518→392 分辨率探针（需 bump feature_version
   重建索引 + 三指标复测）、AMF 显式码控（`-rc vbr_peak` 防欠冲）。

## 4. 别再做的事（本批判负/排除清单）

- **dense_recheck 分级复核**：1fps 粗证据结构性框不住 10fps 细峰（10fps 峰常落 +0.1~0.9s），
  test1 实测 −1 且细窗仅占 locate 5-10%。代码已留 opt-in，**不要再提降 fps 预筛方案**。
- **d3d11va 硬解**：本机实测比 CPU 软解慢（0.48 vs 0.22s/2s 窗），解码仅占渲染 36%。
- **INT8 量化**（DML EP 不支持，静默回退 CPU）/ **WebGPU EP**（无 AMD 桌面 ViT 数据，实验性）/
  **换 SBD 主干**（正反打是信号源问题非模型问题）/ **换 backbone / FAISS**（护栏/规模不配）。
- 历史判负不变：DTW、TopK、TN 原片侧、三通道、subshot、非外观信号（用户 2026-10-19 裁定）、灰带下放。

## 5. 环境与复现

- `PY=D:/claudework/video-dedup-tool/.venv/Scripts/python.exe`；后端全套
  `PYTHONPATH="D:/claudework/benchmark/mvp/src;D:/claudework/benchmark/mvp" $PY -m unittest
  discover -s mvp/tests -p "test_*.py"`（742 项 ≈3 分钟）。
- 渲染复现：`work/scn4_2mkv.results.json` + `TimelineMovieRenderer`（workers=config.render.workers）。
- A/B 产物：`work/ab_dense_recheck_coarse_{2mkv,test1,test2}.results.json`（判负证据）；
  对照基 = `work/ab_dense_recheck_{case}`。
- 关机前所有后台任务已结束；无未保存状态。
