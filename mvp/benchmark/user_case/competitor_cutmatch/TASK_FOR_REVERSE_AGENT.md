# TASK —— 给 cutmatch-analysis 逆向对话的任务单（常量绑定优先级提升）

> 来源：benchmark 侧（Source Video Locator）。请求方已完成的工作见本次新增的两份 FINDINGS：
> \`FINDINGS_TRANSNETV2_SEGMENTATION.md\`（A1）、\`FINDINGS_TN_CUT_QUALITY_VS_METRIC.md\`（A1+ 盲判）、
> \`FINDINGS_ALIGNMENT_RANKING.md\`（A2）、\`INTEL_REQUESTS_CUTMATCH.md\`（原始情报需求）。

## 0. 为什么优先级变了（请先读）

1. **运行期路线已确认走不通**：用户本机实测 → **"进不去，需要卡密"**。结合已知事实
   （a01/a02 为 AES-256-GCM 密文，\`content_key\` 由服务器 P-256 ECDH + HKDF 下发，二进制内零密钥材料），
   **绕过授权也拿不到模型**。⇒ **静态常量提取从"辅助手段"升级为唯一可行来源**。
2. benchmark 侧当下的阻塞点只有一个：**缺他们的后处理参数**。切分模型本身已复现
   （a01 = 官方 TransNetV2，权重 SHA256/元素数逐位一致，我们本地 ONNX 与官方 PyTorch 对拍 max|diff| = 6.1e-8），
   但"为什么他们的场景切分更好"落在这一批常量上。
3. 盲判已给出硬证据：**仅 TN 独有的边界 8/8 是真切换，仅基线独有的只有 2/8（2mkv）、4/6（test3）**。
   我们需要的不是"再看一眼产品"，而是**把他们的判据与阈值复现出来**。

## 1. 任务 A（最高优先）：完成 name→value 精确绑定

目标模块：\`cutmatch\matching\fast_timeline\options.py\`、\`matching\scene_detection\*.py\`（含 boundary / boundary_refiner / commentary_scenes 相关 code object）。
方法：按 **code object 切帧**（\`FINDINGS/08\` §3 待办 1：反汇编 \`0x15640fe60\` 附近的加载器），把 co_names 与 co_consts **正确配对**，
不要再按 blob 里的线性顺序硬对齐（同一值会被 co_consts 去重、不同 code object 常量会混排）。

必须绑定的参数（括号内是 benchmark 侧的用途）：

- **A1 编辑侧场景判定**：\`commentary_scene_dual_single_min\` / \`dual_many_min\` / \`dual_combined_min\`
  （我们现在只能用"共现候选 0.55/0.35/0.62"，等级仅"中"）
- **A2 多判据**：\`commentary_scene_visual_score_min\` / \`visual_strong_score_min\` / \`visual_peak_ratio_min\` /
  \`structure_distance_min\` / \`structure_strong_distance\` / \`motion_ecc_similarity_max\` / \`motion_histogram_distance_max\` /
  \`flash_luminance_min\` / \`flash_luminance_jump_min\`（**并说明组合方式**：谁是硬门、谁加分、先后顺序）
- **A3 几何参数**：\`commentary_scene_descriptor_width|height\`、\`move_radius_frames\`、
  \`candidate_snap_radius_frames\`、\`visual_context_frames\`、\`min_side_frames\`、
  \`max_additions_per_segment\`、\`prediction_support_radius\`
- **A4 边界精修**：\`commentary_boundary_refine_*\` 全组（\`min_segment_frames\`/\`min_side_frames\`/\`near_cut_frames\`/
  \`max_move_frames\`/\`max_additions_per_segment\`/\`proxy_width\`/\`proxy_height\`/\`absolute_diff_min\`/\`mad_multiplier\`）
- **A5 短场景合并**：\`commentary_short_scene_merge_enabled\`、\`commentary_short_scene_min_frames\`
  ⚠️ **专项核实**：\`FINDINGS/08\` 把 \`180\` 放在 \`commentary_short_scene_min_frames\` 之后，但 benchmark 侧实测
  "按 180 帧合并"是灾难（GT 覆盖 .862→.172）⇒ **该绑定几乎肯定错误**，请给出真正的值与其归属。
- **A6 其它开关**：\`commentary_scene_refine_enabled\`、\`boundary_backshift_enabled\`/\`boundary_backshift_max_seconds\`、
  \`use_scene_proxy\`、\`scene_proxy_height\`（已强绑定 720，请确认是否有第二处）、\`fast_hwaccel_enabled\`、\`runtime_vision_vits14\`
- **A7 复核 benchmark 侧的临时绑定**：\`refine_commentary_scene_split_with_frame_diff\` 我们按参数顺序匹配到
  \`min_segment_frames=32, min_side_frames=10, near_cut_frames=16, absolute_diff_min=45.0, mad_multiplier=4.0,
  max_move_frames=16, max_additions_per_segment=1\`（等级：强推断）—— 请确认或纠正。

## 2. 任务 B：原片侧索引（对应 INTEL P1#9/#10）

- \`build_scene_feature_index_{standard,low_memory,streaming}\`：粒度/特征来源（是否 DINOv2 CLS、fps、维度、是否有代理降采样）
- \`source_global_fps\`、\`global_weight\`、\`local_global_similarities\`、\`build_source_timeline_index\`、
  \`save_fast_global_index\` / \`load_fast_global_index\` 的参数
（我方原片侧目前是 1 fps DINOv2 CLS 特征聚合出的 \`scenes.npy\`，需要知道他们的口径才能做 H3。）

## 3. 任务 C：路径选择与 offset 精修（对应 INTEL P1#13/#14）

- \`select_scene_match_path\` / \`resolve_consecutive_scene_offsets\` / \`describe_scene_path_quality\` 的**目标函数**与以下权重默认值：
  \`path_consistency_weight\`、\`path_transition_max_penalty\`、\`path_backward_max_penalty\`、
  \`path_coarse_weight\`、\`path_local_weight\`、\`path_support_weight\`、\`path_transition_grace_seconds\`
- \`offset_refine_*\` 与 \`offset_refine_dtw_*\` 全默认值（\`min_score\`/\`min_support\`/\`max_shift_seconds\`/\`max_shift_frames\`/
  \`sample_interval_seconds\`/\`sample_points\`/\`max_samples\`/\`start_window_enabled\`/\`start_window_radius_frames\`/
  \`start_window_min_improvement\`/\`topk_rerank_enabled\`/\`topk_rerank_max_candidates\`/\`topk_rerank_min_scene_coverage\`）
- 顺带（在 fast_timeline/options 段里出现，未在请求单里）：\`ordered_search_coarse_min_score\`、
  \`ordered_search_coarse_min_support_ratio\`、\`ordered_search_refined_min_score\`、
  \`ordered_search_consistency_min_score\`、\`ordered_search_candidate_margin\`、
  \`actual_refine_min_score_gain\`、\`actual_refine_score_threshold\`、\`leading_score_gain_threshold\`、
  \`recovery_local_score_threshold\`、\`dense_early_weight\`（已强绑定 1.5）、\`continuity_tiebreak_bonus\`（已强绑定 0.02）

## 4. 任务 D（可选）：导出层字段（对应 INTEL P0#7）

\`exporting/segments/builder.py\`、\`exporting/timing/video_timing.py\`、\`exporting/jianying/fcpxml_generator.py\`、
\`exporting/premiere/xml_generator.py\`：输出字段名、时间码精度、是否携带场景 id / offset。

## 5. 任务 E：回填"运行期不可行"的结论

请在 \`FINDINGS/06\` 或 \`.agent/STATE.md\` 记录：**用户本机实测被授权拦住（需卡密），且即使绕过授权也因
服务器 model lease 拿不到模型 ⇒ 运行期路线关闭；静态常量提取为唯一来源**。（避免后续再重复尝试运行路线。）

## 6. 交付要求

- 新增 \`FINDINGS/09_*.md\`（或续写 08），**表格化**：参数名 | 值 | 证据（偏移 / code object 边界 / 配对依据）| 等级（确证/强推断/推断）。
- 原始产物落盘（dump 文本 / 反汇编片段 / 脚本），保证可复跑。
- **不要修改 \`D:\claudework\benchmark\` 下任何文件**（既有约定）；benchmark 侧只读引用你们的产物。

## 7. 收到后 benchmark 侧会做什么

- A1–A5 → 按真实阈值实现"TN 双头 + 多判据 + 帧差精修 + 短场景合并"的编辑侧切分，做**四片结构对照**
  （片段数/时长分布/intact/split/inner vs 我方 twopass 69/41/54/67 与裸 TN 71/33/66/87）；
- B → H3（原片侧 TN 场景索引）设计；
- C → H4（场景级 offset 路径选择）探针的目标函数与门限。
