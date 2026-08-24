import React from 'react';
import type { JobStatus } from '../../types/api';
import { CheckCircle2, Clock, Play, AlertOctagon, RotateCw, Skull, ArrowRight } from 'lucide-react';

interface JobTimelineProps {
  status: JobStatus;
  attempt: number;
}

export const JobTimeline: React.FC<JobTimelineProps> = ({ status, attempt }) => {
  const isFailedPath = status === 'FAILED' || status === 'RETRY_WAITING' || status === 'DEAD_LETTER';

  const steps = [
    { key: 'QUEUED', label: 'Queued', icon: Clock },
    { key: 'CLAIMED', label: 'Claimed', icon: ArrowRight },
    { key: 'RUNNING', label: 'Running', icon: Play },
    ...(isFailedPath
      ? [
          { key: 'FAILED', label: 'Failed', icon: AlertOctagon },
          ...(status === 'RETRY_WAITING'
            ? [{ key: 'RETRY_WAITING', label: 'Retry Waiting', icon: RotateCw }]
            : []),
          ...(status === 'DEAD_LETTER'
            ? [{ key: 'DEAD_LETTER', label: 'Dead Letter Queue', icon: Skull }]
            : []),
        ]
      : [{ key: 'COMPLETED', label: 'Completed', icon: CheckCircle2 }]),
  ];

  const getStepState = (stepKey: string) => {
    if (status === stepKey) return 'active';

    const order = ['SCHEDULED', 'QUEUED', 'CLAIMED', 'RUNNING', 'COMPLETED'];
    const currentIndex = order.indexOf(status);
    const stepIndex = order.indexOf(stepKey);

    if (currentIndex !== -1 && stepIndex !== -1 && stepIndex < currentIndex) {
      return 'passed';
    }
    if (isFailedPath && (stepKey === 'QUEUED' || stepKey === 'CLAIMED' || stepKey === 'RUNNING')) {
      return 'passed';
    }

    return 'upcoming';
  };

  return (
    <div className="rounded-2xl bg-slate-900/80 p-6 border border-slate-800 shadow-xl backdrop-blur-sm">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-sm font-semibold text-white uppercase tracking-wider">
          Lifecycle Transition Pipeline
        </h3>
        <span className="text-xs font-mono text-slate-400">
          Attempt {attempt}
        </span>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4">
        {steps.map((step, i) => {
          const state = getStepState(step.key);
          const Icon = step.icon;

          let colorClasses = 'bg-slate-950 text-slate-600 border-slate-800';
          if (state === 'active') {
            if (step.key === 'COMPLETED') colorClasses = 'bg-emerald-950/80 text-emerald-400 border-emerald-500 shadow-lg shadow-emerald-950';
            else if (step.key === 'RUNNING') colorClasses = 'bg-sky-950/80 text-sky-400 border-sky-500 animate-pulse shadow-lg shadow-sky-950';
            else if (step.key === 'DEAD_LETTER') colorClasses = 'bg-red-950/80 text-red-400 border-red-500 shadow-lg shadow-red-950';
            else if (step.key === 'FAILED' || step.key === 'RETRY_WAITING') colorClasses = 'bg-rose-950/80 text-rose-400 border-rose-500 shadow-lg shadow-rose-950';
            else colorClasses = 'bg-amber-950/80 text-amber-400 border-amber-500';
          } else if (state === 'passed') {
            colorClasses = 'bg-slate-900 text-sky-400 border-sky-800/60';
          }

          return (
            <React.Fragment key={step.key}>
              <div className="flex items-center gap-3">
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-xl border text-sm font-bold transition-all ${colorClasses}`}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <div>
                  <span className="block text-xs font-semibold text-white">{step.label}</span>
                  <span className="block text-[10px] text-slate-500 capitalize">{state}</span>
                </div>
              </div>
              {i < steps.length - 1 && (
                <div className="hidden sm:block flex-1 h-0.5 bg-slate-800 mx-2 min-w-[2rem]" />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};
