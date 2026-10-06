# source-video-locator

桌面端（Windows / macOS）视频片段定位工具的工作区。

## 当前状态

```
2026-10-06  ch61  rel:r11(win) mac:ci-artifact(unverified)
gate  543 / 105 / 142 / 0
q     A136-139  B131  C138  D4-9
t     22 27 30 32   (min, 4 片, 同机同档)
plat  H1 H2 H3 > H4(hold:no-env)
db    GT v4+3  idx 4/4  fv 未动
```

## 目录

```
mvp/          产品实现（src 后端 / api HTTP / ui Electron+Vue / tests / scripts）
src/          早期引擎对照实验
datasets/     素材与标注
results/      历史实验结果
.agent/       工程记录
work/         运行期产物（不入库）
```

## 备注

- 提交信息里的 `chNN` 对应 `.agent/` 的章节号。
- `rel:` 行是当前发行物，其余目录下的历史包为回滚件。
- 未标 `verified` 的构建不作为可用产物对待。
