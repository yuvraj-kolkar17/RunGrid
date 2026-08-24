import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getMetrics } from '../services/metrics';
import { getJobs } from '../services/jobs';
import { getQueues } from '../services/queues';
import type { SystemMetrics, Job, Queue } from '../types/api';
import { ThroughputChart } from '../components/dashboard/ThroughputChart';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { getJobTitle, truncateUuid, formatDate } from '../utils/formatters';
import { POLLING_INTERVALS } from '../utils/constants';
import {
  List,
  Pending,
  PlayCircle,
  CheckCircle2,
  Autorenew,
  Dangerous,
  History,
  Refresh,
  SearchCheck
} from '../components/common/MaterialIcons';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);
  const [queues, setQueues] = useState<Queue[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardMetrics = async () => {
    try {
      const [metricsData, jobsData, queuesData] = await Promise.all([
        getMetrics(),
        getJobs({ page_size: 6 }).catch(() => ({ items: [] })),
        getQueues().catch(() => [])
      ]);
      setMetrics(metricsData);
      setRecentJobs(jobsData.items || []);
      setQueues(queuesData || []);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to connect to backend metrics service.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardMetrics();
    const interval = setInterval(fetchDashboardMetrics, POLLING_INTERVALS.METRICS);
    return () => clearInterval(interval);
  }, []);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton type="kpi" count={6} />
        <LoadingSkeleton type="chart" />
        <LoadingSkeleton type="table" count={3} />
      </div>
    );
  }

  const sysRaw = metrics?.jobs || metrics?.system_overview;
  const sys = {
    total: sysRaw?.total ?? sysRaw?.total_jobs ?? 0,
    queued: sysRaw?.queued ?? 0,
    running: sysRaw?.running ?? 0,
    completed: sysRaw?.completed ?? 0,
    failed: sysRaw?.failed ?? 0,
    retry_waiting: sysRaw?.retry_waiting ?? 0,
    dead_letter: sysRaw?.dead_letter ?? 0,
    scheduled: sysRaw?.scheduled ?? 0,
    rates: sysRaw?.rates || {
      success_rate: 0,
      failure_rate: 0,
      retry_rate: 0,
      total_retry_attempts: 0,
    },
  };

  const tp = metrics?.throughput || {
    completed_last_5m: 0,
    completed_last_15m: 0,
    completed_last_hour: 0,
    failed_last_hour: 0,
    avg_jobs_per_minute: 0,
  };
  const bonus = metrics?.bonus_features || {
    batch_jobs_created: 0,
    dependency_blocked_jobs: 0,
    rate_limit_rejections: 0,
    failure_summaries_generated: 0,
  };

  // Helper map for queue names
  const queueMap = new Map(queues.map((q) => [q.id, q.name]));

  return (
    <div className="space-y-6 pb-12">
      {/* Top Banner & Context Header */}
      <div className="flex flex-col space-y-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-[#424754]/30 pb-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-[#e1e2ec]">
              Dashboard Overview
            </h1>
            <p className="mt-0.5 text-xs text-[#c2c6d6]">
              Real-time task monitoring &amp; workload execution telemetry
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchDashboardMetrics}
              className="flex items-center gap-2 rounded bg-[#272a31] border border-[#424754]/50 px-3 py-1.5 text-xs font-medium text-[#e1e2ec] hover:bg-[#32353c] transition-colors"
            >
              <Refresh className="text-[16px]" />
              <span>Refresh Metrics</span>
            </button>

            <Link
              to="/platform/observability"
              className="flex items-center gap-2 rounded bg-[#1e293b] border border-sky-500/40 text-sky-400 hover:bg-slate-800 px-3.5 py-1.5 text-xs font-semibold transition-all shadow-sm"
            >
              <span>Prometheus Telemetry</span>
            </Link>

            <Link
              to="/jobs"
              className="flex items-center gap-2 rounded bg-[#571bc1] hover:brightness-110 text-[#c4abff] px-3.5 py-1.5 text-xs font-semibold transition-all"
            >
              <SearchCheck className="text-[16px]" />
              <span>Jobs Explorer</span>
            </Link>
          </div>

        </div>
      </div>

      {error && <ErrorAlert message={error} onRetry={fetchDashboardMetrics} />}


      {/* Metric Tiles Row */}
      <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* Total Jobs */}
        <div className="bg-[#12121a] border border-[#1f1f2e] rounded p-4 flex flex-col gap-2 hover:bg-[#1a1a24] transition-colors cursor-pointer" onClick={() => navigate('/jobs')}>
          <div className="flex justify-between items-start">
            <span className="text-[11px] font-semibold text-[#c2c6d6] opacity-80 uppercase tracking-wider">Total Jobs</span>
            <List className="text-[16px] text-[#c2c6d6]" />
          </div>
          <div className="font-mono-code text-3xl font-medium text-[#e1e2ec]">{sys.total}</div>
        </div>

        {/* Queued */}
        <div className="bg-[#12121a] border border-[#1f1f2e] rounded p-4 flex flex-col gap-2 hover:bg-[#1a1a24] transition-colors cursor-pointer" onClick={() => navigate('/jobs?status=QUEUED')}>
          <div className="flex justify-between items-start">
            <span className="text-[11px] font-semibold text-[#c2c6d6] opacity-80 uppercase tracking-wider">Queued</span>
            <Pending className="text-[16px] text-[#c2c6d6]" />
          </div>
          <div className="font-mono-code text-3xl font-medium text-[#e1e2ec]">{sys.queued}</div>
        </div>

        {/* Running */}
        <div className="bg-[#12121a] border border-[#1f1f2e] rounded p-4 flex flex-col gap-2 hover:bg-[#1a1a24] transition-colors cursor-pointer" onClick={() => navigate('/jobs?status=RUNNING')}>
          <div className="flex justify-between items-start">
            <span className="text-[11px] font-semibold text-[#adc6ff] opacity-80 uppercase tracking-wider">Running</span>
            <PlayCircle className="text-[16px] text-[#adc6ff]" />
          </div>
          <div className="font-mono-code text-3xl font-medium text-[#adc6ff]">{sys.running}</div>
        </div>

        {/* Completed */}
        <div className="bg-[#12121a] border border-[#1f1f2e] rounded p-4 flex flex-col gap-2 hover:bg-[#1a1a24] transition-colors cursor-pointer" onClick={() => navigate('/jobs?status=COMPLETED')}>
          <div className="flex justify-between items-start">
            <span className="text-[11px] font-semibold text-[#4cd7f6] opacity-80 uppercase tracking-wider">Completed</span>
            <CheckCircle2 className="text-[16px] text-[#4cd7f6]" />
          </div>
          <div className="font-mono-code text-3xl font-medium text-[#e1e2ec]">{sys.completed}</div>
        </div>

        {/* Retrying */}
        <div className="bg-[#12121a] border border-[#1f1f2e] rounded p-4 flex flex-col gap-2 hover:bg-[#1a1a24] transition-colors cursor-pointer" onClick={() => navigate('/jobs?status=RETRY_WAITING')}>
          <div className="flex justify-between items-start">
            <span className="text-[11px] font-semibold text-[#d0bcff] opacity-80 uppercase tracking-wider">Retrying</span>
            <Autorenew className="text-[16px] text-[#d0bcff]" />
          </div>
          <div className="font-mono-code text-3xl font-medium text-[#e1e2ec]">{sys.retry_waiting}</div>
        </div>

        {/* Dead Letter */}
        <div className="bg-[#12121a] border border-[#1f1f2e] rounded p-4 flex flex-col gap-2 hover:bg-[#1a1a24] transition-colors cursor-pointer" onClick={() => navigate('/jobs?status=DEAD_LETTER')}>
          <div className="flex justify-between items-start">
            <span className="text-[11px] font-semibold text-[#ffb4ab] opacity-80 uppercase tracking-wider">Dead Letter</span>
            <Dangerous className="text-[16px] text-[#ffb4ab]" />
          </div>
          <div className="font-mono-code text-3xl font-medium text-[#ffb4ab]">{sys.dead_letter}</div>
        </div>
      </section>

      {/* Main 2-Column Dashboard Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        {/* Left / Center Column */}
        <div className="xl:col-span-3 flex flex-col gap-6">
          {/* Execution Throughput Chart (24h) */}
          <div className="bg-[#12121a] border border-[#1f1f2e] rounded p-4 flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-[11px] font-semibold text-[#c2c6d6] uppercase tracking-wider opacity-80">
                Execution Throughput (24h)
              </h2>
              <div className="flex gap-4 text-xs font-mono">
                <div className="flex items-center gap-1.5 text-[#4cd7f6]">
                  <span className="w-2 h-2 rounded bg-[#4cd7f6]" /> Completed
                </div>
                <div className="flex items-center gap-1.5 text-[#ffb4ab]">
                  <span className="w-2 h-2 rounded bg-[#ffb4ab]" /> Failed
                </div>
              </div>
            </div>
            <div className="h-[240px]">
              <ThroughputChart throughput={tp} />
            </div>
          </div>

          {/* Recent Workloads Table */}
          <div className="bg-[#12121a] border border-[#1f1f2e] rounded overflow-hidden">
            <div className="px-4 py-3 border-b border-[#424754]/30 flex justify-between items-center">
              <h2 className="text-[11px] font-semibold text-[#c2c6d6] uppercase tracking-wider opacity-80">
                Recent Workloads
              </h2>
              <Link to="/jobs" className="text-xs text-[#adc6ff] hover:underline font-semibold">
                Explorer →
              </Link>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="text-[11px] font-semibold text-[#c2c6d6] uppercase tracking-wider border-b border-[#424754]/30">
                    <th className="px-4 py-2.5 font-medium">Job</th>
                    <th className="px-4 py-2.5 font-medium">Task Type</th>
                    <th className="px-4 py-2.5 font-medium">Queue</th>
                    <th className="px-4 py-2.5 font-medium">Worker</th>
                    <th className="px-4 py-2.5 font-medium">Attempt</th>
                    <th className="px-4 py-2.5 font-medium">Status</th>
                    <th className="px-4 py-2.5 font-medium text-right">Started</th>
                  </tr>
                </thead>
                <tbody className="text-xs divide-y divide-[#424754]/30">
                  {recentJobs.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-6 text-center text-[#c2c6d6]">
                        No workloads found.
                      </td>
                    </tr>
                  ) : (
                    recentJobs.map((job) => {
                      const title = getJobTitle(job);
                      const qName = queueMap.get(job.queue_id) || truncateUuid(job.queue_id, 6);
                      const workerName = job.claimed_by_worker_id
                        ? truncateUuid(job.claimed_by_worker_id, 6)
                        : 'Unassigned';

                      return (
                        <tr
                          key={job.id}
                          onClick={() => navigate(`/jobs/${job.id}`)}
                          className="hover:bg-[#1a1a24] h-[44px] cursor-pointer transition-colors"
                        >
                          <td className="px-4 py-2 text-[#e1e2ec] font-medium truncate max-w-[200px]">
                            {title}
                          </td>
                          <td className="px-4 py-2">
                            <span className="font-mono-code text-[12px] text-[#d0bcff]">{job.task_type}</span>
                          </td>
                          <td className="px-4 py-2 text-[#c2c6d6] capitalize">{qName}</td>
                          <td className="px-4 py-2">
                            <span className="font-mono-code text-[12px] text-[#c2c6d6]">{workerName}</span>
                          </td>
                          <td className="px-4 py-2 text-[#c2c6d6] font-mono">{job.attempt}</td>
                          <td className="px-4 py-2">
                            <StatusBadge status={job.status} size="sm" />
                          </td>
                          <td className="px-4 py-2 text-[#c2c6d6] text-right font-mono text-[11px]">
                            {formatDate(job.created_at)}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right Column (Activity & Insights) */}
        <div className="xl:col-span-1 flex flex-col gap-6">
          {/* Network Topography Telemetry Card */}
          <div className="bg-[#12121a] border border-[#1f1f2e] rounded overflow-hidden h-48 relative group">
            <div className="absolute inset-0 z-10 bg-gradient-to-t from-[#12121a] to-transparent" />
            <img
              className="w-full h-full object-cover opacity-60 group-hover:opacity-80 transition-opacity"
              data-alt="A highly detailed abstract network telemetry illustration with glowing blue lines."
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuAs1vtgl-b-3xjhT5uxCVRZW6kvzrHPsWX8cUmejMNK_ArSRsZf6GTkV3oSV1tTIU7yAVkL8UuUQppMIOBDx-Aveh7OvCAcUFLBbiJGEWqIElKsrzNU5rofHDrStMyS73sJcyqV0rJaJFbPXPG3GXyshRwX1lNB0M1_87buzS2G8mPr4bhvwGXjm0UKTJvKOjDxQXSTbVspTMxgFiez9NwHNgqL1skuehxKQ2u6jFH58A-Po9EML9UisBShll38T0qK4Lg"
              alt="Network Topography"
            />
            <div className="absolute bottom-4 left-4 z-20">
              <h3 className="text-[11px] font-semibold text-[#e1e2ec] uppercase tracking-wider">
                Network Topography
              </h3>
              <p className="text-xs text-[#c2c6d6]">Live visual telemetry</p>
            </div>
          </div>

          {/* Reliability Activity Feed */}
          <div className="bg-[#12121a] border border-[#1f1f2e] rounded flex flex-col">
            <div className="px-4 py-3 border-b border-[#424754]/30 flex justify-between items-center">
              <h2 className="text-[11px] font-semibold text-[#c2c6d6] uppercase tracking-wider opacity-80">
                Reliability Feed
              </h2>
              <History className="text-[16px] text-[#c2c6d6]" />
            </div>
            <div className="flex flex-col p-4 gap-4 overflow-y-auto max-h-[300px]">
              {recentJobs.length === 0 ? (
                <p className="text-xs text-[#8c909f] text-center py-4">No recent job activity</p>
              ) : (
                recentJobs.slice(0, 5).map((j) => {
                  let feedIcon = <Pending className="text-[12px] text-[#c2c6d6]" />;
                  let bgStyle = 'bg-[#32353c] border-[#424754]/50';
                  let msg = `Job created (${j.task_type})`;

                  if (j.status === 'COMPLETED') {
                    feedIcon = <CheckCircle2 className="text-[12px] text-[#4cd7f6]" />;
                    bgStyle = 'bg-[#4cd7f6]/10 border-[#4cd7f6]/30';
                    msg = `Job completed successfully`;
                  } else if (j.status === 'RUNNING') {
                    feedIcon = <PlayCircle className="text-[12px] text-[#adc6ff]" />;
                    bgStyle = 'bg-[#adc6ff]/10 border-[#adc6ff]/30';
                    msg = `Execution in progress`;
                  } else if (j.status === 'RETRY_WAITING') {
                    feedIcon = <Autorenew className="text-[12px] text-[#d0bcff]" />;
                    bgStyle = 'bg-[#571bc1]/20 border-[#571bc1]/40';
                    msg = `Job waiting for retry (Attempt ${j.attempt})`;
                  } else if (j.status === 'DEAD_LETTER' || j.status === 'FAILED') {
                    feedIcon = <Dangerous className="text-[12px] text-[#ffb4ab]" />;
                    bgStyle = 'bg-rose-500/20 border-rose-500/40';
                    msg = j.status === 'DEAD_LETTER' ? 'Moved to Dead Letter Queue' : 'Job execution failed';
                  }

                  return (
                    <div key={j.id} className="flex gap-3 items-start cursor-pointer" onClick={() => navigate(`/jobs/${j.id}`)}>
                      <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 border ${bgStyle}`}>
                        {feedIcon}
                      </div>
                      <div className="flex flex-col">
                        <p className="text-xs text-[#e1e2ec] font-medium">{msg}</p>
                        <p className="font-mono-code text-[11px] text-[#c2c6d6] mt-0.5">
                          {j.task_type} • <span className="text-[#8c909f]">{truncateUuid(j.id, 8)}</span>
                        </p>
                        <span className="text-[10px] text-[#8c909f] mt-0.5">{formatDate(j.created_at)}</span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Platform Insights (Compact Grid) */}
          <div className="bg-[#12121a] border border-[#1f1f2e] rounded flex flex-col">
            <div className="px-4 py-3 border-b border-[#424754]/30 flex justify-between items-center">
              <h2 className="text-[11px] font-semibold text-[#c2c6d6] uppercase tracking-wider opacity-80">
                Platform Insights
              </h2>
              <Link to="/platform" className="text-xs text-[#adc6ff] hover:underline font-semibold">
                Manage
              </Link>
            </div>
            <div className="grid grid-cols-2 gap-[1px] bg-[#424754]/30 p-[1px]">
              <div
                onClick={() => navigate('/platform/batches')}
                className="bg-[#12121a] p-3 flex flex-col gap-1 hover:bg-[#1a1a24] transition-colors cursor-pointer"
              >
                <span className="text-[11px] font-semibold text-[#c2c6d6] opacity-80 uppercase">Batch Jobs</span>
                <span className="font-mono-code text-xl text-[#e1e2ec]">{bonus.batch_jobs_created}</span>
              </div>
              <div
                onClick={() => navigate('/platform/workflows')}
                className="bg-[#12121a] p-3 flex flex-col gap-1 hover:bg-[#1a1a24] transition-colors cursor-pointer"
              >
                <span className="text-[11px] font-semibold text-[#c2c6d6] opacity-80 uppercase">Dependencies</span>
                <span className="font-mono-code text-xl text-[#e1e2ec]">{bonus.dependency_blocked_jobs}</span>
              </div>
              <div
                onClick={() => navigate('/platform/rate-limits')}
                className="bg-[#12121a] p-3 flex flex-col gap-1 hover:bg-[#1a1a24] transition-colors cursor-pointer"
              >
                <span className="text-[11px] font-semibold text-[#c2c6d6] opacity-80 uppercase">Limit Rejects</span>
                <span className="font-mono-code text-xl text-[#d0bcff]">{bonus.rate_limit_rejections}</span>
              </div>
              <div
                onClick={() => navigate('/platform/failures')}
                className="bg-[#12121a] p-3 flex flex-col gap-1 hover:bg-[#1a1a24] transition-colors cursor-pointer"
              >
                <span className="text-[11px] font-semibold text-[#c2c6d6] opacity-80 uppercase">Fail Analyses</span>
                <span className="font-mono-code text-xl text-[#ffb4ab]">{bonus.failure_summaries_generated}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

