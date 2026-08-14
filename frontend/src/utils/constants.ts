export const ROUTES = {
  OVERVIEW: '/',
  STATIONS: '/stations',
  STATION_DETAIL: '/stations/:stationId',
  REGIONS: '/regions',
  REGION_DETAIL: '/regions/:regionId',
  RANKING: '/ranking',
  PIPELINES: '/pipelines',
} as const;

export const HEALTH_STATUS_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  HEALTHY: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  WARNING: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  FAILED: { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' },
  STALE: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
  UNKNOWN: { bg: 'bg-slate-100', text: 'text-slate-700', border: 'border-slate-200' },
};

export const DEMAND_CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  HIGH: { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' },
  MEDIUM: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  LOW: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  BALANCED: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
};

export const DEFAULT_PAGE_SIZE = 50;
export const DEFAULT_TOP_N = 10;
