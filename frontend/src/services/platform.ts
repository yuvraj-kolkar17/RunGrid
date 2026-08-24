import api from './api';
import type {
  PlatformOverview,
  ObservabilityMetrics,
  ObservabilityTimeSeriesResponse,
  BatchSubmissionList,

  BatchSubmissionDetail,
  WorkflowsResponse,
  RateLimitStatus,
  RateLimitTestResult,
  FailureAnalysisResponse,
} from '../types/api';

export const platformService = {
  async getOverview(): Promise<PlatformOverview> {
    const response = await api.get<PlatformOverview>('/platform/overview');
    return response.data;
  },

  async getObservability(): Promise<ObservabilityMetrics> {
    const response = await api.get<ObservabilityMetrics>('/platform/observability');
    return response.data;
  },

  async getTimeSeries(range = '15m', step?: string): Promise<ObservabilityTimeSeriesResponse> {
    const response = await api.get<ObservabilityTimeSeriesResponse>('/platform/observability/timeseries', {
      params: { range, step },
    });
    return response.data;
  },


  async getBatches(page = 1, pageSize = 20): Promise<BatchSubmissionList> {
    const response = await api.get<BatchSubmissionList>('/platform/batches', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  async getBatchDetail(batchId: string): Promise<BatchSubmissionDetail> {
    const response = await api.get<BatchSubmissionDetail>(`/platform/batches/${batchId}`);
    return response.data;
  },

  async getWorkflows(): Promise<WorkflowsResponse> {
    const response = await api.get<WorkflowsResponse>('/platform/workflows');
    return response.data;
  },

  async getRateLimitStatus(): Promise<RateLimitStatus> {
    const response = await api.get<RateLimitStatus>('/platform/rate-limits');
    return response.data;
  },

  async testRateLimit(numRequests = 25): Promise<RateLimitTestResult> {
    const response = await api.post<RateLimitTestResult>(
      `/platform/rate-limits/test?num_requests=${numRequests}`
    );
    return response.data;
  },

  async getFailures(params?: {
    status_filter?: string;
    task_type?: string;
    queue_id?: string;
    page?: number;
    page_size?: number;
  }): Promise<FailureAnalysisResponse> {
    const response = await api.get<FailureAnalysisResponse>('/platform/failures', {
      params,
    });
    return response.data;
  },
};
