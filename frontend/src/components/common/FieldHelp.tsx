import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Info } from 'lucide-react';

interface HelpTooltipProps {
  text: string;
  className?: string;
}

export function HelpTooltip({ text, className = '' }: HelpTooltipProps) {
  const [open, setOpen] = useState(false);
  const tooltipId = useId();
  const containerRef = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handleDocumentPointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target as Node | null;
      if (containerRef.current && target && !containerRef.current.contains(target)) {
        setOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handleDocumentPointerDown);
    document.addEventListener('touchstart', handleDocumentPointerDown, { passive: true });
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleDocumentPointerDown);
      document.removeEventListener('touchstart', handleDocumentPointerDown);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [open]);

  return (
    <span
      ref={containerRef}
      className={`group relative inline-flex items-center ${className}`.trim()}
    >
      <button
        type="button"
        title={text}
        aria-label={`Help: ${text}`}
        aria-expanded={open}
        aria-controls={tooltipId}
        onClick={() => setOpen((current) => !current)}
        onBlur={(event) => {
          const nextFocused = event.relatedTarget as Node | null;
          if (!nextFocused || (containerRef.current && !containerRef.current.contains(nextFocused))) {
            setOpen(false);
          }
        }}
        className="inline-flex h-5 w-5 items-center justify-center rounded-full text-slate-700 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
      >
        <Info className="h-4 w-4" />
      </button>
      <span
        id={tooltipId}
        role="tooltip"
        className={`absolute left-1/2 top-full z-20 mt-2 w-64 -translate-x-1/2 rounded-md border border-slate-300 bg-white p-2 text-xs font-medium text-slate-900 shadow-lg group-hover:block group-focus-within:block ${open ? 'block pointer-events-auto' : 'hidden pointer-events-none'}`}
      >
        {text}
      </span>
    </span>
  );
}

interface FieldLabelProps {
  label: ReactNode;
  help: string;
  htmlFor?: string;
  required?: boolean;
  className?: string;
  textClassName?: string;
}

export function FieldLabel({
  label,
  help,
  htmlFor,
  required = false,
  className = 'mb-2 flex items-center gap-1.5',
  textClassName = 'block text-sm font-medium text-slate-800',
}: FieldLabelProps) {
  return (
    <div className={className}>
      {htmlFor ? (
        <label htmlFor={htmlFor} className={textClassName}>
          {label}
          {required ? ' *' : ''}
        </label>
      ) : (
        <p className={textClassName}>
          {label}
          {required ? ' *' : ''}
        </p>
      )}
      <HelpTooltip text={help} />
    </div>
  );
}
