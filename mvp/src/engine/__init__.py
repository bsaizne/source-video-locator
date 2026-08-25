"""engine — Source Video Locator 定位引擎（分段/检索/聚类/重排/定位/置信）。

已实现子模块（Stage 1）：
- ``feature_store``：Original 特征索引（第 3 项）。
- ``retrieval`` / ``clustering`` / ``ranking``：候选检索 / 聚类 / n_reps 重排（第 4 项）。
- ``localization`` / ``confidence``：精定位 longest_run + montage 检测 + 工程化置信度（第 5 项）。
- ``segment``：无 GT 编辑侧查询单元切分（第 6 项，跳过 GT 定义查询单元）。
"""
