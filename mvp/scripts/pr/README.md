# PR (Premiere Pro) 自动验证通道

> 2026-08-31 定案:NLE 自动验证通道 = **Premiere Pro CEP 面板**(PASS,119/119 匹配);
> DaVinci Resolve 21.0.4 免费版 = **死路**(外部脚本 API 为 Studio 独占,免费版禁用),仅保留作 XML 手动目检工具。

## 定位

「PR 读轨道 → 自动验收」闭环:SVL 导出计划(FCP7 XML)→ PR 面板一键导入并打开序列 →
导出时间轴 JSON → 脚本与 XML 声明逐项四元组(start/end/in/out)自动比对。

比对逻辑:`mvp/scripts/verify_pr_timeline.py`(交接固化,E2E = 119/119 匹配、最大偏差 0.0000s、退出码 0)。

## 安装(一次性)

1. 扩展目录:`%APPDATA%\Roaming\Adobe\CEP\extensions\com.svl.timelineexport\`
   (仓库副本:`mvp/scripts/pr/cep_extensions/com.svl.timelineexport/`,以仓库为源)
2. 目录结构(manifest **必须**在 `CSXS\` 子目录,放根目录不加载):
   ```
   com.svl.timelineexport/
     index.html
     host.jsx
     CSXS/manifest.xml
   ```
3. CEP 调试开关(已有):HKCU `Software\Adobe\CSXS.9`..`CSXS.13` 的 `PlayerDebugMode`=1。
4. **面板改动需关开面板或重启 PR 生效**。

## 用法

1. 重启 Premiere Pro,菜单 **窗口 > 扩展 > SVL 时间轴导出** 打开面板。
2. (可选)在面板输入框填:
   - **FCP7 XML 路径**(留空 = 默认 `mvp/benchmark/user_case/export_smoke/test1-ed.loc.xml`)
   - **输出 JSON 路径**(留空 = 默认 `work/svl_pr_timeline.json`)
3. 点按钮「① 导入 XML 并导出时间轴 JSON」→ 面板状态区返回 OK(序列/fps/轨数/片段数/时长)。
4. 运行比对脚本:
   ```bash
   python mvp/scripts/verify_pr_timeline.py \
     --xml <exported.xml> --json <pr_timeline.json> [--tol 0.02]
   ```
   退出码 0 = 全部匹配;1 = 有超差/缺失。

## 参数化说明(2026-08-31)

- `host.jsx` 的 `svlRunAll(xmlPath, outPath)` 由面板 evalScript 以字符串参数调用;
  空/undefined 回退默认路径(`SVL_XML_DEFAULT`/`SVL_OUT_DEFAULT`)。旧调用 `svlRunAll()` 兼容。
- `index.html` 的 `q()` 把路径双写反斜杠后嵌入 evalScript 字符串,避免 ExtendScript
  把 `\b`/`\t`/`\n` 等误当转义序列(已用 Node 往返测试验证,含 `\b`/`\t`/`\n` 字符的路径还原正确)。

## ExtendScript 要点(踩坑记录)

- ExtendScript = ES3:无原生 JSON(CEP 面板用自研 `jsn()` 手写序列化器,兼容任意宿主;
  早期独立脚本 `svl_export_timeline.jsx` 依赖宿主 `JSON.stringify`——若宿主无该全局对象则失败,不作主通道)。
- PR 26.0 的 `Time` 对象 `.toString()` 崩(undefined)→ 走 `.ticks` 数值通道,`fps = TICKS_PER_SEC / timebase`。
- `t2s()` 优先 `.ticks`(254016000000/s),失败回退 `.seconds`。

## 相关文件

- 面板宿主逻辑:`host.jsx`(CEP 扩展内,仓库副本在 `cep_extensions/`)
- 面板 UI:`index.html`(CEP 扩展内,仓库副本同上)
- 比对脚本:`mvp/scripts/verify_pr_timeline.py`
- 早期独立脚本(不使用 CEP,PR 菜单 文件>脚本>运行):`svl_export_timeline.jsx`(保留参考)
- 示例数据:导出计划 `mvp/benchmark/user_case/export_smoke/test1-ed.loc.xml` ↔
  PR 导出结果 `work/svl_pr_timeline.json`
