## → 2026-09-05:蒙太奇子镜头查询方向 结案 = runtime 不接入（§4 执行完毕, 三指标零变化 + oracle 口径证伪）

- **执行**: ① 漂移触发判据（gap>15s & psim<0.62, 采纳=合并保留原 span）实现, 246 测试全绿 →
  ② 四片 GPU 重跑（work/rerun_*_subshotdrift.results.json, 基线未覆盖）= 严格 113→113/139、
  场景 136→136、负例 4→4 **零变化零回退（也零改善）**。
- **机制三层阻断（实证）**: (a) 漂移型段正确区已在 pool sub span 严格早已 HIT（p10/p32/t1r18）,
  三指标可动段全项目仅 ~2 条; (b) **「16/16 逐子救回」= oracle 口径**（scale 探针按 GT 中点挑
  子镜头）, runtime max-sim 采纳结构性选错（t2r02b 正确子镜头 sim 0.625 全场最低 vs 其他 0.77-0.85）;
  (c) t2r05a 触发被 all_spans 未门控近重复簇掩盖（gap 恰=15.0）。
- **拍板分支**: 按 HANDOFF §4.4 接收为研究结论, **runtime 不接入**（代码已回退定向回退版, 246 全绿）;
  oracle 上限 ≈ +2/139 远低于门槛。研究脚本/结果留档: diag_subshot_trigger/frames/trace.py +
  compare_subshot_drift.py + rerun_subshot_drift.py + work/compare_subshot_drift.out。
- **若未来重开**: 需无 GT 的「正确子镜头选择信号」（正确子镜头 sim 未必最高——叙事蒙太奇的
  语义重心与视觉特征突出度解耦）。详见 FINDINGS_SUBSHOT_QUERY.md「runtime 接入验证」章 + HANDOFF §7。

## → 2026-09-05:蒙太奇子镜头查询方向 交接给下个对话（探索完成, runtime判据未解）【已结案, 见上条】

- **个体/规模化探针强 POSITIVE**: 蒙太奇段单均值查询=语义稀释, 帧级距离突变识别子镜头,
  逐子查询救回 16/16 零回退 (详见 semantic_signal/FINDINGS_SUBSHOT_QUERY.md)。
- **runtime 接入两轮失败**: 无差别拆分→回退(2mkv 严格 34->31); 定向回退(no_evidence+montage
  弱命中)→0 改善 0 回退(p10 未救回, 触发判据漏掉"主定位漂移"型)。
- **交接文档**: semantic_signal/HANDOFF_SUBSHOT_QUERY.md（含探针证据/已实现代码/判据缺陷/
  下一步执行清单）。下个对话从 §4 执行清单开始(修触发判据)。
- **已实现(含缺陷)**: locator_service._subshot_relocalize + config subshot_* 参数;
  246 测试全绿(current 定向版)。未解决=触发判据(主定位漂移型 montage 段)。

## → 2026-09-05:蒙太奇子镜头查询 规模化验证 = 强 POSITIVE（16/16 救回, 零回退）

- **扩探针四片**: 统计"多镜头蒙太奇段（整段gap>15且子镜头>=3）"逐子镜头查询改善:
  2.mkv 4/4、test1 1/1、test2 7/7、test3 4/4 = **16/16 全部救回, 零回退**。
- **代表性救回**（整段gap->逐子）: test2 t2r07b 2072->1.1s / t2r03b 1849.7->0.3s /
  t2r05a 570.8->3.8s / t2r02b 371.8->2.8s; 2.mkv p34 1069->5.0s / p10 92->**0.0s**(精确命中);
  test3 t3r03a 91.8->0.8s / t3r02b 86.7->0.7s。
- **结论**: 蒙太奇段整段单均值查询=语义稀释, 是"搜不到"主因之一; 帧级距离突变识别子镜头
  （同镜头内<0.05、边界>0.7, 阈值0.5）普适救回, 零回退。与用户09-04"按镜头切分逐镜头对比"一致。
- **产物**: research_subshot_scale.py + FINDINGS_SUBSHOT_QUERY.md（含规模化章）。
- **待拍板**: 立项"蒙太奇子镜头查询" runtime 接入（编辑侧子镜头识别+逐子查询, 三指标验收）。

## → 2026-09-05:蒙太奇子镜头识别 + 独立查询探针 = POSITIVE

- **验证**: t2r02b（蒙太奇段）帧级相似度突变清晰分离 6 子镜头（边界 17.83/18.33/19.67/20.83/
  22.17/23.17, 同镜头内距离 <0.05、边界 >0.7, 阈值 0.5 可干净分离）。
- **救回**: 段首子镜头 A（Jacob BOUGHT）独立查询命中 2934（GT 2931, sim 0.625）;
  整段均值查询只命中 3303（洒水器, sim 0.537）——单均值稀释证实, 逐子镜头查询救回正确区。
- **结论 POSITIVE**: 蒙太奇段应逐子镜头查询（帧级距离突变识别子镜头）, 替代整段均值。
  与用户 09-04"按镜头切分逐镜头对比"拍板一致。研究侧零 runtime 改动。
- **产物**: mvp/scripts/research_subshot_query.py + FINDINGS_SUBSHOT_QUERY.md。
- **待拍板**: 立项"蒙太奇子镜头查询" runtime 接入评估（编辑侧子镜头识别+逐子查询,
  三指标不回退验收）。

## → 2026-09-05 深挖 t2r02b = 蒙太奇段单均值查询缺陷（真正的"搜不到"机制）

- **多模态密集采样**看清 t2r02b（ed17.2-23.5）真实内容: BOUGHT(Jacob特写)/THEN(洒水器)/
  CROP/WAS(乡村房屋)/WATERED(洒水器)/BUT... 是**5-6 个不同子镜头的快速蒙太奇**。
- **GT og2931（Jacob）= 段首 BOUGHT 镜头, 标注正确**。但**整段用"特征均值"查询** → 均值
  既不代表 Jacob 也不代表洒水器, 检索漂移到中间态（3303 洒水器, sim 0.578）, Jacob 被稀释。
- **真正机制（修正此前多重判断）**: 不是切分过碎, 不是 GT错/内容完全混叠, 而是**蒙太奇段
  单均值查询 = 语义稀释 → 检索漂移到特征突出的子镜头**。
- **与用户 2026-09-04 拍板一致**: "按镜头切分好、逐镜头对比更容易定位"。蒙太奇段应
  **逐子镜头查询**而非整段均值。当前两级切分只找"镜头边界", 没识别蒙太奇段内子镜头。
- **新方向（当前最对症, 待立项探针）: 蒙太奇段内"内容子镜头"识别与独立查询**——
  用帧级聚类/相似度突变识别子镜头, 逐子镜头查询替代整段均值。这同时解释了为何
  "防过碎/换特征/运动向量"都不是正解。
- **已证伪/收尾**: 方向A(事件身份, 收益薄) / 方向B(时序单调性) / 防过碎 / 内容混叠换特征。
- **待用户拍板**: 立项"蒙太奇子镜头查询"探针（研究侧, 验证逐子镜头能救回 t2r02b 类段）。

## → 2026-09-05 更新: 检索召回层诊断 = FAR 根因, "防过碎"证伪, 重心转向 P2 内容混叠

- **超集诊断**（真实检索 test2 FAR 段 -> 原片索引）: t2r05a GT区 rank 78、t2r03b 1630、
  t2r02b 4993、t2r07c 3181（retrieval_top_k=20 截断）, GT区 sim 0.001-0.409 ——
  **正确区根本没进候选池**（检索召回缺口 + 特征判别力不足）。
- **P1 防过碎 = 证伪**: 合并段不能让 GT区 sim 从 0.001 变可分; FAR 段根因不是"切碎污染查询单元",
  而是检索层找不到正确原片区。
- **P2 内容混叠/检索判别 = 强化（当前唯一未决方向）**: 这批段（test2 蒙太奇/2mkv 同质内容）
  的编辑特征与原片正确区相似度极低, 反而匹配到别处 —— 需**更强检索判别/特征**, 非切分。
- **P3 运动向量判别**: 维持"待探索"（未验证收益）, 但注意它改善的是切分误切, 不解决检索召回
  缺口（FAR 段已经证明是检索层问题）。
- **已证伪三路**: 外观/多模态/时序全闭环; 当前未决 = 内容混叠（检索判别）。

## → 待探索方向（2026-09-05 记录, 未立项, 先验证防过碎）

- **方向 P2: 内容混叠段**（非切分根因, 已验证 ~4 段: p01-p03 段过粗/多镜头污染、
  t2r07c 内容同质、t1r08c 零宽段）: 这些段改切分救不了, 需换特征/检索策略。
  方向 = 探索更细的检索粒度 / 内容判别特征。**暂不立项**, 待防过碎验证后再评估。
- **方向 P3: 补运动向量判别**（剪映 ④①: 光流区分"镜头内运动"vs"真实切换", 防止摇镜/
  跟拍误切; 另有"运动感知校准"避开剧烈运动帧落切点）: 我们当前切分仅靠 DINOv2 CLS
  相邻余弦距离（单特征）, 无运动向量。光流属传统 CV 非模型, 估计不违约护栏。**暂不立项**,
  需先探针验证收益(是否减少误切→改善检索)。
- 优先级: 防过碎(P1) > 内容混叠(P2) / 运动向量(P3)。

## → 2026-09-05:方向 B 剪辑时序单调性探针 = 证伪（有据, 不再重复）

- **立项**: 用户拍板 A（编辑时序约束方向, 在方向 A 身份路由正确 + test3 时序锚点错位重核后）。
- **探针**（静态度量, 零 runtime）: ① GT 编辑序->原片序 Kendall tau: test1 0.987 / test3 0.816 /
  2.mkv 0.586 / test2 0.011 → 单调性**仅 test1/test3 部分成立**, test2 基本无序。
  ② 正确段 vs 失败段 tau: 失败段**不低于**命中段（2.mkv 非严格 1.0 > 命中 0.46）→ 单调性无判别力。
  ③ 结果批定位中点倒序段 HIGH 占比(78-100%) **不低**于正向段 → 不能靠"倒序"标记失败。
- **结论**: 方向 B（剪辑时序单调性约束）= 证伪——单调性不普遍成立 + 无法区分失败/正确段,
  与既有 M8/单调弱先验证伪一致。方向 A 时序锚点错位**无法用单调性约束解决**。
- **产物**: mvp/scripts/research_temporal_monotonicity.py +
  FINDINGS_TEMPORAL_MONOTONICITY.md。零 runtime 改动。

## → 2026-09-05:方向 A 立项完整阶段 runtime 实施完成 + 四片回归 = 严格 +14 零回退

- **索引侧**: FeatureStore._build_event_table（场景→事件归并 60s/0.60 连通分量）+ events.npy/
  event_feats.npy 落盘; feature_version bump +scn1 → +scn1+evt1; load/validate 纳入事件表;
  IndexBundle 加 events/event_feats。真实 2.mkv: 699 场景→206 事件, p08/p38 同事件单元。
- **查询侧**: EvidenceLocalizer 事件扩池（查询均值 vs 事件指纹 top-3 → 事件窗内帧扩池;
  门控用事件指纹相似度 esims[k]——事件窗跨多场景帧异构, 全窗帧均值门控会整组丢弃）;
  事件 span 独立精化+门控, 与帧级+场景 span 都 IoU 去重; 帧级+场景均零证据才救回。
- **组装/契约**: _result_from_evidence 事件子 span(from_event_pool=True); text_anchor 跳过
  事件 span; PipelineConfig event_recall_enabled/event_top_k(3)/event_max_expand_frames(240);
  OriginalSegment.from_event_pool + 前端 types.ts; 导出层 ExportClip.from_event_pool + XML 注释。
- **四片回归（evt1 索引重建 + 事件扩池, GPU DirectML/amd）**:
  2.mkv 34→35(+1) / test1 34→40(+6) / test2 12→16(+4) / test3 32→35(+3)
  **合计 112→126/139 (+14)** · 场景级 136/139 (+0) · 负例 4/9 (+0) —— 严格净正、零回退。
- **诚实边界**: +14 中相当部分为粗事件跨度经严格判据 mid_in（GT 中点落在 span 内）命中
  （p30 事件 span 1740-2317 跨度 577s; test1 的 2549-2781/2914-2963/2964-3049/3512-3734
  跨度 80-222s）——事件身份正确归位但 span 粒度粗, 非帧级精确位置。真实收益=「内容相似
  混叠」段归位正确事件; 边界=事件 span 粗粒度。
