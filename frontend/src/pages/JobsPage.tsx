import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getJobs } from '../services/jobs';
import { getQueues } from '../services/queues';
import type { Job, Queue } from '../types/api';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import { CreateJobModal } from '../components/jobs/CreateJobModal';
import { BatchJobModal } from '../components/jobs/BatchJobModal';
import { formatDate, truncateUuid, getJobTitle } from '../utils/formatters';
import {
  Briefcase,
  Plus,
  ChevronLeft,
  ChevronRight,
  Eye,
  Search,
  Layers,
  RotateCcw
} from 'lucide-react';

export const JobsPage: React.FC = () => {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [queues, setQueues] = useState<Queue[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(20);

  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [queueFilter, setQueueFilter] = useState<string>('');
  const [isDemoOnly, setIsDemoOnly] = useState<boolean>(false);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isSingleModalOpen, setIsSingleModalOpen] = useState<boolean>(false);
  const [isBatchModalOpen, setIsBatchModalOpen] = useState<boolean>(false);

  const fetchJobs = async () => {
    setIsLoading(true);
    try {
      const res = await getJobs({
        page,
        page_size: pageSize,
        status: statusFilter || undefined,
        queue_id: queueFilter || undefined,
      });

      let filteredItems = res.items;
      if (isDemoOnly) {
        filteredItems = filteredItems.filter(
          (j) => Boolean(j.payload?.demo_marker || j.payload?.demo_id)
        );
      }

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        filteredItems = filteredItems.filter(
          (j) =>
            j.id.toLowerCase().includes(q) ||
            j.task_type.toLowerCase().includes(q) ||
            getJobTitle(j).toLowerCase().includes(q) ||
            (j.claimed_by_worker_id && j.claimed_by_worker_id.toLowerCase().includes(q))
        );
      }

      setJobs(filteredItems);
      setTotal(res.total);
      setTotalPages(res.total_pages);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch jobs.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    getQueues()
      .then(setQueues)
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [page, pageSize, statusFilter, queueFilter, searchQuery, isDemoOnly]);

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">Workload Explorer</h1>
          <p className="mt-1 text-xs text-slate-400">
            Monitor and manage background task executions across all system queues
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setIsBatchModalOpen(true)}
            className="flex items-center gap-2 rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-800 px-3.5 py-2 text-xs font-semibold text-sky-400 transition-colors"
          >
            <Layers className="h-4 w-4" />
            <span>+ Batch Jobs</span>
          </button>

          <button
            onClick={() => setIsSingleModalOpen(true)}
            className="flex items-center gap-2 rounded-xl bg-sky-600 px-4 py-2 text-xs font-semibold text-white hover:bg-sky-500 transition-all shadow-md shadow-sky-600/20"
          >
            <Plus className="h-4 w-4" />
            <span>Create Job</span>
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 rounded-2xl bg-slate-900/60 p-4 border border-slate-800/80">
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => {
              setIsDemoOnly(!isDemoOnly);
              setPage(1);
            }}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
              isDemoOnly
                ? 'bg-sky-950 text-sky-300 border-sky-600 shadow-sm shadow-sky-900/40'
                : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-white'
            }`}
          >
            {isDemoOnly ? '✓ Demo Workloads' : 'Demo Workloads'}
          </button>

          <div className="relative min-w-[220px]">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search Job Title, ID, Task..."
              className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-sky-500 font-mono"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-xl bg-slate-950 border border-slate-800 px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
          >
            <option value="">All Statuses</option>
            <option value="QUEUED">QUEUED</option>
            <option value="CLAIMED">CLAIMED</option>
            <option value="RUNNING">RUNNING</option>
            <option value="COMPLETED">COMPLETED</option>
            <option value="FAILED">FAILED</option>
            <option value="RETRY_WAITING">RETRY_WAITING</option>
            <option value="DEAD_LETTER">DEAD_LETTER</option>
            <option value="SCHEDULED">SCHEDULED</option>
          </select>

          <select
            value={queueFilter}
            onChange={(e) => {
              setQueueFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-xl bg-slate-950 border border-slate-800 px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
          >
            <option value="">All Queues</option>
            {queues.map((q) => (
              <option key={q.id} value={q.id}>
                {q.name}
              </option>
            ))}
          </select>

          {(statusFilter || queueFilter || searchQuery || isDemoOnly) && (
            <button
              onClick={() => {
                setStatusFilter('');
                setQueueFilter('');
                setSearchQuery('');
                setIsDemoOnly(false);
                setPage(1);
              }}
              className="flex items-center gap-1 text-xs text-slate-400 hover:text-sky-400 transition-colors"
            >
              <RotateCcw className="h-3 w-3" />
              <span>Reset</span>
            </button>
          )}
        </div>

        <div className="text-xs text-slate-400 font-mono">
          Showing <span className="text-white font-semibold">{jobs.length}</span> of{' '}
          <span className="text-white font-semibold">{total}</span> jobs
        </div>
      </div>

      {error && <ErrorAlert message={error} onRetry={fetchJobs} />}

      {isLoading ? (
        <LoadingSkeleton type="table" count={6} />
      ) : jobs.length === 0 ? (
        <EmptyState
          title="No Jobs Found"
          description={
            statusFilter || queueFilter || searchQuery
              ? 'No background jobs match your search filters.'
              : 'Submit your first background job to monitor execution.'
          }
          actionLabel="Create Job"
          onAction={() => setIsSingleModalOpen(true)}
          icon={<Briefcase className="h-8 w-8 text-sky-400" />}
        />
      ) : (
        <div className="overflow-hidden rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950 text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 font-mono">
                <tr>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5">Job Title & Task</th>
                  <th className="px-5 py-3.5">Job ID</th>
                  <th className="px-5 py-3.5">Queue</th>
                  <th className="px-5 py-3.5">Attempt</th>
                  <th className="px-5 py-3.5">Worker</th>
                  <th className="px-5 py-3.5">Submitted</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {jobs.map((job) => {
                  const title = getJobTitle(job);
                  return (
                    <tr
                      key={job.id}
                      onClick={() => navigate(`/jobs/${job.id}`)}
                      className="hover:bg-slate-800/40 transition-colors cursor-pointer group"
                    >
                      <td className="px-5 py-3.5">
                        <StatusBadge status={job.status} size="sm" />
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="font-semibold text-white group-hover:text-sky-400 transition-colors">
                          {title}
                        </div>
                        <div className="text-[11px] font-mono text-slate-400">
                          {job.task_type}
                        </div>
                      </td>
                      <td className="px-5 py-3.5 font-mono text-sky-400 font-medium">
                        {truncateUuid(job.id, 8)}
                      </td>
                      <td className="px-5 py-3.5 font-mono text-slate-400">
                        {queues.find((q) => q.id === job.queue_id)?.name || truncateUuid(job.queue_id, 6)}
                      </td>
                      <td className="px-5 py-3.5 font-mono text-slate-300">
                        #{job.attempt} / {job.max_retries}
                      </td>
                      <td className="px-5 py-3.5 font-mono text-slate-400">
                        {job.claimed_by_worker_id ? truncateUuid(job.claimed_by_worker_id, 8) : '—'}
                      </td>
                      <td className="px-5 py-3.5 font-mono text-slate-400">
                        {formatDate(job.created_at)}
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/jobs/${job.id}`);
                          }}
                          className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-sky-400 transition-colors"
                          title="View Job Details"
                        >
                          <Eye className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between px-5 py-3.5 bg-slate-950 border-t border-slate-800 text-xs text-slate-400">
            <div className="flex items-center gap-2">
              <span>Per page:</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
                className="rounded-lg bg-slate-900 border border-slate-800 px-2 py-1 text-slate-200 focus:outline-none"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
              </select>
            </div>

            <div className="flex items-center gap-4">
              <span>
                Page <strong className="text-white font-mono">{page}</strong> of{' '}
                <strong className="text-white font-mono">{totalPages}</strong>
              </span>

              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(p - 1, 1))}
                  disabled={page <= 1}
                  className="p-1.5 rounded-lg border border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                  disabled={page >= totalPages}
                  className="p-1.5 rounded-lg border border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <CreateJobModal
        isOpen={isSingleModalOpen}
        onClose={() => setIsSingleModalOpen(false)}
        onSuccess={fetchJobs}
      />

      <BatchJobModal
        isOpen={isBatchModalOpen}
        onClose={() => setIsBatchModalOpen(false)}
        queues={queues}
        onSuccess={fetchJobs}
      />
    </div>
  );
};
