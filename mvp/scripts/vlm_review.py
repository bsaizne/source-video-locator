# -*- coding: utf-8 -*-
"""VLM 复审助手: 调用本地 vision-subagent 的方舟配置, 对图片提问 (只读配置, 不回显 key)."""
import base64, json, sys, urllib.request
from pathlib import Path

CFG = json.loads(Path(r"D:\deepseek harnees\vision-subagent\vision-mcp-config.json").read_text(encoding="utf-8"))


def ask(images, prompt, *, max_tokens=400, timeout=120):
    content = [{"type": "text", "text": prompt}]
    for p in images:
        b = Path(p).read_bytes()
        mime = "image/jpeg" if str(p).lower().endswith((".jpg", ".jpeg")) else "image/png"
        content.append({"type": "image_url", "image_url": {"url": "data:%s;base64,%s" % (mime, base64.b64encode(b).decode())}})
    body = json.dumps({"model": CFG["model"], "messages": [{"role": "user", "content": content}],
                       "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(CFG["base"] + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + CFG["apiKey"]})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    return d["choices"][0]["message"]["content"]


if __name__ == "__main__":
    out = ask([sys.argv[1]], sys.argv[2] if len(sys.argv) > 2 else "这张图里有什么？一句话。")
    print(out)