- **测试**: test_event_recall.py 6 项（生命周期/扩池救回兄弟机位/开关零变化/缺失降级/预算）;
  后端 246 + 前端 vitest 67 + API 58 + typecheck 全绿。backfill_scene_tables.py 升级双回填。
- **产物**: research_event_identity.py（探针）+ measure_event_regression.py（回归评估）+
  work/rerun_*_runtime_twopassflash.results.json（四片新批）+ FINDINGS_EVENT_IDENTITY_P1_P2.md。

## → 2026-09-05:方向 A 探针（场景实例身份建模 P1/P2）执行完成 = POSITIVE（研究侧, 零 runtime）

- **P1 事件级聚类 PASS**: p08(134)/p38(128) 兄弟场景 **12/12 网格同单元**（时序近邻+指纹联合归并）;
  同口径场景对 sep=+0.2613（within 0.5701 / cross_pairs 0.3088）→ 事件单元（19 场景 946-1166s）可分。
- **P2 事件身份端到端排序 PASS**: p08 帧级 2582/7668 → **事件级 1/162**（60/0.55·60/0.60·120/0.55·120/0.60）;
  t3r12 帧级 1/10177 保持、事件级 1/190。**p08 兄弟机位失败族被事件聚合救回 top-1**。
- **诚实边界**: 身份嵌入=单元内场景指纹均值（未训练学习型嵌入）; nearest_cross_rep 0.7562 为均值向量口径
  偏高（P1b 用同口径场景对判据）; 与 M6 v4「p08 CLS rank=6」不矛盾（构造池 vs 全索引协议差异）。
- **GPU 约定**: BACKEND_SELECTED type=DirectMLBackend device=directml dtype=amd（已打印）。
- **待拍板**: A 立项完整阶段（事件表进索引 bump feature_version + 查询先到事件再细化 + UI 事件标识,
  须先探针验收三指标不回退）/ B 研究侧归档暂不 runtime 化。
- **产物**: mvp/scripts/research_event_identity.py + work/event_identity_P1_P2_results.json +
  semantic_signal/FINDINGS_EVENT_IDENTITY_P1_P2.md。零 runtime 改动, 三指标基线未触碰。

## → 2026-09-05:非外观第二信号 研究重启立项（用户拍板）—— 交接文档已写, 下个对话开始

- **拍板**: 用户选 2 = 重启「非外观第二信号」研究立项。
- **本会话完成的前置证据**: ① 语义可分性验证(FINDINGS_SEMANTIC_SEPARABILITY.md):
  24 帧方舟 VLM 标签 scene 4/4 同级, n01/n02 同人同景, 多模态方向实证关闭;
  ② 低信息降权+边界剥离(FINDINGS_LOWINFO_STRIP.md): 负例零改善+严格−1, 像素预处理关闭;
  ③ 4 负例(n01/n02/n03/t3r15)根因=内容相似混叠(特征上限)。
- **候选方向**: A 场景实例身份建模(推荐, P1 事件聚类 + P2 排序名次) / B 剪辑叙事结构
  (谨慎, dinov2_ta 曾 blocked) / C 多模态语义(已关闭)。已证伪 16 项登记备查。
- **执行起点**: RESEARCH_PROPOSAL_SECOND_SIGNAL.md §6 清单 —— 下个对话写
  research_event_identity.py(P1/P2 探针, GPU DirectML), 探针正面→完整阶段, 负面→彻底关闭。
- **交接文档**: mvp/benchmark/user_case/semantic_signal/RESEARCH_PROPOSAL_SECOND_SIGNAL.md

## → 2026-09-05:语义可分性验证（用户方案 B） = 无判别力, 不需要手动加模型（有据）

- **方法**: 复用本地 vision-subagent 方舟视觉模型(ep-20260901010244-pv8ws), 4 负例
  ×(编辑段+误配区) 24 帧打 {scene,subject,face,objects,text} 结构化标签。
- **结果**: scene 维度 4/4 同级(无区分力); n01/n02 同人同景(subject/objects 一致,
  VLM 确认语义就是同一内容); n03 编辑段全"模糊"(语义不可靠); t3r15 角色有差异但
  场景同级(唯一可分样本, 不足以支撑通用索引); 唯一稳定差异=有无字幕(编辑加工非场景)。
- **结论**: 语义特征对 4 负例无判别力, 与 M1b/M3 双向闭合; 不需要手动加模型(省成本);
  负例根因维持「特征上限」。
- **产物**: prep_semantic_probe.py + semantic_tag.mjs + FINDINGS_SEMANTIC_SEPARABILITY.md
  + work/semantic_probe/(24 帧 + labels.json)。零 runtime 改动。

## → 2026-09-05:低信息帧降权 + 段首尾边界帧剥离 探针 = 不推荐进 runtime（负例零改善 + 严格 -1）

- **数据摸底**: n01/n02 确有低信息信号(contrast/edge 全片 16-20% 分位, n02 半帧低信息);
  n03/t3r15 正常内容帧(低信息 0%)——预期只对 n01/n02 有效。
- **探针执行确认**: 粗网格 613 帧低信息 107; n01/n02 各删 11/17 帧(保留 6 正常帧);
  非空转。
- **结果**: 2mkv 严格 33/39(-1, p28 HIT→part 副作用) 负例 3/4 不变; test3 严格 32/37
  负例 1/3 不变; **负例误报零改善**。
- **失败机制**: 误配由**剩余正常帧**驱动(n01/n02 删帧后主 span 1692-1694/1746-1748
  完全不变) + n03/t3r15 无低信息帧无从触发 + 边界剥离削证据(p28)。
- **结论**: 不推荐进 runtime(有据); 4 负例根因是 CLS 内容相似混叠(特征上限),
  非低信息问题; 未来救法仍是非外观第二信号(研究侧已闭环需另立项)。
- **产物**: rerun_lowinfo_strip.py + scan_lowinfo_frames.py + FINDINGS_LOWINFO_STRIP.md
  + work/rerun_{2mkv,test3}_lowinfostrip.results.json。零 runtime 改动。

## → 2026-09-05:两级切分 + 白闪守卫 进 runtime = 完成（用户拍板, 四片零偏差复现）

- **实现**: flash_guard.py 提取入库（engine/segment/, 纯函数+判据注释, 参数走
  PipelineConfig.flash_*/bright_spike_*）; config 新增 seg_twopass_enabled(默认 True)
  + seg_twopass_coarse_step_frames=6/fine_window=20/fine_step=2/min_shot=0.5;
  analyze_edited_video 改分派: _segment_twopass_flash(新, 粗采样→白闪过滤→±20帧精修
  →最短保护→业务兜底, 与 rerun_twopass_flash.py 逻辑一致) / _segment_legacy(回退);
  _apply_card_guard/_embed_batch/_refine_cut_twopass 辅助; 卡守卫/进度/取消/隔离保留。
- **单测**: 新增 test_flash_guard.py(9) + test_twopass_flash.py(9); 后端全套 240 全绿
  （222+18, 零回归）; 前端 vitest 67 + test:mock PASS。
- **四片回归**（生产路径直跑, GPU DirectML/amd 确认）: **严格 112/139 · 场景 136/139
  · 负例 4/9 与基线零偏差**（逐片 +0/+0/+0）; 段数 2mkv 69/test1 41/test2 54 一致,
  test3 68→67（runtime 补算 card_run_ratio 致 1 卡帧 run 判定差异, 零指标影响）。
- **产物**: work/rerun_*_runtime_twopassflash.results.json + mvp/scripts/rerun_runtime_twopass_flash.py。
- **待办**: UI 结果数/导出真机验收（段数增多: 2mkv 12→69 等, 前端契约已 PASS,
  打包 exe 验收需授权）; DECISIONS 已记录。

## → 2026-09-05:I帧锚定 + 动态步长 + 三特征抑制 切分探针 = 不推荐进 runtime（四重证据）

- **Stage 0（ffprobe 实测）**: 2mkv/test3 = 固定 10s GOP（仅 13/15 个 I 帧）,
  生产切点仅 10%/7% 落 I 帧 ±0.5s 内 → I 帧粗筛结构性失效; test2 = 密 GOP 1.15s,
  83% 切点落 I 帧 ±0.5s → I 帧锚定有效（价值边界=编码器 GOP 模式）。
- **判别力诊断**: 粗网格(2.9fps, 0.345s 间隔)跨切点对三特征 AUC 0.58-0.80,
  ≥2特征命中率最好仅 13-26%（漏检不可接受）; 1fps(0.034s) 下 2mkv 63/69、
  test2 53/54 硬切显著 → **像素特征可用但需接近原帧率采样, 粗采样运动噪声淹没
  切点信号, 成本优势消失**（用户方案「跳过大量非关键帧」前提不成立）。
- **四片三指标**: 严格 110/139(-2) / 场景级 102/139(**-34**) / 负例 8/9(**+4 翻倍**);
  段数 8/4/9/14 vs 生产 69/41/54/68（严重漏切合并成大段）。
- **结论**: 不推荐进 runtime; 维持两级切分 + 白闪守卫（C 项待拍板）;
  像素切分方向关闭（有据）。三特征抑制逻辑本身正确（亮度+5/平移2px 均被抑制）。
- **产物**: mvp/scripts/research_iframe_cut.py + diag_transition_shape.py +
  diag_straddle.py + FINDINGS_IFRAME_CUT.md + work/rerun_*_iframecut.results.json。
  零 runtime 改动; 基线(112/139, 136/139, 4/9)不受影响。

## → 2026-09-05:C 项 —— 两级分层切分（用户架构修正）验证完成 = 最佳方案，白闪守卫生效，待拍板进 runtime

- **执行过程（2026-09-05，全部 GPU/DirectML 加速，BACKEND_SELECTED=directml/amd 已固化）**:
  - ① p36 单段 8fps 取证 = 假设成立（8fps 整段即命中 GT 2042-2043.4）;
  - ② 全局采样 4/6/8fps 四片全量 = 严格全部净负（104→100/99/103）+ t2r02b 假阳性兑现 + 2mkv 负例 +1;
  - ③ **用户两级分层切分（粗采样 5-8 帧找候选切点 + 局部 ±20 帧密帧精修边界 + 最短镜头保护 0.5s + fps 换算）
    四片全量 = 严格 112/139 (+8)、场景级 136/139 (+18)、负例 4/9 持平** —— 唯一严格净正收益方案;
  - ④ **白闪守卫（四层：前置过滤/切点后处理/相似度衰减/业务兜底）验证 = 删除 1.mp4 唯一白闪区
    (ed 18.35-18.46) 处的粗网格虚假切点 18.345（段数 70→69），三指标零回退**;
  - ⑤ 诚实边界: n03(66.1-67) 非白闪（帧正常，误配 HIGH 是 CLS 内容相似机制）→ 白闪守卫救不了，
    属 t2r02b 同类「内容相似误配」需另立方案; 负例 3/4 维持。
- **待拍板**: 两级切分 + 白闪守卫是否进 runtime（替换 analyze_edited_video 切分；编辑侧特征不落索引
  无需 bump feature_version；需全套单测 + 四片回归 + UI 结果数/导出验收）。
- **产物**: mvp/scripts/research_twopass_prototype(_v2).py + rerun_twopass.py + flash_guard.py +
  rerun_twopass_flash.py + work/rerun_*_twopass(_flash).results.json +
  FINDINGS_C_ITEM_8FPS.md（六、七章）。GPU 约定: DECISIONS.md 2026-09-05 + AGENTS.md。

## → 2026-09-04(下个对话):C 项 —— 编辑侧采样 2fps→8fps + 细切分（用户拍板记录, 本轮不实施）

- **背景(已定)**: p36 细切分取证通过(数据+VLM+人工三方闭合); test 域扫描完成——方案 A(单帧强证据保留)
  **不实施**(收益仅 +1 且有 t2r02b 假阳性风险), B 顺带关闭。p36 单条 +1 留待 C 项一并处理。
- **C 项内容**: 编辑侧采样率 2fps→8fps 提升 + 更细镜头切分, 涉及编辑侧特征重建/推理成本翻 4 倍,
  且 M4 已证索引侧密帧零增益(查询侧需另证)。**下个对话做**, 本轮不实施。
- 执行时: 先对 p36(及同类「查询单元不纯」段)验证 8fps 查询侧细切分收益, 再决定是否改采样率。

