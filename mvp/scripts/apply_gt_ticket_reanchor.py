# -*- coding: utf-8 -*-
"""应用 18 条 GT 工单裁决（2026-09-30，用户逐帧确认 18/18 全部通过）。

依据链：probe_gt_tickets_retrieval.py（生产检索判别）→ review_gt_tickets_visual.py
（六张拼图逐张读图 18/18 与判别一致）→ 用户逐帧裁决「18 条全部确认（按建议口径改）」。

动作：
  - 16 条「GT 疑错」行：original 窗重新锚定到我方落位区间（同 GT 行多工单取并集，
    镜头级边界精修按裁决口径后续另做）；corrections 追加 relocate 条目 + note 追加依据。
  - 2 条「同源重复」行（p24 / t2r03b）：original 不动，note 追加同源重复注释。
改前快照 -> work/gt_backup_pre_ticket_20260930/（GT 文件不在 git，必须显式留痕）。
改后更新 work/gt_version_manifest.json 哈希。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/apply_gt_ticket_reanchor.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
sys.stdout.reconfigure(encoding="utf-8")

TICKETS = BENCH / "work" / "gt_tickets_retrieval.json"
BACKUP = BENCH / "work" / "gt_backup_pre_ticket_20260930"
MANIFEST = BENCH / "work" / "gt_version_manifest.json"
GT_OF_CASE = {"2mkv": "datasets/real/ground_truth_v4.json",
              "test1": "datasets/real/ground_truth_test1.json",
              "test2": "datasets/real/ground_truth_test2.json",
              "test3": "datasets/real/ground_truth_test3.json"}
BASIS = ("续32 GT 工单逐帧裁决 2026-09-30（用户确认 18/18）：ED 帧与我方落位读图匹配、"
         "与旧 GT 窗不符（六拼图 work/gt_tickets_visual/ + 生产检索 top-20 判别一致）")


def main() -> int:
    tickets = json.loads(TICKETS.read_text(encoding="utf-8"))
    BACKUP.mkdir(parents=True, exist_ok=True)

    # 按 (case, gt_row) 聚合：疑错行收集我方落位并集；同源重复行只注释
    reanchor, dup_note = {}, {}
    for tk in tickets:
        key = (tk["case"], tk["gt_row"])
        if tk["verdict"] == "GT 疑错":
            reanchor.setdefault(key, []).append(tk)
        elif tk["verdict"] == "同源重复":
            dup_note.setdefault(key, []).append(tk)
        else:
            print("!! 未预期裁决 %s: %s" % (key, tk["verdict"]))
            return 1

    changed = []
    for case in sorted({k[0] for k in list(reanchor) + list(dup_note)}):
        rel = GT_OF_CASE[case]
        path = BENCH / rel
        shutil.copy2(path, BACKUP / Path(rel).name)
        gt = json.loads(path.read_text(encoding="utf-8"))
        pos = {p["id"]: p for p in gt["positives"]}
        for (c, pid), tks in sorted(reanchor.items()):
            if c != case:
                continue
            p = pos[pid]
            old = list(p["original"])
            new = [min(t["ours"][0] for t in tks), max(t["ours"][1] for t in tks)]
            p["original"] = new
            segs = ",".join("s%d" % t["seg"] for t in sorted(tks, key=lambda x: x["seg"]))
            p["note"] = (p.get("note", "") + "；" if p.get("note") else "") + (
                "[2026-09-30 续32 工单重锚定 %s: 旧窗 %s-%s 与 ED 内容不符（读图+检索）, "
                "新窗=我方落位 %s-%s]" % (segs, old[0], old[1], new[0], new[1]))
            gt["corrections"].append({"id": pid, "action": "relocate",
                                      "from": old, "to": new,
                                      "basis": BASIS + "（工单段 %s）" % segs})
            changed.append("%s %s %s -> %s" % (case, pid, old, new))
        for (c, pid), tks in sorted(dup_note.items()):
            if c != case:
                continue
            p = pos[pid]
            segs = ",".join("s%d" % t["seg"] for t in sorted(tks, key=lambda x: x["seg"]))
            p["note"] = (p.get("note", "") + "；" if p.get("note") else "") + (
                "[2026-09-30 续32 工单注记 %s: 同源重复（ED 镜头在原片他处亦出现, 我方落位 "
                "%s-%s 与 GT 窗均为同镜头真出现, 维持原判）]" % (
                    segs, tks[0]["ours"][0], tks[0]["ours"][1]))
            changed.append("%s %s 注释(同源重复, 窗不动)" % (case, pid))
        path.write_text(json.dumps(gt, ensure_ascii=False, indent=1), encoding="utf-8")
        print("[%s] 已写 %s" % (case, path.name))

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for case in sorted({k[0] for k in list(reanchor) + list(dup_note)}):
        rel = GT_OF_CASE[case]
        manifest[Path(rel).name] = hashlib.md5(
            (BENCH / rel).read_bytes()).hexdigest()[:16]
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print("\n共 %d 处变更:" % len(changed))
    for line in changed:
        print(" ", line)
    print("快照: %s | manifest 哈希已更新" % BACKUP)
    return 0


if __name__ == "__main__":
    sys.exit(main())
