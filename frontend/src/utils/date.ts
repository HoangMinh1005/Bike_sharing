export function getTodayDateString(): string {
  return new Date().toISOString().split('T')[0];
}

export function getPastDateString(daysAgo: number, baseDateStr?: string): string {
  const d = baseDateStr ? new Date(baseDateStr) : new Date();
  d.setDate(d.getDate() - daysAgo);
  return d.toISOString().split('T')[0];
}