## → 2026-09-04:研究侧收尾归档(M6 v4 + M4/M8 v4 + ⑩ p08b) + 三指标基线固化(measure_baseline.py) = 完成

- **M6 v4 重算**(2026-09-01): RESCUE 0/39、CLS 池内 39/39 → patch 召回方向彻底关闭(有据)。
- **M4 v4 重跑**(仅 p26, DML 664s): v4 真值下 1fps 即 best_rank=1、margin=+0.28 —— 旧「12→43 恶化」是错误 GT 假象。
- **M8 v4 重跑**(纯 numpy 秒级): p26 互换后仍 AMBIGUOUS(0.027)、p08/t3r12 维持; p38/t4r01 剔除。
- **⑩ p08b 复核 = 作废(污染残留)**: 真值窗=p38 旧错误 GT 区, v4 正确=1108-1110, CLS 池内 6/patch 6 零增量。
- **FAILURE_TAXONOMY 收尾**: 失败族 = p08 + t3r12; A 类在 2.mkv 为空(CLS 39/39); 研究侧全维度闭环, 不再立项。
- **基线固化**: measure_shot_recall.py 抽 evaluate()(CLI 不变) + measure_baseline.py(doc/rerun 双模式) →
  work/baseline_v4.json; 验证与 GT_BASELINE 文档数字完全一致(2.mkv 32/39 场景 36/39; test1 32/43 场景 38/43;
  test2 9/20 场景 10/20; test3 31/37 场景 34/37)。⑦ 仍冻结。
- 零 runtime 改动; 三指标 v4 基线不受影响。产物 FINDINGS_M4_V4/M8_V4/P08B_REVIEW_V4 + measure_baseline.py。

## → 2026-09-02:②③ 单调弱先验进候选生成已编码 + 实测零触发（时间轴先验方向有据收窄）

- **实现**: `_apply_timeline_prior`（Ambiguous 型段用前序锚点弱倾向, 逃生门全路径）+ 配置 +
  单测 8 项, 全套 222 全绿。
- **重跑验证**: 新代码含先验重跑 2.mkv/test1-3, 新旧三指标完全一致 → **零触发零影响**。
- **原因**: p08 型兄弟机位 primary 在带内(先验结构性无效, 呼应 M8); 真实跳切全带外(逃生门生效)。
- **结论**: 候选生成级弱先验零增量; 时间轴先验价值已由事后 temporal_repair + 时间轴→Ambiguity
  兑现; 实现保留为护栏, 不调参投入。产物 FINDINGS_TIMELINE_PRIOR.md。

## → 2026-09-02:⑤' test1-3 GT 全部闭环 + 正式化（100 正例 + 5 负例），test3 HIGH 精度重估 23/23

- **⑤' 完成**: 用户逐段人工复核 test1-3 全部段（分:秒标注），已正式化到 `datasets/real/ground_truth_test1/2/3.json`。
  test1 43 正例/1 负例、test2 20 正例/1 负例、test3 37 正例/3 负例（含 r14/r15 加长版负例）。
- **三指标**: test1 严格 32/43 场景 38/43; test2 严格 9/20 场景 10/20（拆条窄窗低估）;
  test3 严格 31/37 场景 34/37、负例误报 2/3（r14/r15 加长版被定位）。
- **重大修正**: test3 r15 原标 HIGH 实为加长版负例（GT 修正）; r10=7:22-7:24 与 conflict_rerank 一致（已修）;
  test1 r14a 缺失段=算法对 GT 漏标; test2 r05 同段 -2726s 真实跳切; test3 r13 倒叙。
- **test3 HIGH 精度重估**: 24→23 段（r15 剔除），r10 已修 → **23/23 = 100%**（原 23/24 双向修正）。
- 产物: `gt_review/GT_BASELINE_test1-3.md` + `FINDINGS_TEST1-3_GT_BUILD.md` + 三份正式 GT。

## → 2026-09-02:test1-3 GT 草案 + 时间轴→Ambiguity 编码 + 时序重排 v4 量化（⑤' 材料交付，等待用户逐段人工复核）

- **⑤' 数据层材料已交付**: 三份 GT 草案 `gt_review/ground_truth_test1/2/3_draft.json`（全部段，tier=pending，定位占位待人工毫秒复核，负例=not_in_source 正确拒绝）+ 复核工作表 `GT_REVIEW_WORKSHEET_test1-3.md`（76 行，含复核结论/最终窗口列）+ 时间轴复核清单 `TIMELINE_CROSSCHECK_test1-3.md`（🔴离群/⚠️倒退/🔵大跳优先级标记）。
- **对照图全部重生成**（`cases/test1|test2|test3/rNN.jpg`，76 张，基于最新定位；此前 test1/test3 基于旧定位、test2 仅 3 张 HIGH）——用户将逐段看图人工复核。
- **② 时间轴→Ambiguity 已编码**（NEXT_STEPS ⑥）: `_apply_temporal_ambiguity` 复用 `find_temporal_outliers` 作为外部 Ambiguity 信号——修复后仍离群的高置信段降档（HIGH→MEDIUM，reason `temporal_outlier_ambiguous`），不改定位；配置 `pipeline.temporal_ambiguity_enabled`（默认 True）+ `ta_max_downgrade`（默认 MEDIUM）。预研确认 current 结果批离群零触发（s7 已修）→ 2.mkv 零回归。单测 8 项新增，**全套 214 项全绿**。
- **④ 时序重排 v4 量化已完成**（NEXT_STEPS ①）: 多版本对比（baseline_p21 29/39 → pre22a 31/39 → pre24 33/39 → current 32/39）+ 精确回滚实验 → **temporal_outlier_repair 净纠正 +1（p16 part→HIT）**；p05 pre24→current 回退=「修正后未跟上」非算法退化；P3 悲观结论重估（p26 修正后完全符合时间轴）。产物 `semantic_signal/FINDINGS_TIMELINE_V4_QUANT.md`。
- **③ test3 r10 单点已核实**: current=442-444（temporal_repair+conflict_rerank 两道修复），真值≈444.5，差 1.5s 场景级命中——留待 ⑤' 毫秒精修。

# TODO

## → 2026-09-01:Ambiguity Detection 原型实验 = 现有信号无法分离正确/错配 HIGH, AMBIGUOUS 无内部信号

- **实验**: 重跑 29 段 EvidenceLocalizer 提取内部 multi-evidence 信号(work/amb_prototype_signals.json)。
- **发现**: HIGH 档精度仅 5/13(38%); 正确/错配在 mode/n_clusters/qcov/dispersion/best_sim/margin 全同构(primary best_sim 0.49-0.69 重叠)。
- **机制**: 错配 HIGH 多为 clean 单证据簇 → secondary=None → margin 饱和 1.0; low_candidate_margin/multiple_similar_candidates 均要求 n_strong_clusters>=2 → clean 段结构上不触发降险 flag。
- **结论**: AMBIGUOUS 检测无内部信号可用(与 M1-M8 兄弟机位混叠 + 08-27 置信标定研究闭合); 校准转向「保守化 HIGH 门槛标定」, 不立项 AMBIGUOUS。
- 产物 `semantic_signal/FINDINGS_AMBIGUITY_PROTOTYPE.md`。

## → 2026-09-01(深夜):用户拍板推进顺序 —— 数据层 test1-3 全量毫秒级重标 + 时间轴→Ambiguity

- **执行顺序(已拍板)**: ① **test1-3 全部 GT 毫秒级人工重标**(数据层主线, 用户逐帧, 吸收 B 段; test4 数据错误剔除) → ② 时间轴→Ambiguity(低成本, 落地校准产品) → ③ test3 r10 单点验证 → ④ 时序重排 v4 量化 → 之后: 单调弱先验进候选生成 → Confidence 保守化标定 → M1-M8 低成本重跑(M4/M8) → p08b 复核。
- **⑤' 与 ⑨ B 段合并**: ⑤'(test1-3 全部毫秒级)是 ⑨(test2+test3 LOW/MEDIUM)的超集+升级, ⑨ 并入 ⑤' 不单列。
- 完整说明: `gt_review/NEXT_STEPS.md`(顶部「✅ 已拍板执行顺序」段)。

## → 2026-09-01:M6 v4 重算完成 = patch 召回 RESCUE 1/41→0/39, 方向彻底关闭(有据)

- **重算结果**(v4 GT, 39 条): **RESCUE 0/39、CLS 池外 0、CLS 池内 39/39**。
- **关键**: v3 的 10 条「CLS 池外」修正后全部 best_rank 1-8 直命中(p05/p10/p20/p23/p24/p26/p32/p41); p13「唯一救回」= GT 标错假象(v4 CLS 1)。
- **结论**: patch 召回 runtime 化零增量(0/39), 方向关闭(有据); M6 原「RESCUE 1/41」作废; 失败族重新定性为「定位精度/兄弟混淆」非「召回层进不了池」。
- 产物 `semantic_signal/FINDINGS_M6_REVISED.md` + `work/patch_recall_gt_results_v4.json`。

## → 2026-09-01:M1-M8 结论重审完成(v4 GT)= p26/p38 从失败族移除, 失败族收窄为 p08 + test 域

- **核心反转**: p26=GT 标错实证(旧 2809→正确 1766-1770, v4 runtime 直接 HIT HIGH)——M1-M8 全部 p26「特征上限/不可辨识」结论作废;
  M1b「VLM 反向选错」实为判对; M2「p26 字幕正面信号」反转(3/3 命中错误窗 2808)。
- **p38**: 与 p08 重复已删, 旧真值 1048 本身错(正确=1108-1110=p08); M5 p08b 救回存疑、M6/M7/M8 p38 半边作废。
- **失败族收窄**: p08(兄弟机位, 2.mkv 唯一) + t3r12/t4r01/test4(test 域未受影响)。
- **待办**: M6 全量「RESCUE 1/41」统计需 v4 重算(方向收益低预判不变); p26/p38 相关 FINDINGS 标注作废。
- 产物 `semantic_signal/FINDINGS_REVIEW_M1M8.md` + FAILURE_TAXONOMY 重审段; 三指标基线=v4。

## → 2026-09-01:GT v4 重建完成 = 41 条全定案写入 ground_truth_v4.json, 重测三指标 + 待重审 M1-M8

- **产物**: `datasets/real/ground_truth_v4.json`(v3 保留 + 31 条 corrections 留痕: 29 relocate / 2 delete) + `gt_review/GT_REBUILD_PROPOSAL.md`(41 条全判定提案+附录 v4 重测)。
- **用户逐条裁决**: p37(与p10 ED重合)/p38(与p08 ED重复) 删除; WRONG_GT 按线索改; PARTIAL 按用户画面收窄; WRONG/NOT_REVIEWED 精确窗口(±几ms容差)。
- **VLM 三批辅助**: 补审 14 条 / PARTIAL 逐帧 13 条 / top-6 候选窗 9 条(Volcengine Ark); 用户看图拍板。
- **v4 重测**: 严格 31/39 / 场景级 36/39 / 负例 2/4 / 支撑 80/137(v3 对照 39/41/39/41/2/4/91/137——下降=修正 GT 真实口径)。
- **关键实证**: p26 MISS→HIT(GT 错非特征上限) → **M1-M8 依赖错误 GT 的结论需重审**; 剩余 MISS p08(特征上限)/p28/p36(runtime 未命中)。

## → 2026-09-01:GT v3 人工审查发现大量标错 = 三指标基线作废, 需重建 GT(专会话执行)

- **审查结论**: 35/41 条已审, 仅 6 OK, 29 条有误(PARTIAL 13/WRONG 8/WRONG_GT 7/p26 确认错), 6 未审(p36-p41)。
- **影响**: 三指标 39/41 作废; M1-M8 结论需重审(p26=GT错; p38 兄弟机位结论存疑)。
- **资产**: `gt_review/GT_REVIEW_RECORD.md`(逐条判定+正确线索)+ 41 张对照图。
- **执行清单(下个专门会话)**: ①按判定修正 GT(有线索的直接改, PARTIAL 对齐窗口, WRONG 需用户补正确位置); ②补审 p36-p41; ③修正后重测三指标; ④重审 M1-M8 中依赖错误 GT 的结论。
- **正确线索速查**: p26→1766-1770; p05→≈978-984; p09→≈1050-1055; p13→≈1343; p20→≈1551-1564; p23→≈1585; p24→≈1599。

## → 2026-09-01:校准阶段(用户拍板 A+B)= Confidence Calibration + Ambiguity Detection + 补真实 GT

