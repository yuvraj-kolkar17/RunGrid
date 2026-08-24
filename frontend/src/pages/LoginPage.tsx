import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { register } from '../services/auth';
import { Server, UserCheck, Shield } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { loginUser } = useAuth();

  const [isRegistering, setIsRegistering] = useState<boolean>(false);
  const [email, setEmail] = useState<string>('owner@demo.com');
  const [password, setPassword] = useState<string>('Password123!');
  const [organizationName, setOrganizationName] = useState<string>('Acme Engineering');

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      if (isRegistering) {
        await register(email, password, organizationName);
      }
      await loginUser(email, password);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickSelect = (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword('Password123!');
    setIsRegistering(false);
    setError(null);
  };


  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 font-sans relative overflow-hidden">
      <div className="absolute -top-40 -left-40 h-[500px] w-[500px] rounded-full bg-sky-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 h-[500px] w-[500px] rounded-full bg-indigo-600/10 blur-[120px] pointer-events-none" />

      <div className="relative w-full max-w-md rounded-3xl bg-slate-900/80 border border-slate-800/80 p-8 shadow-2xl backdrop-blur-xl space-y-6">
        <div className="text-center space-y-2">
          <div className="mx-auto h-12 w-12 rounded-2xl bg-gradient-to-tr from-sky-600 to-indigo-600 flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-sky-600/30">
            <Server className="h-6 w-6" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            {isRegistering ? 'Create Engine Account' : 'Sign in to Dashboard'}
          </h1>
          <p className="text-xs text-slate-400">
            Distributed Job Scheduler Management Platform
          </p>
        </div>

        {error && (
          <div className="p-3 text-xs rounded-xl bg-rose-950/60 text-rose-300 border border-rose-800/60 font-medium leading-relaxed">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {isRegistering && (
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Organization Name</label>
              <input
                type="text"
                required
                value={organizationName}
                onChange={(e) => setOrganizationName(e.target.value)}
                className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-sky-500 font-mono"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Email Address</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-sky-500 font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-sky-500 font-mono"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-xl bg-gradient-to-r from-sky-600 to-indigo-600 px-4 py-3 text-xs font-semibold text-white hover:from-sky-500 hover:to-indigo-500 transition-all shadow-lg shadow-sky-600/25 disabled:opacity-50 mt-2"
          >
            {isLoading ? 'Authenticating...' : isRegistering ? 'Register & Sign In' : 'Sign In'}
          </button>
        </form>

        <div className="pt-3 border-t border-slate-800/80 space-y-2">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider text-center">
            Quick Fill Demo Persona
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => handleQuickSelect('owner@demo.com')}
              className="p-2 rounded-xl bg-purple-950/40 border border-purple-800/40 text-purple-300 hover:bg-purple-900/40 text-[11px] font-semibold flex items-center justify-center gap-1.5 transition-colors"
            >
              <Shield className="h-3 w-3" />
              <span>Owner</span>
            </button>

            <button
              type="button"
              onClick={() => handleQuickSelect('admin@demo.com')}
              className="p-2 rounded-xl bg-sky-950/40 border border-sky-800/40 text-sky-300 hover:bg-sky-900/40 text-[11px] font-semibold flex items-center justify-center gap-1.5 transition-colors"
            >
              <UserCheck className="h-3 w-3" />
              <span>Admin</span>
            </button>
          </div>
        </div>

        <div className="text-center pt-2 border-t border-slate-800/80">
          <button
            type="button"
            onClick={() => {
              setIsRegistering(!isRegistering);
              setError(null);
            }}
            className="text-xs text-sky-400 hover:underline"
          >
            {isRegistering ? 'Already have an account? Sign in' : "Don't have an account? Register organization"}
          </button>
        </div>
      </div>
    </div>
  );
};
