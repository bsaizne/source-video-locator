# FINDINGS：边界精度开源方案调研（GitHub，2026-10-24）+ 非商业化裁定后的候选修订

> 口令：「开子代理去 github 上，根据我们现在卡住的地方，针对边界精度这些问题，寻找开源解决这些问题，
> 子代理用 5.3flash 模型」→「本项目不商业化，可以把那两个被否定的加入，不商业化入文档」。
> **`mvp/src` 零改动、未出包、未提交。** 完整版报告（30KB markdown 卡片，含逐仓核对行）=
> workflow run `dwfrun-eb6f1920-5634-457f-9c9e-a73d04d061ee` 的 artifact「边界精度开源方案调研报告」；
> 本文是落档版结论 + 裁定后修订，不重复卡片全文。

## 0. 一句话

三个卡点方向（镜头边界漏切 / 身份级信号 / 跨镜头采纳层）在 GitHub 上各有**许可干净且可试点**的候选，
最值得先试的是 **tslearn 子序列 DTW（正对我们唯一没测的 DTW 打分口子）** 与 **opencv_zoo YuNet+SFace
（全场唯一当日本机实测可跑的身份信号件）**；用户拍板**不商业化**后，insightface 与 fast-reid/torchreid
两条因许可被否的候选**重新入列**。

## 1. 方法与可信度

- workflow 三调研员（镜头边界漏切 / 身份级信号 / 跨镜头采纳层）+ 一核对员，全部 GLM-5.3-Flash。
- 任务书内嵌**已知死路清单**（TransNetV2 判负 / TransVCL 零预测 / VDF AGPL / ViSiL TF1+NC /
  通用嵌入解不了身份级 / OCR 语音不立项）与硬约束（离线、Python 3.11、只推理不训练、DirectML/MPS）。
- 核对员经 api.github.com 逐仓核对 15 个候选（存在性/license.spdx_id/star/pushed_at/archived），**11 个一致**。
- ⚠️ 可信度分级（技术判断契约）：**本机实测证据**仅 YuNet+SFace 烟测（权重下载成功、
  cv2 CPU 检测 33.9ms/帧、识别 8.3ms/个、同人镜像 cos 0.822 vs 人脸-随机块 0.093）；
  其余「机制对症」均为调研员陈述 + API 事实核对，**不构成验收证据**，试点必须拿 scn5/正反打素材实测。

## 2. worth_pilot 5 条（调研员排序）

| # | 候选 | 方向 | 机制要点 | 关键风险 |
|---|---|---|---|---|
| 1 | `tslearn` dtw_subsequence_path（BSD-2，活跃） | C 采纳层 | 子序列 DTW 一个调用同时出「子段采纳信号 + 帧级边界 snap」；pip 即用、无权重无训练 | 普通 DTW 非 shape-aware，需按镜头分治 + 带约束 |
| 2 | `opencv/opencv_zoo` YuNet+SFace（模型级 MIT/Apache 已逐字核） | B 身份级 | 检测 5 点 landmark + 128 维身份嵌入，判「切点前后是否同一主体」；**已本机烟测通过** | SFace 精度中等；侧脸/暗光/古装未实测；OpenCV5 DNN 暂 CPU-only（可走 onnxruntime-directml） |
| 3 | `tryolabs/norfair`（BSD-3） | B 身份级 | 人脸框+嵌入串轨迹的最小胶水；跨切点比轨迹嵌入质心 = 正交身份门 | 跨镜头关联胶水自写；稀疏脸场景退化为直接余弦 |
| 4 | `alipay/VCSL` VTA（MIT；本地 engines/ 已有 clone） | C 采纳层 | 五个 VTA 算法（含 DTW/DP/HV）已改造成「两视频间多段检出」，直接吃帧特征 npy | benchmark 代码风格、Python3.11 需适配；DTW 非其最强 baseline |
| 5 | `UVA-Computer-Vision-Lab/OmniShotCut`（MIT，339★，2026-09 仍活跃） | A 漏切 | shot-query Transformer 直接出镜头区间+转场类型，自述对同场景硬切（=我们的漏切形态）敏感 | 权重在 HuggingFace（本机直连不稳）；非 CUDA 后端未验证；**新仓库，先亲核再谈试点** |

## 3. ⭐ 非商业化裁定后的修订（2026-10-24 用户拍板，权威见 DECISIONS.md 同日条目）

原任务书硬约束「AGPL/CC-NC 一律 no」**作废**。据此：

