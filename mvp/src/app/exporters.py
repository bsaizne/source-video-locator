"""app.exporters — Phase 22 导出器：ResultBatch -> NLE 工程文件（纯函数，无 IO）。

三个导出通道（TODO.md P0 Phase 22 第 1 项）：
- **CMX3600 EDL**（.edl，纯文本，单视频轨，PR/达芬奇等通用）
- **FCP7 XML**（.xml，xmeml v4，PR 直接导入，信息更全：多轨/路径/时长）
- **剪映 draft_content.json**（beta：自研生成器，按社区已知 schema，锁 ``app_version``；
  真机导入验收=TODO 第 6 项，未过验收前勿承诺兼容）

clip 来源（交接单）：``Result.original``（主 span）+ ``original_segments``
（蒙太奇子 span / 场景候选）。按编辑时间排序。

时间换算约定（与 FFmpegIO/FeatureStore 一致）：管线里的秒都是「相对媒体文件首帧」
的媒体时间；导出时按「源片 timecode 原点 = 首帧 00:00:00:00」换算帧号
（MKV start_time 的首帧偏移与 NLE 打开素材的行为一致，均锚定首帧，不需要修正）。
timecode 一律 NON-DROP FRAME；NTSC 速率（23.976 等）按名义 fps（24）拆分 h/m/s。

导出策略（TODO 第 3 项）：``min_confidence`` 门槛（默认 MEDIUM=HIGH/MEDIUM 直进）；
``not_in_source`` / 段级失败（``failure_reason``）/ 零宽 original 不导；
LOW 按 ``low_policy``：``exclude``（默认，待第 5 项 Confidence 标定后定稿）或
``backup``（进独立备用轨；EDL 无轨概念，LOW 主 clip 照常出事件并在注释标注）。

场景切点吸附（TODO 第 2 项）：``snap_clips_to_scenes`` 把 clip 的**源片侧** in/out
吸附到最近原片镜头切点（``IndexBundle.scenes`` 的边界集合，±tol 秒内才吸附），
记录侧（编辑时间）不动。吸附导致 in/out 塌缩/交叉时回退对应边界。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from domain import ResultBatch
from domain.enums import ConfidenceLevel

__all__ = [
    "ExportClip", "build_export_plan", "snap_clips_to_scenes",
    "seconds_to_frames", "timecode_ndf", "render_edl", "render_fcp7_xml",
    "plan_jianying_assets", "create_jianying_draft_dir", "write_jianying_draft",
    "expand_material_spans",
    "EXPORT_FORMATS",
]

EXPORT_FORMATS = ("edl", "fcp7_xml", "jianying")
JIANYING_APP_VERSION = "5.9.0"   # beta 锁定目标版本（真机验收前不升级承诺）

# main span 与子 span 去重容差（秒）：子 span 与主 span 几乎重合时不重复导出
_DEDUPE_EPS_S = 0.5
# 吸附后最短有效 clip 宽（秒）：吸附导致源片侧塌缩则回退该边界
_MIN_SNAP_WIDTH_S = 0.05
# 子 span 记录槽从父段编辑起点开始、最长占用父段编辑时长（不与相邻结果槽重叠）
_SUB_RECORD_CAP = True


@dataclass
class ExportClip:
    """一个导出 clip（计划单元）：源片侧区间 + 记录侧（编辑时间轴）区间。

    - ``kind``：``main``（主 span，置信过门槛）/ ``low``（主 span，LOW 备用轨）/
      ``sub``（``original_segments`` 子 span / 场景候选）。
    - ``edited_start/end``：记录侧（NLE 时间轴）秒。
    - ``orig_start/end``：源片侧秒（吸附后）。
    - ``snap_in/snap_out``：该边界是否被吸附到切点（留痕）。
    """

    kind: str
    edited_start: float
    edited_end: float
    orig_start: float
    orig_end: float
    confidence: str = "LOW"
    score: float = 0.0
    from_scene_pool: bool = False
    from_event_pool: bool = False   # 方向 A 事件扩池产物(2026-09-05):仅展示候选
    seg_index: int = 0
    sub_index: int = 0
    snap_in: bool = False
    snap_out: bool = False

    @property
    def orig_width(self) -> float:
        return self.orig_end - self.orig_start

    @property
    def record_width(self) -> float:
        return self.edited_end - self.edited_start


def _level_rank(level: str) -> int:
    return {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(level, -1)


def build_export_plan(batch: ResultBatch, *, min_confidence: str = "MEDIUM",
                      low_policy: str = "exclude", include_subs: bool = True) -> list[ExportClip]:
    """按导出策略把 ``ResultBatch`` 展平为 clip 计划（按编辑时间升序）。

    - 不导：``not_in_source`` / ``failure_reason``（unresolved）/ original 零宽 /
      置信低于门槛。
    - LOW 主 span：``low_policy="backup"`` -> kind="low"；``"exclude"``（默认）-> 跳过。
    - 子 span（``original_segments``，含场景候选）：kind="sub"；与主 span 近重合
      （±``_DEDUPE_EPS_S``）去重；记录槽 = 父段编辑起点起、宽 ≤ 父段编辑时长。
    """
    if min_confidence not in ("LOW", "MEDIUM", "HIGH"):
        raise ValueError(f"invalid min_confidence: {min_confidence!r}")
    if low_policy not in ("exclude", "backup"):
        raise ValueError(f"invalid low_policy: {low_policy!r}")
    min_rank = _level_rank(min_confidence)

    clips: list[ExportClip] = []
    results = sorted(batch.results, key=lambda r: (r.edited.start, r.edited.end))
    for seg_index, r in enumerate(results):
        if r.not_in_source or r.failure_reason or r.excluded:
            continue   # excluded=用户手动排除(反馈四轮 r16:内容不匹配的段不进剪辑软件)
        if r.original.end - r.original.start <= 0 or r.edited.end - r.edited.start <= 0:
            continue
        level = r.confidence.level.value if r.confidence else "LOW"
        score = r.confidence.score if r.confidence else 0.0
        kind = "main"
        if _level_rank(level) < min_rank:
            # 门槛之下的主 span：LOW + backup 策略进备用轨，其余（含 MEDIUM 之下）不导
            if level == "LOW" and low_policy == "backup":
                kind = "low"
            else:
                continue
        clips.append(ExportClip(kind=kind, edited_start=r.edited.start,
                                edited_end=r.edited.end,
                                orig_start=r.original.start, orig_end=r.original.end,
                                confidence=level, score=score, seg_index=seg_index))
        if kind != "main" or not include_subs:
            # 反馈二轮：候选子 span 不进剪辑软件——只在结果页复核/替换。
            # include_subs=False 时三种 NLE 格式都只出主定位。
            continue
        main = (r.original.start, r.original.end)
        sub_index = 0
        for s in r.original_segments:
            if s.end - s.start <= 0:
                continue
            if abs(s.start - main[0]) < _DEDUPE_EPS_S and abs(s.end - main[1]) < _DEDUPE_EPS_S:
                continue   # 与主 span 近重合，主 clip 已覆盖
            slot_w = r.edited.end - r.edited.start
            rec_w = min(s.end - s.start, slot_w) if _SUB_RECORD_CAP else s.end - s.start
            clips.append(ExportClip(
                kind="sub", edited_start=r.edited.start,
                edited_end=r.edited.start + rec_w,
                orig_start=s.start, orig_end=s.end,
                confidence=level, score=s.score or 0.0,
                from_scene_pool=bool(getattr(s, "from_scene_pool", False)),
                from_event_pool=bool(getattr(s, "from_event_pool", False)),
                seg_index=seg_index, sub_index=sub_index))
            sub_index += 1
    return clips


def _scene_boundaries(scenes) -> "object":
    """scenes [S,2] -> 排序去重的切点集合（scene 起止边界并集）。"""
    import numpy as np
    if scenes is None or getattr(scenes, "size", 0) == 0:
        return None
    return np.unique(np.concatenate([np.asarray(scenes[:, 0], dtype=float),
                                     np.asarray(scenes[:, 1], dtype=float)]))


def _nearest_boundary(boundaries, t: float, tol_s: float):
    """最近的切点；超过 ``tol_s`` 返回 None。"""
    import numpy as np
    i = int(np.searchsorted(boundaries, t))
    best, best_d = None, None
    for j in (i - 1, i):
        if 0 <= j < len(boundaries):
            d = abs(float(boundaries[j]) - t)
            if best_d is None or d < best_d:
                best, best_d = float(boundaries[j]), d
    if best is not None and best_d <= tol_s:
        return best
    return None


def snap_clips_to_scenes(clips: list[ExportClip], scenes, *, tol_s: float = 1.0,
                         orig_duration: float | None = None) -> int:
    """把 clip 源片侧 in/out 吸附到最近原片镜头切点（±``tol_s`` 内才吸附）。

    只动 ``orig_start/orig_end``（记录侧编辑时间不动）。吸附后 ``out <= in +``
    ``_MIN_SNAP_WIDTH_S`` 时回退导致塌缩的那一侧（两侧都坏则整体回退）；
    回退/夹紧后仍塌缩则该 clip 整体不吸附。返回发生吸附的 clip 数。
    """
    boundaries = _scene_boundaries(scenes)
    if boundaries is None:
        return 0
    n_snapped = 0
    for c in clips:
        in0, out0 = c.orig_start, c.orig_end
        b_in = _nearest_boundary(boundaries, in0, tol_s)
        b_out = _nearest_boundary(boundaries, out0, tol_s)
        new_in = b_in if b_in is not None else in0
        new_out = b_out if b_out is not None else out0
        if orig_duration is not None and orig_duration > 0:
            new_in = min(max(new_in, 0.0), orig_duration)
            new_out = min(max(new_out, 0.0), orig_duration)
        if new_out <= new_in + _MIN_SNAP_WIDTH_S:
            # 吸附/夹紧导致塌缩：优先回退 out，再回退 in，仍坏则整体回退
            if out0 > new_in + _MIN_SNAP_WIDTH_S:
                new_out, b_out = out0, None
            elif new_out > in0 + _MIN_SNAP_WIDTH_S:
                new_in, b_in = in0, None
            else:
                new_in, new_out, b_in, b_out = in0, out0, None, None
        changed = False
        if b_in is not None and abs(new_in - in0) > 1e-9:
            c.snap_in = True
            changed = True
        if b_out is not None and abs(new_out - out0) > 1e-9:
            c.snap_out = True
            changed = True
        c.orig_start, c.orig_end = round(new_in, 3), round(new_out, 3)
        if changed:
            n_snapped += 1
    return n_snapped


# --------------------------------------------------------------------- #
# 时间换算
# --------------------------------------------------------------------- #
def seconds_to_frames(t: float, fps: float) -> int:
    """秒 -> 帧号（round；负值夹 0）。"""
    if fps <= 0:
        fps = 25.0
    return max(0, int(round(t * fps)))


def timecode_ndf(t: float, fps: float) -> str:
    """秒 -> NDF timecode ``HH:MM:SS:FF``（NTSC 速率按名义 fps 拆分）。"""
    if fps <= 0:
        fps = 25.0
    nominal = max(1, int(round(fps)))
    frames = seconds_to_frames(t, fps)
    ff = frames % nominal
    total_s = frames // nominal
    s = total_s % 60
    m = (total_s // 60) % 60
    h = total_s // 3600
    return f"{h:02d}:{m:02d}:{s:02d}:{ff:02d}"


def _fps_fields(fps: float) -> tuple[int, bool]:
    """(timebase, ntsc)：23.976->(24,TRUE)、25->(25,FALSE)、29.97->(30,TRUE)。"""
    if fps <= 0:
        return 25, False
    tb = max(1, int(round(fps)))
    ntsc = abs(fps - tb) > 0.01
    return tb, ntsc


# --------------------------------------------------------------------- #
# CMX3600 EDL
# --------------------------------------------------------------------- #
def _edl_reel(name: str | None) -> str:
    """源片名 -> 8 字符大写 reel 名（CMX3600 字段宽度）。"""
    stem = Path(name or "AX").stem
    stem = re.sub(r"[^A-Za-z0-9]", "", stem).upper() or "AX"
    return stem[:8].ljust(8)[:8]


def _edl_title(name: str | None) -> str:
    text = Path(name or "LOCATED").stem
    return re.sub(r"[^A-Za-z0-9 _.-]", "_", text)[:70] or "LOCATED"


def render_edl(plan: list[ExportClip], *, title: str, source_name: str,
               source_fps: float, record_fps: float) -> str:
    """CMX3600 EDL 文本。记录侧 = 编辑段区间；事件按记录时间升序。

    EDL 是单视频轨格式：只放 main/low 主 clip（子 span 多对一会话槽重叠，
    进 EDL 会互相覆盖；多轨候选用 FCP7 XML / 剪映通道）。LOW 备用 clip 在
    EDL 里只是普通事件，注释标 ``conf=LOW``。
    """
    mains = [c for c in plan if c.kind in ("main", "low")]
    mains.sort(key=lambda c: (c.edited_start, c.edited_end))
    lines = [f"TITLE: {_edl_title(title)}", "FCM: NON-DROP FRAME", ""]
    reel = _edl_reel(source_name)
    clip_name = Path(source_name or "source").name
    for i, c in enumerate(mains, start=1):
        src_in = timecode_ndf(c.orig_start, source_fps)
        src_out = timecode_ndf(c.orig_end, source_fps)
        rec_in = timecode_ndf(c.edited_start, record_fps)
        rec_out = timecode_ndf(c.edited_end, record_fps)
        lines.append(f"{i:03d}  {reel} V     C        "
                     f"{src_in} {src_out} {rec_in} {rec_out}")
        lines.append(f"* FROM CLIP NAME: {clip_name}")
        snap = []
        if c.snap_in:
            snap.append("in")
        if c.snap_out:
            snap.append("out")
        snap_txt = ",".join(snap) if snap else "none"
        lines.append(f"* LOCATOR: seg={c.seg_index + 1} conf={c.confidence} "
                     f"score={c.score:.2f} orig={c.orig_start:.2f}-{c.orig_end:.2f} "
                     f"snap={snap_txt}")
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------- #
# FCP7 XML (xmeml v4)
# --------------------------------------------------------------------- #
def _pathurl(p: str | Path) -> str:
    posix = Path(p).resolve().as_posix()
    if re.match(r"^[A-Za-z]:", posix):
        return "file://localhost/" + quote(posix, safe="/:.")     # D:/... -> file://localhost/D:/...
    return "file://localhost" + quote(posix, safe="/:.")          # /home/... -> file://localhost/home/...


def _rate_xml(fps: float, indent: str) -> str:
    tb, ntsc = _fps_fields(fps)
    return (f"{indent}<rate>\n{indent}  <timebase>{tb}</timebase>\n"
            f"{indent}  <ntsc>{'TRUE' if ntsc else 'FALSE'}</ntsc>\n{indent}</rate>")


def render_fcp7_xml(plan: list[ExportClip], *, seq_name: str, source_path: str | Path,
                    source_fps: float, source_duration: float | None,
                    record_fps: float,
                    source_size: tuple[int, int] | None = None) -> str:
    """FCP7 XML（xmeml v4）文本。轨道布局：V1=main、V2=low 备用、V3+=子 span
    （第 k 个子 span 共用一条轨；记录槽被父段编辑时长封顶，跨结果不重叠）。
    """
    src_name = Path(source_path).name
    file_id = "masterclip-1"
    tb_s, ntsc_s = _fps_fields(source_fps)
    tb_r, ntsc_r = _fps_fields(record_fps)

    # 记录侧帧位（序列 rate）；源侧帧位（素材 rate）
    def item(c: ExportClip, cid: str, start_f: int, end_f: int, name: str) -> str:
        in_f = seconds_to_frames(c.orig_start, source_fps)
        out_f = max(in_f + 1, seconds_to_frames(c.orig_end, source_fps))
        notes = [f"locator seg={c.seg_index + 1} conf={c.confidence} "
                 f"score={c.score:.2f} kind={c.kind}"]
        if c.from_scene_pool:
            notes.append("scene-pool candidate")
        if c.from_event_pool:
            notes.append("event-pool candidate")
        if c.snap_in or c.snap_out:
            notes.append("snapped: " + ("in" if c.snap_in else "")
                         + ("," if c.snap_in and c.snap_out else "")
                         + ("out" if c.snap_out else ""))
        # 每个 clipitem 携带完整 <file> 定义（与 Premiere 自身导出一致，按 id 去重）
        return f"""      <clipitem id="{cid}">
        <masterclipid>{file_id}</masterclipid>
        <name>{_x(name)}</name>
        <enabled>TRUE</enabled>
        <duration>{out_f - in_f}</duration>
{_rate_xml(source_fps, "        ")}
        <start>{start_f}</start>
        <end>{end_f}</end>
        <in>{in_f}</in>
        <out>{out_f}</out>
        <file id="{file_id}">
          <name>{_x(src_name)}</name>
          <pathurl>{_pathurl(source_path)}</pathurl>
{_rate_xml(source_fps, "          ")}
          <timecode>
{_rate_xml(source_fps, "            ")}
            <string>00:00:00:00</string>
            <frame>0</frame>
            <displayformat>NDF</displayformat>
          </timecode>
          <media>
            <video>
              <samplecharacteristics>
                <rate>
                  <timebase>{tb_s}</timebase>
                  <ntsc>{'TRUE' if ntsc_s else 'FALSE'}</ntsc>
                </rate>
                {'<width>%d</width><height>%d</height>' % source_size if source_size else ''}
              </samplecharacteristics>
            </video>
          </media>
        </file>
        <comments>{_x(" | ".join(notes))}</comments>
      </clipitem>"""

    mains = [c for c in plan if c.kind == "main"]
    lows = [c for c in plan if c.kind == "low"]
    subs = [c for c in plan if c.kind == "sub"]
    subs.sort(key=lambda c: (c.seg_index, c.sub_index))

    def track(clips: list[ExportClip], cid_prefix: str, name_prefix: str) -> list[str]:
        out = []
        for k, c in enumerate(clips):
            start_f = seconds_to_frames(c.edited_start, record_fps)
            end_f = max(start_f + 1, seconds_to_frames(c.edited_end, record_fps))
            out.append(item(c, f"{cid_prefix}-{k + 1}", start_f, end_f,
                            f"{name_prefix} {k + 1:03d}"))
        return out

    # 子 span 记录槽：起点=父段编辑起点，宽度封顶父段编辑时长（秒->帧换算后）
    sub_tracks: list[list[str]] = []
    by_pos: dict[int, list[ExportClip]] = {}
    for c in subs:
        by_pos.setdefault(c.sub_index, []).append(c)
    for pos in sorted(by_pos):
        items = []
        for k, c in enumerate(sorted(by_pos[pos], key=lambda x: x.edited_start)):
            start_f = seconds_to_frames(c.edited_start, record_fps)
            slot_f = max(1, seconds_to_frames(c.record_width, record_fps))
            end_f = min(start_f + max(1, seconds_to_frames(c.orig_width, record_fps)),
                        start_f + slot_f)
            items.append(item(c, f"sub{pos}-{k + 1}", start_f, end_f,
                              f"seg{c.seg_index + 1} sub{pos + 1}"))
        sub_tracks.append(items)

    all_clips = mains + lows + subs
    seq_dur = max((seconds_to_frames(c.edited_end, record_fps) for c in all_clips),
                  default=0)
    src_w_h = ""
    if source_size:
        src_w_h = f"<width>{source_size[0]}</width><height>{source_size[1]}</height>"

    parts = [f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4">
 <project>
  <name>{_x(seq_name)}</name>
  <children>
   <sequence id="sequence-1">
    <name>{_x(seq_name)}</name>
    <duration>{seq_dur}</duration>
{_rate_xml(record_fps, "    ")}
    <media>
     <video>
      <format>
       <samplecharacteristics>
        <rate>
         <timebase>{tb_r}</timebase>
         <ntsc>{'TRUE' if ntsc_r else 'FALSE'}</ntsc>
        </rate>
        {src_w_h}
       </samplecharacteristics>
      </format>"""]

    def emit_track(label: str, items: list[str]) -> None:
        if not items:
            return
        parts.append(f"""     <track>
      <!-- {label} -->
{chr(10).join(items)}
     </track>""")

    emit_track("V1 located mains", track(mains, "main", "main"))
    emit_track("V2 LOW backup", track(lows, "low", "low"))
    for pos, items in enumerate(sub_tracks):
        emit_track(f"V{pos + 3} sub-candidates (slot {pos + 1})", items)
    if not any([mains, lows, subs]):
        parts.append("     <track/>")
    parts.append(f"""     </video>
    </media>
   </sequence>
  </children>
 </project>
</xmeml>
""")
    return "\n".join(parts)


