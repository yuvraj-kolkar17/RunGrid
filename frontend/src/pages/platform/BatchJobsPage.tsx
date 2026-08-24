import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Layers3, Plus, RefreshCw, CheckCircle2, 
  AlertTriangle, Clock, ArrowRight, X 
} from 'lucide-react';
import { platformService } from '../../services/platform';
import { submitBatchJobs } from '../../services/jobs';
import { getQueues } from '../../services/queues';
import type { BatchSubmissionItem, BatchSubmissionList, Queue } from '../../types/api';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';

export const BatchJobsPage: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<BatchSubmissionList | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [queues, setQueues] = useState<Queue[]>([]);
  const [selectedQueueId, setSelectedQueueId] = useState('');
  const [taskType, setTaskType] = useState('email.send');
  const [batchSize, setBatchSize] = useState(5);
  const [submitting, setSubmitting] = useState(false);

  const fetchBatches = async () => {
    try {
      setRefreshing(true);
      const res = await platformService.getBatches();
      setData(res);
    } catch (err) {
      console.error('Failed to load batch submissions:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchBatches();
    getQueues().then((qs: Queue[]) => {
      setQueues(qs);
      if (qs.length > 0) setSelectedQueueId(qs[0].id);
    }).catch(console.error);
  }, []);

  const handleCreateBatch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedQueueId) return;

    try {
      setSubmitting(true);
      const jobs = Array.from({ length: batchSize }).map((_, idx) => ({
        task_type: taskType,
        queue_id: selectedQueueId,
        payload: { batch_index: idx + 1, timestamp: new Date().toISOString() },
        priority: 5,
      }));

      await submitBatchJobs(jobs);
      setIsModalOpen(false);
      fetchBatches();
    } catch (err) {
      console.error('Batch creation failed:', err);
      alert('Failed to submit batch. Verify request payload and queue validity.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <LoadingSkeleton type="table" />;
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3.5 w-3.5" /> Completed
          </span>
        );
      case 'PARTIAL_FAILURE':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertTriangle className="h-3.5 w-3.5" /> Partial Failure
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertTriangle className="h-3.5 w-3.5" /> Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20">
            <Clock className="h-3.5 w-3.5" /> Processing
          </span>
        );
    }
  };

  return (
    <div className="space-y-8 pb-10">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-slate-900/90 border border-slate-800 p-6 rounded-3xl shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold uppercase bg-sky-500/10 text-sky-400 border border-sky-500/20">
              Atomic Batch Operations
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <Layers3 className="h-7 w-7 text-sky-400" /> Batch Job Submissions
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Manage atomic batch job creation and inspect batch execution histories across queues.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-sky-600 hover:bg-sky-500 text-white rounded-2xl text-xs font-semibold shadow-lg shadow-sky-950/40 transition-all active:scale-95"
          >
            <Plus className="h-4 w-4" /> Create Batch Submission
          </button>
          <button
            onClick={fetchBatches}
            disabled={refreshing}
            className="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-2xl border border-slate-700 transition-all"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin text-sky-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 shadow-lg">
          <div className="text-xs text-slate-400 font-semibold uppercase">Total Batches</div>
          <div className="text-2xl font-bold font-mono text-white mt-1">{data?.summary?.total_batches ?? 0}</div>
        </div>
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 shadow-lg">
          <div className="text-xs text-slate-400 font-semibold uppercase">Total Batch Jobs</div>
          <div className="text-2xl font-bold font-mono text-slate-200 mt-1">{data?.summary?.total_batch_jobs ?? 0}</div>
        </div>
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 shadow-lg">
          <div className="text-xs text-emerald-400 font-semibold uppercase">Successful Batches</div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">{data?.summary?.successful_batches ?? 0}</div>
        </div>
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 shadow-lg">
          <div className="text-xs text-rose-400 font-semibold uppercase">Failed Batches</div>
          <div className="text-2xl font-bold font-mono text-rose-400 mt-1">{data?.summary?.failed_batches ?? 0}</div>
        </div>
      </div>

      {/* Batches Table */}
      <div className="rounded-3xl bg-slate-900/90 border border-slate-800 overflow-hidden shadow-xl">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <h3 className="text-base font-bold text-white">Batch Submissions</h3>
          <span className="text-xs text-slate-400 font-mono">Showing {(data?.items || []).length} batches</span>
        </div>

        {(!data?.items || data.items.length === 0) ? (
          <div className="p-12 text-center text-slate-400">
            <Layers3 className="h-10 w-10 text-slate-600 mx-auto mb-3" />
            <p className="text-sm font-semibold">No batch submissions found</p>
            <p className="text-xs text-slate-400 mt-1">Submit a new atomic batch above to begin tracking.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/60 text-slate-400 uppercase font-semibold border-b border-slate-800">
                <tr>
                  <th className="px-6 py-3.5">Batch Name / ID</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5">Total Jobs</th>
                  <th className="px-6 py-3.5">Successful</th>
                  <th className="px-6 py-3.5">Failed</th>
                  <th className="px-6 py-3.5">Submitted At</th>
                  <th className="px-6 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {(data?.items || []).map((batch: BatchSubmissionItem) => (
                  <tr
                    key={batch.id}
                    onClick={() => navigate(`/platform/batches/${batch.id}`)}
                    className="hover:bg-slate-800/40 cursor-pointer transition-colors group"
                  >
                    <td className="px-6 py-4 font-medium text-white font-mono">
                      <div>{batch.name}</div>
                      <div className="text-[10px] text-slate-400">{batch.id}</div>
                    </td>
                    <td className="px-6 py-4">{getStatusBadge(batch.status)}</td>
                    <td className="px-6 py-4 font-mono">{batch.total_jobs}</td>
                    <td className="px-6 py-4 font-mono text-emerald-400">{batch.successful_jobs}</td>
                    <td className="px-6 py-4 font-mono text-rose-400">{batch.failed_jobs}</td>
                    <td className="px-6 py-4 font-mono text-slate-400">
                      {batch.created_at ? new Date(batch.created_at).toLocaleString() : 'N/A'}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span className="text-sky-400 group-hover:translate-x-1 transition-transform inline-flex items-center gap-1 font-semibold">
                        View Jobs <ArrowRight className="h-3 w-3" />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Atomic Batch Creation Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-md w-full shadow-2xl space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Layers3 className="h-5 w-5 text-sky-400" /> New Atomic Batch Submission
              </h3>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-white p-1">
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateBatch} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-400 font-semibold mb-1">Target Queue</label>
                <select
                  value={selectedQueueId}
                  onChange={(e) => setSelectedQueueId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:border-sky-500 focus:outline-none"
                >
                  {queues.map((q) => (
                    <option key={q.id} value={q.id}>
                      {q.name} (Priority {q.priority})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Task Type</label>
                <select
                  value={taskType}
                  onChange={(e) => setTaskType(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:border-sky-500 focus:outline-none"
                >
                  <option value="email.send">email.send</option>
                  <option value="invoice.generate">invoice.generate</option>
                  <option value="report.generate">report.generate</option>
                  <option value="image.process">image.process</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Number of Jobs in Batch</label>
                <input
                  type="number"
                  min="1"
                  max="50"
                  value={batchSize}
                  onChange={(e) => setBatchSize(parseInt(e.target.value) || 1)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white font-mono focus:border-sky-500 focus:outline-none"
                />
                <p className="text-[10px] text-slate-400 mt-1">
                  Jobs are created atomically in a single PostgreSQL transaction.
                </p>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-semibold hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-sky-600 text-white rounded-xl font-semibold hover:bg-sky-500 shadow-md active:scale-95 disabled:opacity-50"
                >
                  {submitting ? 'Submitting...' : 'Submit Atomic Batch'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
