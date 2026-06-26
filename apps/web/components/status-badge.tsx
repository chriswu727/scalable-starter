import { cn } from '@/lib/utils';

type Status = 'ok' | 'down' | 'unknown';

const STYLES: Record<Status, string> = {
  ok: 'bg-green-500/15 text-green-600 dark:text-green-400',
  down: 'bg-red-500/15 text-red-600 dark:text-red-400',
  unknown: 'bg-zinc-500/15 text-zinc-500',
};

const LABELS: Record<Status, string> = {
  ok: 'API reachable',
  down: 'API unreachable',
  unknown: 'API status unknown',
};

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium',
        STYLES[status],
      )}
    >
      <span className="h-2 w-2 rounded-full bg-current" />
      {LABELS[status]}
    </span>
  );
}
