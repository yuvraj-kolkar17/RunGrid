import React from 'react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  borderAccent?: string;
  trend?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  borderAccent = 'border-slate-800',
  trend,
}) => {
  return (
    <div
      className={`relative overflow-hidden rounded-xl bg-slate-900/80 p-5 border ${borderAccent} backdrop-blur-sm transition-all hover:border-slate-700 shadow-lg shadow-slate-950/50`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          {title}
        </span>
        {icon && <div className="text-slate-400 p-2 rounded-lg bg-slate-800/50">{icon}</div>}
      </div>
      <div className="mt-3 flex items-baseline justify-between">
        <span className="text-3xl font-bold tracking-tight text-white">{value}</span>
        {trend && <span className="text-xs font-medium text-emerald-400">{trend}</span>}
      </div>
      {subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}
    </div>
  );
};
