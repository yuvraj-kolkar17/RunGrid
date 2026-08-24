import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Flame, RefreshCw, AlertTriangle, CheckCircle2, 
  HelpCircle, ArrowRight 
} from 'lucide-react';
import { platformService } from '../../services/platform';
import type { FailureAnalysisItem, FailureAnalysisResponse } from '../../types/api';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';

export const FailureAnalysisPage: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<FailureAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchFailures = async () => {
    try {
      setRefreshing(true);
      const res = await platformService.getFailures();
      setData(res);
    } catch (err) {
      console.error('Failed to load failure analysis items:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchFailures();
  }, []);

  if (loading) {
    return <LoadingSkeleton type="table" />;
  }

  return (
    <div className="space-y-8 pb-10">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-slate-900/90 border border-slate-800 p-6 rounded-3xl shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold uppercase bg-rose-500/10 text-rose-400 border border-rose-500/20">
              Root Cause Diagnostics
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <Flame className="h-7 w-7 text-rose-400" /> Failure Analysis Operations
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Automated log inspection, failure classification, and operational remediation suggestions for failed job executions.
          </p>
        </div>

        <button
          onClick={fetchFailures}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-2xl text-xs font-semibold border border-slate-700 transition-all shadow-md active:scale-95 disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin text-rose-400' : ''}`} />
          Refresh Diagnostics
        </button>
      </div>

      {/* Top Failure Causes Summary */}
      {(data?.top_failure_causes || []).length > 0 && (
        <div className="rounded-3xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl space-y-4">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider text-slate-400">
            Top Classified Failure Categories
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {(data?.top_failure_causes || []).map((cat, idx) => (
              <div key={idx} className="rounded-2xl bg-slate-950/60 p-4 border border-slate-800">
                <div className="text-xs text-rose-400 font-semibold">{cat.cause}</div>
                <div className="text-2xl font-bold font-mono text-white mt-1">{cat.count} <span className="text-xs font-normal text-slate-400">jobs</span></div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Failure Analysis Item Cards */}
      {(!data?.items || data.items.length === 0) ? (
        <div className="rounded-3xl bg-slate-900/90 border border-slate-800 p-12 text-center text-slate-400 shadow-xl">
          <CheckCircle2 className="h-10 w-10 text-emerald-400 mx-auto mb-3" />
          <p className="text-sm font-semibold text-white">No failed jobs detected</p>
          <p className="text-xs text-slate-400 mt-1">All executions across active queues are completing cleanly.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {(data?.items || []).map((item: FailureAnalysisItem) => (
            <div
              key={item.id}
              className="rounded-3xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl space-y-5"
            >
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold uppercase bg-rose-500/10 text-rose-400 border border-rose-500/20">
                      {item.status}
                    </span>
                    <span className="text-xs font-mono text-slate-400">Job ID: {item.id}</span>
                  </div>
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    {item.title}
                  </h3>
                  <div className="text-xs text-slate-400 font-mono mt-0.5">Task Type: {item.task_type}</div>
                </div>

                <button
                  onClick={() => navigate(`/jobs/${item.id}`)}
                  className="flex items-center gap-1.5 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-sky-400 rounded-xl text-xs font-semibold border border-slate-700 transition-all"
                >
                  Inspect Job Logs <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>

              {/* Diagnostic Box */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-1">
                  <div className="text-slate-400 font-semibold flex items-center gap-1.5">
                    <AlertTriangle className="h-3.5 w-3.5 text-rose-400" /> What Happened
                  </div>
                  <div className="text-slate-200">{item.failure_analysis.summary}</div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-1">
                  <div className="text-slate-400 font-semibold flex items-center gap-1.5">
                    <HelpCircle className="h-3.5 w-3.5 text-amber-400" /> Likely Cause
                  </div>
                  <div className="text-slate-200">{item.failure_analysis.likely_cause}</div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-1">
                  <div className="text-slate-400 font-semibold flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> Recommended Action
                  </div>
                  <div className="text-slate-200">{item.failure_analysis.recommended_action}</div>
                </div>
              </div>

              {/* Error Trace Snippet */}
              {item.error && (
                <div className="p-3.5 rounded-2xl bg-slate-950/90 border border-rose-500/20 text-xs font-mono text-rose-300 overflow-x-auto">
                  <span className="text-slate-400 font-semibold uppercase text-[10px] block mb-1">Raw Exception Message:</span>
                  {item.error}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
