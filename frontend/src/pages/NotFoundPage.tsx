import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-4">
      <h1 className="text-6xl font-extrabold text-slate-700 font-mono">404</h1>
      <h2 className="text-xl font-bold text-white">Page Not Found</h2>
      <p className="text-xs text-slate-400 max-w-sm">
        The requested dashboard route does not exist or has been moved.
      </p>
      <button
        onClick={() => navigate('/dashboard')}
        className="flex items-center gap-2 rounded-xl bg-sky-600 px-4 py-2 text-xs font-semibold text-white hover:bg-sky-500 transition-colors shadow-lg shadow-sky-600/20"
      >
        <ArrowLeft className="h-4 w-4" />
        <span>Return to Dashboard</span>
      </button>
    </div>
  );
};
