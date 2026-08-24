import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getJob, retryJob } from '../services/jobs';
import type { Job } from '../types/api';
import { StatusBadge } from '../components/common/StatusBadge';
import { JobTimeline } from '../components/jobs/JobTimeline';
import { ExecutionHistoryTable } from '../components/jobs/ExecutionHistoryTable';
import { JobLogsTable } from '../components/jobs/JobLogsTable';
import { JsonViewer } from '../components/common/JsonViewer';
import { FailureAnalysisCard } from '../components/jobs/FailureAnalysisCard';
import { DependencyGraph } from '../components/jobs/DependencyGraph';
import { AddDependencyModal } from '../components/jobs/AddDependencyModal';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { useToast } from '../context/ToastContext';
import { formatDate, truncateUuid, getJobTitle } from '../utils/formatters';
import { POLLING_INTERVALS } from '../utils/constants';
import {
  ArrowLeft,
  RotateCw,
  Copy,
  Check,
  User,
  Package
} from 'lucide-react';

export const JobDetailPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { addToast } = useToast();

  const [job, setJob] = useState<Job | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [isAddDepModalOpen, setIsAddDepModalOpen] = useState<boolean>(false);

  const fetchJobDetail = async () => {
    if (!jobId) return;
    try {
      const data = await getJob(jobId);
      setJob(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load job details.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchJobDetail();
  }, [jobId]);

  useEffect(() => {
    if (!job) return;
    const isActive = ['QUEUED', 'CLAIMED', 'RUNNING'].includes(job.status);
    if (!isActive) return;

    const interval = setInterval(fetchJobDetail, POLLING_INTERVALS.JOB_DETAIL);
    return () => clearInterval(interval);
  }, [job?.status]);

  const handleCopyId = () => {
    if (!jobId) return;
    navigator.clipboard.writeText(jobId);
    setCopied(true);
    addToast('Job UUID copied to clipboard', 'info');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleManualRetry = async () => {
    if (!jobId) return;
    try {
      setIsRetrying(true);
      await retryJob(jobId);
      addToast('Job requeued for retry execution', 'success');
      await fetchJobDetail();
    } catch (err: any) {
      addToast(err.message || 'Failed to retry job.', 'error');
    } finally {
      setIsRetrying(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton type="detail" />
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="space-y-6">
        <button
          onClick={() => navigate('/jobs')}
          className="flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Jobs Explorer
        </button>
        <ErrorAlert message={error || 'Job not found'} onRetry={fetchJobDetail} />
      </div>
    );
  }

  const canRetry = job.status === 'FAILED' || job.status === 'DEAD_LETTER';
  const title = getJobTitle(job);
  const payload = job.payload || {};
  const customerId = payload.customer_id;
  const orderId = payload.order_id;

  return (
    <div className="space-y-8 pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div className="space-y-1">
          <button
            onClick={() => navigate('/jobs')}
            className="flex items-center gap-1.5 text-xs font-semibold text-sky-400 hover:underline mb-2"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Jobs Explorer
          </button>

          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold tracking-tight text-white">{title}</h1>
            <StatusBadge status={job.status} size="md" />
            {Boolean(job.payload?.demo_marker || job.payload?.demo_id) && (
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-sky-950 text-sky-300 border border-sky-800/60 font-mono">
                Demo Scenario: Acme Cloud · Customer Operations
              </span>
            )}
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-400 font-mono flex-wrap">
            <span>ID: <strong className="text-sky-400">{truncateUuid(job.id, 12)}</strong></span>
            <button
              onClick={handleCopyId}
              className="p-1 rounded bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition-colors"
              title="Copy Job UUID"
            >
              {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
            </button>
            <span>•</span>
            <span>Task Type: <strong className="text-slate-200">{job.task_type}</strong></span>
            {customerId && (
              <>
                <span>•</span>
                <span className="flex items-center gap-1 text-purple-300">
                  <User className="h-3 w-3 text-purple-400" />
                  <span>Customer: {customerId}</span>
                </span>
              </>
            )}
            {orderId && (
              <>
                <span>•</span>
                <span className="flex items-center gap-1 text-amber-300">
                  <Package className="h-3 w-3 text-amber-400" />
                  <span>Order: {orderId}</span>
                </span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {canRetry && (
            <button
              onClick={handleManualRetry}
              disabled={isRetrying}
              className="flex items-center gap-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white px-4 py-2 text-xs font-semibold transition-all shadow-md shadow-amber-600/20 disabled:opacity-50"
            >
              <RotateCw className={`h-4 w-4 ${isRetrying ? 'animate-spin' : ''}`} />
              <span>{isRetrying ? 'Requeueing...' : 'Re-queue Job'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Lifecycle Timeline */}
      <JobTimeline status={job.status} attempt={job.attempt} />

      {/* Workflow Dependency Graph */}
      <DependencyGraph
        currentJob={job}
        dependencies={job.dependencies}
        dependents={job.dependents}
        onOpenAddModal={() => setIsAddDepModalOpen(true)}
      />

      {/* AI Failure Diagnostics (if FAILED or DEAD_LETTER) */}
      {(job.status === 'FAILED' || job.status === 'DEAD_LETTER' || job.error) && (
        <FailureAnalysisCard
          summary={job.failure_summary || {
            summary: job.error || 'Execution Error',
            likely_cause: 'Job execution failed during worker processing.',
            recommended_action: 'Inspect terminal execution logs and retry execution.',
            error_type: 'RUNTIME_ERROR'
          }}
        />
      )}

      {/* Metadata & Payloads */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-2xl bg-slate-900/60 p-5 border border-slate-800/80 space-y-3 shadow-xl">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 font-mono">
            Input Payload Parameters
          </h3>
          <JsonViewer data={job.payload} />
        </div>

        <div className="rounded-2xl bg-slate-900/60 p-5 border border-slate-800/80 space-y-3 shadow-xl">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 font-mono">
            Execution Result / Output
          </h3>
          <JsonViewer data={job.result || { message: 'No output result generated yet' }} />
        </div>
      </div>

      {/* Metadata Overview Card */}
      <div className="rounded-2xl bg-slate-900/60 p-5 border border-slate-800/80 space-y-4 shadow-xl">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 font-mono">
          Engine Execution Context
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
          <div>
            <span className="text-slate-500 block text-[10px]">CURRENT ATTEMPT</span>
            <span className="text-white font-bold">#{job.attempt} / {job.max_retries}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px]">CLAIMED WORKER</span>
            <span className="text-sky-400 font-bold">{job.claimed_by_worker_id ? truncateUuid(job.claimed_by_worker_id, 10) : 'Unassigned'}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px]">SUBMITTED AT</span>
            <span className="text-slate-300">{formatDate(job.created_at)}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px]">LEASE EXPIRATION</span>
            <span className="text-slate-300">{formatDate(job.lease_expires_at)}</span>
          </div>
        </div>
      </div>

      {/* Execution History */}
      <ExecutionHistoryTable executions={job.executions} />

      {/* Terminal Logs */}
      <JobLogsTable logs={job.logs} />

      {/* Dependency Modal */}
      <AddDependencyModal
        isOpen={isAddDepModalOpen}
        onClose={() => setIsAddDepModalOpen(false)}
        targetJobId={job.id}
        onSuccess={fetchJobDetail}
      />
    </div>
  );
};
