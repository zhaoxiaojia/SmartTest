export const HEALTH_LABELS = {
  BLOCK: 'Blocked', WARNING: 'Attention', 'DATA INCOMPLETE': 'Data incomplete', NORMAL: 'Normal'
}

export function healthLabel(state) {
  return HEALTH_LABELS[state] ?? state ?? 'Unknown'
}

export function healthClass(state) {
  return `release-health release-health-${String(state || 'unknown').toLowerCase().replace(/\s+/g, '-')}`
}
