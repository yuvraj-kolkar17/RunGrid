import React from 'react';
import { Link } from 'react-router-dom';
import type { JobDependency, Job } from '../../types/api';
import { StatusBadge } from '../common/StatusBadge';
import { GitCommit, ArrowRight, Link2, Plus } from 'lucide-react';

interface DependencyGraphProps {
  currentJob: Job;
  dependencies?: JobDependency[];
  dependents?: JobDependency[];
  onOpenAddModal: () => void;
}

export const DependencyGraph: React.FC<DependencyGraphProps> = ({
  currentJob,
  dependencies = [],
  dependents = [],
  onOpenAddModal,
}) => {
  const hasParents = dependencies.length > 0;
  const hasChildren = dependents.length > 0;

  return (
    <div className="rounded-2xl bg-slate-900/60 border border-slate-800/80 p-5 space-y-4 shadow-xl">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <GitCommit className="h-4 w-4 text-sky-400" />
            <h3 className="text-sm font-bold text-white">Customer Reporting Workflow</h3>
          </div>
          <p className="text-xs text-slate-400 pl-6">
            Jobs execute only after their prerequisites complete.
          </p>
        </div>
        <button
          onClick={onOpenAddModal}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-sky-600/20 hover:bg-sky-600/30 text-sky-300 border border-sky-500/30 text-xs font-semibold rounded-xl transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>Add Parent Dependency</span>
        </button>
      </div>

      {!hasParents && !hasChildren ? (
        <div className="p-6 text-center bg-slate-950/40 rounded-xl border border-slate-800/40 space-y-2">
          <Link2 className="h-8 w-8 text-slate-600 mx-auto" />
          <p className="text-xs text-slate-400">No parent or child dependencies linked to this job.</p>
        </div>
      ) : (
        <div className="flex flex-col md:flex-row items-stretch justify-between gap-4 overflow-x-auto p-2">
          {/* Parents (Depends On) */}
          <div className="flex-1 space-y-2 min-w-[220px]">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Parent Dependencies ({dependencies.length})
            </div>
            {hasParents ? (
              <div className="space-y-2">
                {dependencies.map((dep) => (
                  <Link
                    key={dep.id}
                    to={`/jobs/${dep.depends_on_job_id}`}
                    className="block p-3 bg-slate-950 border border-slate-800 hover:border-sky-500/50 rounded-xl transition-all group"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs text-sky-400 font-semibold group-hover:underline">
                        {dep.depends_on_job_id.substring(0, 8)}...
                      </span>
                      {dep.depends_on_job?.status && (
                        <StatusBadge status={dep.depends_on_job.status} size="sm" />
                      )}
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono">
                      Task: {dep.depends_on_job?.task_type || 'Parent Job'}
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="p-3 text-[11px] text-slate-400 italic bg-slate-950/40 rounded-xl border border-slate-800/40">
                No prerequisites required.
              </div>
            )}
          </div>

          {/* Flow Connector Arrow */}
          <div className="flex items-center justify-center text-slate-600 shrink-0">
            <ArrowRight className="h-6 w-6 hidden md:block" />
            <div className="h-6 w-0.5 bg-slate-800 md:hidden" />
          </div>

          {/* Current Job Node */}
          <div className="flex-1 space-y-2 min-w-[220px]">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Current Target Node
            </div>
            <div className="p-3.5 bg-sky-950/40 border-2 border-sky-500/40 rounded-xl shadow-lg space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-white font-bold">
                  {currentJob.id.substring(0, 8)}...
                </span>
                <StatusBadge status={currentJob.status} size="sm" />
              </div>
              <div className="text-xs text-sky-200 font-mono truncate">
                {currentJob.task_type}
              </div>
            </div>
          </div>

          {/* Flow Connector Arrow */}
          <div className="flex items-center justify-center text-slate-600 shrink-0">
            <ArrowRight className="h-6 w-6 hidden md:block" />
            <div className="h-6 w-0.5 bg-slate-800 md:hidden" />
          </div>

          {/* Children (Dependents) */}
          <div className="flex-1 space-y-2 min-w-[220px]">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Child Dependents ({dependents.length})
            </div>
            {hasChildren ? (
              <div className="space-y-2">
                {dependents.map((dep) => (
                  <Link
                    key={dep.id}
                    to={`/jobs/${dep.job_id}`}
                    className="block p-3 bg-slate-950 border border-slate-800 hover:border-indigo-500/50 rounded-xl transition-all group"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs text-indigo-400 font-semibold group-hover:underline">
                        {dep.job_id.substring(0, 8)}...
                      </span>
                      {dep.depends_on_job?.status && (
                        <StatusBadge status={dep.depends_on_job.status} size="sm" />
                      )}
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono">
                      Blocked Child
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="p-3 text-[11px] text-slate-400 italic bg-slate-950/40 rounded-xl border border-slate-800/40">
                No downstream jobs waiting.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
