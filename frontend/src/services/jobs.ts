import api from './api';
import type { Job, PaginatedJobs, ScheduledJob, BatchJobCreateItem, BatchJobCreateResponse, JobDependency } from '../types/api';

export interface GetJobsParams {
  page?: number;
  page_size?: number;
  status?: string;
  queue_id?: string;
  priority?: number;
  task_type?: string;
  search?: string;
}

export async function getJobs(params?: GetJobsParams): Promise<PaginatedJobs> {
  const response = await api.get<PaginatedJobs>('/api/v1/jobs', { params });
  return response.data;
}

export async function getJob(jobId: string): Promise<Job> {
  const response = await api.get<Job>(`/api/v1/jobs/${jobId}`);
  return response.data;
}

export async function submitJob(data: {
  queue_id: string;
  task_type: string;
  payload?: Record<string, any>;
  priority?: number;
  delay?: number;
  retry_policy_id?: string;
  max_retries?: number;
}): Promise<Job> {
  const response = await api.post<Job>('/api/v1/jobs', data);
  return response.data;
}

export async function submitBatchJobs(jobs: BatchJobCreateItem[]): Promise<BatchJobCreateResponse> {
  const response = await api.post<BatchJobCreateResponse>('/api/v1/jobs/batch', { jobs });
  return response.data;
}

export async function addJobDependency(jobId: string, dependsOnJobId: string): Promise<JobDependency> {
  const response = await api.post<JobDependency>(`/api/v1/jobs/${jobId}/dependencies`, {
    depends_on_job_id: dependsOnJobId,
  });
  return response.data;
}

export async function submitScheduledJob(data: {
  project_id: string;
  queue_id: string;
  name: string;
  cron_expression: string;
  payload?: Record<string, any>;
  is_active?: boolean;
}): Promise<ScheduledJob> {
  const response = await api.post<ScheduledJob>('/api/v1/jobs/scheduled', data);
  return response.data;
}

export async function retryJob(jobId: string): Promise<Job> {
  const response = await api.post<Job>(`/api/v1/jobs/${jobId}/retry`);
  return response.data;
}
