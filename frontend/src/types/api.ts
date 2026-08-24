export type JobStatus = 
  | 'SCHEDULED' 
  | 'QUEUED' 
  | 'CLAIMED' 
  | 'RUNNING' 
  | 'COMPLETED' 
  | 'FAILED' 
  | 'RETRY_WAITING' 
  | 'DEAD_LETTER';

export type UserRole = 'OWNER' | 'ADMIN' | 'MEMBER' | 'VIEWER';

export interface User {
  id: string;
  email: string;
  role: UserRole;
  organization_id: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Project {
  id: string;
  organization_id: string;
  name: string;
  created_at: string;
}

export interface Queue {
  id: string;
  project_id: string;
  name: string;
  concurrency_limit: number | null;
  priority: number;
  is_paused: boolean;
  created_at: string;
  active_jobs_count?: number;
}

export interface QueueStats {
  queued_count: number;
  running_count: number;
  claimed_count: number;
  completed_count: number;
  failed_count: number;
  dead_letter_count: number;
}

export interface JobExecution {
  id: string;
  job_id: string;
  worker_id: string | null;
  attempt: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  error: string | null;
}

export interface JobLog {
  id: string;
  job_id: string;
  execution_id: string | null;
  level: string;
  message: string;
  timestamp: string;
}

export interface FailureSummary {
  summary: string;
  likely_cause: string;
  recommended_action: string;
  error_type: string;
}

export interface JobDependency {
  id: string;
  job_id: string;
  depends_on_job_id: string;
  created_at: string;
  depends_on_job?: Job;
}

export interface Job {
  id: string;
  queue_id: string;
  status: JobStatus;
  task_type: string;
  payload: Record<string, any>;
  result?: any;
  error: string | null;
  priority: number;
  attempt: number;
  max_retries: number;
  claimed_by_worker_id: string | null;
  scheduled_at: string;
  available_at: string;
  claimed_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  lease_expires_at: string | null;
  retry_policy_id: string | null;
  created_at: string;
  updated_at: string;
  failure_summary?: FailureSummary | null;
  dependencies?: JobDependency[];
  dependents?: JobDependency[];
  executions?: JobExecution[];
  logs?: JobLog[];
}

export interface BatchJobCreateItem {
  task_type: string;
  queue_id: string;
  payload?: Record<string, any>;
  priority?: number;
  max_retries?: number;
  delay?: number;
}

export interface BatchJobCreateResponse {
  total_created: number;
  jobs: Job[];
}

export interface PaginatedJobs {
  items: Job[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ScheduledJob {
  id: string;
  project_id: string;
  queue_id: string;
  name: string;
  cron_expression: string;
  payload: Record<string, any>;
  is_active: boolean;
  next_run_at: string;
  created_at: string;
}

export interface QueueUtilization {
  queue_id: string;
  queue_name: string;
  is_paused: boolean;
  concurrency_limit: number | null;
  active_jobs: number;
  queued_jobs?: number;
  completed_jobs?: number;
  failed_jobs?: number;
  retry_waiting_jobs?: number;
  priority?: number;
  utilization_percentage: number | null;
  is_saturated?: boolean;
  has_backlog?: boolean;
}

export interface WorkerNodeMetric {
  worker_id: string;
  hostname: string;
  ip_address: string;
  status: 'ACTIVE' | 'INACTIVE' | string;
  health_status?: 'ACTIVE' | 'STALE' | 'INACTIVE' | string;
  last_heartbeat: string | null;
  seconds_since_heartbeat?: number;
  heartbeat_age_seconds?: number;
  active_jobs: number;
  max_concurrency: number;
  available_capacity: number;
  created_at: string | null;
}

export interface JobRates {
  success_rate: number;
  failure_rate: number;
  retry_rate: number;
  total_retry_attempts: number;
}

export interface SystemOverviewMetrics {
  total?: number;
  total_jobs?: number;
  queued: number;
  claimed?: number;
  running: number;
  completed: number;
  failed: number;
  retry_waiting: number;
  dead_letter: number;
  scheduled: number;
  rates?: JobRates;
}

export interface WorkerOverviewMetrics {
  total_workers: number;
  active_workers: number;
  stale_workers?: number;
  inactive_workers?: number;
  total_capacity?: number;
  active_capacity?: number;
}

export interface ThroughputMetrics {
  completed_last_5m?: number;
  completed_last_15m?: number;
  completed_last_hour: number;
  failed_last_hour?: number;
  avg_jobs_per_minute?: number;
}

export interface ExecutionPerformanceMetrics {
  completed_executions_count: number;
  failed_executions_count: number;
  avg_duration_ms: number;
  min_duration_ms: number;
  max_duration_ms: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
}

export interface SchedulerMetrics {
  active_schedules_count: number;
  due_schedules_count: number;
  total_scheduled_jobs: number;
}

export interface ReaperMetrics {
  stale_workers_detected: number;
  recovered_jobs_count: number;
  dead_letter_total: number;
}

export interface BonusFeaturesMetrics {
  batch_jobs_created: number;
  dependency_blocked_jobs: number;
  rate_limit_rejections: number;
  failure_summaries_generated: number;
}

export interface SystemMetrics {
  jobs?: SystemOverviewMetrics;
  system_overview?: SystemOverviewMetrics;
  workers?: WorkerOverviewMetrics;
  worker_metrics?: WorkerOverviewMetrics;
  queues?: QueueUtilization[];
  queue_utilization?: QueueUtilization[];
  worker_nodes?: WorkerNodeMetric[];
  throughput: ThroughputMetrics;
  execution_performance?: ExecutionPerformanceMetrics;
  scheduler?: SchedulerMetrics;
  reaper?: ReaperMetrics;
  bonus_features?: BonusFeaturesMetrics;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    request_id?: string;
  };
}

// --- Platform Operations Center Types ---

export interface PlatformOverview {
  timestamp: string;
  organization_id: string;
  summary: {
    batch_jobs_created: number;
    dependency_blocks: number;
    rate_limit_rejections: number;
    failure_analyses: number;
  };
  system_health: {
    status: 'HEALTHY' | 'DEGRADED' | 'CRITICAL' | string;
    total_workers: number;
    active_workers: number;
    stale_workers: number;
    inactive_workers: number;
    total_queues: number;
    paused_queues: number;
    total_jobs: number;
  };
}
export interface TimeSeriesPoint {
  timestamp: number;
  time_label: string;
  completed_per_second: number;
  failed_per_second: number;
  retry_per_second: number;
  dlq_per_second: number;
  throughput: number;
  http_rate: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
}

export interface ObservabilityTimeSeriesResponse {
  range: string;
  step: number;
  prometheus_status: 'HEALTHY' | 'UNREACHABLE' | string;
  series: TimeSeriesPoint[];
  latest_values: {
    throughput: number;
    completed: number;
    failed: number;
    retry: number;
    dlq: number;
    p50_ms: number;
    p95_ms: number;
    p99_ms: number;
  };
}

export interface ObservabilityMetrics {

