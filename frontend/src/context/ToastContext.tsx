import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { AlertCircle, CheckCircle2, Info, AlertTriangle, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastItem {
  id: string;
  message: string;
  title?: string;
  type: ToastType;
}

interface ToastContextType {
  addToast: (message: string, type?: ToastType, title?: string) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback((message: string, type: ToastType = 'info', title?: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev.slice(-4), { id, message, title, type }]);
    
    // Auto dismiss after 5 seconds
    setTimeout(() => {
      removeToast(id);
    }, 5000);
  }, [removeToast]);

  useEffect(() => {
    const handleRateLimit = (e: Event) => {
      const customEvent = e as CustomEvent<{ message: string }>;
      addToast(
        customEvent.detail?.message || "You're sending requests too quickly. Please wait a moment and try again.",
        'warning',
        'Rate Limit Exceeded'
      );
    };

    window.addEventListener('api-rate-limit', handleRateLimit);
    return () => {
      window.removeEventListener('api-rate-limit', handleRateLimit);
    };
  }, [addToast]);

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      {/* Floating Toast Portal Stack */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-md w-full px-4 pointer-events-none">
        {toasts.map((toast) => {
          const isError = toast.type === 'error';
          const isWarning = toast.type === 'warning';
          const isSuccess = toast.type === 'success';

          return (
            <div
              key={toast.id}
              className={`pointer-events-auto flex items-start gap-3 p-4 rounded-xl border shadow-2xl backdrop-blur-xl transition-all duration-200 animate-in fade-in slide-in-from-top-2 ${
                isError
                  ? 'bg-rose-950/90 border-rose-800/80 text-rose-100'
                  : isWarning
                  ? 'bg-amber-950/90 border-amber-800/80 text-amber-100'
                  : isSuccess
                  ? 'bg-emerald-950/90 border-emerald-800/80 text-emerald-100'
                  : 'bg-slate-900/90 border-slate-800 text-slate-100'
              }`}
            >
              <div className="shrink-0 mt-0.5">
                {isError && <AlertCircle className="h-5 w-5 text-rose-400" />}
                {isWarning && <AlertTriangle className="h-5 w-5 text-amber-400" />}
                {isSuccess && <CheckCircle2 className="h-5 w-5 text-emerald-400" />}
                {toast.type === 'info' && <Info className="h-5 w-5 text-sky-400" />}
              </div>

              <div className="flex-1 min-w-0">
                {toast.title && (
                  <h4 className="text-xs font-semibold tracking-wide uppercase opacity-90 mb-0.5">
                    {toast.title}
                  </h4>
                )}
                <p className="text-xs font-medium leading-relaxed">{toast.message}</p>
              </div>

              <button
                onClick={() => removeToast(toast.id)}
                className="shrink-0 p-1 text-slate-400 hover:text-white rounded-lg transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = (): ToastContextType => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
};
