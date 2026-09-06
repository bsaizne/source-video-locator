# Video Locator — macOS (Apple Silicon) 未签名 alpha 包

**安装**:
1. 下载 zip 解压，得到 `Video Locator.app`
2. 终端执行: `xattr -cr "Video Locator.app"`（未签名，需绕过 Gatekeeper）
3. 拖入 Applications 打开

首次构建原片索引需要几分钟（MPS 加速）。

⚠️ 测试基线: macOS CI 264 项单测通过（MPS 实机）；真实影片四片基准在 Windows 验证（严格 117/139），mac 端首次实跑请从小片段开始。
