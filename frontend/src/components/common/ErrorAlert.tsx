import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorAlertProps {
  message: string;
  onRetry?: () => void;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({ message, onRetry }) => {
  return (
    <div className="flex items-center justify-between rounded-xl bg-rose-950/40 p-4 border border-rose-800/60 text-rose-300 my-4 shadow-lg shadow-rose-950/40">
      <div className="flex items-center gap-3">
        <AlertTriangle className="h-5 w-5 text-rose-400 shrink-0" />
        <span className="text-sm font-medium">{message}</span>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 rounded-lg bg-rose-900/60 px-3 py-1.5 text-xs font-semibold text-rose-200 hover:bg-rose-800 transition-colors border border-rose-700/50"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
};
