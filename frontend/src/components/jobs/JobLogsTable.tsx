import React from 'react';
import type { JobLog } from '../../types/api';
import { formatDate } from '../../utils/formatters';

interface JobLogsTableProps {
  logs?: JobLog[];
}

export const JobLogsTable: React.FC<JobLogsTableProps> = ({ logs }) => {
  if (!logs || logs.length === 0) {
    return (
      <div className="rounded-xl bg-slate-950 p-6 text-center text-xs text-slate-500 border border-slate-800">
        No stdout/stderr logs captured for this job.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs">
      <div className="bg-slate-900 px-4 py-2 border-b border-slate-800 text-slate-400 font-bold uppercase text-[10px]">
        Execution Log Stream ({logs.length} entries)
      </div>
      <div className="p-4 space-y-1.5 max-h-60 overflow-y-auto">
        {logs.map((log) => {
          let levelColor = 'text-slate-300';
          if (log.level === 'ERROR') levelColor = 'text-rose-400 font-bold';
          if (log.level === 'WARNING') levelColor = 'text-amber-400';
          if (log.level === 'INFO') levelColor = 'text-sky-400';

          return (
            <div key={log.id} className="flex items-start gap-3 hover:bg-slate-900/50 p-1 rounded">
              <span className="text-slate-500 shrink-0">{formatDate(log.timestamp)}</span>
              <span className={`shrink-0 w-16 uppercase ${levelColor}`}>[{log.level}]</span>
              <span className="text-slate-200 break-all">{log.message}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
