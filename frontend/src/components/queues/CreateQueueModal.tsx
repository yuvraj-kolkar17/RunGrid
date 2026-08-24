import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { getProjects } from '../../services/projects';
import { createQueue } from '../../services/queues';
import type { Project } from '../../types/api';

interface CreateQueueModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const CreateQueueModal: React.FC<CreateQueueModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string>('');
  const [name, setName] = useState<string>('');
  const [concurrencyLimit, setConcurrencyLimit] = useState<number>(5);
  const [priority, setPriority] = useState<number>(1);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      getProjects()
        .then((data) => {
          setProjects(data);
          if (data.length > 0) setProjectId(data[0].id);
        })
        .catch(() => setError('Failed to load projects.'));
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Queue name is required.');
      return;
    }
    if (!projectId) {
      setError('Please select a project.');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await createQueue({
        project_id: projectId,
        name: name.trim(),
        concurrency_limit: Number(concurrencyLimit),
        priority: Number(priority),
      });
      onSuccess();
      onClose();
      setName('');
    } catch (err: any) {
      setError(err.message || 'Failed to create queue.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create New Queue">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="p-3 text-xs rounded bg-rose-950/60 text-rose-300 border border-rose-800">{error}</div>}

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">Project</label>
          <select
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.id.substring(0, 8)}...)
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">Queue Name</label>
          <input
            type="text"
            placeholder="e.g. high-priority-tasks"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Concurrency Limit</label>
            <input
              type="number"
              min={1}
              max={100}
              value={concurrencyLimit}
              onChange={(e) => setConcurrencyLimit(parseInt(e.target.value) || 1)}
              className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Priority (1 = Highest)</label>
            <input
              type="number"
              min={1}
              max={10}
              value={priority}
              onChange={(e) => setPriority(parseInt(e.target.value) || 1)}
              className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
            />
          </div>
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
            disabled={isSubmitting}
            className="px-4 py-2 rounded-xl text-xs font-medium bg-sky-600 text-white hover:bg-sky-500 transition-colors shadow-lg shadow-sky-600/20 disabled:opacity-50"
          >
            {isSubmitting ? 'Creating...' : 'Create Queue'}
          </button>
        </div>
      </form>
    </Modal>
  );
};