def _x(text: str) -> str:
    """XML 文本转义（含控制字符清理）。"""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


# --------------------------------------------------------------------- #
# 剪映 draft（v2：pyJianYingDraft + 预转码 H.264 MP4 素材）
# --------------------------------------------------------------------- #
def _us(t: float) -> int:
    """秒 -> 微秒（剪映时间单位）。"""
    return int(round(t * 1_000_000))


@dataclass
class JianyingAsset:
    """一个抽取的素材 clip 及其在时间轴上的摆位（反馈实测 v1 修复：素材必须
    预转码 H.264 MP4——剪映播放器对 MKV/HEVC 直链报「媒体格式不支持」）。"""

    file_stem: str
    orig_start: float
    orig_end: float
    placements: list[dict] = field(default_factory=list)
    clip_path: Path | None = None      # 抽取后由 service 填
    clip_duration: float = 0.0         # 实测 clip 时长（抽取后由 service 填）

    @property
    def orig_width(self) -> float:
        return self.orig_end - self.orig_start


def expand_material_spans(plan: list[ExportClip], scenes, *,
                          max_span_s: float = 60.0) -> int:
    """导出取材扩展 v5（反馈四轮：相似度游走会跨镜头→溯源错乱）。

    用索引镜头表（``scenes.npy``，原片真实切点）把每个主定位核心窗口扩成
    **它所覆盖的完整原片镜头**（被覆盖场景的并集）——切片=完整镜头，天然不跨
    镜头、可精确溯源。并集宽度 > ``max_span_s`` 的长场景不扩（保守回退核心窗）。
    无镜头表（旧索引）不扩。只影响导出素材宽度，不改 Result 定位语义。
    返回被扩宽的 clip 数。
    """
    if scenes is None or getattr(scenes, "shape", (0, 0))[0] == 0:
        return 0
    changed = 0
    for c in plan:
        if c.orig_end - c.orig_start <= 0:
            continue
        covered = scenes[(scenes[:, 0] < c.orig_end) & (scenes[:, 1] > c.orig_start)]
        if covered.size == 0:
            continue
        new_s, new_e = round(float(covered[:, 0].min()), 2), round(float(covered[:, 1].max()), 2)
        if (new_e - new_s) > max_span_s:
            continue   # 长场景（如大段对话）不扩，保守回退核心窗口
        if (new_e - new_s) > (c.orig_end - c.orig_start) + 1e-6:
            c.orig_start, c.orig_end = new_s, new_e
            changed += 1
    return changed


