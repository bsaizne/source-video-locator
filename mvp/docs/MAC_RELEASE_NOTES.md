# Video Locator — macOS (Apple Silicon) alpha 包（ad-hoc 签名）

**安装**:
1. 下载 zip 解压，得到 `Video Locator.app`
2. 终端执行: `xattr -cr "Video Locator.app"`（清除下载隔离标记，必须）
3. 拖入 Applications 打开

首次构建原片索引需要几分钟（MPS 加速）。

> **为什么必须 `xattr -cr`**：本包为 **ad-hoc 签名**（无 Apple 开发者证书、未公证）。
> macOS Gatekeeper 对「从网络下载 + 未公证 + ad-hoc 签名」的应用会提示「已损坏，无法打开」——
> 这不是文件真损坏，而是 Gatekeeper 拦截。执行 `xattr -cr` 清除 quarantine 隔离标记后即可正常打开。
> （若仍提示损坏，多为 zip 解压工具未保留符号链接，请改用系统自带「归档实用工具」或 `ditto -x -k` 解压。）

⚠️ 测试基线: macOS CI 264 项单测通过（MPS 实机）；真实影片四片基准在 Windows 验证（严格 117/139），mac 端首次实跑请从小片段开始。
