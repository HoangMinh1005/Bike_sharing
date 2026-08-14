export function safeValue<T>(value: T | null | undefined, fallback: string = '-'): T | string {
  if (value === null || value === undefined) return fallback;
  return value;
}

export function formatNumber(value: number | null | undefined, decimals: number = 0): string {
  if (value === null || value === undefined || isNaN(value)) return '-';
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatPercent(value: number | null | undefined, decimals: number = 1): string {
  if (value === null || value === undefined || isNaN(value)) return '-';
  // If rate is between 0 and 1, convert to percentage
  const percent = value <= 1.0 ? value * 100 : value;
  return `${percent.toFixed(decimals)}%`;
}

function parseToUtcDate(value: string | Date): Date {
  if (value instanceof Date) return value;
  const str = String(value).trim();
  // If string is an ISO format without timezone offset (e.g. 2026-08-14T09:00:04), append 'Z' so it is parsed as UTC
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(str)) {
    return new Date(str.replace(' ', 'T') + 'Z');
  }
  return new Date(str);
}

export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return '-';
  try {
    const d = parseToUtcDate(value);
    if (isNaN(d.getTime())) return String(value);
    return d.toISOString().split('T')[0];
  } catch {
    return String(value);
  }
}

export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return '-';
  try {
    const d = parseToUtcDate(value);
    if (isNaN(d.getTime())) return String(value);
    return d.toISOString().replace('T', ' ').substring(0, 19);
  } catch {
    return String(value);
  }
}

export function formatDurationMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined || isNaN(minutes)) return '-';
  if (minutes < 1) return '< 1m';
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  return `${hours}h ${mins}m`;
}