def plan_jianying_assets(plan: list[ExportClip]) -> list[JianyingAsset]:
    """纯函数：候选轨取消（用户反馈二轮）——只取 main/low 主定位，按剪辑顺序
    合并重叠源区间、去重，**全部 1.0 原速**首尾相接排成一条素材卷轴。

    v2 的「记录槽对齐编辑时间轴」设计被用户否决（原片 6s 塞进剪辑 2s 槽
    导致全部片段变速）；用户要的是可自行重编的原速镜头序列。候选子 span
    （original_segments）只在结果页复核，不进剪辑软件。
    """
    clips = sorted((c for c in plan if c.kind in ("main", "low")),
                   key=lambda x: (x.edited_start, x.edited_end))
    assets: list[JianyingAsset] = []
    cur: JianyingAsset | None = None
    for c in clips:
        if cur is not None and c.orig_start <= cur.orig_end + 1e-6:
            # 源区间重叠 → 并入当前素材（扩到并集），不产生重复片段
            cur.orig_end = max(cur.orig_end, c.orig_end)
            continue
        # 素材名带原片时间区间（反馈四轮：时间线上直接可溯源）
        cur = JianyingAsset(file_stem=f"og{int(round(c.orig_start))}-{int(round(c.orig_end))}",
                            orig_start=c.orig_start, orig_end=c.orig_end)
        assets.append(cur)
    # 顺序卷轴：原速、首尾相接
    t = 0.0
    for a in assets:
        w = a.orig_end - a.orig_start
        a.placements.append({"edited_start": round(t, 3), "edited_end": round(t + w, 3),
                             "speed": 1.0, "kind": "main", "seg_index": 0, "sub_index": 0})
        t += w
    return assets


