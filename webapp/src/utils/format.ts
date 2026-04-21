export function formatDateTime(input?: string | null) {
  if (!input) return '--'
  const date = new Date(input)
  if (Number.isNaN(date.getTime())) return input
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date)
}

export function formatTimeShort(input?: string | null) {
  if (!input) return '--'
  const date = new Date(input)
  if (Number.isNaN(date.getTime())) return input
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function riskLabel(level?: string | null) {
  const map: Record<string, string> = {
    low: '低风险',
    moderate: '中风险',
    high: '高风险',
    critical: '极高风险',
    unknown: '未知',
  }
  return map[level || 'unknown'] || level || '--'
}

export function riskTagType(level?: string | null): '' | 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, '' | 'success' | 'warning' | 'danger' | 'info'> = {
    low: 'success',
    moderate: 'warning',
    high: 'danger',
    critical: 'danger',
    unknown: 'info',
  }
  return map[level || 'unknown'] || 'info'
}

export function bytesToHex(bytes: Uint8Array | number[]): string {
  const arr = bytes instanceof Uint8Array ? Array.from(bytes) : bytes
  return arr.map((b) => (b & 0xff).toString(16).padStart(2, '0')).join(' ')
}

export function hexToBytes(hex: string): Uint8Array {
  const parts = hex.trim().split(/\s+/).filter(Boolean)
  const nums = parts.map((p) => parseInt(p, 16))
  if (nums.some((n) => Number.isNaN(n) || n < 0 || n > 255)) {
    throw new Error('不是合法的十六进制字节序列')
  }
  return new Uint8Array(nums)
}
