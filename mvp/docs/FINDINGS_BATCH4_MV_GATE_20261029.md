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

## PyAV 复核（2026-10-29 补，隔离安装，未污染产品 venv）

`av==19.0.2`（wheel 28MB，自带 libavcodec 63.1.102 ≈ ffmpeg 8.x）装到 `work/b3_20261028/pylibs`
（`pip install --target`，产品环境零改动）。两种置位法都试了：

| 方法 | flags2 | H.264 (test3) 20 帧带 MOTION_VECTORS |
|---|---|---|
| `av.open(options={'flags2': '+export_mvs'})` | 0x0（未生效） | 0 |
| `stream.codec_context.flags2 \|= 0x20000` | **0x20000（已生效）** | **0** |

⇒ **PyAV 这条路在本机拿不到 MV（连 H.264 也拿不到）**，是解码栈/API 层面的问题，不是 HEVC 特有。
因此：

- **"HEVC 无 MV"的结论只对 ffmpeg CLI 7.1 成立**（该 CLI 上 H.264 正控通过、HEVC 三个时刻全 0）；
- 换解码栈是否可行**仍未知且未闭合**，但已确认 PyAV 19 不行；要再试得换别的栈（成本高于本问题价值）。

## 未闭合

- 换解码栈能否导出 HEVC MV：**未知**。已排除 PyAV 19；ffmpeg CLI 7.1 不行。
  再往下试需另找带 `export_mvs` 的 build，成本高于该候选的预期收益。

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
