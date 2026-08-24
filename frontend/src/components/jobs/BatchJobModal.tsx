import React, { useState } from 'react';
import type { Queue, BatchJobCreateItem } from '../../types/api';
import { submitBatchJobs } from '../../services/jobs';
import { Modal } from '../common/Modal';
import { useToast } from '../../context/ToastContext';
import { Plus, Trash2, CheckCircle2, Copy } from 'lucide-react';

interface BatchJobModalProps {
  isOpen: boolean;
  onClose: () => void;
  queues: Queue[];
  onSuccess: () => void;
}

const DEFAULT_JOB: BatchJobCreateItem = {
  task_type: 'demo.success',
  queue_id: '',
  priority: 1,
  max_retries: 3,
  payload: { key: 'value' },
};

export const BatchJobModal: React.FC<BatchJobModalProps> = ({
  isOpen,
  onClose,
  queues,
  onSuccess,
}) => {
  const { addToast } = useToast();
  const [jobs, setJobs] = useState<Array<{ id: string; item: BatchJobCreateItem; payloadJson: string }>>([
    {
      id: '1',
      item: { ...DEFAULT_JOB, queue_id: queues[0]?.id || '' },
      payloadJson: '{\n  "batch_index": 1\n}',
    },
  ]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createdCount, setCreatedCount] = useState<number | null>(null);

  const handleAddRow = () => {
    const nextId = (jobs.length + 1).toString();
    const defaultQueueId = queues[0]?.id || '';
    setJobs((prev) => [
      ...prev,
      {
        id: nextId,
        item: {
          task_type: 'demo.success',
          queue_id: defaultQueueId,
          priority: 1,
          max_retries: 3,
        },
        payloadJson: `{\n  "batch_index": ${prev.length + 1}\n}`,
      },
    ]);
  };

  const handleDuplicateRow = (index: number) => {
    const target = jobs[index];
    const nextId = (jobs.length + 1).toString();
    setJobs((prev) => [
      ...prev,
      {
        id: nextId,
        item: { ...target.item },
        payloadJson: target.payloadJson,
      },
    ]);
  };

  const handleRemoveRow = (index: number) => {
    if (jobs.length <= 1) return;
    setJobs((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpdateItem = (index: number, key: keyof BatchJobCreateItem, value: any) => {
    setJobs((prev) => {
      const copy = [...prev];
      copy[index] = {
        ...copy[index],
        item: { ...copy[index].item, [key]: value },
      };
      return copy;
    });
  };

  const handleUpdatePayloadJson = (index: number, jsonStr: string) => {
    setJobs((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], payloadJson: jsonStr };
      return copy;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatedCount(null);

    const parsedItems: BatchJobCreateItem[] = [];
    for (let i = 0; i < jobs.length; i++) {
      const row = jobs[i];
      if (!row.item.queue_id) {
        addToast(`Job #${i + 1} requires a selected queue`, 'error');
        return;
      }
      if (!row.item.task_type.trim()) {
        addToast(`Job #${i + 1} requires a task type`, 'error');
        return;
      }
      try {
        const payloadObj = row.payloadJson.trim() ? JSON.parse(row.payloadJson) : {};
        parsedItems.push({
          ...row.item,
          payload: payloadObj,
        });
      } catch {
        addToast(`Job #${i + 1} payload contains invalid JSON`, 'error');
        return;
      }
    }

    try {
      setIsSubmitting(true);
      const result = await submitBatchJobs(parsedItems);
      setCreatedCount(result.total_created);
      addToast(`Batch created successfully! Submitted ${result.total_created} jobs atomically.`, 'success');
      onSuccess();
      setTimeout(() => {
        setIsSubmitting(false);
        onClose();
      }, 1500);
    } catch (err: any) {
      setIsSubmitting(false);
      addToast(err.message || 'Failed to submit batch jobs', 'error');
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Submit Atomic Batch Jobs"
      maxWidth="4xl"
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <p className="text-xs text-slate-400">
              Create multiple jobs in a single atomic database transaction. If any job fails validation, all creations are rolled back.
            </p>
          </div>
          <span className="px-2.5 py-1 rounded-full text-xs font-mono font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/30">
            {jobs.length} {jobs.length === 1 ? 'Job' : 'Jobs'} Ready
          </span>
        </div>

        {createdCount !== null ? (
          <div className="p-6 bg-emerald-950/40 border border-emerald-800/60 rounded-2xl text-center space-y-3">
            <CheckCircle2 className="h-10 w-10 text-emerald-400 mx-auto" />
            <h3 className="text-base font-bold text-emerald-200">Batch Submission Successful</h3>
            <p className="text-xs text-emerald-300">
              All {createdCount} jobs were atomically created and enqueued.
            </p>
          </div>
        ) : (
          <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
            {jobs.map((row, idx) => (
              <div
                key={row.id}
                className="p-4 bg-slate-950 border border-slate-800/80 rounded-2xl space-y-3 relative group"
              >
                <div className="flex items-center justify-between text-xs font-mono text-slate-400 border-b border-slate-800/60 pb-2">
                  <span className="font-semibold text-slate-200">Job #{idx + 1}</span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleDuplicateRow(idx)}
                      className="p-1 text-slate-400 hover:text-white rounded transition-colors"
                      title="Duplicate job row"
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </button>
                    {jobs.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveRow(idx)}
                        className="p-1 text-rose-400 hover:text-rose-300 rounded transition-colors"
                        title="Remove job row"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Task Type
                    </label>
                    <input
                      type="text"
                      value={row.item.task_type}
                      onChange={(e) => handleUpdateItem(idx, 'task_type', e.target.value)}
                      placeholder="e.g. demo.success"
                      className="w-full px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white font-mono focus:border-sky-500 focus:outline-none"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Queue
                    </label>
                    <select
                      value={row.item.queue_id}
                      onChange={(e) => handleUpdateItem(idx, 'queue_id', e.target.value)}
                      className="w-full px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white focus:border-sky-500 focus:outline-none"
                      required
                    >
                      {queues.map((q) => (
                        <option key={q.id} value={q.id}>
                          {q.name} (Priority {q.priority})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">
                        Priority
                      </label>
                      <input
                        type="number"
                        value={row.item.priority || 1}
                        onChange={(e) => handleUpdateItem(idx, 'priority', parseInt(e.target.value) || 1)}
                        className="w-full px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white font-mono focus:border-sky-500 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">
                        Max Retries
                      </label>
                      <input
                        type="number"
                        value={row.item.max_retries || 3}
                        onChange={(e) => handleUpdateItem(idx, 'max_retries', parseInt(e.target.value) || 0)}
                        className="w-full px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white font-mono focus:border-sky-500 focus:outline-none"
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">
                    Payload (JSON)
                  </label>
                  <textarea
                    rows={2}
                    value={row.payloadJson}
                    onChange={(e) => handleUpdatePayloadJson(idx, e.target.value)}
                    className="w-full px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 font-mono focus:border-sky-500 focus:outline-none"
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between pt-3 border-t border-slate-800">
          <button
            type="button"
            onClick={handleAddRow}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-slate-200 font-medium rounded-xl transition-colors"
          >
            <Plus className="h-4 w-4 text-sky-400" />
            <span>Add Job to Batch</span>
          </button>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || createdCount !== null}
              className="flex items-center gap-2 px-5 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition-all shadow-lg shadow-sky-600/20"
            >
              <span>{isSubmitting ? 'Submitting Batch...' : `Submit Batch (${jobs.length})`}</span>
            </button>
          </div>
        </div>
      </form>
    </Modal>
  );
};
