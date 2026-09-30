# -*- coding: utf-8 -*-
"""独立重放并确定对方 B 段(场景切分)后处理规则 —— FINDINGS/11 §1/§3 的未知 1/2 已解。

规则(本脚本确证, 6 片 x 4 阈值 = 24/24 逐帧完全一致):
  1) active = prob > threshold (NaN 视为未激活);
  2) 组 = 连续帧号 (half-open [s, e));
  3) 临时切点 = 组中点, 上取整: closed (a+b+1)//2 <=> half-open (s+e)//2;
  4) 迭代: 只要相邻切点间距 < min_gap(8) 就合并两段 (span = [min a, max b]), 直到稳定;
  5) 最终切点 = 合并后跨距的中点, 同样上取整。

⇒ FINDINGS/11 的「未知 1(中点取整)」「未知 2(min_gap 保留谁)」已定;
   未知 3(sensitivity) 在本路径上不影响切点生成(不用它也能 24/24 复现)。
输出 work/replay_postprocess.json
"""
import json, sys
import numpy as np
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PROXY = Path(r"D:\claudework\cutmatch-analysis\sandbox\out")
WORK = Path(r"D:\claudework\benchmark\work")
CLIPS = ["1.mp4", "2.mkv", "test1-ed.mp4", "test1-om.mkv", "tset2-ed.mp4", "test3-ed.mp4"]
THS = ["030", "040", "050", "060"]
MIN_GAP = 8


def groups_of(prob, th):
    act = np.where(np.nan_to_num(prob, nan=-1.0) > th)[0]
    out = []
    if len(act):
        s = q = int(act[0])
        for i in act[1:]:
            i = int(i)
            if i == q + 1:
                q = i
            else:
                out.append((s, q + 1)); s = q = i
        out.append((s, q + 1))
    return out


def merge_by_cut_gap(items, min_gap):
    while True:
        out, i, changed = [], 0, False
        while i < len(items):
            if i + 1 < len(items):
                a, b = items[i], items[i + 1]
                if ((b[0] + b[1] + 1) // 2) - ((a[0] + a[1] + 1) // 2) < min_gap:
                    out.append([a[0], b[1]]); i += 2; changed = True; continue
            out.append(items[i]); i += 1
        items = out
        if not changed:
            return items


def cuts_of(prob, th, min_gap=MIN_GAP):
    groups = groups_of(prob, th)
    items = [[s, e - 1] for s, e in groups]
    merged = merge_by_cut_gap(items, min_gap) if items else []
    return [int((a + b + 1) // 2) for a, b in merged], groups, merged


def main() -> int:
    rule = "active=prob>threshold; groups=consecutive; cut=group_midpoint_ceil;"
    rule += " iterative merge while adjacent cut gap < min_gap(8); final=span_midpoint_ceil"
    res = {"rule": rule, "verified": {}, "per_clip": {}}
    ok = tot = 0
    for clip in CLIPS:
        prob = np.load(PROXY / ("%s.probs.npy" % clip))
        n = int(len(prob))
        nanmask = np.isnan(prob)
        first_ok = int(np.argmax(~nanmask))
        last_ok = int(n - 1 - np.argmax(~nanmask[::-1]))
        per = {"n_frames": n, "covered": [first_ok, last_ok + 1],
               "inner_nan": int(np.isnan(prob[first_ok:last_ok + 1]).sum()), "thresholds": {}}
        for th in THS:
            payload = json.loads((PROXY / ("scene_split_t%s.json" % th)).read_text(encoding="utf-8"))[clip]
            theirs = [int(c["frame"]) for c in payload["cuts"]]
            got, groups, merged = cuts_of(prob, int(th) / 100.0)
            grp = [(int(a), int(b)) for a, b in json.loads((PROXY / ("groups_t%s.json" % th)).read_text(encoding="utf-8"))[clip]]
            per["thresholds"][th] = {"n_theirs": len(theirs), "n_replay": len(got),
                                     "cuts_exact": bool(got == theirs), "groups_exact": bool(groups == grp),
                                     "n_groups": len(groups), "n_merged": len(merged)}
            tot += 1
            ok += int(got == theirs)
        res["per_clip"][clip] = per
    res["verified"] = {"cuts_exact": "%d/%d" % (ok, tot), "clips": len(CLIPS), "thresholds": THS}
    (WORK / "replay_postprocess.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("cuts 逐帧完全一致: %d/%d" % (ok, tot))
    for clip, per in res["per_clip"].items():
        ex = [t for t, d in per["thresholds"].items() if d["cuts_exact"]]
        gr = [t for t, d in per["thresholds"].items() if d["groups_exact"]]
        print("  %-16s 覆盖=[%d,%d) 内部NaN=%d | cuts 一致阈值 %s | groups 一致阈值 %s" % (
            clip, per["covered"][0], per["covered"][1], per["inner_nan"], ex, gr))
    return 0


if __name__ == "__main__":
    sys.exit(main())