| 候选 | 原判 | 修订后 | 残余风险（从许可改为实质） |
|---|---|---|---|
| `deepinsight/insightface`（SCRFD+ArcFace，权重非商业） | 许可一票否决 | **重新入列（maybe→试点候选）** | 域适配未实测；作为 SFace 精度不够时的升级件（精度高一档、ONNX 生态成熟） |
| `JDAI-CV/fast-reid` / `torchreid`（全身 ReID） | 权重许可不净，no | **重新入列（观察项）** | 监控/行人 vs 影视运镜**零证据**；人脸不可见时的备胎，优先级仍低于人脸路线 |

- 追溯：VDF(AGPL) 同理不再被许可挡，但其判负是 merit 口径（5.46 < VCSL 6.00），维持不变。
- **维持不变的排除**（机制原因，与许可无关）：PySceneDetect（像素/HSV 差分族 = 已判负同范式）；
  boxmot(AGPL) 现在也**不再因许可排除**，但其与 Norfair/ByteTrack 功能重叠无增量，维持不占位。

## 4. maybes（方法论参考，不占试点位）

AutoShot（同 TransNetV2 帧对范式风险 + 权重在百度网盘；**SHOT 数据集**对边界判据校准有独立价值）；
AdaFace/CVLFace（侧脸精度优，权重 Google Drive/HF + 许可未标，现仅作 SFace 升级备胎）；
ByteTrack 关联模块（暗光漏检鲁棒的 Norfair 替换件）；dtaidistance（local concurrences 视角，
与 tslearn 二选一）；EGO4D VQ2D 系 / vq2d_cvpr DQS / PRVQL（「多假设→视觉证据选择」的成熟范式参考，
落地形态是抄判别思路而非引依赖）。

## 5. 未覆盖（不许外推）

- 未在本机实测任何候选的真实速度/效果（除 YuNet+SFace 烟测）；权重可达性按仓库声明判断未逐个试下。
- paperswithcode 已下线，ClipShots SOTA 榜无法独立复核，F1 数字以各论文自述为准。
- 方向 B 检索共识：**不存在维护中的「身份感知镜头切分」单体仓库**，学界先例（Character Attention
  Network / Dynamic Character Graph）均无开源实现 ⇒ 路线 = 检测器+身份嵌入+跟踪**自组**。
- 场景级切分线（BaSSL/MSRC/VSMBD/TELNet）方向相反（切得更粗），未列候选。

## 6. 下一步（试点排序建议，**都需口令**，均不动 `mvp/src`）

1. **tslearn 子序列 DTW**：对 41 段 GT 出三臂对照（现役单点精排 vs DTW path vs VCSL-DTW），
   同时回答「采纳信号」与「边界 snap」两个问题；成本最低。
2. **YuNet+SFace 身份门探针**：在正反打 17 条 + 单镜头 9 条（续68 补三的两组）上判
   「切点前后是否同一主体」，量身份信号的存在性（AUC 口径同 CLS 腿先例）。
   精度不够再升 insightface SCRFD+ArcFace（已入列）。
3. **OmniShotCut**：先亲核仓库/权重可达（HF 镜像）→ 再在 scn5 同场景素材上实测召回
   （对照 TransNetV2 375 切点 / 现役 912 的基数）。

## 5. OmniShotCut 亲核结果（2026-10-24 续90，主代理实测）

- **真身确认**（api.github.com 匿名读，网页 443 阻断属本机网络已知态）：`UVA-Computer-Vision-Lab/OmniShotCut`，
  NeurIPS 2026 / Shot-Query Transformer / MIT / 339★ / 2026-04 创建、2026-09-09 仍推送 / Python /
  pip 可装（`pip install git+...`，本机需走 api tarball 替代）。README 存档 `work/omnishotcut_readme_20261024.md`。
- **输出对口**：`inference(video, mode)` 直接返回 `[start_frame, end_frame]` 镜头区间 +
  转场类型（dissolve/fade/wipe）；接受视频路径或 numpy/tensor 帧数组。v1.5（52.8M，推荐）
  自述「对连续运镜/光照变化更少假切、密集快剪召回更好」= 与我们「同场景硬切漏检」方向匹配。
  四个下游工作（DreamX-Creator/Sekai2/ContextMaster/AlayaWorld）在数据管线用它 ⇒ 工程可信度加分。
- **三道实测门槛**（试点前必须过）：① 权重在 HF `uva-cv-lab/OmniShotCut_v1.5`（直连不稳，需镜像）；
  ② **README 官方口径 = PyTorch CUDA**——本机 AMD/DirectML 无 CUDA，CPU 推理速度未知，
  必须先在 scn5 短素材（15 段真漏切窗口）上测速+召回，不能直接全片；③ 代码获取走 github 443 阻断，
  改 api tarball。
- **结论**：亲核通过、试点价值维持；实测（装包+权重+短素材）为试点级动作，**待口令**。
