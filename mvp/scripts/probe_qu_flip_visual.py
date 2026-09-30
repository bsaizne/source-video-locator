# -*- coding: utf-8 -*-
"""查询单元对照: 我方生产 vs 竞品查询单元 —— 逐 GT 例判定差 + 多模态对照图. """
import json, os, re, sys
from pathlib import Path
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BENCH = Path(r"D:\claudework\benchmark")
WORK = BENCH / "work"
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
from media.ffmpeg import FFmpegIO

CASES = {"2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv", "ground_truth_v4.json"),
         "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv", "ground_truth_test1.json"),
         "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4", "ground_truth_test2.json"),
         "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4", "ground_truth_test3.json")}
LINE = re.compile(r"^\[(HIT |part|MISS)\]\s+(\S+)\s+ed\s*([\d.]+)-\s*([\d.]+)\s*->\s*og\s*([\d.]+)-\s*([\d.]+)")
WIN = re.compile(r"s\d+\((main|sub)\s+([\d.]+)-\s*([\d.]+)")

def verdicts(txt: Path):
    out = {}
    for ln in txt.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE.match(ln)
        if m:
            w = WIN.search(ln)
            out[m.group(2)] = {"v": m.group(1).strip(), "ed": (float(m.group(3)), float(m.group(4))),
                               "og": (float(m.group(5)), float(m.group(6))),
                               "win": (w.group(1), (float(w.group(2)), float(w.group(3)))) if w else None}
    return out

def strips(ff, path, span, n=4, H=170):
    a, b = span
    ts = [a + (b - a) * k / max(n - 1, 1) for k in range(n)] if b > a else [a]
    tiles = []
    for t in ts:
        img = np.asarray(ff.grab_frame(Path(path), max(0.0, t)))
        hh, ww = img.shape[:2]
        im = cv2.resize(img, (max(1, int(round(ww * H / hh))), H), interpolation=cv2.INTER_AREA)
        bar = np.full((22, im.shape[1], 3), 255, np.uint8)
        cv2.putText(bar, "%.2f" % t, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
        tiles.append(np.vstack([bar, im]))
    gap = np.full((tiles[0].shape[0], 5, 3), 255, np.uint8)
    row = tiles[0]
    for c in tiles[1:]:
        row = np.hstack([row, gap, c])
    return row

def label_row(row, text, color):
    lab = np.full((row.shape[0], 210, 3), 255, np.uint8)
    cv2.putText(lab, text, (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    return np.hstack([lab, row])

def main():
    case = sys.argv[1] if len(sys.argv) > 1 else "2mkv"
    ed, om, gt_name = CASES[case]
    vb = verdicts(WORK / ("_m_base_%s.txt" % case)) if (WORK / ("_m_base_%s.txt" % case)).exists() else verdicts(WORK / "_m_base.txt")
    vq = verdicts(WORK / ("_m_pqu_%s.txt" % case)) if (WORK / ("_m_pqu_%s.txt" % case)).exists() else verdicts(WORK / "_m_pqu.txt")
    flips = [(k, vb[k], vq[k]) for k in vb if k in vq and vb[k]["v"] == "HIT" and vq[k]["v"] != "HIT"]
    back = [(k, vb[k], vq[k]) for k in vb if k in vq and vb[k]["v"] != "HIT" and vq[k]["v"] == "HIT"]
    print("baseline HIT -> pqu 非HIT: %d 例 %s" % (len(flips), [f[0] for f in flips]))
    print("baseline 非HIT -> pqu HIT: %d 例 %s" % (len(back), [b[0] for b in back]))
    out = WORK / "qu_flip_visual"
    out.mkdir(exist_ok=True)
    ff = FFmpegIO()
    base_res = json.loads((WORK / ("rerun_%s_runtime_twopassflash.results.json" % case)).read_text(encoding="utf-8"))["results"]
    pqu_res = json.loads((WORK / ("proxy_qu_%s.results.json" % case)).read_text(encoding="utf-8"))["results"]

    def pick(res, e0, e1):
        best, bo = None, -1.0
        for r in res:
            s = float(r["edited_segment"]["start"]); t = float(r["edited_segment"]["end"])
            ov = min(t, e1) - max(s, e0)
            if ov > bo:
                best, bo = r, ov
        return best

    for k, a, b in flips + back:
        gt_ed, gt_og = a["ed"], a["og"]
        rb, rq = pick(base_res, *gt_ed), pick(pqu_res, *gt_ed)
        bspan = a["win"][1] if a.get("win") else (float(rb["original"]["candidate_start"]), float(rb["original"]["candidate_end"]))
        qspan = b["win"][1] if b.get("win") else (float(rq["original"]["candidate_start"]), float(rq["original"]["candidate_end"]))
        qed = (float(rq["edited_segment"]["start"]), float(rq["edited_segment"]["end"]))
        bed = (float(rb["edited_segment"]["start"]), float(rb["edited_segment"]["end"]))
        r0 = label_row(strips(ff, ed, bed), "ED(base seg)", (0, 0, 0))
        r1 = label_row(strips(ff, ed, qed), "ED(pqu unit)", (0, 120, 0))
        r2 = label_row(strips(ff, om, bspan), "OG(base %s) %s" % ((a["win"][0] if a.get("win") else "main-fallback"), a["v"]), (0, 0, 180))
        r3 = label_row(strips(ff, om, qspan), "OG(pqu %s) %s" % ((b["win"][0] if b.get("win") else "not_in_source"), b["v"]), (0, 120, 0))
        r4 = label_row(strips(ff, om, gt_og), "OG(GT)", (140, 0, 140))
        head = np.full((28, r1.shape[1], 3), 255, np.uint8)
        cv2.putText(head, "%s %s | GT ed %.2f-%.2f og %.2f-%.2f | base ed %.2f-%.2f loc %.2f-%.2f %s | pqu ed %.2f-%.2f loc %.2f-%.2f %s" % (
            case, k, gt_ed[0], gt_ed[1], gt_og[0], gt_og[1], bed[0], bed[1], bspan[0], bspan[1], a["v"],
            qed[0], qed[1], qspan[0], qspan[1], b["v"]) and "%s %s | GT ed %.2f-%.2f  og %.2f-%.2f | base=%s pqu=%s" % (
            case, k, gt_ed[0], gt_ed[1], gt_og[0], gt_og[1], a["v"], b["v"]),
            (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        rows = [head, r0, r1, r2, r3, r4]
        w = max(r.shape[1] for r in rows)
        def pad(row):
            if row.shape[1] == w:
                return row
            return np.hstack([row, np.full((row.shape[0], w - row.shape[1], 3), 255, np.uint8)])
        rows = [pad(r) for r in rows]
        sep = np.full((4, w, 3), 200, np.uint8)
        sheet = np.vstack([rows[0], rows[1], sep, rows[2], sep, rows[3], sep, rows[4], sep, rows[5]])
        fp = out / ("%s_%s.png" % (case, k))
        cv2.imwrite(str(fp), sheet)
        print("saved", fp)
    return 0

if __name__ == "__main__":
    sys.exit(main())