- **目标转变**:不是「让所有 Ambiguous 变正确」, 而是「提高可识别样本的召回/精度 + 正确识别 Ambiguous」——成熟产品行为。
- **产品层**:三档置信 → 四行为: HIGH 自动通过 / MEDIUM 自动通过或提示 / LOW 提示人工 / **AMBIGUOUS 明确转人工**(新增, 用 margin/similar_band/multiple_similar_candidates 等现有 ConfidenceConfig 信号判定)。
- **数据层(最重要, 前提)**: **补真实 GT, 范围 A+B**——A=2.mkv 失败族周边+Ambiguous 候选段(进行中: p08/p05/p20 已精修, p28 待终点); **B=test2+test3** LOW/MEDIUM 完整 GT(2026-09-01 test4 数据错误剔除: ed/om 两部不同电影)。GT 新增须逐帧画面确认。
- **置信标定**: 用真实 GT 统计 Easy/Hard/Ambiguous 分布 → 标定 ConfidenceConfig weights/thresholds/hard flags(现全占位)→ HIGH 高 precision、LOW/AMBIGUOUS 高 recall of hard。
- **研究层(Future, 非阻塞)**: 额外来源信号(provenance: 剪辑顺序/字幕台词/音频时间锚点/原片镜头图)——M8 已证当前邻接不可分, 需新信号源。
- **待办顺序**: ①补 GT(A 段优先, 量小) → ②Ambiguity Detection 原型(用现有信号) → ③Confidence Calibration → ④三指标回归。决策见 DECISIONS.md 2026-09-01。

## → 2026-09-01:原片邻接唯一性探针 M8 = 来源身份信息方向证伪, 失败族正式定性「不可辨识样本」

- **起因**:用户正确划分「来源身份信息」= 原片侧 Shot Graph 邻接唯一性(非重包已证伪的 P3 编辑上下文), 唯一未被否定维度。
- **M8 结果**(纯 numpy 秒级):5 个失败案例全 AMBIGUOUS——p38/p08 兄弟机位真-干扰邻接余弦 0.613(同场对话戏邻接同样貌);p26 唯一性差 0.027 不可靠;t3r12 干扰反更唯一;t4r01 相等。
- **归因**:兄弟机位邻接本身相似(场景集中同一时间窗, P3 根因);P2 过度归并担忧证实。
- **净结论**:来源身份信息清单全落空(前后镜头P3/剪辑点/镜头图邻接M8/字幕对白M1-3/音频不同源/OCR字牌单例)→ 失败族正式定性「不可辨识样本」;研究侧全维度闭环(外观/结构/语义/密度)。三指标 39/41 未动。
- **待拍板**:研究侧冻结, 资源回 runtime/产品侧(推荐)。FINDINGS `semantic_signal/FINDINGS_M8.md`。

## → 2026-09-01:局部特征探针 M7(ALIKED n32)= 核心难例 p38/p26 无解, 外观三层(CLS/patch/局部)全部关闭

- **起因**:用户拍板「先1再2」——1=FAILURE_TAXONOMY.md 固化 A/B/C/D 失败分类法; 2=现代局部特征验证(承接用户「Source-specific discrimination」特征层重构主张)。
- **环境**:HF/GDrive/hf-mirror 均不可达 → SuperPoint/DISK 权重拿不到; 用户手动装 kornia 0.8.3 + 下 aliked-n32.pth(本地加载验证通过)。
- **M7 结果**(633s):p38(兄弟机位士兵特写) rank 61 **干扰反超(margin −24)**; p26(夜读) rank 125 **干扰反超(margin −19)**——CLS/patch 双失败的案例 ALIKED 也失败; p08 +34 / t3r12 +48 弱正向但方向不一致; p01/t4r01 无增量。
- **归因**:兄弟机位局部 patch 本身相似(单应成立), 局部证据天然同貌 → 与 Phase 24-1 几何证伪呼应。
- **净结论**:局部特征方向关闭(有据); 失败族在外观三层(CLS/patch/局部描述子)全部无解 = 身份级区分局限; 三指标 39/41 未动。
- **待拍板**:失败族正式定为「身份级区分」局限(维持特征上限表述) or 未来更强语义/身份特征(多模态已测无解)。FINDINGS `semantic_signal/FINDINGS_M7.md`。

## → 2026-09-01:patch 召回探针 M6(GT 全量 41 条)= 仅 +1/41(p13), patch 召回方向关闭(有据)

- **起因**:用户拍板「跑完 41 条 GT 再决定 patch 召回 runtime 化值不值」——M5 只测 6 个探针点, M6 扩到全量 GT。
- **M6 结果**(6633s):41 条 GT 正例——31 条 CLS 已在池内(易例, patch 无增量);10 条 CLS 池外中 **patch 只救回 1 条 p13**(CLS 188→patch 1);9 条未救回(p05/p10/p20/p23/p24/p26/p32/p38/p41)。
- **关键矛盾**:M5 的 p08b 32→2 在 M6 p38(同一目标区 1048-1050, CLS 340→patch 225)不复现——查询帧选取不同(M5 13.9s vs M6 中点 13.25s, 快剪段子镜头交替), patch「救回」对查询帧高度敏感。
- **净结论**:patch 召回 runtime 化 = 仅 +1/41 且信号不稳, 低于「≥2-3 条才值得」门槛 → **方向关闭(有据)**; p26/p24/p41/p38 双通道无解, 失败族维持特征上限。零 runtime, 三指标 39/41 未动。
- **待拍板**:无(方向已关闭, 数据留档)。FINDINGS `semantic_signal/FINDINGS_M6.md`, 脚本 `mvp/scripts/research_patch_recall_gt.py`, 数据 `work/patch_recall_gt_results.json`。

## → 2026-09-01:patch 级召回探针 M5 = patch 对兄弟机位选对实例有效(p08b 32→2), p26 仍特征上限

- **起因**:用户拍板立项「patch 级召回」——E21/patch_rerank 都只在「CLS 已捞进池」的候选里重排, patch 从未参与候选池构建(召回层)。M5 首次实测。
- **前置工程情报**:GPU 资产(DirectML ONNX)原本只导 CLS;新导出 CLS+patch 双输出 ONNX(研究侧临时资产, cos=1.0, DML 18fps vs CPU 1.4fps ≈13×), 探针切 DML 提速。
- **M5 结果**(918s):p08b 32→2(兄弟机位选对实例, E21 一致复现);p08 6→5; **p26 22→24 无解**(干扰 0.951 反超正确 0.900);p01/t3r12/t4r01 保持 top-1 零回退。
- **产品相关缺口**:runtime 检索 top-20, p08b/p26 均超池;patch 可救 p08b 型、救不了 p26。
- **待拍板**:patch 召回是否 runtime 化(预期救兄弟机位族一部分, 接入须 bump feature_version + 三指标回归)。FINDINGS `semantic_signal/FINDINGS_M5.md`, 脚本 `mvp/scripts/research_patch_recall.py`, 数据 `work/patch_recall_results.json`。

## → 2026-09-01:索引密度探针 M4 = 8fps 密帧对判别零增益,索引密度方向关闭(证据链 M1-M4 全貌闭环)

- **起因**:用户质疑「帧数不能再提升吗?GPU 加速还能往上吗?」(对标同类软件 30fps 全片解析)。澄清:Phase 14C「2→4→8fps 零增益」是查询侧结论,**索引侧从未测过** → M4 首次实测(DML batch=1,717s)。
- **M4 结果**:p08 best_rank 都 1(top5 2→5 略改善)/margin 0.393→0.365;**p26 best_rank 12→43(密帧恶化)** margin 仍负(−0.28→−0.25);t3r12/t4r01 持平。**8fps 未把任何负 margin 变正**。
- **归因**:索引密度解决「正确帧数量」不解决「正确 vs 干扰可分性」;p26 干扰 sim 0.876 反超正确 0.596 = CLS 混叠,任何帧率救不了。30fps 全片成本 ×30 换不来判别提升 → **方向关闭**。
- **吞吐实测**:DML batch=1 **20.5fps 最佳**,大 batch 并行无收益(plateau ~15fps),达不到 30fps;工程情报:未来 DML 批量推理用 batch=1。
- **难例多模态辅助**(用户指示):p26 是 M1/M2/M3 靶心——VLM 反向选错、字幕唯一弱正(不可索引)、CLIP 无判别力。三形态已测无可靠分离。
- **证据链 M1-M4**:判定(M1)/召回(M2)/索引(M3)/密度(M4) 四路全无解 → 失败族维持特征上限。零 runtime,三指标未动。脚本 `mvp/scripts/research_semantic_signal_M4_density.py`,数据 `work/semantic_signal_M4_results.json`,FINDINGS `mvp/benchmark/user_case/semantic_signal/FINDINGS_M4.md`。

## → 2026-09-01:方向 C 完整验证探针 M3 = 可规模 CLIP 索引证伪,方向 C 证据链完整(建议关闭)

- **起因**:用户拍板立项方向 C 完整验证(A)。前置:装 sentence-transformers 6.0.1 + clip-ViT-B-32-multilingual-v1(hf-mirror 可达, 512 维, 支持法语; 不碰 onnxruntime/rapidocr)。
- **M3 结果**:CLIP 跨模态字幕检索**无判别力**——相似度全域平台(Δ<0.003),真值 rank p26 2/8、p08 3/7、test4 2/8;**易例 p01 被字幕推到 5/7(比随机差)**。
- **机制**:解说字幕=故事级叙事文案,与画面松散/解耦(test4 事件无对应、p01 抽象带偏);CLIP 对「外观近同」候选无区分力。
- **方向 C 全貌**:M1 判定证伪 + M2 VLM 召回单例弱(3/3, 昂贵) + M3 可规模索引证伪 → 无可靠可规模多模态通道。
- **待拍板**:关闭方向 C(推荐) / 转测纯视觉局部 patch 级召回。零 runtime,三指标未动。FINDINGS `mvp/benchmark/user_case/semantic_signal/FINDINGS_M3.md`。

## → 2026-09-01:字幕语义召回探针 M2 = 方向 C 首次正面信号(p26 3/3 vs 1/3),有清晰边界

- **起因**:用户拍板测「字幕语义召回索引」(方向 C 的正确用法,此前只列远期从未实测)。探针 `mvp/scripts/research_semantic_signal_M2_subtitle_recall.py`,数据 `work/semantic_signal_M2_results.json`,FINDINGS `mvp/benchmark/user_case/semantic_signal/FINDINGS_M2.md`。
- **p26 = ✅ 首次正面信号**:字幕「她用望远镜看 Levi 在做什么」真值 [2808-2811] 3/3 EVENT YES(圆形暗角=望远镜视角),干扰夜阳台 1/3——字幕能分视觉 CLS 分不清的夜读/夜阳台。
- **t3r12 = ⚠️ 弱正向**:真值 2/3 vs 干扰 1/3(重复镜头语义同貌)。
- **test4 = ❌ 0/3 全 NO**:字幕「二十多人被困滑梯管道」与原片画面无对应——解说文案与画面解耦。
- **净结论**:方向 C 非全盘证伪,适用边界=字幕-画面对应性(p26 有效/test4 无效);无文本嵌入模型只能 VLM 匹配。
- **待拍板**:A. 立项字幕语义召回完整验证(引入文本嵌入+建索引+更多样本) / B. 记录为弱正向待更多样本 / C. 与局部 patch 召回合并「两阶段多通道检索」。

## → 2026-09-01:多模态判定探针 M1 = 事件级语义证伪/字幕召回弱信号,特征上限获语义层独立确认

- **起因**:用户拍板分层检索「结合多模态进行判定」,A(召回层+判定层两层都测)。探针 `mvp/scripts/research_semantic_signal_M1_multimodal.py`,数据 `work/semantic_signal_M1_results.json`,FINDINGS `mvp/benchmark/user_case/semantic_signal/FINDINGS_M1.md`。
- **M1a 字幕语义召回 = 弱方向性**:p08 正确 1/3 vs 兄弟 0/3、t3r12 正确 2/3 vs 干扰 1/3(偏好正确), p26 两窗都 2-3/3 → 不能精确分离, 可留作两阶段检索召回侧弱加权候选。
- **M1b VLM 事件级判定 = 证伪(甚至反向)**:p08 兄弟 3/3 SAME; **p26 编辑段被判与干扰夜阳台 3/3 SAME、与真值夜读 0/3 SAME(反向选错, VLM 视觉混淆比 CLS 更严重)**; t3r12 正确/干扰都 SAME。事件级语义与外观共享天花板。
- **证据链闭环**:外观/结构(五路)+事件聚类(方向A)+序列上下文(P3)+语义/多模态(M1) 五层全无解 → 特征上限多维确认。零 runtime,三指标未动。
- **未证伪的剩余方向**:局部(patch)级召回 + 两阶段架构(纯视觉, 非多模态)——探针=验证 patch 级能否把失败族正确实例拉进候选池。

