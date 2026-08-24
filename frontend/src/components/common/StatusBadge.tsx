import React from 'react';
import type { JobStatus } from '../../types/api';

interface StatusBadgeProps {
  status: JobStatus | string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const normalizedStatus = status.toUpperCase();

  const getStyle = (st: string) => {
    switch (st) {
      case 'COMPLETED':
      case 'SUCCESS':
      case 'HEALTHY':
      case 'ACTIVE':
      case 'READY':
        return 'bg-emerald-950/60 text-emerald-400 border-emerald-800/60';
      case 'RUNNING':
      case 'CLAIMED':
      case 'PROCESSING':
        return 'bg-sky-950/60 text-sky-400 border-sky-800/60';
      case 'QUEUED':
      case 'SCHEDULED':
        return 'bg-indigo-950/60 text-indigo-300 border-indigo-800/60';
      case 'RETRYING':
      case 'RETRY_WAITING':
      case 'PAUSED':
      case 'WARNING':
        return 'bg-amber-950/60 text-amber-400 border-amber-800/60';
      case 'FAILED':
        return 'bg-rose-950/60 text-rose-400 border-rose-800/60';
      case 'DEAD_LETTER':
      case 'ERROR':
      case 'CRITICAL':
        return 'bg-red-950/80 text-red-400 border-red-800/80 font-bold';
      case 'INACTIVE':
      case 'STALE':
      default:
        return 'bg-slate-900 text-slate-400 border-slate-800';
    }
  };

  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-mono font-medium tracking-wide uppercase ${sizeClass} ${getStyle(
        normalizedStatus
      )}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full shrink-0 ${
          ['COMPLETED', 'HEALTHY', 'ACTIVE'].includes(normalizedStatus)
            ? 'bg-emerald-400'
            : ['RUNNING', 'CLAIMED'].includes(normalizedStatus)
            ? 'bg-sky-400 animate-pulse'
            : ['RETRY_WAITING', 'PAUSED'].includes(normalizedStatus)
            ? 'bg-amber-400'
            : ['FAILED', 'DEAD_LETTER'].includes(normalizedStatus)
            ? 'bg-rose-400'
            : 'bg-slate-400'
        }`}
      />
      <span>{normalizedStatus.replace('_', ' ')}</span>
    </span>
  );
};
