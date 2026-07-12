import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { QueuePage } from './QueuePage';
import AuditLogPage from './AuditLog/AuditLogPage';
import { StatisticsPage } from './Statistics';
import { ListTodo, ClipboardList, BarChart3 } from 'lucide-react';

export function SystemPage() {
  const { tab } = useParams<{ tab?: string }>();
  const activeTab = tab && ['statistics', 'queue', 'audit'].includes(tab) ? tab : 'statistics';

  return (
    <div className="flex flex-col gap-4">
      {/* Tab Navigation */}
      <div className="flex items-center gap-1.5 border-b border-stone-200/80 pb-1 overflow-x-auto whitespace-nowrap [scrollbar-width:thin] [&::-webkit-scrollbar]:h-1 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-stone-300">
        <Link
          to="/system/statistics"
          className={`flex shrink-0 items-center gap-1.5 px-3 py-2 text-xs sm:text-sm font-semibold rounded-t-xl border-t border-x transition-all ${
            activeTab === 'statistics'
              ? 'bg-white text-stone-900 border-stone-200/80 border-b-white -mb-[2px] z-10'
              : 'border-transparent text-stone-500 hover:text-stone-800 hover:bg-stone-50'
          }`}
        >
          <BarChart3 size={15} />
          <span className="hidden sm:inline">Statistics</span>
          <span className="sm:hidden">Stats</span>
        </Link>
        <Link
          to="/system/queue"
          className={`flex shrink-0 items-center gap-1.5 px-3 py-2 text-xs sm:text-sm font-semibold rounded-t-xl border-t border-x transition-all ${
            activeTab === 'queue'
              ? 'bg-white text-stone-900 border-stone-200/80 border-b-white -mb-[2px] z-10'
              : 'border-transparent text-stone-500 hover:text-stone-800 hover:bg-stone-50'
          }`}
        >
          <ListTodo size={15} />
          <span className="hidden sm:inline">Generation Queue</span>
          <span className="sm:hidden">Queue</span>
        </Link>
        <Link
          to="/system/audit"
          className={`flex shrink-0 items-center gap-1.5 px-3 py-2 text-xs sm:text-sm font-semibold rounded-t-xl border-t border-x transition-all ${
            activeTab === 'audit'
              ? 'bg-white text-stone-900 border-stone-200/80 border-b-white -mb-[2px] z-10'
              : 'border-transparent text-stone-500 hover:text-stone-800 hover:bg-stone-50'
          }`}
        >
          <ClipboardList size={15} />
          <span className="hidden sm:inline">Audit Log</span>
          <span className="sm:hidden">Audit</span>
        </Link>
      </div>

      {/* Tab Content */}
      <div className="mt-2">
        {activeTab === 'statistics' && <StatisticsPage />}
        {activeTab === 'queue' && <QueuePage />}
        {activeTab === 'audit' && <AuditLogPage />}
      </div>
    </div>
  );
}