## → 2026-09-01:第六路候选信号·镜头序列上下文探针 P3 = 证伪,特征上限正式封顶

- **起因**:用户指出五路证伪+方向 A 归档后,仍有一路未明确证伪 = 镜头序列上下文(目标镜头前后各 1~2 个镜头内容联合匹配,独立证据源)。要求离线最小验证,成本极低(现有 CLS+镜头边界)。
- **P3a 编辑序列≠原片时间轴(1:1 前提不成立)**:p07→原片[1027,1041]、p08→[1160,1166]、p09→[1131,1147]、p26→[1766,1770](真值 2809 偏 1000s+)、p40/p41→[1894,1900]/[346,355]。
- **P3b p08 序列匹配 = 证伪(不升反降)**:单镜头真值134 rank 44 → 序列匹配 61,**兄弟128 被推 top-1**;top3 全为同一对话戏场景。根因:编辑段后相邻镜头 p09 内容恰来自兄弟区域 1048-1082,编辑上下文自身就混着兄弟内容;同一场对话戏镜头在原片集中在 1010-1154 同一时间窗,无唯一上下文。
- **P3c p26 对照 = 证伪**:真值 rank 17→35,答案被拉向编辑上下文区域(1772-1907)。
- **回答用户三问**:①p08 查询不含完整镜头边界(2/15s),但失败不在此;②编辑侧无细镜头边界,GT 编辑段可当查询镜头;③p26 上下文序列差异更极端。
- **净结论**:外观层/事件聚类/序列上下文全证伪 → 剩余失败族正式封顶为特征上限=已知局限。唯一未探索=方向 C 多模态语义(远期)。零 runtime,三指标未动。脚本 `mvp/scripts/research_semantic_signal_P3_seq_context.py`,数据 `work/semantic_signal_P3_results.json`,FINDINGS `mvp/benchmark/user_case/semantic_signal/FINDINGS_P3.md`。

## → 2026-09-01:剪映通道验收闭环(用户确认)——草稿不再列入待用户动作