  timestamp: string;
  prometheus?: {
    status: 'HEALTHY' | 'UNREACHABLE' | string;
    url: string;
    targets: Array<{
      job: string;
      instance: string;
      health: 'UP' | 'DOWN' | string;
      last_scrape?: string;
      last_error?: string;
    }>;
    quantiles_ms: {
      p50: number;
      p95: number;
      p99: number;
    };
  };
  job_states: {
    queued: number;
    scheduled: number;
    claimed: number;
    running: number;
    completed: number;
    failed: number;
    retry_waiting: number;
    dead_letter: number;
    total: number;
  };
  throughput_series: Array<{
    timestamp: string;
    completed: number;
    failed: number;
    rate_per_min: number;
  }>;
  execution_performance: {
    completed_executions: number;
    failed_executions: number;
    avg_duration_ms: number;
    p50_duration_ms?: number;
    p95_duration_ms?: number;
    p99_duration_ms?: number;
    total_executions: number;
  };
  workers?: Array<{
    id: string;
    hostname: string;
    ip_address: string;
    status: string;
    active_jobs: number;
    max_concurrency: number;
    capacity_ratio: number;
    last_heartbeat_at?: string;
  }>;
  queues?: Array<{
    id: string;
    name: string;
    project_name: string;
    concurrency_limit: number;
    active_jobs: number;
    queued_jobs: number;
    utilization_pct: number;
  }>;
  rate_limiting?: {
    architecture: string;
    total_allowed: number;
    total_rejected: number;
    active_window_seconds: number;
    current_active_requests: number;
    active_tracked_keys: number;
  };
}


export interface BatchSubmissionItem {
  id: string;
  name: string;
  status: string;
  total_jobs: number;
  successful_jobs: number;
  failed_jobs: number;
  created_at: string | null;
}

export interface BatchSubmissionList {
  items: BatchSubmissionItem[];
  page: number;
  page_size: number;
  total: number;
  summary: {
    total_batches: number;
    total_batch_jobs: number;
    successful_batches: number;
    failed_batches: number;
  };
}

export interface BatchSubmissionDetail extends BatchSubmissionItem {
  jobs: Array<{
    id: string;
    task_type: string;
    status: JobStatus;
    queue_id: string;
    priority: number;
    attempt: number;
    created_at: string | null;
  }>;
}

export interface WorkflowNode {
  id: string;
  title: string;
  task_type: string;
  status: JobStatus;
  is_blocked: boolean;
  parent_ids: string[];
}

export interface WorkflowEdge {
  source: string;
  target: string;
}

export interface WorkflowItem {
  id: string;
  name: string;
  root_job_id: string;
  total_jobs: number;
  completed_jobs: number;
  running_jobs: number;
  blocked_jobs: number;
  failed_jobs: number;
  status: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface WorkflowsResponse {
  workflows: WorkflowItem[];
  total_dependencies: number;
}

export interface RateLimitPolicy {
  endpoint: string;
  description: string;
  limit: number;
  window_seconds: number;
  key_format: string;
}

export interface RateLimitStatus {
  architecture: string;
  total_allowed: number;
  total_rejected: number;
  active_window_seconds: number;
  current_active_requests: number;
  active_tracked_keys: number;
  protected_endpoints: RateLimitPolicy[];
}

export interface RateLimitTestResult {
  tested_key: string;
  configured_limit: string;
  requests_sent: number;
  allowed_requests: number;
  rejected_429_requests: number;
  limiter_total_rejections: number;
}

export interface FailureAnalysisItem {
  id: string;
  task_type: string;
  title: string;
  status: JobStatus;
  queue_id: string;
  attempt: number;
  max_retries: number;
  worker_id: string | null;
  error: string | null;
  created_at: string | null;
  updated_at: string | null;
  failure_analysis: {
    summary: string;
    likely_cause: string;
    recommended_action: string;
  };
}

export interface FailureAnalysisResponse {
  items: FailureAnalysisItem[];
  page: number;
  page_size: number;
  total: number;
  top_failure_causes: Array<{ cause: string; count: number }>;
}
