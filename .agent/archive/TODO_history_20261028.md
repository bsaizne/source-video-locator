# TODO 历史迁移（2026-10-28 批次1 同批，逐字迁出）

> **▶ 2026-10-26（续97~98）/ 2026-10-27（续99）— 出片性能批 + smart render 真片判负；ArcFace 替换 + XFeat 四片验收【现读这条】**
> 口令「可以，9点前花完token」→「Continue this project」。代码笔 `379c1fd`；本批改动未提交、未出包。
> ✅ 渲染 workers 2→6（60.1s→26.3s 实测）；✅ 三路调研（FINDINGS_PERF_HARDPROBLEMS_SURVEY
> + PLAN_SMART_RENDER）；❌ dense_recheck 分级复核判负（test1 −1 + 细窗仅占 5-10%，opt-in 默认关）。
> ❌ **smart render 默认关**：test3 off=4513/4513、35.352858s；on 容器 4513 但严格解码 1975，
> AMF/libx264 与早期 POC 均有非法 PTS，未完成收益测量。实验代码保留 opt-in；新成片/缓存复用加强制
> 严格帧数校验，普通渲染不变。后端 **752 OK(skipped=2)** / API **150 OK**。
> **续99（口令「开始吧」→「交接」）+ 2026-10-28「1，翻默认」**：✅ ArcFace SCRFD2.5G+MobileFace 已替换，
> 302行可判57→70、same↔different直接翻转0，0.51±0.10灰带unknown；✅ XFeat四片离线101独立段49/47/5，
> 生产严格147→148、主span142→144、假阳4→4、导出不变式全绿；**2026-10-28 已翻默认开**
> （`xfeat_start_enabled=True`，默认开态复验：不变式FAILED=0、148/150·144/150·假阳4/9；专项5/后端758/API150）。
> ✅ **成本已闭合（2026-10-28）**：四片阶段合计 2249.0s ≈37.5min（302 行/198 精修，~7.5s/行）；
> 2mkv 同脚本双臂（缓存全热）+583.1s，与阶段 557.9s 差 4.5%；首组 151.5s 臂差 = 冷缓存重建
> +347.8s（升级后首跑一次性）伪影，已作废。证据 `work/xfeat_cost_20261028/`。UI166/双typecheck0（本批未动UI，沿用10-27读数）。
> **待用户**：① ~~补同脚本双臂成本~~ = ✅ 已做；②提交/出包（现役r29不含XFeat ⇒ 出包才生效）；③ mac（需授权改workflow加
> kornia/XFeat/新face资产后dispatch）；④ r29/r28删除等口令。HEVC输出契约仍不改；smart render修复须重新立项。
