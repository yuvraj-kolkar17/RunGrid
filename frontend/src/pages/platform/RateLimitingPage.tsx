import React, { useEffect, useState } from 'react';
import { 
  ShieldAlert, RefreshCw, Play, CheckCircle2, 
  Info, X 
} from 'lucide-react';
import { platformService } from '../../services/platform';
import type { RateLimitStatus, RateLimitTestResult } from '../../types/api';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';

export const RateLimitingPage: React.FC = () => {
  const [statusData, setStatusData] = useState<RateLimitStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [isTestModalOpen, setIsTestModalOpen] = useState(false);
  const [testRequestsCount, setTestRequestsCount] = useState(25);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<RateLimitTestResult | null>(null);

  const fetchRateLimitStatus = async () => {
    try {
      setRefreshing(true);
      const res = await platformService.getRateLimitStatus();
      setStatusData(res);
    } catch (err) {
      console.error('Failed to fetch rate limiter status:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchRateLimitStatus();
  }, []);

  const handleRunTest = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setTesting(true);
      const result = await platformService.testRateLimit(testRequestsCount);
      setTestResult(result);
      fetchRateLimitStatus();
    } catch (err) {
      console.error('Rate limit test error:', err);
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return <LoadingSkeleton type="card" />;
  }

  return (
    <div className="space-y-8 pb-10">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-slate-900/90 border border-slate-800 p-6 rounded-3xl shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold uppercase bg-amber-500/10 text-amber-400 border border-amber-500/20">
              Protection & Telemetry
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <ShieldAlert className="h-7 w-7 text-amber-400" /> API Rate Limiting & Protection
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Thread-safe sliding window rate limit status, endpoint policies, and interactive operational testing.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsTestModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-amber-600 hover:bg-amber-500 text-white rounded-2xl text-xs font-semibold shadow-lg shadow-amber-950/40 transition-all active:scale-95"
          >
            <Play className="h-3.5 w-3.5 fill-current" /> Run Rate Limit Test
          </button>
          <button
            onClick={fetchRateLimitStatus}
            disabled={refreshing}
            className="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-2xl border border-slate-700 transition-all"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin text-amber-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Architecture Notice */}
      <div className="flex items-center gap-3 bg-slate-950/80 border border-slate-800 p-4 rounded-2xl text-xs text-slate-300">
        <Info className="h-5 w-5 text-sky-400 shrink-0" />
        <div>
          <span className="font-semibold text-white">Limiter Architecture: </span>
          <span className="font-mono text-slate-300">{statusData?.architecture}</span>
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 shadow-lg">
          <div className="text-xs text-emerald-400 font-semibold uppercase">Total Requests Allowed</div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
            {statusData?.total_allowed ?? 0}
          </div>
        </div>
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 shadow-lg">
          <div className="text-xs text-amber-400 font-semibold uppercase">Total Rejections (429)</div>
          <div className="text-2xl font-bold font-mono text-amber-400 mt-1">
            {statusData?.total_rejected ?? 0}
          </div>
        </div>
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 shadow-lg">
          <div className="text-xs text-slate-400 font-semibold uppercase">Active Tracked Keys</div>
          <div className="text-2xl font-bold font-mono text-white mt-1">
            {statusData?.active_tracked_keys ?? 0}
          </div>
        </div>
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 shadow-lg">
          <div className="text-xs text-slate-400 font-semibold uppercase">Sliding Window</div>
          <div className="text-2xl font-bold font-mono text-sky-400 mt-1">
            {statusData?.active_window_seconds ?? 60}s
          </div>
        </div>
      </div>

      {/* Protected Endpoints Table */}
      <div className="rounded-3xl bg-slate-900/90 border border-slate-800 overflow-hidden shadow-xl">
        <div className="px-6 py-4 border-b border-slate-800">
          <h3 className="text-base font-bold text-white">Protected API Endpoints & Policies</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/60 text-slate-400 uppercase font-semibold border-b border-slate-800">
              <tr>
                <th className="px-6 py-3.5">Endpoint</th>
                <th className="px-6 py-3.5">Description</th>
                <th className="px-6 py-3.5">Rate Limit</th>
                <th className="px-6 py-3.5">Window</th>
                <th className="px-6 py-3.5">Key Format</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {(statusData?.protected_endpoints || []).map((ep) => (
                <tr key={ep.endpoint} className="hover:bg-slate-800/40 transition-colors">
                  <td className="px-6 py-4 font-mono font-bold text-amber-400">{ep.endpoint}</td>
                  <td className="px-6 py-4 text-slate-300">{ep.description}</td>
                  <td className="px-6 py-4 font-mono font-semibold text-white">{ep.limit} req</td>
                  <td className="px-6 py-4 font-mono">{ep.window_seconds}s</td>
                  <td className="px-6 py-4 font-mono text-slate-400">{ep.key_format}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Operator Rate Limit Test Control Modal */}
      {isTestModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-md w-full shadow-2xl space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <ShieldAlert className="h-5 w-5 text-amber-400" /> Operational Rate Limit Test
              </h3>
              <button onClick={() => setIsTestModalOpen(false)} className="text-slate-400 hover:text-white p-1">
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleRunTest} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-400 font-semibold mb-1">
                  Requests Burst Count (Trigger Limit)
                </label>
                <input
                  type="number"
                  min="1"
                  max="150"
                  value={testRequestsCount}
                  onChange={(e) => setTestRequestsCount(parseInt(e.target.value) || 1)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white font-mono focus:border-amber-500 focus:outline-none"
                />
                <p className="text-[10px] text-slate-400 mt-1">
                  Configured limit is 20 req/60s. Sending 25 requests will allow 20 and trigger 5 HTTP 429 rejections.
                </p>
              </div>

              <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsTestModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-semibold hover:bg-slate-700"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={testing}
                  className="px-4 py-2 bg-amber-600 text-white rounded-xl font-semibold hover:bg-amber-500 shadow-md active:scale-95 disabled:opacity-50"
                >
                  {testing ? 'Executing Burst...' : 'Run Test Burst'}
                </button>
              </div>
            </form>

            {/* Test Results View */}
            {testResult && (
              <div className="rounded-2xl bg-slate-950 p-4 border border-slate-800 space-y-2 mt-4 text-xs font-mono">
                <div className="text-emerald-400 font-bold flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4" /> Test Executed Cleanly
                </div>
                <div className="text-slate-300">Target Key: {testResult.tested_key}</div>
                <div className="text-slate-300">Limit: {testResult.configured_limit}</div>
                <div className="text-slate-300">Requests Sent: {testResult.requests_sent}</div>
                <div className="text-emerald-400">Accepted Requests: {testResult.allowed_requests}</div>
                <div className="text-amber-400 font-bold">HTTP 429 Rejections: {testResult.rejected_429_requests}</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
