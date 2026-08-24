import React from 'react';
import type { FailureSummary } from '../../types/api';
import { AlertOctagon, Wrench, FileSearch, Sparkles } from 'lucide-react';

interface FailureAnalysisCardProps {
  summary: FailureSummary;
}

export const FailureAnalysisCard: React.FC<FailureAnalysisCardProps> = ({ summary }) => {
  return (
    <div className="rounded-2xl bg-rose-950/20 border border-rose-800/50 p-5 space-y-4 shadow-xl">
      <div className="flex items-center justify-between border-b border-rose-800/40 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-rose-900/50 border border-rose-700/60 flex items-center justify-center text-rose-400">
            <AlertOctagon className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-rose-200 tracking-tight">Failure Analysis</h3>
            <p className="text-[11px] text-rose-400/80">Deterministic Error Diagnostic Engine</p>
          </div>
        </div>
        <span className="px-2.5 py-1 rounded-full text-[10px] font-mono font-semibold bg-rose-900/60 text-rose-300 border border-rose-700/60 uppercase">
          {summary.error_type || 'RUNTIME_ERROR'}
        </span>
      </div>

      <div className="space-y-3 text-xs">
        {/* What Happened */}
        <div className="p-3 bg-slate-950/60 border border-rose-900/40 rounded-xl space-y-1">
          <div className="flex items-center gap-1.5 text-rose-300 font-semibold">
            <Sparkles className="h-3.5 w-3.5 text-rose-400" />
            <span>Diagnostic Summary</span>
          </div>
          <p className="text-slate-300 leading-relaxed pl-5 font-mono text-[11px]">
            {summary.summary}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* Likely Cause */}
          <div className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-xl space-y-1">
            <div className="flex items-center gap-1.5 text-amber-300 font-semibold">
              <FileSearch className="h-3.5 w-3.5 text-amber-400" />
              <span>Likely Cause</span>
            </div>
            <p className="text-slate-300 leading-relaxed font-mono text-[11px] break-words">
              {summary.likely_cause}
            </p>
          </div>

          {/* Recommended Action */}
          <div className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-xl space-y-1">
            <div className="flex items-center gap-1.5 text-sky-300 font-semibold">
              <Wrench className="h-3.5 w-3.5 text-sky-400" />
              <span>Recommended Action</span>
            </div>
            <p className="text-slate-300 leading-relaxed font-mono text-[11px]">
              {summary.recommended_action}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
