import api from './api';
import type { SystemMetrics } from '../types/api';

export async function getMetrics(): Promise<SystemMetrics> {
  const response = await api.get<SystemMetrics>('/api/v1/metrics');
  return response.data;
}

export async function getHealth(): Promise<{ status: string }> {
  const response = await api.get<{ status: string }>('/health');
  return response.data;
}

export async function getReady(): Promise<{ status: string }> {
  const response = await api.get<{ status: string }>('/ready');
  return response.data;
}
