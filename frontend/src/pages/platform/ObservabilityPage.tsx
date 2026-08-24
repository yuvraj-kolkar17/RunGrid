import React, { useEffect, useState, useRef } from 'react';
import { 
  Activity, RefreshCw, BarChart2, CheckCircle2, 
  AlertTriangle, Clock, PlayCircle, Cpu, Zap, ShieldAlert,
  Server, Gauge, Layers, WifiOff
} from 'lucide-react';

import { 
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, 
  Tooltip, CartesianGrid, LineChart, Line 
} from 'recharts';

import { platformService } from '../../services/platform';
import type { ObservabilityMetrics, ObservabilityTimeSeriesResponse } from '../../types/api';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';

type TimeRange = '5m' | '15m' | '30m' | '1h';

export const ObservabilityPage: React.FC = () => {
  const [data, setData] = useState<ObservabilityMetrics | null>(null);
  const [tsData, setTsData] = useState<ObservabilityTimeSeriesResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  
  const [timeRange, setTimeRange] = useState<TimeRange>('15m');
  const [isLive, setIsLive] = useState<boolean>(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [currentTime, setCurrentTime] = useState<Date>(new Date());
  const [tabVisible, setTabVisible] = useState<boolean>(true);

  // Keep a reference to prevent race conditions
  const isFetchingRef = useRef<boolean>(false);

  // Update current time tick every 1s to refresh "Updated X s ago"
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Track document visibility state
  useEffect(() => {
    const handleVisibilityChange = () => {
      const isVis = document.visibilityState === 'visible';
      setTabVisible(isVis);
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  const fetchAllData = async () => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    setRefreshing(true);

    try {
      const [obsRes, tsRes] = await Promise.all([
        platformService.getObservability().catch(() => null),
        platformService.getTimeSeries(timeRange).catch(() => null)
      ]);

      if (obsRes) setData(obsRes);
      if (tsRes) setTsData(tsRes);
      if (obsRes || tsRes) setLastUpdated(new Date());
    } catch (err) {
      console.error('Error fetching observability telemetry:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
      isFetchingRef.current = false;
    }
  };

  // Main polling effect (every 3 seconds)
  useEffect(() => {
    fetchAllData();

    if (!isLive || !tabVisible) {
      return;
    }

    const interval = setInterval(() => {
      fetchAllData();
    }, 3000);

    return () => clearInterval(interval);
  }, [isLive, tabVisible, timeRange]);

  if (loading) {
    return <LoadingSkeleton type="card" />;
  }

  // Calculate Connection & Prometheus Status
  const secondsAgo = lastUpdated ? Math.max(0, Math.floor((currentTime.getTime() - lastUpdated.getTime()) / 1000)) : null;
  const isPrometheusAvailable = tsData?.prometheus_status === 'HEALTHY' || data?.prometheus?.status === 'HEALTHY';
  
  let connectionState: 'LIVE' | 'STALE' | 'PROMETHEUS_UNAVAILABLE' = 'LIVE';
  if (!isPrometheusAvailable) {
    connectionState = 'PROMETHEUS_UNAVAILABLE';
  } else if (secondsAgo === null || secondsAgo >= 10) {
    connectionState = 'STALE';
  }

  const latestVals = tsData?.latest_values || {
    throughput: 0.0,
    completed: 0.0,
    failed: 0.0,
    retry: 0.0,
    dlq: 0.0,
    p50_ms: data?.prometheus?.quantiles_ms?.p50 || 0.0,
    p95_ms: data?.prometheus?.quantiles_ms?.p95 || 0.0,
    p99_ms: data?.prometheus?.quantiles_ms?.p99 || 0.0,
  };

  const seriesPoints = tsData?.series || [];
  const jobStates = data?.job_states;
  const workers = data?.workers || [];
  const queues = data?.queues || [];

  return (
    <div className="space-y-8 pb-10">
      {/* Header Banner */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 bg-slate-900/90 border border-slate-800 p-6 rounded-3xl shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            {/* Connection Status Badge */}
            {connectionState === 'LIVE' && (
              <span className="px-3 py-1 rounded-full text-xs font-mono font-semibold uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" /> Live Prometheus Telemetry
              </span>
            )}
            {connectionState === 'STALE' && (
              <span className="px-3 py-1 rounded-full text-xs font-mono font-semibold uppercase bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-amber-400" /> Connection Stale
              </span>
            )}
            {connectionState === 'PROMETHEUS_UNAVAILABLE' && (
              <span className="px-3 py-1 rounded-full text-xs font-mono font-semibold uppercase bg-rose-500/10 text-rose-400 border border-rose-500/20 flex items-center gap-2">
                <WifiOff className="h-3.5 w-3.5" /> Prometheus Unavailable
              </span>
            )}

            <span className="text-xs font-mono text-slate-400">
              {secondsAgo !== null ? `Updated ${secondsAgo}s ago` : 'Connecting...'}
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <Activity className="h-7 w-7 text-sky-400" /> Platform Observability
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Real-time Prometheus range queries, sliding window throughput, latency quantiles, and worker cluster state.
          </p>
        </div>

        {/* Controls Header */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Time Range Selector */}
          <div className="flex items-center bg-slate-950 p-1 rounded-2xl border border-slate-800">
            {(['5m', '15m', '30m', '1h'] as TimeRange[]).map((r) => (
              <button
                key={r}
                onClick={() => setTimeRange(r)}
                className={`px-3 py-1.5 rounded-xl text-xs font-mono font-semibold transition-all ${
                  timeRange === r
                    ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {r}
              </button>
            ))}
          </div>

          {/* Live Toggle */}
          <button
            onClick={() => setIsLive(!isLive)}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-2xl text-xs font-semibold border transition-all ${
              isLive
                ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                : 'bg-slate-800 text-slate-400 border-slate-700'
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${isLive ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
            {isLive ? 'LIVE (3s)' : 'PAUSED'}
          </button>

          {/* External Links */}
          <a
            href="http://localhost:9090"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-sky-400 border border-sky-500/30 rounded-2xl text-xs font-semibold transition-all"
          >
            Prometheus ↗
          </a>
          <a
            href="http://localhost:8000/metrics"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-emerald-500/30 rounded-2xl text-xs font-semibold transition-all font-mono"
          >
            /metrics ↗
          </a>

          <button
            onClick={fetchAllData}
            disabled={refreshing}
            className="flex items-center gap-2 px-3.5 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-2xl text-xs font-semibold shadow-lg shadow-sky-950/40 transition-all active:scale-95 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Prometheus Down Warning Banner */}
      {!isPrometheusAvailable && (
        <div className="flex items-center justify-between p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-medium">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
            <span>Prometheus server unavailable — displaying last known telemetry dataset.</span>
          </div>
          <span className="font-mono text-[11px] text-amber-400">Target: http://prometheus:9090</span>
        </div>
      )}

      {/* Primary Real-time Throughput Wave Chart */}
      <div className="rounded-3xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl space-y-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <BarChart2 className="h-5 w-5 text-sky-400" /> Workload Throughput Wave
              </h3>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-sky-500/10 text-sky-400 border border-sky-500/20">
                Range: {timeRange} (Step: {tsData?.step || 10}s)
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Prometheus rate queries (<code className="font-mono text-sky-300">rate(scheduler_jobs_*[1m])</code>)
            </p>
          </div>

          {/* Live KPI Metric Badges */}
          <div className="flex flex-wrap items-center gap-4 bg-slate-950/80 p-3 rounded-2xl border border-slate-800 font-mono text-xs">
            <div>
              <span className="text-slate-400 block text-[10px] uppercase">Current Rate</span>
              <span className="text-white font-bold text-sm">{latestVals.throughput.toFixed(2)} <span className="text-[10px] font-normal text-slate-400">jobs/s</span></span>
            </div>
            <div className="border-l border-slate-800 pl-4">
              <span className="text-emerald-400 block text-[10px] uppercase">Completed</span>
              <span className="text-emerald-400 font-bold">{latestVals.completed.toFixed(2)}/s</span>
            </div>
            <div className="border-l border-slate-800 pl-4">
              <span className="text-rose-400 block text-[10px] uppercase">Failed</span>
              <span className="text-rose-400 font-bold">{latestVals.failed.toFixed(2)}/s</span>
            </div>
            <div className="border-l border-slate-800 pl-4">
              <span className="text-purple-400 block text-[10px] uppercase">Retrying</span>
              <span className="text-purple-400 font-bold">{latestVals.retry.toFixed(2)}/s</span>
            </div>
          </div>
        </div>

        {/* Recharts Area Wave Chart */}
        <div className="h-64 w-full">
          {seriesPoints.length === 0 ? (
            <div className="h-full flex items-center justify-center text-xs text-slate-500 italic">
              Awaiting Prometheus time-series range query response...
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={seriesPoints} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="completedGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="failedGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#f43f5e" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="retryGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#a855f7" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis 
                  dataKey="time_label" 
                  stroke="#64748b" 
                  tick={{ fontSize: 11, fill: '#94a3b8' }} 
                />
                <YAxis 
                  stroke="#64748b" 
                  tick={{ fontSize: 11, fill: '#94a3b8' }} 
                  unit=" /s"
                />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }} 
                  itemStyle={{ fontSize: '12px' }}
                />
                <Area 
                  type="monotone" 
                  dataKey="completed_per_second" 
                  name="Completed" 
                  stroke="#06b6d4" 
                  fill="url(#completedGrad)" 
                  strokeWidth={2.5} 
                />
                <Area 
                  type="monotone" 
                  dataKey="failed_per_second" 
                  name="Failed" 
                  stroke="#f43f5e" 
                  fill="url(#failedGrad)" 
                  strokeWidth={2} 
                />
                <Area 
                  type="monotone" 
                  dataKey="retry_per_second" 
                  name="Retrying" 
                  stroke="#a855f7" 
                  fill="url(#retryGrad)" 
                  strokeWidth={1.5} 
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Latency Quantiles & Request Rate Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Latency Histogram Quantiles Chart */}
        <div className="lg:col-span-2 rounded-3xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Gauge className="h-4 w-4 text-sky-400" /> Execution Latency Quantiles (P50, P95, P99)
              </h3>
              <p className="text-xs text-slate-400">Histogram processing duration in milliseconds</p>
            </div>
            <div className="flex items-center gap-3 text-[11px] font-mono">
              <span className="text-sky-400">P50: {latestVals.p50_ms}ms</span>
              <span className="text-indigo-400">P95: {latestVals.p95_ms}ms</span>
              <span className="text-purple-400">P99: {latestVals.p99_ms}ms</span>
            </div>
          </div>

          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={seriesPoints} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time_label" stroke="#64748b" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 10, fill: '#94a3b8' }} unit=" ms" />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '11px' }} />
                <Line type="monotone" dataKey="p50_ms" name="P50 Median" stroke="#06b6d4" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="p95_ms" name="P95 Tail" stroke="#6366f1" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="p99_ms" name="P99 SLA" stroke="#a855f7" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* HTTP Request Rate Chart */}
        <div className="rounded-3xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Zap className="h-4 w-4 text-emerald-400" /> API Request Rate
              </h3>
              <p className="text-xs text-slate-400">HTTP requests / second</p>
            </div>
          </div>

          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={seriesPoints} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time_label" stroke="#64748b" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '11px' }} />
                <Area type="monotone" dataKey="http_rate" name="HTTP Rate (req/s)" stroke="#10b981" fill="#10b981" fillOpacity={0.15} strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Job State Gauges */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-4">
        {[
          { label: 'Queued', value: jobStates?.queued, color: 'text-amber-400', bg: 'bg-amber-500/10', icon: Clock },
          { label: 'Claimed', value: jobStates?.claimed, color: 'text-sky-400', bg: 'bg-sky-500/10', icon: PlayCircle },
          { label: 'Running', value: jobStates?.running, color: 'text-blue-400', bg: 'bg-blue-500/10', icon: Zap },
          { label: 'Completed', value: jobStates?.completed, color: 'text-emerald-400', bg: 'bg-emerald-500/10', icon: CheckCircle2 },
          { label: 'Failed', value: jobStates?.failed, color: 'text-rose-400', bg: 'bg-rose-500/10', icon: AlertTriangle },
          { label: 'Retry Wait', value: jobStates?.retry_waiting, color: 'text-orange-400', bg: 'bg-orange-500/10', icon: RefreshCw },
          { label: 'Scheduled', value: jobStates?.scheduled, color: 'text-indigo-400', bg: 'bg-indigo-500/10', icon: Cpu },
          { label: 'Dead Letter', value: jobStates?.dead_letter, color: 'text-red-500', bg: 'bg-red-500/10', icon: ShieldAlert },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 shadow-lg">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">{item.label}</span>
                <div className={`p-1.5 rounded-xl ${item.bg} ${item.color}`}>
                  <Icon className="h-3.5 w-3.5" />
                </div>
              </div>
              <div className={`text-xl font-bold font-mono mt-2 ${item.color}`}>
                {item.value ?? 0}
              </div>
            </div>
          );
        })}
      </div>

      {/* Worker Telemetry & Queue Health */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Workers Telemetry */}
        <div className="rounded-3xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Server className="h-4 w-4 text-emerald-400" /> Worker Nodes ({workers.length})
            </h3>
            <span className="text-xs text-slate-400 font-mono">3s Heartbeat Sync</span>
          </div>

          {workers.length === 0 ? (
            <p className="text-xs text-slate-500 italic py-4">No active worker nodes registered.</p>
          ) : (
            <div className="space-y-3">
              {workers.map((w) => {
                const capPct = Math.min(100, Math.round(w.capacity_ratio * 100));
                return (
                  <div key={w.id} className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-2xl flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={`h-2.5 w-2.5 rounded-full ${w.status === 'ACTIVE' ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`} />
                        <span className="text-xs font-bold text-white font-mono">{w.hostname}</span>
                        <span className="text-[10px] font-mono text-slate-500">({w.ip_address})</span>
                      </div>
                      <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold ${
                        w.status === 'ACTIVE' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}>
                        {w.status}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs text-slate-400 font-mono pt-1">
                      <span>Active Tasks: {w.active_jobs} / {w.max_concurrency}</span>
                      <span>Capacity: {capPct}%</span>
                    </div>

                    <div className="w-full bg-slate-900 h-2 rounded-full overflow-hidden">
                      <div 
                        className={`h-full transition-all duration-500 ${capPct > 80 ? 'bg-rose-500' : capPct > 50 ? 'bg-amber-500' : 'bg-sky-500'}`}
                        style={{ width: `${capPct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Queue Concurrency Health */}
        <div className="rounded-3xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Layers className="h-4 w-4 text-indigo-400" /> Queue Health & Concurrency ({queues.length})
            </h3>
            <span className="text-xs text-slate-400 font-mono">Row Locks</span>
          </div>

          {queues.length === 0 ? (
            <p className="text-xs text-slate-500 italic py-4">No active queues defined.</p>
          ) : (
            <div className="space-y-3">
              {queues.map((q) => (
                <div key={q.id} className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-2xl flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-xs font-bold text-white">{q.name}</span>
                      <span className="text-[10px] text-slate-400 ml-2 font-mono">({q.project_name})</span>
                    </div>
                    <span className="text-xs font-mono font-semibold text-indigo-400">{q.utilization_pct}% Util</span>
                  </div>

                  <div className="flex items-center justify-between text-xs text-slate-400 font-mono pt-1">
                    <span>Active: {q.active_jobs} / Max {q.concurrency_limit}</span>
                    <span>Queued Backlog: {q.queued_jobs}</span>
                  </div>

                  <div className="w-full bg-slate-900 h-2 rounded-full overflow-hidden">
                    <div 
                      className="bg-indigo-500 h-full transition-all duration-500"
                      style={{ width: `${Math.min(100, q.utilization_pct)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
