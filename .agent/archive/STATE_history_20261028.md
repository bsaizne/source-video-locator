# STATE 历史迁移（2026-10-28 批次1 同批，逐字迁出）

> **▶ 2026-10-25（续93）— 候选 B 人脸身份标注已接线（代码笔+门禁全绿，未出包）；ai_visual 11 行代查定案（无一推翻）；灰带 26 段闭合（阈值不下放）【已退休，见上】**
> 口令「1.先做b吧，2.我懒得自查了…自己查一下，3.读一下吧」三件同批执行。**`mvp/src` 有改动（旁路标注）、未出包、未 push。**
> **一、⭐ B 接线落地**（`domain.FaceIdentity` + `engine/face_identity.py` + config 两字段 +
> `locator_service._annotate_face_identity` 旁路 + `install_face_models.py` 资产安装）：挂点在
> locate() 修复链**之后**（起点已定案）、结果行素材起点边界两侧各 3 帧（±0.10/0.25/0.40s，
> **480 宽口径**——全分辨率会多检边缘小脸，实测必须对齐探针）、**两侧均单脸才判**
> same/different（阈 0.57）、多脸/无脸/失败=unknown/None；资产缺失整层降级。**口径校验**：
> same 3 点（cos 0.87/0.94/0.86）+ different 2 点（0.16/0.20）+ 多脸不判，与探针逐点一致。
> **门禁**：新增 test_face_identity 10 项 + 后端全套 **723 OK(skipped=2)** + API **150 OK**；
> 惰性锁 = _locate_features（纯管线）与开关逐键无关。**端到端分布**（真 results）：test1 55 行
> 27s（same 10/diff 3/unknown 41）、2mkv 84 行 25s（same 22/diff 5/unknown 55）⇒ 成本 ~0.5s/行。
> UI 呈现层未做（PLAN 决策点③待拍板）；出包待口令。
> **二、ai_visual 11 行代查定案**：8 行单帧对图 9/10 同镜头维持 + 3 行二轮已确证 ⇒ **无一推翻**。
> **三、灰带 26 段闭合**（`work/grayband_20261025/`）：7 切换 / 18 无切换 / 1 暗帧不可判；
> 切换组 dmax {0.175~0.370} 与无切换组 {0.295~0.403} **完全重叠**（无切换组最高 0.403 > 切换组
> 全体）⇒ 灰带主体是同镜头 CLS 抖动，**query_cross_cut_thresh=0.50 维持不下放**。
> **四、档案**：FINDINGS_QUERY_CROSS_CUT §11（灰带闭合）+ GT_PATCH_PROBES §4.2ter（代查定案）；
> 迁移：STATE 续90 块、TODO 续92 块逐字迁 archive（`work/premigrate_20261025_h/` 回滚备份）。
