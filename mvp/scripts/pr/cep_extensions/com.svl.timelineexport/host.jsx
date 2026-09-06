// SVL 时间轴导出 — PR ExtendScript 宿主(CEP 面板调用)
// ExtendScript=ES3:无 JSON;Time 对象走 .ticks/.seconds 数值通道,不依赖字符串时间码。
// svlRunAll(xmlPath, outPath) 由面板 evalScript 以字符串参数调用;参数为空则回退默认。
var SVL_XML_DEFAULT = "D:\\claudework\\benchmark\\mvp\\benchmark\\user_case\\export_smoke\\test1-ed.loc.xml";
var SVL_OUT_DEFAULT = "D:\\claudework\\benchmark\\work\\svl_pr_timeline.json";
var TICKS_PER_SEC = 254016000000;

function esc(s) {
    s = String(s);
    return s.replace(/\\/g, "\\\\").replace(/"/g, '\\"')
            .replace(/\r/g, "\\r").replace(/\n/g, "\\n").replace(/\t/g, "\\t");
}

function jsn(v) {
    var t = typeof v;
    if (v === null || t === "undefined") return "null";
    if (t === "number") return isFinite(v) ? String(v) : "null";
    if (t === "boolean") return v ? "true" : "false";
    if (t === "string") return '"' + esc(v) + '"';
    if (v instanceof Array) {
        var a = [];
        for (var i = 0; i < v.length; i++) a.push(jsn(v[i]));
        return "[" + a.join(",") + "]";
    }
    var kv = [];
    for (var k in v) if (v.hasOwnProperty(k)) kv.push('"' + esc(k) + '":' + jsn(v[k]));
    return "{" + kv.join(",") + "}";
}

// Time 对象 -> 秒(优先 ticks 数值,失败给 null)
function t2s(tObj) {
    try {
        if (tObj && typeof tObj.ticks !== "undefined" && tObj.ticks !== "") {
            return Number(tObj.ticks) / TICKS_PER_SEC;
        }
        if (tObj && typeof tObj.seconds !== "undefined") return Number(tObj.seconds);
    } catch (e) {}
    return null;
}

function svlExportActive(outPath) {
    var proj = app.project;
    if (!proj) return "ERR: 没有打开的项目";
    var seq = proj.activeSequence;
    if (!seq) return "ERR: 没有活动序列(先双击打开序列)";

    // timebase = 每帧 ticks;fps = TICKS_PER_SEC / timebase
    var tb = Number(seq.timebase);
    var fps = (tb > 0) ? (TICKS_PER_SEC / tb) : 25;
    if (!isFinite(fps) || fps <= 0) fps = 25;

    var tracks = [];
    var maxEnd = 0;
    for (var t = 0; t < seq.videoTracks.numTracks; t++) {
        var vt = seq.videoTracks[t];
        var clips = [];
        for (var c = 0; c < vt.clips.numItems; c++) {
            var clip = vt.clips[c];
            var ss = t2s(clip.start), se = t2s(clip.end);
            var si = t2s(clip.inPoint), so = t2s(clip.outPoint);
            if (se !== null && se > maxEnd) maxEnd = se;
            var mp = "";
            try { if (clip.projectItem && clip.projectItem.getMediaPath) mp = clip.projectItem.getMediaPath(); } catch (e0) {}
            clips.push({
                name: String(clip.name),
                start_s: ss, end_s: se, in_s: si, out_s: so,
                media_path: mp
            });
        }
        tracks.push({ kind: "video", index: t, name: String(vt.name || ""), clips: clips });
    }

    var dur = t2s(seq.endTime);
    if (dur === null) dur = maxEnd;

    var data = {
        project: String(proj.name), sequence: String(seq.name), fps: fps,
        timebase: tb, duration_s: dur, tracks: tracks
    };

    var f = new File(outPath);
    f.encoding = "UTF-8";
    f.open("w");
    f.write(jsn(data));
    f.close();
    var nClips = 0;
    for (var k = 0; k < tracks.length; k++) nClips += tracks[k].clips.length;
    return "OK: 已导出 " + outPath + "\n序列=" + seq.name + " fps=" + fps.toFixed(3) +
           " 视频轨=" + tracks.length + " 片段=" + nClips + " 时长=" + dur.toFixed(2) + "s";
}

function svlRunAll(xmlPath, outPath) {
    try {
        var proj = app.project;
        if (!proj) return "ERR: 没有打开的项目(先新建/打开一个项目)";

        // 参数化:空/undefined 回退默认路径
        if (!xmlPath || xmlPath.length === 0) xmlPath = SVL_XML_DEFAULT;
        if (!outPath || outPath.length === 0) outPath = SVL_OUT_DEFAULT;

        if (!(proj.activeSequence) || proj.sequences.numSequences === 0) {
            var ok = proj.importFiles([xmlPath], true, proj.rootItem, false);
            if (!ok) return "ERR: 导入 XML 失败: " + xmlPath;
        }

        if (!proj.activeSequence) {
            for (var i = 0; i < proj.sequences.numSequences; i++) {
                var s = proj.sequences[i];
                if (s && s.sequenceID) { proj.openSequence(s.sequenceID); break; }
            }
            if (!proj.activeSequence) return "ERR: 导入成功但打开序列失败";
        }
        return svlExportActive(outPath);
    } catch (e) {
        return "ERR: " + (e.message || e.toString()) + " @line " + (e.line || "?");
    }
}
