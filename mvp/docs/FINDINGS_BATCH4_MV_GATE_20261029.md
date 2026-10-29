# FINDINGS — 批次4 可行性闸门：压缩域运动向量（MV）能不能用在我们的素材上（2026-10-29）

> 目的：调研 v2 批次4 的「MV 压缩域切点通道」是唯一「换信号源」的候选（机位切换 = 运动场翻转，
> 外观无关）。在投入实现前先验**本机能不能拿到 MV**，尤其是那 15 条真漏切所在的 test1。

## 结论

**HEVC 素材拿不到运动向量，H.264 可以。** 而 15 条真漏切全在 test1（HEVC 10-bit），
2.mkv / test2 同族 ⇒ **MV 通道对主素材不可用**。

| 素材 | 编码 | codecview MV 叠加 vs 原帧（同一时刻） |
|---|---|---|
| test3-om | H.264 | **maxdiff 255**（箭头确被画出）⇒ MV 可导出 |
| test1-om @2153s | HEVC 10-bit | maxdiff 12 / 变化像素 **1** ⇒ 无 MV |
| test1-om @2420s | HEVC 10-bit | maxdiff 5 / 变化像素 **0** ⇒ 无 MV |
| test1-om @3608s | HEVC 10-bit | maxdiff 4 / 变化像素 **0** ⇒ 无 MV |

## 仪器自证（避免假阴）

- 正向对照：同一命令在 test3（H.264）上 maxdiff **255** ⇒ 命令、滤镜、导出链本身没问题；
  HEVC 上的"无输出"不是命令写错造成的。
- 三个时刻取样（含快动作段），全部 0~1 个变化像素 ⇒ 不是"恰好这一帧没有运动"。
- build：`ffmpeg 7.1-essentials_build-www.gyan.dev`；`-flags2 +export_mvs` + `codecview=mv=pf+bf+bb`。

## 未闭合

- **PyAV 数值口径未验**（`pip install av` 在本机网络下超时，两次均未完成）。PyAV 若上位，
  其自带 ffmpeg 若版本不同，HEVC 的 `MOTION_VECTORS` side data 可能可用 ⇒ 但这属于换解码栈，
  不是"现役依赖能做的事"，落地要新增 ~100MB 级依赖。**未验证前不下"永远不行"的结论**，
  只下"现役工具链不行"。

## 影响与可选路径

1. **关闭该候选（推荐）**：主素材（2mkv/test1/test2 = HEVC）拿不到 MV，而 15 条真漏切全在 test1；
   只测 test3 无法回答原问题。
2. **重编代理**（不推荐）：先解码再以固定参数编成 H.264 取 MV —— MV 由**编码器自己**的重估决定，
   已不是源片压缩域信号（见 `Known Issues` 的 provenance 纪律），且 2h 素材重编成本高。
3. **换信号源但不换编码域**：批次4 其余候选（T-DEED 新腿 / 人脸跟踪接线 / OmniShotCut torch CPU 轮）
   仍在，但都不是"MV 那条"。

## 复现

```bash
FF=tools/ffmpeg.exe
# H.264 正向对照（应画出箭头）
$FF -flags2 +export_mvs -ss 336 -i "D:/ProjectXIXI/test3/test3-om.mp4" -vf codecview=mv=pf+bf+bb -frames:v 1 -update 1 -y a.png
$FF -ss 336 -i "D:/ProjectXIXI/test3/test3-om.mp4" -frames:v 1 -update 1 -y b.png
# HEVC（应与原帧几乎相同）
$FF -flags2 +export_mvs -ss 2153 -i "D:/ProjectXIXI/test1/test1-om.mkv" -vf codecview=mv=pf+bf+bb -frames:v 1 -update 1 -y c.png
```
