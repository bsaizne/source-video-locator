# FINDINGS — 竞品 opcode 通道试采（2026-10-07 续62 补三，挂账项⑤结案）

> **触发**：续61 入口层档 §4 诚实留白「指令序列（opcode）读不到 ⇒ 能证明『有什么』，
> 不能证明『先做哪个』」，作为唯一未拍板项挂账；用户 2026-10-07 拍板「试试」。
> **纪律不变**：全程只读（cutmatch-analysis 侧零写入），不运行竞品、不碰授权与受保护模型。
> **零 `mvp/src` 改动。** 产物：`benchmark/work/cm_opcode/`（probe v1~v3 + evidence*.json）。

## 0. 结论（三句）

1. **字面 opcode 通道 = 判死（确证）**：竞品 Nuitka+mypyc AOT 编译，解包树 0 个 `.py/.pyc`
   （FINDINGS/03 早有结论，本轮复核），不存在可反汇编的 Python 字节码。
2. **机器码→常量绑定通道 = 本轮判死（三种廉价形态全部实测不成立）**；剩余唯一理论路径是
   「全量反汇编 + 模块 init 锚定」的 RE 工程，量级见 §3，未立项。
3. **常量 blob 序通道 = 打开（带边界条件）**：blob 序 = 源码书写序（按代码区分批序列化，
   组内有效）。验证 = 进度元组内嵌 pct 与 blob 序互证；产出示例 = 竞品阶段词表/流程注册序
   （§4）。这把续61 的「不能证明先做哪个」从**完全未知**升到**弱排序证据**。

## 1. 字面通道：判死（确证）

解包树（8.4GB）`find -name "*.pyc"` = **0 个**；打包器 = Nuitka（`__nuitka_binary_dir` 等指纹，
FINDINGS/10 §1）+ mypyc 运行时 `__mypyc.pyd`。Python 源码 → C → 机器码，**字节码从未存在**。

## 2. 机器码引用通道：三形态探针（全部只读静态）

| # | 形态 | 结果 | 证据 |
|---|---|---|---|
| A | `LEA rip→常量 blob 字节` | **判死**：blob VA 域内 tgt 仅 **2/172,604**（巧合级）——代码不直接引用 blob 字节，blob 只在启动时被解码器读一次 | v1 探针 + `lea_xref.npz`（capstone 校验过的既有索引） |
| B | `MOV r64,[rip]→.data+.bss`（代码解引用常量指针数组的形态） | **引用群存在**：**3,922,992** 条指向 .data+vs 域（.bss = 7.5MB 零初始化，`vs=0x7853F0` ≫ raw `0x60200`——v2 扫错上限 811 条的教训） | v3 探针 |
| C | B + 「平铺 mod_consts 数组」假设（元素地址 = base + 8×blob 序号） | **验证 FAIL**：.bss 引用密度 3.9M/916,462 槽 ≈ 4.3 引用/槽 ⇒ 共现签名无区分度（4 槽全中的 base 在前 20 万 tgt 里就有 186,019 个假阳性）；代理话术 4 元组（blob 序号 237/263/267/269）无一 base 通过「全被引用 + cod 同簇递增」检验 | v2/v3 探针 + evidence_v2/v3.json |

**通道 C 剩余的理论路径**（未立项，量级供拍板）：用 `.pdata` 异常目录的 **163,664 个精确函数
边界**（0x27e200/12）做全量线性反汇编 → 定位每模块 init 的 `createModuleConstants` 调用序列
锚定该模块数组基址 → 再建「代码位置→常量」绑定。这是真正的 RE 工程（预计多会话），且
mypyc 编译的核心模块可能用另一套常量机制，投入产出比低——**精度侧已判「竞品没肉」，
此通道的潜在收益只在工程/UX 形态的顺序确认**，与成本不匹配，建议维持关闭。

## 3. blob 序通道：打开（验证 + 边界条件）

**原理**：Nuitka 按模块+代码区分批序列化常量，**同批内 = 源码书写序**；批边界会打乱全局序。

**验证（有内嵌真值的素材）**：`web.processing_api.single` 的进度元组 `["视频拼接", pct, 话术]`
——pct 是执行序真值。blob 序展开：

```
idx=237  32%  已开启 720p 视频加速，正在检查加速素材...
idx=258 100%  拼接阶段完成，开始处理...        ← 别的代码区（边界标记）
idx=263  35%  正在生成 720p 代理视频...
idx=267  50%  720p 代理生成完成
idx=269  50%  原视频已是 720p 或更低，无需代理
```

代理链 4 条 blob 序 = pct 执行序（32→35→50→50，含 else 分支先后）✔；乱序插入的那条恰好
是分批边界 ⇒ **用内嵌 pct/序号即可识别并切分批次**。

**产出示例（`processing.progress.tracker`，blob217 按序）**——续61 拿不到的「先做哪个」实锤：

- 阶段词表序：`['特征','候选','召回','定位']`（idx41）、`['候选','召回','定位']`（idx75）
  ⇒ 竞品匹配管线的阶段拓扑 = 特征→候选→召回→定位（注册序）。
- V2 流程注册序（idx53~75）：V2 智能匹配 → V2 完成 → 解说 offset 精排 → 补解说关键帧 →
  原片 offset 精排 → 补原片关键帧 → DTW offset 精排 → 缓存关键帧特征校正 →
  V2 镜头级匹配路径选择 → 长镜头局部召回准备 → 镜头切割/切割缓存。
  ⇒ 与 DEFAULT_PIPELINE_OPTIONS 的 `offset_refine_dtw_*` 互证，并给出**执行位置**：
  DTW 精排排在双路 offset 精排之后、路径选择之前。
- 同义阶段名族（idx33：原片特征完成/…/原片索引构建完成 8 条）= 其 ETA 表 16 阶段的
  别名映射素材；`['本地素材预检','授权复核']`（idx52）⇒ 授权复核在素材预检之后。

**使用纪律**：blob 序证据一律标「**强推断**（源码书写序）」，不得单独当执行序断言；
有内嵌 pct/序号/表序等真值时优先用真值分段。

## 4. 复跑方法

```powershell
$py = "D:\claudework\video-dedup-tool\.venv\Scripts\python.exe"
& $py D:\claudework\benchmark\work\cm_opcode_probe_20261007.py     # v1：LEA→blob 判死
& $py D:\claudework\benchmark\work\cm_opcode_probe2_20261007.py    # v2：.data raw 域（811 条）
& $py D:\claudework\benchmark\work\cm_opcode_probe3_20261007.py    # v3：+bss MOV 群 + base 投票
```

产物 `work/cm_opcode/{evidence,evidence_v2,evidence_v3}.json`；blob 数据复用
`cutmatch-analysis/data/nuitka_blob_values.json`（FINDINGS/10 §7 一键校验 50/50 PASS 的同一来源）。