def create_jianying_draft_dir(draft_root: str | Path, draft_name: str, *,
                              fps: float, width: int, height: int,
                              allow_replace: bool = True) -> Path:
    """用 pyJianYingDraft 建草稿文件夹（含已知可导入的 draft_meta_info 模板）。

    注意 allow_replace=True 会清空同名文件夹——先建目录再抽 clip。
    """
    import pyJianYingDraft as dj
    folder = dj.DraftFolder(str(Path(draft_root).resolve()))
    script = folder.create_draft(draft_name, int(width), int(height),
                                 max(24, int(round(fps or 30))),
                                 allow_replace=allow_replace)
    return Path(draft_root).resolve() / draft_name, script


def write_jianying_draft(script, assets: list[JianyingAsset], draft_dir: Path) -> Path:
    """把素材摆位写进已创建的草稿（script 由 create_jianying_draft_dir 返回）。

    轨道布局与 FCP7 XML 一致：主轨 located / low backup / candidates k。
    speed 语义：target(编辑时长) × speed = source(素材时长)——快剪压缩比>1 的真实节奏。
    speed 取 (实测素材时长×0.999)/记录时长，避免重编码时长差 1 帧导致越界。
    """
    import pyJianYingDraft as dj

    track_refs: dict[str, object] = {}

    def track_for(kind: str, sub_index: int):
        name = ("located" if kind == "main"
                else "low backup" if kind == "low"
                else f"candidates {sub_index + 1}")
        if name not in track_refs:
            track_refs[name] = script.append_track(dj.TrackSpec(dj.TrackType.video, name))
        return track_refs[name]

    for asset in assets:
        if asset.clip_path is None or not asset.clip_path.exists():
            continue
        mat = dj.VideoMaterial(str(asset.clip_path))
        mat_dur = asset.clip_duration or (mat.duration / 1_000_000)
        for p in sorted(asset.placements, key=lambda x: x["edited_start"]):
            rec_w = max(0.1, p["edited_end"] - p["edited_start"])
            speed = max(0.05, (max(0.1, min(mat_dur, asset.orig_width)) - 1e-3) / rec_w)
            if abs(speed - 1.0) <= 0.02:
                speed = 1.0   # 重编码时长误差 ≤2% 时锁原速（用户反馈：不要变速片段）
            # trange 的 float 参数按微秒解释——必须传 _us() 微秒整数
            seg = dj.VideoSegment(mat, target_timerange=dj.trange(_us(p["edited_start"]), _us(rec_w)),
                                  speed=round(speed, 6))
            script.add_segment(seg, track=track_for(p["kind"], p["sub_index"]))
    script.save()
    return draft_dir
