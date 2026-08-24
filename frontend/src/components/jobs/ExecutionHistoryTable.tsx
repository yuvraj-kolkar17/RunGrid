import React from 'react';
import type { JobExecution } from '../../types/api';
import { StatusBadge } from '../common/StatusBadge';
import { formatDate, formatDuration, truncateUuid } from '../../utils/formatters';

interface ExecutionHistoryTableProps {
  executions?: JobExecution[];
}

export const ExecutionHistoryTable: React.FC<ExecutionHistoryTableProps> = ({ executions }) => {
  if (!executions || executions.length === 0) {
    return (
      <div className="rounded-xl bg-slate-950 p-6 text-center text-xs text-slate-500 border border-slate-800">
        No execution attempts recorded yet.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl bg-slate-950 border border-slate-800">
      <table className="w-full text-left text-xs text-slate-300">
        <thead className="bg-slate-900 text-slate-400 border-b border-slate-800 font-mono uppercase">
          <tr>
            <th className="px-4 py-3">Attempt</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Worker Node</th>
            <th className="px-4 py-3">Started At</th>
            <th className="px-4 py-3">Finished At</th>
            <th className="px-4 py-3">Duration</th>
            <th className="px-4 py-3">Error / Reason</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/50 font-mono">
          {executions.map((exec) => (
            <tr key={exec.id} className="hover:bg-slate-900/40">
              <td className="px-4 py-3 font-bold text-white">Attempt #{exec.attempt}</td>
              <td className="px-4 py-3">
                <StatusBadge status={exec.status} size="sm" />
              </td>
              <td className="px-4 py-3 text-slate-400">
                {exec.worker_id ? truncateUuid(exec.worker_id, 10) : '—'}
              </td>
              <td className="px-4 py-3 text-slate-400">{formatDate(exec.started_at)}</td>
              <td className="px-4 py-3 text-slate-400">{formatDate(exec.finished_at)}</td>
              <td className="px-4 py-3 font-semibold text-sky-400">
                {formatDuration(exec.duration_ms)}
              </td>
              <td className="px-4 py-3 text-rose-400 max-w-xs truncate">
                {exec.error || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
