import React, { useState } from 'react';
import { QueuePage } from './QueuePage';
import AuditLogPage from './AuditLog/AuditLogPage';
import { StatisticsPage } from './Statistics';
import { ListTodo, ClipboardList, BarChart3 } from 'lucide-react';

export function SystemPage() {
  const [activeTab, setActiveTab] = useState<'statistics' | 'queue' | 'audit'>('statistics');

  return (
    <div className="flex flex-col gap-4">
      {/* Tab Navigation */}
      <div className="flex items-center gap-1.5 border-b border-stone-200/80 pb-1 overflow-x-auto whitespace-nowrap [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <button
          onClick={() => setActiveTab('statistics')}
          className={`flex shrink-0 items-center gap-2 px-4 py-2 text-sm font-semibold rounded-t-xl border-t border-x transition-all ${
            activeTab === 'statistics'
              ? 'bg-white text-stone-900 border-stone-200/80 border-b-white -mb-[2px] z-10'
              : 'border-transparent text-stone-500 hover:text-stone-800 hover:bg-stone-50'
          }`}
        >
          <BarChart3 size={16} />
          Statistics
        </button>
        <button
          onClick={() => setActiveTab('queue')}
          className={`flex shrink-0 items-center gap-2 px-4 py-2 text-sm font-semibold rounded-t-xl border-t border-x transition-all ${
            activeTab === 'queue'
              ? 'bg-white text-stone-900 border-stone-200/80 border-b-white -mb-[2px] z-10'
              : 'border-transparent text-stone-500 hover:text-stone-800 hover:bg-stone-50'
          }`}
        >
          <ListTodo size={16} />
          Generation Queue
        </button>
        <button
          onClick={() => setActiveTab('audit')}
          className={`flex shrink-0 items-center gap-2 px-4 py-2 text-sm font-semibold rounded-t-xl border-t border-x transition-all ${
            activeTab === 'audit'
              ? 'bg-white text-stone-900 border-stone-200/80 border-b-white -mb-[2px] z-10'
              : 'border-transparent text-stone-500 hover:text-stone-800 hover:bg-stone-50'
          }`}
        >
          <ClipboardList size={16} />
          Audit Log
        </button>
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
