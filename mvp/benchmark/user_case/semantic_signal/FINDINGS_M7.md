# Phase 24-2 · 局部特征探针 M7 FINDINGS —— ALIKED 局部空间结构证据区分失败族实测
> ⚠️ **test4 数据错误(2026-09-01):** test4-ed.mp4 与 test4-om.mkv 为两部不同电影(81s竖屏 vs 71min横屏), 本文件中依赖 test4/t4r01 的结论全部作废(逻辑剔除, 详见 datasets/real/test4-INVALID.md)。

> 日期:2026-09-01 | 性质:**研究侧探针(零 runtime 改动, CPU ALIKED n32, 633s)**
> 起因:用户拍板「先1再2」——1=FAILURE_TAXONOMY.md 固化 A/B/C/D 分类; 2=现代局部特征(SuperPoint/DISK/ALIKED/LightGlue)
> 验证「局部空间结构证据」能否把失败族捞进候选池。网络受限(HF/GDrive/hf-mirror 均不可达)致 SuperPoint/DISK 权重拿不到,
> 用户手动装了 kornia 0.8.3 + 下载 aliked-n32.pth(纯 state_dict, 本地加载验证通过, 缺 1 无害 buffer dkd.hw_grid)。
> 脚本:`mvp/scripts/research_local_feature.py` | 数据:`work/local_feature_results.json`

## 探针设计

- 查询 = 编辑段 GT 窗中点 ±0.4s 三帧 → ALIKED n32(keypoints + 128D descriptors + scores);
- 候选池 = **均匀采样(~250) ∪ 真值/干扰窗**(~260-318 帧)——ALIKED 无 CLS 输出, 池不借用 CLS top-200,
  测的是「局部特征独立判别力」(非 CLS 导向召回);
- 帧间相似度 = 互近邻(mutual-NN)匹配数(score_thr=0.3 过滤低分关键点), 查询三帧拼接后一次匹配;
- 输出: 真值窗 best_rank / top-N 命中 / margin(真值 max − 干扰 max)。

## 结果

| 案例 | ALIKED best_rank | top5/top10 | margin | 对照 M6 |
|---|---|---|---|---|
| **p08** 兄弟机位(瞭望塔真值) | 21 | 0/0 | **+34**(真>干扰) | CLS 6(池内) |
| **p38** 兄弟机位(士兵特写真值) | 61 | 0/0 | **−24**(干扰反超) | CLS 340 / patch 225 |
| **p26** 夜读 | 125 | 0/0 | **−19**(干扰反超) | CLS 22 / patch 24 |
| **t3r12** 重复镜头 | 16 | 0/0 | +48(真>干扰) | CLS 1 |
| **t4r01** 同质滑梯 | 4 | 2/3 | −11(干扰 max 反超) | CLS 1 |
| **p01** 易例(sanity) | 4 | 2/6 | — | CLS 1 |

## 关键发现

1. **局部特征未能救回两个核心难例**: p38(兄弟机位士兵特写)rank 61 且干扰反超(margin −24)、p26(夜读)rank 125 且
   干扰反超(margin −19)——**在 M6 显示 CLS/patch 双失败的两个案例上, ALIKED 局部结构同样失败**。
2. **局部特征有弱正向但方向不一致**: 同一对兄弟机位, p08(瞭望塔为真值)margin +34 而 p38(士兵特写为真值)margin −24——
   局部匹配对「谁是查询」高度敏感(编辑帧来自某一机位视角), 不能稳定地把正确机位排到兄弟之前。
3. **t3r12/t4r01/p01 表现与 CLS 相当或略差**: t3r12 rank 16(CLS 本来 rank 1)、t4r01 rank 4(干扰 max 反超)、p01 rank 4——
   局部特征在易例上不退化, 但无增量。
4. **与 Phase 24-1 几何结论呼应**: 兄弟机位拍同一刚性场景, 局部 patch 本身也相似(单应约束成立), 局部描述子匹配
   自然分不开「来源相同但机位不同」——M7 从局部特征维度再次确认这是「身份」问题而非「外观分辨率」问题。

## 净结论

1. **局部特征方向 = 关闭(有据)**: ALIKED 在核心难例(p38/p26)上无法区分, 与 CLS/patch 同天花板;
   失败族(兄弟机位/夜读/同质/重复)在**外观三层(CLS/patch/局部描述子)全部无解**——特征上限经外观多尺度确认。
2. **这与用户的直觉相悖但有数据支撑**: 「局部空间结构让高度相似全局画面仍有可区分局部证据」——在兄弟机位上不成立,
   因为**兄弟机位的局部 patch 本身也相似**(同场景同机位组拍摄, 单应成立), 局部证据天然同貌。
3. **A/B/C/D 分类更新**: p38 = A 类(召回失败)在 CLS/patch/ALIKED 三特征下均无法救回——特征召回路径对兄弟机位
   族关闭; p26 = 区分度失败在三个特征层同样关闭。剩余未试: 更强语义/身份特征(多模态已测无解)或接受为已知局限。
4. 零 runtime 改动;三指标 39/41 未动。

## 交接

- **局部特征(ALIKED/DISK 类)= 关闭(有据)**: 核心难例不可分, 与 CLS/patch 同天花板; SuperPoint/DISK 因网络受限未测,
  但 ALIKED 是同类局部描述子, 结果可外推(若要补测 DISK, 权重下到 work/local_feature_weights 后可直接复用探针脚本改一行)。
- **环境成果保留**: kornia 0.8.3 + aliked-n32.pth 已就位(work/local_feature_weights/), 教程见 mvp/docs/LOCAL_FEATURE_SETUP.md;
- **FAILURE_TAXONOMY.md 待更新**: 把 p38/p26 标记为「外观三层(CLS/patch/局部)全部关闭」, 失败族定性为「身份级区分」局限。

## 相关产物

- 脚本:`mvp/scripts/research_local_feature.py`;数据:`work/local_feature_results.json`;
- 前置:M6(`semantic_signal/FINDINGS_M6.md`)+ FAILURE_TAXONOMY.md + M1-M5(`semantic_signal/FINDINGS_M1..M5.md`)。