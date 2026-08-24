import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import { addJobDependency } from '../../services/jobs';
import { useToast } from '../../context/ToastContext';
import { Link2, AlertCircle } from 'lucide-react';

interface AddDependencyModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetJobId: string;
  onSuccess: () => void;
}

export const AddDependencyModal: React.FC<AddDependencyModalProps> = ({
  isOpen,
  onClose,
  targetJobId,
  onSuccess,
}) => {
  const { addToast } = useToast();
  const [dependsOnJobId, setDependsOnJobId] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const cleanParentId = dependsOnJobId.trim();
    if (!cleanParentId) {
      setErrorMessage('Please enter a valid Parent Job UUID.');
      return;
    }

    if (cleanParentId === targetJobId) {
      setErrorMessage('A job cannot depend on itself.');
      return;
    }

    try {
      setIsSubmitting(true);
      await addJobDependency(targetJobId, cleanParentId);
      addToast('Dependency relationship established successfully!', 'success');
      onSuccess();
      setDependsOnJobId('');
      onClose();
    } catch (err: any) {
      const msg = err.message || 'Failed to add job dependency.';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Add Workflow Dependency"
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-xs text-slate-400 leading-relaxed">
          Configure a parent job dependency for job <code className="text-sky-400 font-mono">{targetJobId.substring(0, 8)}...</code>. This job will remain blocked until the parent job reaches <span className="text-emerald-400 font-semibold">COMPLETED</span> status.
        </p>

        {errorMessage && (
          <div className="p-3 bg-rose-950/60 border border-rose-800/80 rounded-xl flex items-start gap-2.5 text-xs text-rose-200">
            <AlertCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
            <div className="leading-relaxed">{errorMessage}</div>
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1.5">
            Parent Job ID (Depends On UUID)
          </label>
          <input
            type="text"
            value={dependsOnJobId}
            onChange={(e) => setDependsOnJobId(e.target.value)}
            placeholder="e.g. 8570eccc-21e3-4184-8978-587283543909"
            className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white font-mono focus:border-sky-500 focus:outline-none placeholder:text-slate-600"
            required
          />
        </div>

        <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs text-slate-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex items-center gap-2 px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition-all shadow-md shadow-sky-600/20"
          >
            <Link2 className="h-4 w-4" />
            <span>{isSubmitting ? 'Verifying Graph...' : 'Attach Dependency'}</span>
          </button>
        </div>
      </form>
    </Modal>
  );
};
