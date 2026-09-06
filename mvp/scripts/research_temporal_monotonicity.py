import json, sys
from pathlib import Path
sys.path.insert(0, r"D:\claudework\benchmark\mvp\scripts")
from measure_shot_recall import evaluate
import io, contextlib

# 四片: (label, gt_file, results_file)
CASES = [
    ("2mkv", "ground_truth_v4.json"),
    ("test1", "ground_truth_test1.json"),
    ("test2", "ground_truth_test2.json"),
    ("test3", "ground_truth_test3.json"),
]

# 单调性: 编辑段按 edited.start 排序 -> GT original.start 序列的 Kendall tau 与逆序对
def kendall_tau(seq):
    """序列的相对排序与自然序的 Kendall tau（1=完全单调递增, -1=完全递减）。"""
    n = len(seq)
    if n < 2:
        return 1.0, 0, 0
    concordant = discordant = 0
    for i in range(n):
        for j in range(i+1, n):
            if seq[i] < seq[j]: concordant += 1
            elif seq[i] > seq[j]: discordant += 1
    total = concordant + discordant
    return (concordant - discordant) / total if total else 1.0, concordant, discordant

def gt_seq(gt):
    """GT 正例按 edited.start 排序 -> original.start 序列（编辑序映射到原片序）。"""
    pos = [(p["edited"][0], p["original"][0]) for p in gt["positives"]]
    pos.sort(key=lambda x: x[0])
    return [o for _, o in pos]

for label, gt_name in CASES:
    gt = json.loads((Path(r"D:\claudework\benchmark\datasets\real") / gt_name).read_text(encoding="utf-8"))
    seq = gt_seq(gt)
    tau, conc, disc = kendall_tau(seq)
    n_inv = disc
    # 统计相邻原片倒序对数（相邻编辑段原片序不递增的次数）
    adj_inv = sum(1 for i in range(len(seq)-1) if seq[i] > seq[i+1])
    print(f"{label}: GT编辑序->原片序 Kendall tau={tau:.3f} ({conc}对/共{conc+disc}对), 相邻倒序 {adj_inv}/{len(seq)-1} 对")
    # 若 test3 倒序明显, 打印具体倒序段
    if label == "test3":
        pos = sorted([(p["edited"][0], p["original"][0]) for p in gt["positives"]], key=lambda x: x[0])
        for i in range(len(pos)-1):
            if pos[i][1] > pos[i+1][1]:
                print(f"    倒序: ed{pos[i][0]}->og{pos[i][1]} 之后 ed{pos[i+1][0]}->og{pos[i+1][1]}")