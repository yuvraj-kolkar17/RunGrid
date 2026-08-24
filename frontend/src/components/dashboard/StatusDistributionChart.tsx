import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import type { SystemOverviewMetrics } from '../../types/api';

interface StatusDistributionChartProps {
  metrics: SystemOverviewMetrics;
}

const COLOR_MAP: Record<string, string> = {
  Completed: '#10b981',
  Running: '#38bdf8',
  Queued: '#f59e0b',
  'Retry Waiting': '#f97316',
  'Dead Letter': '#ef4444',
  Failed: '#f43f5e',
  Scheduled: '#a855f7',
};

export const StatusDistributionChart: React.FC<StatusDistributionChartProps> = ({ metrics }) => {
  const data = [
    { name: 'Completed', value: metrics.completed },
    { name: 'Running', value: metrics.running },
    { name: 'Queued', value: metrics.queued },
    { name: 'Retry Waiting', value: metrics.retry_waiting },
    { name: 'Dead Letter', value: metrics.dead_letter },
    { name: 'Failed', value: metrics.failed },
    { name: 'Scheduled', value: metrics.scheduled },
  ].filter((item) => item.value > 0);

  if (data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-xs text-slate-500 font-mono">
        No active job status metrics available
      </div>
    );
  }

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={80}
            paddingAngle={4}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLOR_MAP[entry.name] || '#64748b'} stroke="#0f172a" strokeWidth={2} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.75rem', color: '#fff' }}
            itemStyle={{ color: '#38bdf8' }}
          />
          <Legend
            verticalAlign="bottom"
            height={36}
            iconType="circle"
            formatter={(value) => <span className="text-xs text-slate-300">{value}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};
