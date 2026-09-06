// build-preload.cjs — 把 Electron preload 打包成单文件（sandbox 兼容）。
//
// Electron 的 sandboxed preload 里 `require` 是受限的：只能加载内置模块
// （electron / node 少量 polyfill），**不能 require 相对路径的自定义模块**。
// 而 preload.ts 依赖 ./backend/bridge，tsc 编译会保留相对的 require("./backend/bridge")，
// 这会让整个 preload 加载失败 -> window.desktop / window.backend 都 undefined
// （拖拽 getPathForFile 失效、renderer->backend 桥失效）。
//
// 解决方案：用 esbuild 把 preload.ts + bridge.ts 一起 bundle 成**单个自包含文件**，
// 只保留外部的 require("electron")（sandbox preload 允许）。这样 contextBridge
// 能正常 expose，拖拽路径与 backend 桥都恢复。
//
// 在 `npm run compile:electron`（tsc 输出 main.js/preload.js/backend/*）之后运行，
// 覆盖同路径的 preload.js 为 bundle 版本。main.js 不受影响（main 有完整 Node，
// 可 require 相对模块，保持 tsc 多文件输出即可）。
const path = require('node:path')
const esbuild = require('esbuild')

const root = path.resolve(__dirname, '..')
const outfile = path.join(root, 'out', 'electron', 'preload.js')

esbuild.buildSync({
  entryPoints: [path.join(root, 'electron', 'preload.ts')],
  outfile,
  bundle: true,
  format: 'cjs',
  platform: 'node',
  target: 'es2022',
  external: ['electron'],
  logLevel: 'warning',
})

console.log(`preload bundled -> ${outfile}`)
