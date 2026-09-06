"""mvp.api.services — 桥的独立能力封装（预览抽取等）。

每个服务只封装一块能力（如视频片段抽取），不复制/实现任何算法，
也不改 ``mvp/src``。路由通过 ``AppContext`` 惰性持有具体服务实例；
测试可注入 fake（覆盖 ``get_context`` 时直接给 ``AppContext.preview_service``）。
"""
