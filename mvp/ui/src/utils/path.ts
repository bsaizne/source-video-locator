// Path helpers shared by stores/pages (与后端 /api/media/info 的绝对路径口径一致)。

/** Windows 盘符 (C:\) 或 UNC (\\server) 或 Unix 绝对 (/…)；裸文件名/相对路径不满足。 */
export function isAbsolutePath(p: string): boolean {
  return /^([A-Za-z]:[\\/]|\\\\[\\/]?|\/)/.test(p)
}

/** 取文件名（含扩展名）。'D:\\a\\movie.mkv' -> 'movie.mkv' */
export function basename(p: string): string {
  return p.split(/[\\/]/).filter(Boolean).pop() ?? ''
}

/** 取项目默认名：文件名去扩展名。 */
export function nameWithoutExt(p: string): string {
  const b = basename(p)
  const dot = b.lastIndexOf('.')
  return dot > 0 ? b.slice(0, dot) : b
}
