import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Layers3, ArrowLeft, CheckCircle2, AlertTriangle, Clock, ArrowRight 
} from 'lucide-react';
import { platformService } from '../../services/platform';
import type { BatchSubmissionDetail } from '../../types/api';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';

export const BatchDetailPage: React.FC = () => {
  const { batchId } = useParams<{ batchId: string }>();
  const navigate = useNavigate();
  const [batch, setBatch] = useState<BatchSubmissionDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (batchId) {
      platformService.getBatchDetail(batchId)
        .then(setBatch)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [batchId]);

  if (loading) {
    return <LoadingSkeleton type="table" />;
  }

  if (!batch) {
    return (
      <div className="p-12 text-center text-slate-400">
        <h3 className="text-lg font-bold text-white mb-2">Batch Not Found</h3>
        <button
          onClick={() => navigate('/platform/batches')}
          className="px-4 py-2 bg-sky-600 text-white text-xs font-semibold rounded-xl"
        >
          Back to Batches
        </button>
      </div>
    );
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3.5 w-3.5" /> Completed
          </span>
        );
      case 'FAILED':
      case 'DEAD_LETTER':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertTriangle className="h-3.5 w-3.5" /> Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Clock className="h-3.5 w-3.5" /> {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-8 pb-10">
      {/* Back Button */}
      <button
        onClick={() => navigate('/platform/batches')}
        className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white transition-colors"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Batch Submissions
      </button>

      {/* Header Summary */}
      <div className="bg-slate-900/90 border border-slate-800 p-6 rounded-3xl shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold uppercase bg-sky-500/10 text-sky-400 border border-sky-500/20">
                Batch Detail
              </span>
              <span className="text-xs font-mono text-slate-400">{batch.id}</span>
            </div>
            <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-3">
              <Layers3 className="h-6 w-6 text-sky-400" /> {batch.name}
            </h1>
          </div>
          <div>{getStatusBadge(batch.status)}</div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2">
          <div>
            <div className="text-xs text-slate-400">Total Jobs</div>
            <div className="text-xl font-bold font-mono text-white mt-0.5">{batch.total_jobs}</div>
          </div>
          <div>
            <div className="text-xs text-emerald-400 font-semibold">Successful Jobs</div>
            <div className="text-xl font-bold font-mono text-emerald-400 mt-0.5">{batch.successful_jobs}</div>
          </div>
          <div>
            <div className="text-xs text-rose-400 font-semibold">Failed Jobs</div>
            <div className="text-xl font-bold font-mono text-rose-400 mt-0.5">{batch.failed_jobs}</div>
          </div>
          <div>
            <div className="text-xs text-slate-400">Submitted At</div>
            <div className="text-xs font-mono text-slate-300 mt-1">
              {batch.created_at ? new Date(batch.created_at).toLocaleString() : 'N/A'}
            </div>
          </div>
        </div>
      </div>

      {/* Associated Batch Jobs List */}
      <div className="rounded-3xl bg-slate-900/90 border border-slate-800 overflow-hidden shadow-xl">
        <div className="px-6 py-4 border-b border-slate-800">
          <h3 className="text-base font-bold text-white">Batch Job Items ({(batch?.jobs || []).length})</h3>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/60 text-slate-400 uppercase font-semibold border-b border-slate-800">
              <tr>
                <th className="px-6 py-3.5">Job ID</th>
                <th className="px-6 py-3.5">Task Type</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5">Priority</th>
                <th className="px-6 py-3.5">Attempt</th>
                <th className="px-6 py-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {(batch?.jobs || []).map((j) => (
                <tr
                  key={j.id}
                  onClick={() => navigate(`/jobs/${j.id}`)}
                  className="hover:bg-slate-800/40 cursor-pointer transition-colors group"
                >
                  <td className="px-6 py-4 font-mono font-medium text-white">{j.id}</td>
                  <td className="px-6 py-4 font-mono text-slate-300">{j.task_type}</td>
                  <td className="px-6 py-4">{getStatusBadge(j.status)}</td>
                  <td className="px-6 py-4 font-mono">{j.priority}</td>
                  <td className="px-6 py-4 font-mono">{j.attempt}</td>
                  <td className="px-6 py-4 text-right">
                    <span className="text-sky-400 group-hover:translate-x-1 transition-transform inline-flex items-center gap-1 font-semibold">
                      Inspect <ArrowRight className="h-3 w-3" />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
