import React from 'react';
import { DEMAND_CATEGORY_COLORS, HEALTH_STATUS_COLORS } from '../../utils/constants';

interface StatusBadgeProps {
  status: string | null | undefined;
  type?: 'health' | 'demand' | 'generic';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, type = 'generic' }) => {
  if (!status) {
    return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">UNKNOWN</span>;
  }

  const upperStatus = status.toUpperCase();

  let colorScheme = { bg: 'bg-slate-100', text: 'text-slate-700', border: 'border-slate-200' };

  if (type === 'health' || HEALTH_STATUS_COLORS[upperStatus]) {
    colorScheme = HEALTH_STATUS_COLORS[upperStatus] || colorScheme;
  } else if (type === 'demand' || DEMAND_CATEGORY_COLORS[upperStatus]) {
    colorScheme = DEMAND_CATEGORY_COLORS[upperStatus] || colorScheme;
  } else if (upperStatus === 'SUCCESS' || upperStatus === 'HEALTHY' || upperStatus === 'LOW') {
    colorScheme = { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' };
  } else if (upperStatus === 'WARNING' || upperStatus === 'MEDIUM') {
    colorScheme = { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' };
  } else if (upperStatus === 'FAILED' || upperStatus === 'CRITICAL' || upperStatus === 'HIGH') {
    colorScheme = { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' };
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${colorScheme.bg} ${colorScheme.text} ${colorScheme.border}`}>
      {upperStatus}
    </span>
  );
};

export default StatusBadge;
