# TODO P0 历史（2026-10-12）

> 从 `.agent/TODO.md` 的 P0 容器**逐字**迁出（防复发纪律：P0 <=1 块）。

> **▶ 2026-10-12（续63 补十五）— 真机 SegmentOverlap 崩修复 + 导出第二层错误边界【现读这条】**
> 根因 = 贴接裁开出 <0.1s 窄素材 × write 的 0.1s 目标下限越出卷轴槽位（与十二轮同族、越的是目标轴）。
> 修 = 卷轴槽位与累加同吃下限（结构性无重叠）+ `/api/export` 意外异常落结构化 400（UI 不再误报
> fetch failed）。门禁 670/130/不变式全绿。**顺带真机实证 derived_stale 首触重刷路径（109s）**。
> **r22 已出**（干净 commit `36dec63`，三道包内验收全绿，zip backend.exe sha16 `f0d00f10c4123813`）；
> ✅ mac 包已更新（用户 dispatch run 38262048171 三 job 全绿，mac zip 覆盖为 916,823,896B）；Windows zip 不挂 GitHub；release/ 四档 r22/r21/r20/r19，删 r19 等口令。
> 明细 = STATE Current Task 顶部「补十五」块。
