import React from 'react';

interface LoadingSkeletonProps {
  type?: 'card' | 'table' | 'chart' | 'detail' | 'kpi';
  count?: number;
}

export const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({ type = 'card', count = 3 }) => {
  if (type === 'kpi') {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            className="h-20 rounded-2xl bg-slate-900/60 border border-slate-800/60 p-4 space-y-2 animate-pulse"
          >
            <div className="h-3 w-16 bg-slate-800 rounded-md" />
            <div className="h-6 w-12 bg-slate-700 rounded-md" />
          </div>
        ))}
      </div>
    );
  }

  if (type === 'table') {
    return (
      <div className="w-full space-y-3">
        <div className="h-10 bg-slate-900/80 rounded-xl border border-slate-800/80 animate-pulse" />
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            className="h-14 bg-slate-900/40 rounded-xl border border-slate-800/40 p-4 flex items-center justify-between animate-pulse"
          >
            <div className="flex items-center gap-4 w-1/3">
              <div className="h-4 w-4 bg-slate-800 rounded-full" />
              <div className="h-4 w-28 bg-slate-800 rounded-md" />
            </div>
            <div className="h-4 w-20 bg-slate-800 rounded-md hidden sm:block" />
            <div className="h-4 w-16 bg-slate-800 rounded-md" />
          </div>
        ))}
      </div>
    );
  }

  if (type === 'chart') {
    return (
      <div className="h-72 w-full bg-slate-900/50 rounded-2xl border border-slate-800/80 p-6 space-y-4 animate-pulse flex flex-col justify-between">
        <div className="flex justify-between items-center">
          <div className="h-4 w-36 bg-slate-800 rounded-md" />
          <div className="h-4 w-20 bg-slate-800 rounded-md" />
        </div>
        <div className="flex items-end justify-between gap-2 h-44 pt-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <div
              key={i}
              className="w-full bg-slate-800/60 rounded-t-md"
              style={{ height: `${Math.floor(Math.random() * 60 + 20)}%` }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (type === 'detail') {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-20 bg-slate-900/60 rounded-2xl border border-slate-800/80 p-6 flex justify-between items-center">
          <div className="space-y-2">
            <div className="h-5 w-48 bg-slate-800 rounded-md" />
            <div className="h-4 w-24 bg-slate-800 rounded-md" />
          </div>
          <div className="h-8 w-24 bg-slate-800 rounded-xl" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 h-64 bg-slate-900/60 rounded-2xl border border-slate-800/80 p-6 space-y-4">
            <div className="h-4 w-32 bg-slate-800 rounded-md" />
            <div className="h-40 bg-slate-950 rounded-xl" />
          </div>
          <div className="h-64 bg-slate-900/60 rounded-2xl border border-slate-800/80 p-6 space-y-4">
            <div className="h-4 w-32 bg-slate-800 rounded-md" />
            <div className="h-40 bg-slate-950 rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="h-32 rounded-2xl bg-slate-900/60 border border-slate-800/80 p-5 space-y-3 animate-pulse"
        >
          <div className="h-4 w-24 bg-slate-800 rounded-md" />
          <div className="h-8 w-16 bg-slate-700 rounded-md" />
        </div>
      ))}
    </div>
  );
};
