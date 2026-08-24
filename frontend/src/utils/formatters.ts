export function formatDate(isoString: string | null | undefined): string {
  if (!isoString) return 'N/A';
  try {
    const d = new Date(isoString);
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return isoString;
  }
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return 'N/A';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const secs = (ms / 1000).toFixed(2);
  return `${secs} s`;
}

export function truncateUuid(uuid: string | null | undefined, length: number = 8): string {
  if (!uuid) return 'N/A';
  if (uuid.length <= length) return uuid;
  return `${uuid.substring(0, length)}...`;
}

export function formatSecondsAgo(seconds: number | null | undefined): string {
  if (seconds == null) return 'Unknown';
  if (seconds < 5) return 'Just now';
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  const mins = Math.floor(seconds / 60);
  return `${mins}m ago`;
}

export function getJobTitle(job: { task_type: string; payload?: Record<string, any> }): string {
  if (!job) return 'Background Job';
  const payload = job.payload || {};
  if (payload.title) return String(payload.title);
  if (payload.name) return String(payload.name);

  const tt = job.task_type || '';
  if (tt === 'email.send') {
    const template = payload.template;
    if (template === 'welcome') return 'Send Welcome Email';
    if (template === 'password_reset') return 'Send Password Reset Email';
    return 'Send Customer Email';
  }
  if (tt === 'invoice.generate') {
    return `Generate Customer Invoice (${payload.invoice_id || 'INV-1001'})`;
  }
  if (tt === 'report.generate') {
    const r = payload.report;
    if (r === 'daily_sales') return 'Generate Daily Sales Report';
    if (r === 'monthly_revenue') return 'Generate Monthly Revenue Report';
    if (r === 'management_summary') return 'Generate Management Summary';
    return 'Generate Operations Report';
  }
  if (tt === 'image.process') {
    return `Resize Product Images (${payload.operation || 'resize'})`;
  }
  if (tt === 'notification.send') {
    if (payload.order_id) return `Send Order Confirmation (${payload.order_id})`;
    return 'Send Customer Notification';
  }
  if (tt === 'customer.sync') {
    if (payload.simulate_failure) return 'Process Invalid Customer Import';
    return `Synchronize Customer Profile (${payload.customer_id || 'CUS-1001'})`;
  }
  if (tt.startsWith('demo.')) {
    const sub = tt.split('.')[1];
    return `Demo Task: ${sub.charAt(0).toUpperCase() + sub.slice(1)}`;
  }
  return tt;
}
