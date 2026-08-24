import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Layers, RefreshCw, GitCommit, ArrowRight 
} from 'lucide-react';
import { platformService } from '../../services/platform';
import type { WorkflowsResponse, WorkflowItem, WorkflowNode } from '../../types/api';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';

export const WorkflowsPage: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<WorkflowsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchWorkflows = async () => {
    try {
      setRefreshing(true);
      const res = await platformService.getWorkflows();
      setData(res);
    } catch (err) {
      console.error('Failed to load workflow DAGs:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchWorkflows();
  }, []);

  if (loading) {
    return <LoadingSkeleton type="card" />;
  }

  const getNodeBadge = (node: WorkflowNode) => {
    if (node.is_blocked) {
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
          Blocked (Prerequisites)
        </span>
      );
    }
    switch (node.status) {
      case 'COMPLETED':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            Completed
          </span>
        );
      case 'RUNNING':
      case 'CLAIMED':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-sky-500/15 text-sky-400 border border-sky-500/30">
            Running
          </span>
        );
      case 'FAILED':
      case 'DEAD_LETTER':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
            Failed
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            {node.status}
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
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold uppercase bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              DAG Visualizer
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <Layers className="h-7 w-7 text-indigo-400" /> Workflow Dependency Graphs
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Inspect real-time directed acyclic graphs (DAGs), prerequisite execution states, and blocked job queues.
          </p>
        </div>

        <button
          onClick={fetchWorkflows}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-2xl text-xs font-semibold border border-slate-700 transition-all shadow-md active:scale-95 disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin text-indigo-400' : ''}`} />
          Refresh DAGs
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 shadow-lg">
          <div className="text-xs text-slate-400 font-semibold uppercase">Total Workflows</div>
          <div className="text-2xl font-bold font-mono text-white mt-1">{(data?.workflows || []).length}</div>
        </div>
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 shadow-lg">
          <div className="text-xs text-slate-400 font-semibold uppercase">Total Dependency Edges</div>
          <div className="text-2xl font-bold font-mono text-slate-200 mt-1">{data?.total_dependencies ?? 0}</div>
        </div>
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 shadow-lg">
          <div className="text-xs text-amber-400 font-semibold uppercase">Blocked Jobs</div>
          <div className="text-2xl font-bold font-mono text-amber-400 mt-1">
            {(data?.workflows || []).reduce((acc, wf) => acc + (wf?.blocked_jobs || 0), 0)}
          </div>
        </div>
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 shadow-lg">
          <div className="text-xs text-emerald-400 font-semibold uppercase">Completed Workflows</div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
            {(data?.workflows || []).filter((wf) => wf?.status === 'COMPLETED').length}
          </div>
        </div>
      </div>

      {/* Workflows Visual List */}
      {(!data?.workflows || data.workflows.length === 0) ? (
        <div className="rounded-3xl bg-slate-900/90 border border-slate-800 p-12 text-center text-slate-400 shadow-xl">
          <GitCommit className="h-10 w-10 text-slate-600 mx-auto mb-3" />
          <p className="text-sm font-semibold text-white">No active workflow dependencies found</p>
          <p className="text-xs text-slate-400 mt-1">
            Add job dependencies via the Job Detail view or batch creation to form connected DAG graphs.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {data?.workflows.map((wf: WorkflowItem) => (
            <div
              key={wf.id}
              className="rounded-3xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl space-y-5"
            >
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold uppercase bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                      {wf.id}
                    </span>
                    <span className="text-xs font-mono text-slate-400">{wf.total_jobs} Connected Nodes</span>
                  </div>
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <GitCommit className="h-5 w-5 text-indigo-400" /> {wf.name}
                  </h3>
                </div>

                <div className="flex items-center gap-3 text-xs">
                  <div className="px-3 py-1 rounded-full font-mono text-slate-300 bg-slate-950 border border-slate-800">
                    <span className="text-emerald-400 font-bold">{wf.completed_jobs}</span> / {wf.total_jobs} Completed
                  </div>
                </div>
              </div>

              {/* Connected Nodes Visual Flow */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {wf.nodes.map((node) => (
                  <div
                    key={node.id}
                    onClick={() => navigate(`/jobs/${node.id}`)}
                    className={`p-4 rounded-2xl border transition-all cursor-pointer group ${
                      node.is_blocked
                        ? 'bg-amber-950/20 border-amber-500/40 hover:border-amber-400 shadow-md shadow-amber-950/20'
                        : 'bg-slate-950/60 border-slate-800 hover:border-indigo-500/40 hover:bg-slate-900'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-xs font-bold text-sky-400 group-hover:underline">
                        {node.id.substring(0, 8)}...
                      </span>
                      {getNodeBadge(node)}
                    </div>
                    <div className="text-xs font-semibold text-white">{node.title}</div>
                    <div className="text-[10px] text-slate-400 font-mono mt-1">Task: {node.task_type}</div>

                    {node.parent_ids.length > 0 && (
                      <div className="mt-3 pt-2 border-t border-slate-800/80 text-[10px] text-slate-400 flex items-center gap-1 font-mono">
                        <ArrowRight className="h-3 w-3 text-indigo-400" />
                        <span>Prerequisites: {node.parent_ids.map((p) => p.substring(0, 6)).join(', ')}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