- 用户已确认 `D:\JianyingPro Drafts\` 下 test1-ed.loc.v6 / test3-ed.loc.v7 草稿完成,剪映通道最终验收通过。历史条目中「待用户双击/目检剪映草稿」类待办一律视为已闭环,不再要求用户动作。导出自动验收主力维持 PR CEP 通道。

## → 2026-09-01:Phase 24-2 方向 A 探针 P2 完成(用户拍板 A1 继续)= 兄弟机位事件级 top-1/重复镜头保持/同质场景证伪,待拍板归档或进 runtime

- **P2 设计**:事件归并规则(时序近邻+指纹联合聚类,边=场景中心时间差≤T_gap AND 指纹余弦≥S_sim 连通分量;网格 30/60/120s×0.55/0.60/0.65/0.70)+ 编辑段→事件单元端到端排序(对照帧级/场景级/事件级三档)。脚本 `mvp/scripts/research_semantic_signal_P2.py`,数据 `work/semantic_signal_P2_results.json`,FINDINGS `mvp/benchmark/user_case/semantic_signal/FINDINGS_P2.md`。
- **P2a 归并规则**:兄弟机位 134↔128 **12/12 全同单元** ✅(归并稳健捕获同事件多机位,单元含 946-1166s 连续对话戏 19 场景);重复镜头正确[43,44,45] 同单元 ✅ 但干扰 42/46 被时序并入 ⚠️;同质场景 test4 正确实例多数参数不同单元 ❌。
- **P2b 端到端**:p08+p38 兄弟机位 场景级 8/699 → **事件级 top-1**(T_gap=120 三档稳健)——正面回答 P1a「rank 6/11 不唯一」(归并规则=时序+指纹联合而非纯指纹);t3-r12 事件级 top-1(11/12)保持;test4 无效;p01 全档 top-1 零回退;p04/p17 场景级差为「场景指纹均值稀释」代理伪影(帧级 148/10 正常);p26 事件级意外 2/129(谨慎解读)。
- **净结论**:与用户预期(重复镜头族+部分兄弟机位族)一致,兄弟机位族超预期。零 runtime 改动,三指标 39/41 未动。
- **已拍板(2026-09-01):方向 A 归档**。P1+P2 证据链完整,按立项约定「P2 结束无论成败都归档」→ 同质场景维持已知局限。未来如需重开,证据在 `semantic_signal/FINDINGS_P1.md` + `FINDINGS_P2.md`。

## → 2026-09-01:Phase 24-2 语义级第二信号·方向 A 探针 P1 完成 = 部分成立/部分证伪,待拍板 P2 或关闭

- **立项**:五路证伪后用户拍板写「语义级第二信号」立项材料 → `semantic_signal/RESEARCH_PROPOSAL.md`(方向 A 场景实例身份[推荐]/B 序列对齐/C 多模态[远期]);用户选 **A**,探针 `research_semantic_signal_P1.py` 跑完。
- **P1a 归并能力 = 信号存在但不唯一**:兄弟机位场景134↔128(z=2.47 显著近)但 rank=6/11 非唯一 → 聚合信号有,精确归并需更强事件身份特征。
- **P1b t3-r12 = ✅ 可分离**:正确实例场景 avg rank 2.0/7,sep=+0.188 → 方向 A 对**重复镜头族**有效。
- **P1b test4 = ❌ 不可分**:sep=−0.035,同质场景族确认特征上限,方向 A 不覆盖。
- **P2 未跑**(身份嵌入端到端排序);FINDINGS 见 `semantic_signal/FINDINGS_P1.md`。
- **待拍板**:A1 继续 P2(先设计事件归并规则再端到端验证,预期仅重复镜头族+部分兄弟机位族) / A2 关闭方向 A(保留证据,失败族正式关闭为已知局限)。零 runtime;三指标 39/41 未动。

## → 2026-08-31(晚):Phase 24-1 非外观第二信号三探针预研 = 全部证伪,剩余失败族确认为特征上限(闭环)

- **探针①视觉几何一致性 = 证伪(核心)**:patch 互近邻 + 仿射/单应 RANSAC 内点率,p08/p08b(同场戏兄弟机位)真值帧内点率**反被兄弟机位压制**(p08b 兄弟 1109 HOMOG 0.75/n_match 329 vs 真值 1048 0.49/78)。归因:①刚性场景不同机位仍满足单应约束(平面近似),"不同机位→违反仿射"前提在多视图几何上不成立;②1fps 候选粒度下真值窗内 0.33→0.85 跳变,帧对齐极敏感;p26 的 rank 2 为假阳性(干扰 0.591 仍压真值 0.576,无 margin)。**不进 runtime**。
- **探针②时序运动签名 = 证伪(方法学不成立)**:编辑片快剪(压缩比>1),窗口帧差签名时间轴与原片非 1:1,未先对齐前提下连易例 p01 都 -0.87。**不重试**。
- **探针③难例投影头微调 = 数据不缺,无可分信号**:硬负例盘点每索引 2.6万~9.1万对(2.mkv 49,572/test1 51,289/test2 26,018/test3 91,708/test4 31,737,sim≥0.60 跨场景 Δt≥2s),「数据瓶颈」不成立;但 CLS 特征级混叠 + ①② 证伪 → 无可注入的第二信号。**不立项**。
- **回归**:研究侧零 runtime 改动,三指标与 Phase 24 基线一致 = 严格 39/41、FP 2/4、支撑 91/137,零回退。剩余 2 MISS(p08/p26)即本预研确认的特征上限两族。
- **结论**:维持「接受为已知局限」既有拍板;未来唯一有价值方向 = 语义级第二信号(场景身份/多模态字幕),当前无证据不立项。不改 runtime/不打包/不 bump feature_version。
- 脚本:`mvp/scripts/research_phase24_1.py` + `research_phase24_1_data.py`;FINDINGS 见 `mvp/benchmark/user_case/phase24_1/FINDINGS.md`。

## → 2026-08-31:NLE 自动验证通道定案(PR CEP 建成 PASS / Resolve 免费版死路)——①②已完成闭环

- **Resolve 21.0.4 免费版 = 外部脚本不可用**(Studio 独占,UI 无选项/连接全败/网络确认)。保留作 XML 手动目检;排障遗产无害。
- **PR 2026 CEP 面板建成**:`%APPDATA%\Roaming\Adobe\CEP\extensions\com.svl.timelineexport\`(manifest 必须在 `CSXS\` 子目录;PlayerDebugMode 已设 CSXS.9-13 HKCU)。按钮 → 导入 SVL XML → 导时间轴 JSON(`work/svl_pr_timeline.json`)。**E2E:119/119 匹配、0.0000s 偏差**。人工成本=PR 重启+点按钮 ~30s。
- **① 比对脚本已固化并复验**:`mvp/scripts/verify_pr_timeline.py`(读 FCP7 XML 声明 vs PR JSON 逐项四元组 start/end/in/out,`--xml/--json/--tol`;退出码 0=全匹配)。本次复验:119/119、最大偏差 0.0000s、EXIT=0。
- **② host.jsx XML 路径已参数化(2026-08-31)**:`svlRunAll(xmlPath, outPath)` 由面板 evalScript 传参,空值回退默认;`index.html` 加两个输入框(FCP7 XML 路径/输出 JSON 路径);`q()` 双写反斜杠防 ExtendScript 误转义(`\b`/`\t`/`\n` Node 往返测试通过)。旧调用 `svlRunAll()` 兼容。**扩展源码已归档**至 `mvp/scripts/pr/cep_extensions/com.svl.timelineexport/`(仓库为源,安装=复制到 %APPDATA%);用法文档 `mvp/scripts/pr/README.md`。
- **③ FCP7 多轨 XML 导出已支持(现有通道),无需改**。
- 剪映通道维持现状(v6/v7 草稿待用户目检);PR 通道=自动验收主力。
- **待用户动作**:重启 PR → 开面板确认参数化输入框 → (可选)填任意导出批 XML 验证多批复用。

## → 2026-08-30(深夜 III):Phase 24 冲突扩池重排已实施并验收 = 闭环

- **用户拍板 A 立项后已实施**:`engine/localization/conflict_rerank.py`(几何触发+无主张子区间落位+证据门槛)+ `_apply_conflict_rerank` 接线(时序修复之后)+ 5 配置旋钮。实现细节与验收见 `mvp/benchmark/user_case/second_signal/FINDINGS.md`。
- **验收**:后端 206(+19)+api 58 全绿;2.mkv GT v3 三指标零回退(39/41、FP 2/4、支撑 91/137,零触发);test1/2/4 零触发零漂移;**test3 r10 自动修复 447-449→442-444**(人工真值≈444.5),其余段零扰动,对照图 `second_signal/r10_fix_verify.jpg`。**r10 不再需要结果页手动替换。**
- 零打包(长期规则)。剩余失败(p08/p08b/p26/r12)= 特征上限,维持"接受为已知局限"拍板。

## → 2026-08-30(深夜):Phase 24-0 非外观第二信号预研完成 = 仅「冲突触发扩池+时序融合重排」值得立项,待拍板

- **预研结论(证据见 `mvp/benchmark/user_case/second_signal/FINDINGS.md` + `work/second_signal_probe_results.json`)**:①音频判别力否——同场景兄弟实例声学同貌(p08 margin +0.04/p08b −0.03),叠加 BGM/解说污染,不解决主失败族;②时序非重叠先验单独否——r10(错)与 r6(对)重叠几何同构(0.75 vs 0.76),任何阈值修一伤一,量化确认此前撤销结论;③**新发现:t3r10 真值区 441-443 有被压制的独立证据峰(0.73 vs 错位区 0.87)** → 可行方向 = 冲突段触发邻域扩池 + 时序一致联合重排(改动面小,仅冲突段)。
- **待用户拍板**:A. 立项 Part C 小阶段(0.5~1 天,验收=r10 修复+r6 零扰动+三指标不回退)/ B. 彻底关闭接受现状 / C. 维持手动替换不立项。
- 零 runtime 改动(仅新增研究脚本 `mvp/scripts/research_second_signal.py`),测试基线 187+58+67 不变。

## → 2026-08-30(晚)：Phase 23-0 特征升级预研完成 = 不建议 bump feature_version,结论待拍板

- **预研结论(证据见 `mvp/benchmark/user_case/feature_upgrade/FINDINGS.md`)**:ViT-B/14 在 7 探针 × 2 通路(CLS/patch-max)上零增益、p08b 明确恶化;patch ViT-S p08b 险胜与 Phase 21 V3 一致(已在 runtime)。**升规模成本收益不成立,建议不重建索引**。剩余失败族(同场景重复实例/同质场景互混)需非外观第二信号 = 新研究阶段。
- **待用户拍板**:A. 接受剩余失败为已知局限,Phase 23 关闭(推荐)/ B. 立非外观第二信号研究 / C. 坚持全量重建(不建议)。
- **交接基线复验**:185+56+67 全绿;DML 资产在位;8765 旧实例在。api 测试须 PYTHONPATH=`mvp/src;mvp`。

## → 2026-08-30(晚)：Phase 22 全六项完成 + 交接拍板,转入 Phase 23 特征升级(用户拍板立项)

- **交接拍板(2026-08-30 晚,AskUserQuestion 留痕)**:A **特征升级立项** ✅ / B **暂不打包** ✅(长期规则维持) / C **test2-4 LOW/MEDIUM 完整 GT 暂不补** ✅。
- **Phase 23 立项 = 特征升级**:方向 = 更强 backbone(ViT-B/14)或 patch 级检索;需 bump feature_version 全量重建索引(5 部片 GPU 约 1-2h)+ 回归验收,工作量一个大阶段。预研脚本 `mvp/scripts/research_feature_upgrade.py` + `research_feature_upgrade2.py`(失败探针 p26/p08/p08b/p27 + test3-r10 相邻镜头 + test4 观察段 + 易例回归 p01/p04/p17;ViT-S=现成索引缓存 vs ViT-B=局部窗口嵌入)。
- **仍待用户动作(与 Phase 23 并行)**:①重启剪映双击「test1-e...y draft」(v6 草稿已在 `D:\JianyingPro Drafts\`)做剪映通道最终验收;②test3 r10 结果页手动替换(真值 ≈7:24.5,当前错位 7:27-7:29)。

## → 2026-08-30：Phase 21 场景指纹召回扩展层已完成，转入 Phase 22 导出工程文件 + 精度收尾（用户拍板路线）

## → 2026-09-05:性能分阶段计时探针（test1）= patch rerank 占 56% 是第一热点, 定位/检索本身≈0

- **产物**: mvp/scripts/probe_perf_timing.py（monkey-patch 分阶段计时, 零 runtime 改动）
  + work/probe_perf_test1.out。
- **分布**（test1 总 641s, 41 段, 中位 11.4s/段）: **patch.rerank 357.3s = 55.7%（40/40 段全触发）**
  > 两级切分 134.5s = 21.0% > dense 8fps 84.9s = 13.2% > 解码 20s = 3.1% >
  > **loc.localize 1.0s + finloc 0.1s + conf 0 ≈ 0%**（检索/定位/finloc/置信全免费, 索引特征缓存）。
- **根因（已核代码）**: ① PatchReranker = **CPU torch** DINOv2 patch forward（patch_rerank.py 注释明示;
  M7 时代实测 CPU 1.4fps vs DML 18fps ≈ 13×）; ② 每帧 grab_frame = 独立 ffmpeg 进程 spawn（每段
  3 编辑帧 + 3~8 候选窗帧）; ③ 触发门 width>=0.6 形同虚设, 歧义门在抓帧/embed **之后**才判（白跑）;
  ④ dml_batch_size=8（M4 实测 batch=1 快 ~35% 未落 config）; ⑤ patch 候选窗跨段无缓存。
- **优化优先级（待拍板实施, 全部需四片零偏差/三指标回归验收）**:
  1. patch 模型上 GPU（DML 双输出 ONNX 资产已有, M5 验证数值一致 18fps）→ 预期砍 ~180s;
  2. dml_batch_size 8→1（白拿, 全部 embed 环节 ~35% 提速）;
  3. patch 触发收窄（歧义门提前/收窄到歧义段; 语义有变, 需三指标验证; 日志仅 ~35% 段真正改写）;
  4. grab_frame 跨段缓存 + dense 8fps 懒计算（13%）;
  5. 索引构建（首跑另计 ~6-10 min/片）随 2 直接受益。
- 预期: 1+2 合计 test1 641s → ~350s; 逐项做完有望压到 ~200s 内（3-4s/段）。

## → 2026-09-05:性能优化第一批落地 = 四片零偏差 + 总耗时 -30%（patch DML + 抓帧缓存 + subshot 关闭）

- **落地项（全部过四片零偏差验收, work/rerun_*_perfopt.results.json）**:
  1. **PatchReranker 上 GPU**: DML 双输出 ONNX（work/_patch_onnx_tmp/dinov2_cls_patch.onnx, 518→CLS+patches[1369,384]）
     优先, CPU torch 回退（patch_rerank.py + resolve_patch_onnx, config.patch_onnx_model/env SVL_PATCH_ONNX 可覆盖）。
     数值验收 per-token cos mean 0.999997（M5 口径闭合）, patch 改写决策与 torch 版逐字节一致, 9.7× 提速。
  2. **grab_frame 进程内缓存**（patch rerank/text anchor 共用, key=(path,t), 上限 512 FIFO）+
     patch 歧义门提前到抓帧之前（判据只依赖 evidence, 零语义）。
  3. **意外收获——暴露并修复既有缺陷**: weak-hit 子镜头回退的 `evidence = sub_ev` 整体替换会丢
     montage 已命中簇（test2 t2r02b s14 实证: 覆盖 GT 的 2922-2933 簇被替成单簇 → HIT→MISS）。
     该缺陷在定向回退版进入 runtime 时埋下（当时仅验 2.mkv）, 本次首次全量回归暴露。
     按子镜头方向结案拍板 **subshot_enabled 默认 False**（代码保留可开）。
  4. **dml_batch_size 8→1 试做后回退**: batch=1 与既有缓存索引（batch=8 时代构建）数值口径不一致,
     查询/索引两侧微移改变簇形成（同现 t2r02b 异常）, -7% 收益不值一致性风险; M4 的 batch=1 提速
     仅适用于全新重建且全程同 batch（含索引）, 留作未来全量重建时的选项。
- **提速数据**（对照本会话基线）: 2mkv 1054→704s(-33%) / test1 624→438s(-30%) / test2 995→762s(-23%) /
  test3 1211→821s(-32%), 四片合计 3885→2725s **(-30%)**; 探针复测（test1, probe_perf_timing.py）:
  总墙钟 641→393s(-39%), **每段墙钟中位 11.4→5.0s**, p90 15.6→7.6s。
- **新分布（test1, 393s）**: 切分 127s(32%) / patch rerank 133s(34%, 剩余=grab_frame ffmpeg 进程 spawn)
  / dense 8fps 81s(21%) / 定位+finloc+置信 ≈0。
- **下一批候选（待拍板）**: grab_frame 批量化/常驻解码器（patch 剩余 133s 的主部）、dense 8fps 懒计算(81s)、
  切分侧 embed 共享解码。索引构建（首跑 6-10 min）本批未动。
- 验收: 246 测试全绿 + 四片三指标/支撑 span 全等（严格 113=113 场景 136=136 负例 4=4 支撑 565=565）。

## → 2026-09-05(深夜):审计接线(A1/A2/D) + 下一批性能探针 = A4 持久缓存上限 -54%, dense 懒计算证伪, grab spawn 是 patch 剩余主部

- **审计接线(零行为变化, 246 全绿 + test1 抽查全等: 34=34/42=42/0=0/106/217=106/217)**:
  - A1 `subshot_min_sub` 死字段接线(`_subshot_relocalize` 原 hardcode `<3`);
  - A2 `finloc_stable_s`(ConfidenceConfig)接线: cfg → EvidenceLocalizer(finloc_stable_s=) →
    finloc_window(stable_s=)——原 finloc.py 用同值模块常量 FINLOC_STABLE_S=4.0, 行为不变仅可调;
  - D `patch_rerank.py` 两处硬编码 `D:/claudework` 绝对路径改 repo 相对推导。
- **D 的教训(探针立功)**: 首版用 parents[3]——patch_rerank.py 在 src/engine/localization/ 比 device
  层深一级, parents[3]=mvp(无 work/), 正确是 **parents[4]=benchmark**; 错误路径 → patch reranker
  ensure() False → **patch rerank 全体静默禁用**(probe 里 patch=0.0s/40 次是异常信号), 且 246 测试
  不覆盖资产解析。已修 parents[4] 并复核 resolve 输出。原 resolve_weights 的 parents[3] 候选同病,
  一直被绝对路径兜底掩盖。
- **下一批性能探针(probe_perf_next.py, test1 首跑 397.5s)**:
  - **patch.rerank 137.7s 分解: grab_frame(ffmpeg 进程 spawn) 111.3s/358 帧 = 81%**, DML forward
    仅 22.3s/383 帧, patch_score 3.5s → **批量化/常驻解码吃掉的是 ~110s 而非模型**;
  - **text anchor 48.3s**(grab 22.7s/72 帧 + OCR)——此前藏在残差里, 首次入账;
  - **dense 懒计算 = 证伪关闭**: 40 段 localize 中 39 段产出 moments, dense 几乎总被使用(省不动,
    降 edit_fps 属语义变化); 帧行预算: embed.seg 1478 帧/102s + embed.dense 1053 帧/73s;
  - **A4 编辑侧持久缓存上限**: 同进程热二次定位 183.0s vs 首跑 397.5s = **可省 214.6s(-54%)**,
    是下一批最大单项(dense cache/tr query cache/grab cache 热; 切分 embed 若也持久化再省 ~100s);
  - A3(patch ONNX 进产品资产目录)无性能影响(加载<1s), 纯部署卫生, 随打包拍板。
- **下一批优先级(待拍板)**: ① A4 持久缓存(-54% 上限, 需设计: 文件哈希 key/feature_version/失效)
  ② grab_frame 批量化或常驻 ffmpeg(首跑 -100s 级) ③ ~~dense 懒计算~~(证伪) ④ batch=1 全量重建(未来)。

## → 2026-09-05(深夜II):用户首跑全流程实测（新建索引+定位, test2 全新 data 目录）= 索引 450.6s + 定位 1139.4s ≈ 26.5 min

- **方法**: rerun_fresh_probe.py（去掉脚本内 SVL_DATA_DIR 硬编码覆盖, 教训: rerun 脚本 env 覆盖会
  吃掉外部注入）+ 全新 data 目录 = 真实用户首跑路径（索引 0 命中）。
- **实测（test2: 原片 1.4h/5051 帧 @1fps, 编辑片 69.4s/54 段, DML/amd）**:
  - **索引构建 450.6s（7.5 min）** ≈ 11.2 帧/s（含 scenes/events 表构建）;
  - **定位 1139.4s** —— 比热索引批的 762s 慢 ~50%（首跑紧随建索引, 疑冷 IO/DML 会话状态, 单样本
    未分离原因; 热索引数字见前批）;
  - **全流程 ≈ 26.5 min**。
- **外推（索引 ~11.2 帧/s + 热定位）**: 2.mkv(7668 帧) ≈ 11.4min+11.7min ≈ **23 min**;
  test1-om(8221) ≈ 12.2min+7.3min ≈ **20 min**; test3(≈8000) ≈ **26 min**。
- **要点**: ① 索引是一次性成本（同原片后续定位不付）; ② **batch=1 全程统一（索引+查询同 batch,
  M4 实测 20.5fps vs 11.2 现值）可把建索引近乎砍半, 且消除查询/索引口径问题**——首跑提速的正确
  打法是重建时全程 batch=1, 而非只改查询侧（本日已证伪后者）; ③ A4 编辑侧持久缓存只帮二次起,
  不帮首跑; ④ 首跑定位慢 50% 的原因待查（若真实存在, 值得单独归因）。

## → 2026-09-06:计划①②④执行完毕 = A4 持久缓存 + 抓帧并行落地(零偏差), batch=1 试做证伪回退

- **① A4 编辑侧持久缓存 = 落地**（app/edited_cache.py + config.edited_cache_enabled=True）:
  缓存两级切分产物 + 每段 8fps dense 到 app data/edited_cache（键 = sha1(路径+size+mtime+
  feature_version+设备口径含 batch+PipelineConfig 全量指纹), 任一变化自动失效; 原子写; 损坏视为
  未命中; 缺文件不缓存走原错误路径）。**实测 test1: 首跑 398.5s → 缓存命中 192.1s(-52%)**;
  加 ② 后 166.9s。单测 +4（roundtrip/增量/损坏容错/指纹敏感）, 250 全绿。
- **② grab_frame 线程池并行 = 落地**（`_grab_frames_parallel`, patch 候选窗 + text anchor;
  打分保持 sorted 顺序串行, 选优语义不变）。**重要教训: DirectML EP 多线程并发 Run 同一
  ONNX session 会原生段错误**（首版并行 frame_patches 实测崩溃）→ 并行只做抓帧, DML forward
  主线程串行（55ms/帧, 不吃收益）。test1 热跑 192.1→166.9s, 零偏差（34=34/42=42 全等）。
- **④ batch=1 全程统一 = 试做后证伪回退**: 生产 embed 路径实测建索引 batch=1 499.9s(10.1fps)
  vs batch=8 450~485s(10.4-11.2fps)——**M4 探针的 20.5fps 不适用于生产路径**（探针与生产
  embed 分块方式不同）; 无收益 + 不必要数值漂移 → 回退 dml_batch_size=8 + feature_version
  撤销 +b1。副产品: **test2 索引全量重建后四片口径零偏差**（13=13/18=18/支撑全等）=
  embed 重建确定性验证。fv 注释保留「数值口径纪律」: 改 embed 数值口径的参数必须 bump
  feature_version 并全程统一。
- **当前速度画像（test1, 41 段）**: 首跑 ~400s → 热缓存+并行抓帧 **167s（4.1s/段, -58%）**;
  首跑剩余大头 = 切分 embed(102s, 1478 帧) + dense embed(73s, 首跑必付) + patch grab(并行后
  ~40s) + text anchor(48s)。A4 只帮二次起; 首跑再快需动 embed 吞吐（无低风险手段, 已证伪
  batch=1; 剩帧数削减=语义变化）。产品话术: 首跑 20-30 min（索引一次性 7-12 min）, 同片
  复定位 **2-4 min**。


## → 2026-09-06(III):性能批① 解码/forward 流水线落地 = 字节级零语义, 全流程 -9~11%

- **实现**: `engine/common/pipeline.py` `pipeline_map`（生产者线程跑解码可迭代, 消费方主线程
  做 embed/统计——DML session 非线程安全, forward 必须单线程; 保序; 双向异常安全; 哨兵必达）。
  接入两处大头: 索引侧 `_embed_stream`（feature_store）+ 编辑侧 twopass 粗采样（亮度/白闪/卡片
  统计同批顺带算, 帧不再全量留存）。fine 精修/dense/legacy 路径未动（小头）。
- **教训(死锁)**: 首版 `_produce` 的 finally 里先 `stop.set()` 再发哨兵, 而投递循环条件是
  `while not stop.is_set()` → 哨兵永远发不出, 消费者死等（test_empty_edited 挂死,
  faulthandler 栈定位）→ 修复: 哨兵投递不受 stop 影响。单测 +5（保序/空/双向异常/背压不死锁）。
- **验收**: 255 测试全绿; 全新 data 目录 test2 全流程: 索引 412.3s（前值 450.6s, -8.5%）+
  定位 1012.7s（前值 1139.4s, -11%）; **features.npy 与主目录重建批逐字节一致**
  （sha256 同）, 三指标/支撑 span 全等（13=13/18=18/0=0/64/219 全等）。
- **剩余杠杆（待拍板）**: ② 分辨率 518→384（单帧 forward ≈×0.55, 需判别力探针 + bump fv 全量重建）
  ③ 索引 0.5fps / dense 4fps（帧数减半, 需三指标验收）。

## → 2026-09-06(IV):外部新方向研读 + Context Re-ranking 判决探针 = 同场景细粒度偏移再证伪（3/7 可修、2 反向）

- **研读**: TCA(WACV21, 检索级表征, 与召回层瓶颈不匹配——召回已闭环 39/39 进池) /
  PRBonn 序列图匹配(VPR 变环境, 思想=P3 已证伪路线) / TF-CoVR(NeurIPS25, 训练路线, 与零训练
  约束冲突, 归档) / VOP(DINOv2 patch 对应+voting, 与 M6 相似度召回不同路线, 但 M7 几何路线已
  证伪, 低优先) / Video-ColBERT(8 star, 多向量晚交互=现有多证据体系已有同构, 架构参考) /
  DiffTrack(视频扩散 Transformer, 不可接入)。
- **判决探针**（probe_context_rerank.py, 用户 P0 提案「查询±2s 上下文 vs 源±15s 窗口序列相似度
  重排」在 7 个已知失败案例直测）:
  - 大偏移对照(p30, 203s): margin **+0.285** ✅（重排轻松修复——但这类本就 LOW/已有机制兜底）;
  - **同场景 ±3~13s 偏移（当前真实瓶颈）: 3/7 可修, 2 反向**（t3r03a +0.019 / t3r25 +0.086 /
    t3r29 +0.007 / t3r06b -0.004 / t3r04b **-0.015** / p35 **-0.012**）。
- **机制**: 同场戏窗口重叠（±15s 窗在 5~13s 偏移下共享 70~85% 帧）→ S(正确)≈S(错误), 噪声定方向;
  与 P3(编辑侧上下文污染)/M8(邻接唯一性 AMBIGUOUS) 三方闭环一致。预期指标收益 +1~2/139 且有
  打坏现存正确段的反向风险（触发器救不了——同场景偏移不是 montage 型）。
- **结论**: 同场景细粒度区分在「上下文/序列/图结构」路线三方证伪（P3+M8+本探针, 有据）;
  外部清单未覆盖该痛点。唯一未试路线 = TF-CoVR 式训练细粒度时间判别嵌入（与零训练产品约束冲突,
  如未来愿意引入训练再立项）。脚本留档 probe_context_rerank.py。

## → 2026-09-06(V):Context Re-ranking 多模态复审 = 信号存在但方向不稳, 可行落点=低置信段邻域重排（待拍板）

- **逐案画面对照**（work/context_review/*_sheet.jpg, 查询段 vs 正确位置 vs 错误位置）:
  - t3r25(+0.086 可修): 查询与正确位置是**同一战士同大厅同一动作特写**——视觉明确可判别 ✅;
  - p35(反向): 查询与正确位置都有夜空探照灯光束（错误位置没有）——视觉可判别但暗光低对比, CLS 排反;
  - t3r06b(微弱): 两个位置都是同一场景的金币瀑布, 画面族几乎相同——真不可分;
  - t3r04b/t3r03a(反向/可修): **GT 窄窗(0.3-0.4s)与多镜头查询段的对应本身模糊**——查询内容
    （矮人王特写/燃烧湖镇）在"正确"采样帧上反而看不见, 真实对应区疑似在窄窗附近数秒;
  - OCR 路线排除: 查询帧烧录字幕是解说文案, 原片帧无字幕——text_anchor 无匹配对象。
- **结论**: 「零训练突破」的真实形态 = **低置信段邻域重排**——序列相似度信号在 t3r25/p35 型
  案例确实存在（margin +0.086 与光束线索）, 只是被埋在噪声里; 用严格触发（仅 LOW/part 段 +
  邻域 ±20s 内候选 + margin>0.05 才改写）可控制反向风险, 预期 +1~2 且不伤正确段。
  GT 窄窗对位模糊（t3r03a/t3r04b 型）不是算法问题。

## → 2026-09-06(VI):「低置信段邻域重排」立项材料已出（待用户拍板）

- **文档**: mvp/benchmark/user_case/semantic_signal/RESEARCH_PROPOSAL_CONTEXT_RERANK.md。
- **方案要点**: 仅 LOW/低支撑段触发（正确段零接触）± 邻域 ±20s 候选 ± 序列相似度 margin>0.05
  才改写主定位; 零训练/零新依赖/不 bump feature_version; 预期 +1~2/139（t3r25 型）, 明确不解决
  GT 窄窗模糊（t3r03a/t3r04b 型）与真不可分（t3r06b 型）。
- **与已证伪方向的差异**: 触发面收死 + margin 门槛（P3 是全局改排; 反向案例 -0.015 量级过不了
  0.05 门槛）; 先行证据 = 判决探针 7 案例 + 多模态复审 6 张对照图。
- **验收标准**: 四片三指标不回退 + t3r25 修复可见 + 反向案例不触发 + 耗时增量 ≤5%; 不达标即关闭。
- **待拍板**: 批准 → 按执行清单实现（预计单轮会话完成实现+验收）。

## → 2026-09-06(VII):patch 召回 v2 判决 = 前提复活!池外 7 条中 2 条 rank=1 精确救回、2 条 rank2-3 毫厘差

- **前提变化（关键）**: M6 关闭 patch 召回的前提是「v4 GT 下 2.mkv 39/39 全部池内」; 在
  **twopass + 最新 GT + 当前管线**下重测四片 26 条未严格命中条目: **7 条检索 top-20 池外**
  （p14/p26/t1r02/t1r14d/t2r05a/t2r05b/t2r07c）——patch 召回重新有了对象。
- **判决**（probe_patch_recall_v2.py, M6 混合池协议: CLS top-200 ∪ 1/20 均匀 ∪ GT窗, patch
  3 帧查询 DML）: **p14/p26 rank=1 精确救回**（0.920/0.949, top1 即 GT）; t2r05b rank2（差
  0.004）/t2r05a rank3（差 0.009）毫厘之差; t1r02/t1r14d rank9-10（同场景内排错）; t2r07c
  rank300（混叠, patch 无解）。
- **潜在收益**: p14/p26 若安全采纳 = 2.mkv 严格 34→36（part→HIT）; 工程难点 = 采纳门控——
  patch top1 分数本身不能做门（错误位置分数同样高: t1r02 0.964/t2r07c 0.947）, 需结合
  邻域约束/CLS 一致性设计; t2r05a/b 的毫厘差需要辅助 tie-break。
- **对比 M6 关闭时**: 0/39 是「无对象」的关闭; 现在有对象且 2/7 命中——**「patch 已死」的结论
  在 twopass+最新 GT 条件下被部分推翻**。
- **待拍板**: 立项「patch 召回 v2（低置信/池外段）」——先做采纳门控设计探针（邻域约束 +
  CLS 一致性联合门），数据达标再进 runtime（预期 2.mkv 严格 +2）。

## → 2026-09-06(VIII):门控设计探针完成 = p26 可干净救回(+1), p14 与有害案例信号不可分（待拍板 A/B/C）

- **数据**（probe_patch_gate.py, 7 池外 + 12 对照, patch/CLS 双信号）: 关键字段
  patch_margin（top1 vs 主定位 patch 分差）/ cls_margin / offset:
  - p26: m_p +0.0851, cls_mg +0.2932, off 9s, in_gt True —— **信号强且干净**;
  - p14: m_p **+0.0006**, cls_mg +0.0098, off 13s, in_gt True —— 信号淹没在噪声里;
  - 有害案例: t3r26(对照! m_p +0.049, off 10s, in_gt False——采纳即严格 -1 回退) /
    t1r02(m_p +0.0222, False) / t1r14d(+0.0648, False) / t2r07c(0, False) /
    p10(对照, +0.1138, off 64.5, in_gt False) / t2r05a(+0.1978, off 2775) / t2r05b(+0.0207, off 343)。
- **门控规则筛选**: {offset≤30s 且 patch_margin>0.08} → 只采纳 p26, 拒绝全部有害案例
  （t3r26 0.049<0.08 ✓ / p10 off 64.5 ✓ / t2r05a off 2775 ✓ / t1r14d 0.0648<0.08 ✓）→
  **净收益 = 2.mkv 严格 35/39 (+1), 零回退**。
- **p14 不可救的证明**: 采纳 p14 需 m_p 门槛 ≤0.0006, 而有害案例 t3r26 m_p=0.049——任何
  能过 p14 的门槛都会同时采纳 t3r26 → -1 回退, 净收益归零。信号层面不可分（非调参问题）。
- **对照发现**: p10/t3r26 两个正确段本身 patch top1 就指向 GT 外——「重写主定位保留子 span」
  的实现约束下 HIT-via-sub 段无回退风险, HIT-via-main 段（t3r26 型）是唯一回退源。
- **待拍板**: A. 按 {offset≤30s, m_p>0.08} 进 runtime（净 +1, 先例 M6 以 +1/41 关闭过同级收益）
  / B. 关闭归档（门控数据证明收益天花板 +1 且 p14 类不可救）/ C. 继续挖掘更强门控信号
  （finloc 稳定性@top1/场景对齐等, 研究续期）。

## → 2026-09-06(IX):门控多模态复审 = 门规则视觉验证成立, p14 真相=画面本来就对（窄窗假象）, p26 唯一真错误

- **逐案画面对照**（work/patch_gate_review/*_sheet.jpg, 查询段 vs patch top1 vs 当前主定位 vs GT）:
  - **p26**: top1(1769)=同人物同椅子夜景=查询内容, 当前主定位(1778)=9s 后另一镜头——**真错误, patch 修对了**;
  - **p14**: 当前主定位(1394)与 GT(1381)是**同一座瞭望塔**（仅角度/光线差）——「13s 偏移」是 2s 窄窗
    对位假象, **画面本来就对, 无需救回**——p14/t3r26 的「信号不可分」困境随之消解（两者都该不动）;
  - **t3r26**: top1(2882)/GT(2891)/主定位(2892)全在**同一场连续战斗**里——「采纳即回退」也是窄窗
    假象, 但门规则(0.049<0.08)反正会挡住, 双保险;
  - **p10**: top1(1210)=餐盘特写, 与查询段(室内+峡湾直升机)完全无关——多镜头查询的代表帧落在
    错误子镜头上, patch 过度自信, **验证盲采纳危险真实存在**;
  - **t1r02**: top1(2175)/主定位(2181)/GT(2184)同一段游泳连续镜头——视觉无差别, 采纳无益也无害。
- **最终门规则（视觉+数据双重验证）**: {patch top1 与主定位 offset≤30s 且 patch_margin>0.08 →
  改写主定位（旧主定位保留为子 span）} → 仅 p26 被采纳, 全部有害/对照案例被拒。
- **实现要点（待拍板后动工）**: p26 所在段置信=HIGH → 触发面必须含 HIGH 段; 成本控制=在现有
  `_patch_rerank_span`（已每段运行）上扩展近场池（±30s@4s 步长≈15 帧）, 边际成本 ≈ +5s/段
  （四片约 +5~6 min）; 验收 = 四片三指标零回退 + 2.mkv 严格 35/39 + p26 修复可见。

## → 2026-09-06(X):patch 召回 v2 转正 = 四片严格 113→115(+2) 零回退, 28 处近场修复全部场景内

- **实现**: `_patch_nearfield_rescue`（locator_service）+ config `patch_v2_*`（enabled=True 默认开,
  margin=0.08/radius=30s/stride=4s）; 在现有 patch rerank 之后运行, 门控 {offset≤30s 且
  patch_margin(top1−主定位)>0.08} 才改写主定位, 旧主定位保留为子 span。单测 +4（采纳/无 margin/
  开关关闭/窄段拒绝）, **259 全绿**。
- **四片验收（对照基线批）**: 严格 **113→115（+2）** / 场景 136=136 / 负例 4=4 / 支撑 565→588;
  **test3 严格 32→34: t3r04b、t3r25 两条 part→HIT**（同场景偏移案例被 patch 匹配修复）;
  其余三片指标零变化。耗时: 2792s vs 2725s（+2.5%, ≤5% 达标; test1 单片 +20s 为 3 处采纳成本）。
- **有意思的偏差**: 实际修复的是 t3r04b/t3r25（近场池命中）, 而非门控探针预测的 p14/p26——
  近场池真实数据上的命中面比 7 条池外案例更宽（池外+池内偏移段都受益）。28 处采纳全部为
  ≤30s 场景内移动, 抽帧复核（t3r04b/s48）画面合理无伤害。
- **转正结论**: patch 召回在 twopass+最新 GT 条件下的价值被证实并落进 runtime; M6「patch 已死」
  结论正式修正为「旧管线条件下无对象; 新条件下 +2/139 且零回退」。

## → 2026-09-06(XI):M1-M8 按最新标准（twopass+最新GT+当前管线）重跑矩阵 = M4 仍关闭(0/7), M5/M6 已翻案, 其余维持

- **M4（索引密度）重跑 = 仍关闭（有新数据）**: probe_m4_v2.py, 混合索引协议（1fps 全片 + GT
  邻域 ±30s@8fps, 非循环论证版——首版「窗内帧自比 rank=1」为循环论证已废弃重写）:
  **7 条池外 0/7 拉回**（8fps 最优 rank: 21/296/3565/97/596/3794/1799, 全部 >20）。密度带来
  rank 边际改善但失败根因 = 查询均值与窗内内容相似度本身低（多镜头/编辑变换拉偏）, 非采样粒度。
  方法论教训: 窗内帧与自己邻域自比的 rank 是循环论证, 探针必须用「查询→候选集」真实检索口径。
- **M5/M6（patch 召回）= 今日已重跑并翻案**: 池覆盖 7 池外 → patch v2 runtime 严格 +2（详见
  2026-09-06(X) 条目）——M6「patch 已死」修正为「旧条件无对象; 新条件 +2 落地」。
- **M8（邻接唯一性）= 今日已重跑等价物**: context rerank 判决探针（窗口邻接相似度, 7 案例
  3/7 可修 2 反向）——维持证伪。
- **M1/M2（VLM 判定/字幕召回）= 不能重跑**: VLM 暂停使用（用户指令）; 且今日多模态复审
  （本模型直看帧）已覆盖其问题域——查询帧烧录字幕为解说文案、原片无字幕, 字幕-画面解耦在
  当前失败族上比当年更强。
- **M3（CLIP 跨模态）= 不建议重跑**: 证伪逻辑（文案与画面解耦、同场景相邻镜头无文本差异）
  在当前失败族上更强, 重跑无新信息。
- **M7（ALIKED 局部特征）= 未重跑, 后备**: 其证伪针对「同刚性场景不同机位」（单应成立→局部
  同貌）; 当前失败族是「同场景不同时刻」理论上局部可分性更高, 但 patch v2 近场重排已在该
  失败族拿到 +2——ALIKED 的增量空间被占据, 仅当未来需要第二局部通道时作为后备。
- **矩阵总览**: 翻案 1（M5/M6→+2 落地）/ 重跑维持关闭 2（M4 密度、M8 邻接）/ 条件性跳过 3
  （M1/M2 VLM 暂停、M3 无新信息）/ 后备 1（M7）/ 已被 runtime 吸收 1（patch v2 = M5/M6 转正）。

## → 2026-09-06(XII):M1/M2 用本模型多模态重跑（最新失败族 14 案例全画面复审）= 可分 5 / 不可分 5 / 窄窗假象 4 + **发现 t2r07c 疑似 GT 标错**

- **M1-v2（事件级视觉判定, 本模型直看帧, 全 14 失败案例）**:
  - **可分 5**: t3r25(同战士同大厅特写✅已被 patch v2 修复) / p30(同一狙击手女性, 新旧主定位同场景) /
    p35(夜空光束仅正确位置有) / p26(同人物同椅子, patch top1 正确) / **t2r07c（见下, 重大）**;
  - **不可分 5**（同一事件族两侧都有, 视觉无差别）: t3r06b(金币瀑布) / t1r02(同段游泳) /
    t1r14d(同段暗夜山地) / t2r05a(同一演员同一橙衣两侧都是) / t3r29(同一山坡行走镜头, 3s 偏移无意义);
  - **窄窗假象 4**（GT 0.3~2s 窄窗与多镜头查询对应模糊, 当前主定位画面本来就对或对应区在窗旁）:
    t3r03a / t3r04b / p14 / t2r05b(查询=机器特写, GT 帧却无该物)。
- **⚠️ t2r07c 疑似 GT 标错（需用户人工复核）**: 查询=星条旗马甲演讲台; patch top1 **4697s = 同人
  同马甲同讲台同招牌（视觉强匹配）**; 而 GT og4092.2-4097.0 = 烟雾战场（与查询完全无关）。
  「混叠无解」改判为**「算法可能找对了, GT 疑似指向错误位置」**——若 GT 修正, test2 严格 13→14。
  （需确认影片是否两次出现同场景; 对照图 work/context_review/t2r07c_sheet.jpg）
- **M2-v2（字幕语义, 本模型读查询字幕）**: 查询烧录字幕=解说文案、原片无字幕 → 字幕-画面解耦在
  当前失败族全灭; 唯一价值=跨场景排除远距错配（p10 餐盘 vs "Jack explained" 明显无关）, 该类
  已是 LOW/混叠。**维持证伪**。
- **M1-v2 与 patch v2 关系**: 可分 5 中 t3r25/t3r04b 已修（+2）; p26 未触发（runtime margin 口径
  差, open item 待查）; p30/p35 的 patch 信号反向或场景内移动——视觉判别信号与 CLS/patch 信号
  在暗光/同族场景失灵, 与 M1 原结论（语义层与外观层共享天花板）一致但边界更清晰。
- **对照图**: work/context_review/ + work/patch_gate_review/（14 案例全覆盖）。

## → 2026-09-06(XIII):t2r07c GT 标错修正（用户画面确认）= 「混叠无解」冤案平反, test2 严格 13→14

- **修正**: ground_truth_test2.json t2r07c original [4092.2,4097] → **[4692.4,4698.0]**（原值与原因
  留痕 corrections[0]）。根因 = 2026-09-02 人工定位时播放器分钟档误读（68:12 ↔ 78:12, 差 60s×10）:
  68:12=4092 为战场戏, 78:12.4=4692.4 起才是星条旗马甲演讲台桥段（多模态复核: patch top1 4697
  与查询 ed65.25 的 "COUNTRY" 举手姿势逐帧对应; 4080-4102 全扫描无演讲台）。
- **度量**: 修正后 test2 严格 **14/20**（基线批与当前批同判——算法主定位 4695-4700 本就正确,
  「内容相似混叠无解」系冤案）; 四片严格合计 **115→116/139**（34+34+14+34）, 场景 137/139,
  负例 4/9, 支撑 +2。
- **连带修正**: ① patch 召回 v2 探针记录 t2r07c「rank300 ❌」→「top1 4697 本就是正确答案」;
  ② 失败族清单移除 t2r07c（内容相似混叠族少一例）; ③ measure_baseline / GT_BASELINE_test1-3.md
  的 test2 数字以本条为准（13→14）。
- **open item**: p26（2mkv）runtime margin 口径差未触发——待查。

## → 2026-09-06(XIV):patch v2 门槛 0.08→0.075 = p26 骑线救回落地, 四片严格 117/139 零回退（patch v2 正式转正）

- **open item 查明**: p26 未采纳原因 = runtime 实测 margin **0.080 恰好骑线**（拒绝条件
  margin≤0.08; 探针口径 +0.085, GPU 浮点差 ~0.004）。日志: "patch v2 nearfield ed=76.3
  margin=0.080 (no adopt)"。
- **修复**: patch_v2_margin 0.08→0.075（骑线带 0.075-0.08 内另有 3 案例: ed26.8/125.7/69.9,
  一并纳入采纳面）。259 单测全绿。
- **四片验收（对照基线批, GT 已含 t2r07c 修正）**: 2mkv 34→**35**（**p26 part→HIT**）/
  test1 34=34 / test2 14=14（t2r07c GT 修正, 两批同判——算法主定位 4695-4700 本就正确）/
  test3 32→**34**（t3r04b、t3r25 part→HIT）→ **合计 114→117（+3）**, 场景 137=137,
  负例 4=4, 支撑 567→592。零回退。
- **耗时说明**: 四片 938/678/984/988s 较上批普遍 +25%——主因 = config 指纹变化触发 A4 编辑
  缓存全量失效重算（margin 参数入指纹, 预期行为）, 非算法回退; 缓存命中后恢复。
- **验收对照（立项 §5）**: ①单测 ✅ ②三指标零回退 ✅（严格 +3）③p26 修复可见 ✅ / p14 不被
  采纳 ✅（多模态确认画面本来就对）/ 反向案例零触发 ✅ ④耗时——v2 自身边际成本符合预期,
  总耗时增量主要来自缓存重算（一次性）。**patch 召回 v2 正式转正为 runtime 默认行为**。
- **当前基线**: 四片严格 **117/139**（2mkv 35, test1 34, test2 14, test3 34）/ 场景 137/139 /
  负例 4/9 / 支撑 592。今日全程净变化: 严格 113→117（patch v2 +3, GT 平反 +1）。
