"""engine.localization.sequence_rerank — 全局时序一致性 DP 重排(Phase 21 场景身份)。

真实案例实证(ProjectXIXI test4,水上乐园片):同场景几十个相似滑道镜头,CLS 单段独立
定位产生 7 次时间倒退——每段各自挑了"长得像"的错误实例。解说回 wall 通常按电影时间轴
展开(test1/test3 实测强单调),因此**全局顺序约束**能在每段的候选窗里挑出正确实例。

算法:Viterbi 式 DP。编辑段按顺序排布;每段状态 = 候选窗(中点,归一分)或 SKIP;
转移代价 = λ × max(0, 前一中点 − 当前三点)(时间倒退罚);SKIP 固定罚(为闪回/乱序
剪辑留逃生门)。归一分 = 该候选的局部分 / 该段候选最大分(段间可比)。

纯函数、无 IO、确定性。λ/skip_penalty 走 PipelineConfig。
"""
from __future__ import annotations


def sequence_rerank(items: list[dict], *, order_lambda: float = 0.001,
                    skip_penalty: float = 0.30) -> list[dict]:
    """时序 DP 重排。

    ``items``(编辑顺序)::
        [{"index": int, "edited_mid": float,
          "cands": [{"mid": float, "score": float, "is_main": bool}]}]

    返回:每项 {"index", "chosen_mid", "chosen_score", "changed"}
    (chosen_mid=None 表示 SKIP——保留原主定位且不参与顺序链)。
    候选只有 1 个的段:无重排余地,直接保持(记 changed=False)。
    """
    usable = [it for it in items if len(it.get("cands", [])) >= 2]
    out: dict[int, dict] = {it["index"]: {"index": it["index"], "chosen_mid": None,
                                          "chosen_score": 0.0, "changed": False}
                            for it in items}

    if len(usable) < 2:
        return [out[it["index"]] for it in items]

    # 归一分(段内 max=1.0)
    for it in usable:
        mx = max(c["score"] for c in it["cands"]) or 1.0
        for c in it["cands"]:
            c["norm"] = c["score"] / mx

    # DP:状态 = (段序, 候选序 or SKIP)
    NEG = float("-inf")
    # value[i][k];states[i] = usable[i]["cands"] + [SKIP]
    states: list[list[dict | None]] = []
    values: list[list[float]] = []
    back: list[list[int]] = []

    for i, it in enumerate(usable):
        cands = it["cands"]
        row_states: list[dict | None] = list(cands) + [None]  # None = SKIP
        if i == 0:
            row_vals = [c["norm"] for c in cands] + [-skip_penalty]
            row_back = [-1] * len(row_states)
        else:
            row_vals = [NEG] * len(row_states)
            row_back = [-1] * len(row_states)
            prev_mids = [(k, (None if s is None else s["mid"])) for k, s in enumerate(states[-1])]
            for k, c in enumerate(cands):
                for pk, pm in prev_mids:
                    if pm is None:
                        prev_pos = it["edited_mid"]  # SKIP 后以前段编辑位置近似
                        base = values[-1][len(states[-1]) - 1] - skip_penalty
                    else:
                        prev_pos = pm
                        base = values[-1][pk]
                    jump = max(0.0, prev_pos - c["mid"])
                    v = base + c["norm"] - order_lambda * jump
                    if v > row_vals[k]:
                        row_vals[k] = v
                        row_back[k] = pk
            # SKIP 状态:从上一状态转移,固定罚,不约束顺序
            for pk in range(len(states[-1])):
                v = values[-1][pk] - skip_penalty
                kk = len(cands)
                if v > row_vals[kk]:
                    row_vals[kk] = v
                    row_back[kk] = pk
        states.append(row_states)
        values.append(row_vals)
        back.append(row_back)

    # 回溯
    last = len(usable) - 1
    k = max(range(len(values[last])), key=lambda x: values[last][x])
    chain = []
    for i in range(last, -1, -1):
        chain.append((i, k))
        k = back[i][k] if back[i][k] >= 0 else -1
    chain.reverse()

    for i, k in chain:
        it = usable[i]
        st = states[i][k]
        if st is None:
            out[it["index"]]["chosen_mid"] = None
            continue
        main_c = next((c for c in it["cands"] if c.get("is_main")), None)
        changed = main_c is not None and abs(main_c["mid"] - st["mid"]) > 0.5
        out[it["index"]] = {"index": it["index"], "chosen_mid": st["mid"],
                            "chosen_score": round(st.get("norm", 0.0), 3),
                            "changed": changed}
    return [out[it["index"]] for it in items]
