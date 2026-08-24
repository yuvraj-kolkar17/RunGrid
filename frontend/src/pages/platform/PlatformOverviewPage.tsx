import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Activity, Layers, ShieldAlert, AlertTriangle, 
  CheckCircle2, Cpu, ArrowRight, RefreshCw, Layers3,
  Flame, Sparkles
} from 'lucide-react';
import { platformService } from '../../services/platform';
import type { PlatformOverview } from '../../types/api';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';

export const PlatformOverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<PlatformOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchOverview = async () => {
    try {
      setRefreshing(true);
      const res = await platformService.getOverview();
      setData(res);
    } catch (err) {
      console.error('Failed to load platform overview:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchOverview();
    const interval = setInterval(fetchOverview, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <LoadingSkeleton type="card" />;
  }

  const getHealthBadge = (status: string) => {
    switch (status) {
      case 'HEALTHY':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-4 w-4" /> Healthy Cluster
          </span>
        );
      case 'DEGRADED':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertTriangle className="h-4 w-4" /> Degraded Performance
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <ShieldAlert className="h-4 w-4" /> Action Required
          </span>
        );
    }
  };

  return (
    <div className="space-y-8 pb-10">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-gradient-to-r from-slate-900 via-sky-950/40 to-slate-900 p-6 rounded-3xl border border-sky-500/20 shadow-xl shadow-sky-950/20">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold uppercase bg-sky-500/20 text-sky-300 border border-sky-500/30">
              Platform Operations Center
            </span>
            {data?.system_health?.status && getHealthBadge(data.system_health.status)}
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            System Operations Overview
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-xl">
            Real-time telemetry, atomic batch control, workflow graph dependencies, API rate limiting, and failure diagnostics.
          </p>
        </div>

        <button
          onClick={fetchOverview}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-2xl text-xs font-semibold border border-slate-700 transition-all shadow-md active:scale-95 disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin text-sky-400' : ''}`} />
          {refreshing ? 'Refreshing...' : 'Refresh Telemetry'}
        </button>
      </div>

      {/* Primary Platform Metric Cards (Directly Linked to Platform Sections) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Card 1: Batch Jobs */}
        <div
          onClick={() => navigate('/platform/batches')}
          className="group relative cursor-pointer overflow-hidden rounded-3xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl transition-all duration-300 hover:-translate-y-1 hover:border-sky-500/40 hover:shadow-2xl hover:shadow-sky-950/50"
        >
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Batch Submissions
            </span>
            <div className="p-2.5 rounded-2xl bg-sky-500/10 text-sky-400 border border-sky-500/20 group-hover:scale-110 transition-transform">
              <Layers3 className="h-5 w-5" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-white font-mono tracking-tight">
            {data?.summary?.batch_jobs_created ?? 0}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-slate-400">Atomic Job Groups</span>
            <span className="text-sky-400 font-semibold group-hover:translate-x-1 transition-transform flex items-center gap-1">
              Explore Batches <ArrowRight className="h-3 w-3" />
            </span>
          </div>
        </div>

        {/* Card 2: Dependency Blocks */}
        <div
          onClick={() => navigate('/platform/workflows')}
          className="group relative cursor-pointer overflow-hidden rounded-3xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl transition-all duration-300 hover:-translate-y-1 hover:border-indigo-500/40 hover:shadow-2xl hover:shadow-indigo-950/50"
        >
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Workflow Dependencies
            </span>
            <div className="p-2.5 rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 group-hover:scale-110 transition-transform">
              <Layers className="h-5 w-5" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-white font-mono tracking-tight">
            {data?.summary?.dependency_blocks ?? 0}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-slate-400">Blocked Jobs</span>
            <span className="text-indigo-400 font-semibold group-hover:translate-x-1 transition-transform flex items-center gap-1">
              View DAG Graph <ArrowRight className="h-3 w-3" />
            </span>
          </div>
        </div>

        {/* Card 3: Rate Limiting */}
        <div
          onClick={() => navigate('/platform/rate-limits')}
          className="group relative cursor-pointer overflow-hidden rounded-3xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl transition-all duration-300 hover:-translate-y-1 hover:border-amber-500/40 hover:shadow-2xl hover:shadow-amber-950/50"
        >
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Rate Limiting
            </span>
            <div className="p-2.5 rounded-2xl bg-amber-500/10 text-amber-400 border border-amber-500/20 group-hover:scale-110 transition-transform">
              <ShieldAlert className="h-5 w-5" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-white font-mono tracking-tight">
            {data?.summary?.rate_limit_rejections ?? 0}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-slate-400">Rejections (429)</span>
            <span className="text-amber-400 font-semibold group-hover:translate-x-1 transition-transform flex items-center gap-1">
              Inspect Limits <ArrowRight className="h-3 w-3" />
            </span>
          </div>
        </div>

        {/* Card 4: Failure Analysis */}
        <div
          onClick={() => navigate('/platform/failures')}
          className="group relative cursor-pointer overflow-hidden rounded-3xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl transition-all duration-300 hover:-translate-y-1 hover:border-rose-500/40 hover:shadow-2xl hover:shadow-rose-950/50"
        >
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Failure Analysis
            </span>
            <div className="p-2.5 rounded-2xl bg-rose-500/10 text-rose-400 border border-rose-500/20 group-hover:scale-110 transition-transform">
              <Flame className="h-5 w-5" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-white font-mono tracking-tight">
            {data?.summary?.failure_analyses ?? 0}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-slate-400">Diagnoses Generated</span>
            <span className="text-rose-400 font-semibold group-hover:translate-x-1 transition-transform flex items-center gap-1">
              Failure Logs <ArrowRight className="h-3 w-3" />
            </span>
          </div>
        </div>
      </div>

      {/* Cluster Status & Telemetry Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Cluster Infrastructure Health */}
        <div className="lg:col-span-2 rounded-3xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl space-y-5">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <Cpu className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Cluster Infrastructure</h3>
                <p className="text-xs text-slate-400">Active worker processes and queue availability</p>
              </div>
            </div>
            <button
              onClick={() => navigate('/platform/observability')}
              className="text-xs font-semibold text-sky-400 hover:text-sky-300 flex items-center gap-1"
            >
              Full Telemetry <ArrowRight className="h-3 w-3" />
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="rounded-2xl bg-slate-950/60 p-4 border border-slate-800">
              <div className="text-xs text-slate-400">Total Workers</div>
              <div className="text-2xl font-bold font-mono text-slate-100 mt-1">
                {data?.system_health?.total_workers ?? 0}
              </div>
            </div>
            <div className="rounded-2xl bg-slate-950/60 p-4 border border-slate-800">
              <div className="text-xs text-emerald-400 font-semibold">Active Workers</div>
              <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
                {data?.system_health?.active_workers ?? 0}
              </div>
            </div>
            <div className="rounded-2xl bg-slate-950/60 p-4 border border-slate-800">
              <div className="text-xs text-amber-400 font-semibold">Stale Workers</div>
              <div className="text-2xl font-bold font-mono text-amber-400 mt-1">
                {data?.system_health?.stale_workers ?? 0}
              </div>
            </div>
            <div className="rounded-2xl bg-slate-950/60 p-4 border border-slate-800">
              <div className="text-xs text-slate-400">Total Queues</div>
              <div className="text-2xl font-bold font-mono text-slate-100 mt-1">
                {data?.system_health?.total_queues ?? 0}
              </div>
            </div>
          </div>
        </div>

        {/* Quick Platform Controls Panel */}
        <div className="rounded-3xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-sky-500/10 text-sky-400 border border-sky-500/20">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Platform Modules</h3>
              <p className="text-xs text-slate-400">Direct operations suite navigation</p>
            </div>
          </div>

          <div className="space-y-2.5 pt-2">
            {[
              { label: 'Real-time Observability', path: '/platform/observability', icon: Activity, desc: 'Live job throughput & latency' },
              { label: 'Batch Submission History', path: '/platform/batches', icon: Layers3, desc: 'Atomic job group management' },
              { label: 'Workflow Visualizer (DAG)', path: '/platform/workflows', icon: Layers, desc: 'Dependency graph validation' },
              { label: 'API Rate Limiting', path: '/platform/rate-limits', icon: ShieldAlert, desc: 'Sliding window limit testing' },
              { label: 'Failure Analysis Center', path: '/platform/failures', icon: Flame, desc: 'Root cause diagnosis' },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.path}
                  onClick={() => navigate(item.path)}
                  className="w-full flex items-center justify-between p-3 rounded-2xl bg-slate-950/60 hover:bg-slate-800/90 border border-slate-800/80 hover:border-sky-500/30 text-left transition-all group"
                >
                  <div className="flex items-center gap-3">
                    <Icon className="h-4 w-4 text-sky-400 group-hover:scale-110 transition-transform" />
                    <div>
                      <div className="text-xs font-semibold text-slate-200 group-hover:text-sky-300 transition-colors">
                        {item.label}
                      </div>
                      <div className="text-[10px] text-slate-400">{item.desc}</div>
                    </div>
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-sky-400 group-hover:translate-x-1 transition-all" />
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
