import React, { useEffect, useState } from 'react';
import { getQueues, pauseQueue, resumeQueue } from '../services/queues';
import type { Queue } from '../types/api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import { CreateQueueModal } from '../components/queues/CreateQueueModal';
import { QueueStatsModal } from '../components/queues/QueueStatsModal';
import { formatDate, truncateUuid } from '../utils/formatters';
import { POLLING_INTERVALS } from '../utils/constants';
import { Layers, Plus, Pause, Play, BarChart2, ShieldAlert } from 'lucide-react';

export const QueuesPage: React.FC = () => {
  const { user } = useAuth();
  const { addToast } = useToast();
  const [queues, setQueues] = useState<Queue[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);
  const [selectedStatsQueue, setSelectedStatsQueue] = useState<{ id: string; name: string } | null>(null);

  const userRole = user?.role || 'OWNER';
  const canManageQueues = ['OWNER', 'ADMIN'].includes(userRole);

  const fetchQueues = async () => {
    try {
      const data = await getQueues();
      setQueues(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load queues.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchQueues();
    const interval = setInterval(fetchQueues, POLLING_INTERVALS.QUEUES);
    return () => clearInterval(interval);
  }, []);

  const handleTogglePause = async (queue: Queue) => {
    if (!canManageQueues) {
      addToast('Role VIEWER/MEMBER does not have permission to modify queue status.', 'error');
      return;
    }
    const action = queue.is_paused ? 'resume' : 'pause';

    try {
      if (queue.is_paused) {
        await resumeQueue(queue.id);
        addToast(`Queue "${queue.name}" resumed`, 'success');
      } else {
        await pauseQueue(queue.id);
        addToast(`Queue "${queue.name}" paused`, 'warning');
      }
      fetchQueues();
    } catch (err: any) {
      addToast(err.message || `Failed to ${action} queue.`, 'error');
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">Queue Management</h1>
          <p className="mt-1 text-xs text-slate-400">
            Configure processing queues, priority levels, and worker concurrency boundaries
          </p>
        </div>

        <button
          onClick={() => {
            if (!canManageQueues) {
              addToast('Queue creation requires OWNER or ADMIN role.', 'error');
              return;
            }
            setIsCreateModalOpen(true);
          }}
          disabled={!canManageQueues}
          className="flex items-center gap-2 rounded-xl bg-sky-600 hover:bg-sky-500 disabled:opacity-40 disabled:cursor-not-allowed px-4 py-2 text-xs font-semibold text-white transition-all shadow-md shadow-sky-600/20"
          title={!canManageQueues ? 'Requires OWNER or ADMIN role' : 'Create new queue'}
        >
          <Plus className="h-4 w-4" />
          <span>New Queue</span>
        </button>
      </div>

      {!canManageQueues && (
        <div className="p-3 bg-amber-950/40 border border-amber-800/60 rounded-xl flex items-center gap-2 text-xs text-amber-300">
          <ShieldAlert className="h-4 w-4 text-amber-400 shrink-0" />
          <span>You are logged in as <strong>{userRole}</strong>. Queue mutation actions are disabled.</span>
        </div>
      )}

      {error && <ErrorAlert message={error} onRetry={fetchQueues} />}

      {isLoading ? (
        <LoadingSkeleton type="table" count={4} />
      ) : queues.length === 0 ? (
        <EmptyState
          title="No Queues Found"
          description="Create your first queue to start processing distributed jobs."
          actionLabel="New Queue"
          onAction={() => setIsCreateModalOpen(true)}
          icon={<Layers className="h-8 w-8 text-sky-400" />}
        />
      ) : (
        <div className="overflow-hidden rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950 text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 font-mono">
                <tr>
                  <th className="px-5 py-3.5">Queue Name</th>
                  <th className="px-5 py-3.5">Project ID</th>
                  <th className="px-5 py-3.5">Priority</th>
                  <th className="px-5 py-3.5">Concurrency Limit</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5">Created At</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {queues.map((q) => (
                  <tr key={q.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-5 py-3.5 font-semibold text-white flex items-center gap-2 font-mono">
                      <Layers className="h-4 w-4 text-sky-400" />
                      {q.name}
                    </td>
                    <td className="px-5 py-3.5 font-mono text-slate-400">
                      {truncateUuid(q.project_id, 8)}
                    </td>
                    <td className="px-5 py-3.5 font-mono font-semibold text-slate-200">
                      P{q.priority}
                    </td>
                    <td className="px-5 py-3.5 font-mono">
                      <span className="px-2.5 py-1 rounded-lg bg-slate-950 text-sky-400 border border-slate-800 font-semibold">
                        {q.concurrency_limit === null ? 'Unlimited' : `${q.concurrency_limit} Max Slots`}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      {q.is_paused ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-950/60 text-amber-400 border border-amber-800/60 font-semibold font-mono text-[10px] uppercase tracking-wider">
                          <Pause className="h-3 w-3" /> Paused
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 font-semibold font-mono text-[10px] uppercase tracking-wider">
                          <Play className="h-3 w-3" /> Active
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 font-mono text-slate-400">
                      {formatDate(q.created_at)}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => setSelectedStatsQueue({ id: q.id, name: q.name })}
                          className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-sky-400 transition-colors"
                          title="View Queue Statistics"
                        >
                          <BarChart2 className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleTogglePause(q)}
                          disabled={!canManageQueues}
                          className={`flex items-center gap-1 px-3 py-1 rounded-xl font-semibold text-xs transition-colors border ${
                            q.is_paused
                              ? 'bg-emerald-950/60 text-emerald-300 border-emerald-800/60 hover:bg-emerald-900'
                              : 'bg-amber-950/60 text-amber-300 border-amber-800/60 hover:bg-amber-900'
                          }`}
                        >
                          {q.is_paused ? <Play className="h-3 w-3" /> : <Pause className="h-3 w-3" />}
                          <span>{q.is_paused ? 'Resume' : 'Pause'}</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <CreateQueueModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSuccess={fetchQueues}
      />

      <QueueStatsModal
        isOpen={!!selectedStatsQueue}
        queueId={selectedStatsQueue?.id || null}
        queueName={selectedStatsQueue?.name || ''}
        onClose={() => setSelectedStatsQueue(null)}
      />
    </div>
  );
};
