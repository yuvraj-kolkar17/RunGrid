import React, { useEffect, useState } from 'react';
import { Modal } from '../common/Modal';
import { getQueueStats } from '../../services/queues';
import type { QueueStats } from '../../types/api';
import { LoadingSkeleton } from '../common/LoadingSkeleton';

interface QueueStatsModalProps {
  queueId: string | null;
  queueName: string;
  isOpen: boolean;
  onClose: () => void;
}

export const QueueStatsModal: React.FC<QueueStatsModalProps> = ({
  queueId,
  queueName,
  isOpen,
  onClose,
}) => {
  const [stats, setStats] = useState<QueueStats | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && queueId) {
      setIsLoading(true);
      getQueueStats(queueId)
        .then((data) => {
          setStats(data);
          setError(null);
        })
        .catch((err) => setError(err.message || 'Failed to load queue statistics.'))
        .finally(() => setIsLoading(false));
    }
  }, [isOpen, queueId]);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Statistics: ${queueName}`}>
      {isLoading ? (
        <LoadingSkeleton type="card" count={2} />
      ) : error ? (
        <div className="p-3 text-xs rounded-xl bg-rose-950/60 text-rose-300 border border-rose-800">{error}</div>
      ) : stats ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-500 block">Queued Count</span>
              <span className="text-lg font-semibold text-indigo-400">{stats.queued_count ?? 0}</span>
            </div>
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-500 block">Running Count</span>
              <span className="text-lg font-semibold text-sky-400">{stats.running_count ?? 0}</span>
            </div>
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-500 block">Claimed Count</span>
              <span className="text-lg font-semibold text-purple-400">{stats.claimed_count ?? 0}</span>
            </div>
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-500 block">Completed Count</span>
              <span className="text-lg font-semibold text-emerald-400">{stats.completed_count ?? 0}</span>
            </div>
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-500 block">Failed Count</span>
              <span className="text-lg font-semibold text-rose-400">{stats.failed_count ?? 0}</span>
            </div>
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-500 block">Dead Letter Count</span>
              <span className="text-lg font-semibold text-red-500">{stats.dead_letter_count ?? 0}</span>
            </div>
          </div>
        </div>
      ) : null}
    </Modal>
  );
};
