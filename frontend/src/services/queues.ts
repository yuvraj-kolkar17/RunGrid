import api from './api';
import type { Queue, QueueStats } from '../types/api';

export async function getQueues(): Promise<Queue[]> {
  const response = await api.get<any>('/api/v1/queues');
  if (Array.isArray(response.data)) {
    return response.data;
  }
  if (response.data && Array.isArray(response.data.items)) {
    return response.data.items;
  }
  return [];
}

export async function createQueue(data: {
  project_id: string;
  name: string;
  concurrency_limit: number;
  priority: number;
}): Promise<Queue> {
  const response = await api.post<Queue>('/api/v1/queues', data);
  return response.data;
}

export async function pauseQueue(queueId: string): Promise<Queue> {
  const response = await api.patch<Queue>(`/api/v1/queues/${queueId}/pause`);
  return response.data;
}

export async function resumeQueue(queueId: string): Promise<Queue> {
  const response = await api.patch<Queue>(`/api/v1/queues/${queueId}/resume`);
  return response.data;
}

export async function getQueueStats(queueId: string): Promise<QueueStats> {
  const response = await api.get<QueueStats>(`/api/v1/queues/${queueId}/stats`);
  return response.data;
}
