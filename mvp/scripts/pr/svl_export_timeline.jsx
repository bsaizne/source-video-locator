// SVL 时间轴导出器 — Premiere Pro ExtendScript
// 把当前活动序列的时间轴(轨道/片段/入出点/时间码)导出为 JSON,供外部自动比对。
// 用法:PR 里 文件 > 脚本 > 运行脚本文件,或由 CEP/命令行调用。
// 输出:%TEMP%/svl_pr_timeline.json(也可由调用方指定)

(function () {
    var OUT = File($.fileName).parent.fsName + "\\svl_pr_timeline.json";

    function tcSeconds(tc, fps) {
        // "00:00:05:12" (NDF) -> 秒
        var p = tc.split(":");
        if (p.length !== 4) return null;
        var frames = (+p[0]) * 3600 * fps + (+p[1]) * 60 * fps + (+p[2]) * fps + (+p[3]);
        return frames / fps;
    }

    var proj = app.project;
    if (!proj) { alert("没有打开的项目"); return; }

    var seq = proj.activeSequence;
    if (!seq) { alert("没有活动序列"); return; }

    var fpsRaw = seq.frameRateHorizontal; // 每秒帧数 x ticks 基数
    var fps = parseFloat(seq.frameRateHorizontal) / parseFloat(seq.timebase);
    if (!isFinite(fps) || fps <= 0) fps = 25;

    var data = {
        project: proj.name,
        sequence: seq.name,
        fps: fps,
        timebase: seq.timebase,
        duration_tc: seq.endTimeString,
        duration_s: tcSeconds(seq.endTimeString, fps),
        tracks: []
    };

    for (var t = 0; t < seq.videoTracks.numTracks; t++) {
        var vt = seq.videoTracks[t];
        var track = { kind: "video", index: t, name: vt.name || "", clips: [] };
        for (var c = 0; c < vt.clips.numItems; c++) {
            var clip = vt.clips[c];
            track.clips.push({
                name: clip.name,
                start_tc: clip.start.toString(),
                end_tc: clip.end.toString(),
                in_tc: clip.inPoint.toString(),
                out_tc: clip.outPoint.toString(),
                start_s: tcSeconds(clip.start.toString(), fps),
                end_s: tcSeconds(clip.end.toString(), fps),
                in_s: tcSeconds(clip.inPoint.toString(), fps),
                out_s: tcSeconds(clip.outPoint.toString(), fps),
                media_path: (clip.projectItem && clip.projectItem.getMediaPath) ?
                            clip.projectItem.getMediaPath() : ""
            });
        }
        data.tracks.push(track);
    }

    var f = new File(OUT);
    f.encoding = "UTF-8";
    f.open("w");
    f.write(JSON.stringify(data, null, 2));
    f.close();
    $.writeln("SVL timeline exported: " + OUT);
    if (app.properties && false) { /* no-op */ }
    alert("SVL: 时间轴已导出\n" + OUT);
})();
