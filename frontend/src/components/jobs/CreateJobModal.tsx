import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { getQueues, createQueue } from '../../services/queues';
import { submitJob, submitScheduledJob } from '../../services/jobs';
import { getProjects, createProject } from '../../services/projects';
import type { Queue, Project } from '../../types/api';

interface CreateJobModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const CreateJobModal: React.FC<CreateJobModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [queues, setQueues] = useState<Queue[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  
  const [isRecurring, setIsRecurring] = useState<boolean>(false);
  const [queueId, setQueueId] = useState<string>('');
  const [projectId, setProjectId] = useState<string>('');
  const [taskType, setTaskType] = useState<string>('demo.success');
  const [payloadJson, setPayloadJson] = useState<string>('{\n  "key": "value"\n}');
  const [priority, setPriority] = useState<number>(1);
  const [delaySeconds, setDelaySeconds] = useState<number>(0);
  
  // Recurring cron specific
  const [jobName, setJobName] = useState<string>('Cron Job');
  const [cronExpression, setCronExpression] = useState<string>('0 * * * *');

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isCreatingDefaultQueue, setIsCreatingDefaultQueue] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadResources = async () => {
    try {
      const qList = await getQueues();
      setQueues(qList);
      if (qList.length > 0) {
        setQueueId(qList[0].id);
      }

      let pList = await getProjects();
      setProjects(pList);
      if (pList.length > 0) {
        setProjectId(pList[0].id);
      }
    } catch {
      setError('Failed to load queues and projects.');
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadResources();
    }
  }, [isOpen]);

  const handleCreateDefaultQueue = async () => {
    setIsCreatingDefaultQueue(true);
    setError(null);
    try {
      let activeProjId = projectId;
      if (!activeProjId) {
        let pList = await getProjects();
        if (pList.length === 0) {
          const newProj = await createProject('Default Project');
          activeProjId = newProj.id;
          setProjects([newProj]);
          setProjectId(newProj.id);
        } else {
          activeProjId = pList[0].id;
          setProjectId(pList[0].id);
        }
      }

      const newQueue = await createQueue({
        project_id: activeProjId,
        name: 'default',
        concurrency_limit: 5,
        priority: 1,
      });

      const updatedQueues = await getQueues();
      setQueues(updatedQueues);
      setQueueId(newQueue.id);
    } catch (err: any) {
      setError(err.message || 'Failed to auto-create default queue.');
    } finally {
      setIsCreatingDefaultQueue(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queueId) {
      setError('Please select a queue.');
      return;
    }

    let parsedPayload = {};
    try {
      if (payloadJson.trim()) {
        parsedPayload = JSON.parse(payloadJson);
      }
    } catch {
      setError('Invalid JSON payload format.');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      if (isRecurring) {
        if (!projectId) {
          setError('Project is required for recurring cron jobs.');
          setIsSubmitting(false);
          return;
        }
        await submitScheduledJob({
          project_id: projectId,
          queue_id: queueId,
          name: jobName,
          cron_expression: cronExpression,
          payload: { task_type: taskType, ...parsedPayload },
        });
      } else {
        await submitJob({
          queue_id: queueId,
          task_type: taskType,
          payload: parsedPayload,
          priority: Number(priority),
          delay: Number(delaySeconds),
        });
      }
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to submit job.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Submit New Job" maxWidth="lg">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="p-3 text-xs rounded bg-rose-950/60 text-rose-300 border border-rose-800">{error}</div>}

        <div className="flex items-center gap-4 p-3 bg-slate-950 rounded-xl border border-slate-800 text-xs">
          <span className="text-slate-300 font-medium">Job Mode:</span>
          <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
            <input
              type="radio"
              name="jobMode"
              checked={!isRecurring}
              onChange={() => setIsRecurring(false)}
              className="accent-sky-500"
            />
            Standard Execution
          </label>
          <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
            <input
              type="radio"
              name="jobMode"
              checked={isRecurring}
              onChange={() => setIsRecurring(true)}
              className="accent-sky-500"
            />
            Recurring Cron Schedule
          </label>
        </div>

        {isRecurring && projects.length > 0 && (
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Project</label>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">Target Queue</label>
          {queues.length === 0 ? (
            <div className="p-3 bg-amber-950/40 text-amber-300 rounded-xl border border-amber-800/40 text-xs flex items-center justify-between">
              <span>No active queue found in project.</span>
              <button
                type="button"
                onClick={handleCreateDefaultQueue}
                disabled={isCreatingDefaultQueue}
                className="px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
              >
                {isCreatingDefaultQueue ? 'Creating...' : "Create 'default' Queue"}
              </button>
            </div>
          ) : (
            <select
              value={queueId}
              onChange={(e) => setQueueId(e.target.value)}
              className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
            >
              {queues.map((q) => (
                <option key={q.id} value={q.id}>
                  {q.name} (Priority {q.priority})
                </option>
              ))}
            </select>
          )}
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">Task Type</label>
          <select
            value={taskType}
            onChange={(e) => setTaskType(e.target.value)}
            className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
          >
            <option value="demo.success">demo.success (Deterministic Success)</option>
            <option value="demo.failure">demo.failure (Deterministic Permanent Failure)</option>
            <option value="demo.retry">demo.retry (Deterministic Retry Flow)</option>
          </select>
        </div>

        {isRecurring ? (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Job Name</label>
              <input
                type="text"
                value={jobName}
                onChange={(e) => setJobName(e.target.value)}
                className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Cron Expression</label>
              <input
                type="text"
                placeholder="0 * * * *"
                value={cronExpression}
                onChange={(e) => setCronExpression(e.target.value)}
                className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500 font-mono text-xs"
              />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Priority</label>
              <input
                type="number"
                min={1}
                max={10}
                value={priority}
                onChange={(e) => setPriority(parseInt(e.target.value) || 1)}
                className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Delay (Seconds)</label>
              <input
                type="number"
                min={0}
                value={delaySeconds}
                onChange={(e) => setDelaySeconds(parseInt(e.target.value) || 0)}
                className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
              />
            </div>
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">Payload JSON</label>
          <textarea
            rows={4}
            value={payloadJson}
            onChange={(e) => setPayloadJson(e.target.value)}
            className="w-full rounded-xl bg-slate-950 border border-slate-800 p-3 text-xs font-mono text-sky-300 focus:outline-none focus:border-sky-500"
          />
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting || queues.length === 0}
            className="px-4 py-2 rounded-xl text-xs font-medium bg-sky-600 text-white hover:bg-sky-500 transition-colors shadow-lg shadow-sky-600/20 disabled:opacity-50"
          >
            {isSubmitting ? 'Submitting...' : 'Submit Job'}
          </button>
        </div>
      </form>
    </Modal>
  );
};
