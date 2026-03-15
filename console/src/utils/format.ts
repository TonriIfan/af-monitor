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

export function riskTagType(level?: string | null) {
  const map: Record<string, '' | 'success' | 'warning' | 'danger' | 'info'> = {
    low: 'success',
    moderate: 'warning',
    high: 'danger',
    critical: 'danger',
    unknown: 'info',
  }
  return map[level || 'unknown'] || 'info'
}
