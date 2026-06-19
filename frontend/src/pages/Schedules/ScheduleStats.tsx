import { memo } from 'react';
import { CalendarDays, Clock3, ToggleLeft, X } from 'lucide-react';
import { type Schedule } from '../../api/client';
import { ScheduleSummaryCard } from './ScheduleSummaryCard';
import { formatDateTime } from '../datetime.utils';

interface ScheduleStatsProps {
  activeCount: number;
  disabledCount: number;
  failedCount: number;
  totalCount: number;
  nextRunItem: Schedule | undefined;
}

export const ScheduleStats = memo(function ScheduleStats({
  activeCount,
  disabledCount,
  failedCount,
  totalCount,
  nextRunItem,
}: ScheduleStatsProps) {
  return (
    <div className="grid grid-cols-2 gap-2.5 xl:grid-cols-4">
      <ScheduleSummaryCard
        title="Active schedules"
        value={String(activeCount)}
        description={`of ${totalCount} total`}
        tone="green"
        icon={<CalendarDays size={18} />}
      />
      <ScheduleSummaryCard
        title="Disabled"
        value={String(disabledCount)}
        description={`of ${totalCount} total`}
        tone="default"
        icon={<ToggleLeft size={18} />}
      />
      <ScheduleSummaryCard
        title="Failed last run"
        value={String(failedCount)}
        description={
          failedCount > 0
            ? 'Review the last result on the schedule cards'
            : 'No errors'
        }
        tone="red"
        icon={<X size={18} />}
      />
      <ScheduleSummaryCard
        title="Next run"
        value={nextRunItem ? nextRunItem.name : 'None'}
        description={
          nextRunItem?.next_run_at
            ? formatDateTime(nextRunItem.next_run_at)
            : 'Not scheduled'
        }
        tone="blue"
        icon={<Clock3 size={18} />}
      />
    </div>
  );
});
