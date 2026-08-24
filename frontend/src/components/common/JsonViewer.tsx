import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

interface JsonViewerProps {
  data: any;
  title?: string;
}

export const JsonViewer: React.FC<JsonViewerProps> = ({ data, title }) => {
  const [copied, setCopied] = useState(false);

  const formattedJson = typeof data === 'object' ? JSON.stringify(data, null, 2) : String(data);

  const handleCopy = () => {
    navigator.clipboard.writeText(formattedJson);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl bg-slate-950 border border-slate-800 overflow-hidden shadow-inner">
      {title && (
        <div className="flex items-center justify-between bg-slate-900/80 px-4 py-2 border-b border-slate-800 text-xs font-mono text-slate-400">
          <span>{title}</span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 hover:text-white transition-colors"
            title="Copy JSON"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      )}
      <pre className="p-4 text-xs font-mono text-sky-300 overflow-x-auto max-h-80 leading-relaxed">
        <code>{formattedJson}</code>
      </pre>
    </div>
  );
};
