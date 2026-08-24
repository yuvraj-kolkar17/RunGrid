import React, { useEffect, useState } from 'react';
import { getMetrics } from '../services/metrics';
import type { WorkerNodeMetric, WorkerOverviewMetrics } from '../types/api';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import { truncateUuid } from '../utils/formatters';
import { POLLING_INTERVALS } from '../utils/constants';
import { Cpu, Server, Activity, RefreshCw, AlertTriangle } from 'lucide-react';

export const WorkersPage: React.FC = () => {
  const [nodes, setNodes] = useState<WorkerNodeMetric[]>([]);
  const [overview, setOverview] = useState<WorkerOverviewMetrics | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchWorkers = async () => {
    try {
      const data = await getMetrics();
      setNodes(data.worker_nodes || []);
      setOverview(data.workers || data.worker_metrics || null);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load worker metrics.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkers();
    const interval = setInterval(fetchWorkers, POLLING_INTERVALS.WORKERS);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">Worker Cluster Infrastructure</h1>
          <p className="mt-1 text-xs text-slate-400">
            Real-time status, heartbeat freshness, and concurrency capacity of active worker nodes
          </p>
        </div>
        <button
          onClick={fetchWorkers}
          className="flex items-center gap-2 rounded-xl bg-slate-900 border border-slate-800 px-3.5 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      {error && <ErrorAlert message={error} onRetry={fetchWorkers} />}

      {overview && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          <div className="p-4 bg-slate-900/60 rounded-2xl border border-slate-800/80 space-y-1">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Total Workers</span>
              <Server className="h-4 w-4 text-sky-400" />
            </div>
            <div className="text-xl font-bold text-white">{overview.total_workers}</div>
            <span className="text-[10px] text-slate-500 font-mono">Registered daemons</span>
          </div>

          <div className="p-4 bg-slate-900/60 rounded-2xl border border-emerald-950/60 space-y-1">
            <div className="flex items-center justify-between text-xs text-emerald-300">
              <span>Active Workers</span>
              <Activity className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="text-xl font-bold text-emerald-400">{overview.active_workers}</div>
            <span className="text-[10px] text-emerald-300/60 font-mono">Heartbeat &lt; 30s</span>
          </div>

          <div className="p-4 bg-slate-900/60 rounded-2xl border border-amber-950/60 space-y-1">
            <div className="flex items-center justify-between text-xs text-amber-300">
              <span>Stale Workers</span>
              <AlertTriangle className="h-4 w-4 text-amber-400" />
            </div>
            <div className="text-xl font-bold text-amber-400">{overview.stale_workers ?? 0}</div>
            <span className="text-[10px] text-amber-300/60 font-mono">Heartbeat &gt; 30s</span>
          </div>

          <div className="p-4 bg-slate-900/60 rounded-2xl border border-slate-800/80 space-y-1">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Concurrency Capacity</span>
              <Cpu className="h-4 w-4 text-purple-400" />
            </div>
            <div className="text-xl font-bold text-purple-400">
              {overview.active_capacity ?? 0} / {overview.total_capacity ?? 0}
            </div>
            <span className="text-[10px] text-slate-500 font-mono">Active slots</span>
          </div>
        </div>
      )}

      {isLoading ? (
        <LoadingSkeleton type="table" count={4} />
      ) : nodes.length === 0 ? (
        <EmptyState
          title="No Worker Nodes Online"
          description="Start worker processes using python -m worker.worker or docker compose up -d."
          icon={<Cpu className="h-8 w-8 text-sky-400" />}
        />
      ) : (
        <div className="overflow-hidden rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950 text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 font-mono">
                <tr>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5">Worker ID</th>
                  <th className="px-5 py-3.5">Hostname</th>
                  <th className="px-5 py-3.5">IP Address</th>
                  <th className="px-5 py-3.5">Heartbeat Age</th>
                  <th className="px-5 py-3.5">Active Load</th>
                  <th className="px-5 py-3.5 text-right">Available Slots</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {nodes.map((node) => {
                  const hbAge = node.heartbeat_age_seconds ?? node.seconds_since_heartbeat ?? 0;
                  const health = node.health_status || (node.status === 'INACTIVE' ? 'INACTIVE' : hbAge > 60 ? 'STALE' : 'ACTIVE');
                  const utilPct = node.max_concurrency > 0 ? Math.round((node.active_jobs / node.max_concurrency) * 100) : 0;

                  return (
                    <tr key={node.worker_id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-5 py-3.5">
                        {health === 'ACTIVE' && (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 font-semibold text-[10px] tracking-wider uppercase">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                            ACTIVE
                          </span>
                        )}
                        {health === 'STALE' && (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-950/60 text-amber-400 border border-amber-800/60 font-semibold text-[10px] tracking-wider uppercase">
                            <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                            STALE
                          </span>
                        )}
                        {health === 'INACTIVE' && (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-950/60 text-rose-400 border border-rose-800/60 font-semibold text-[10px] tracking-wider uppercase">
                            <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
                            INACTIVE
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3.5 font-bold text-sky-400">
                        {truncateUuid(node.worker_id, 10)}
                      </td>
                      <td className="px-5 py-3.5 text-white font-sans font-medium">{node.hostname}</td>
                      <td className="px-5 py-3.5 text-slate-400">{node.ip_address}</td>
                      <td className="px-5 py-3.5 text-slate-300">
                        {Math.round(hbAge)}s ago
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-white">{node.active_jobs} / {node.max_concurrency}</span>
                          <span className="text-[10px] text-slate-500">({utilPct}%)</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-right font-bold text-emerald-400">
                        {node.available_capacity} slots
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
