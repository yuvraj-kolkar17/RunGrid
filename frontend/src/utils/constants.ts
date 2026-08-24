export const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export const POLLING_INTERVALS = {
  METRICS: 3000,
  JOB_DETAIL: 3000,
  WORKERS: 5000,
  QUEUES: 5000,
};

export const STATUS_COLORS: Record<string, { bg: string; text: string; border: string; dot: string }> = {
  SCHEDULED: {
    bg: 'bg-purple-950/40',
    text: 'text-purple-400',
    border: 'border-purple-800/50',
    dot: 'bg-purple-500',
  },
  QUEUED: {
    bg: 'bg-amber-950/40',
    text: 'text-amber-400',
    border: 'border-amber-800/50',
    dot: 'bg-amber-500',
  },
  CLAIMED: {
    bg: 'bg-indigo-950/40',
    text: 'text-indigo-400',
    border: 'border-indigo-800/50',
    dot: 'bg-indigo-500',
  },
  RUNNING: {
    bg: 'bg-sky-950/40',
    text: 'text-sky-400',
    border: 'border-sky-800/50',
    dot: 'bg-sky-500 animate-pulse',
  },
  COMPLETED: {
    bg: 'bg-emerald-950/40',
    text: 'text-emerald-400',
    border: 'border-emerald-800/50',
    dot: 'bg-emerald-500',
  },
  FAILED: {
    bg: 'bg-rose-950/40',
    text: 'text-rose-400',
    border: 'border-rose-800/50',
    dot: 'bg-rose-500',
  },
  RETRY_WAITING: {
    bg: 'bg-orange-950/40',
    text: 'text-orange-400',
    border: 'border-orange-800/50',
    dot: 'bg-orange-500',
  },
  DEAD_LETTER: {
    bg: 'bg-red-950/60',
    text: 'text-red-400 font-semibold',
    border: 'border-red-800/80',
    dot: 'bg-red-600',
  },
  ACTIVE: {
    bg: 'bg-emerald-950/40',
    text: 'text-emerald-400',
    border: 'border-emerald-800/50',
    dot: 'bg-emerald-500',
  },
  INACTIVE: {
    bg: 'bg-slate-900',
    text: 'text-slate-400',
    border: 'border-slate-800',
    dot: 'bg-slate-500',
  },
};
