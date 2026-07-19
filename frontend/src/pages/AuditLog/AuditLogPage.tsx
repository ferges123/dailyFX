import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Download,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Eye,
  Info,
  X,
} from 'lucide-react';
import { getAuditLogs, downloadAuditExport, type AuditEvent } from '../../api/client';
import { formatDateTime } from '../datetime.utils';
import { FilterBar } from '../../components/FilterBar';

export default function AuditLogPage() {
  const [page, setPage] = useState(1);
  const limit = 25;
  const offset = (page - 1) * limit;

  // Filter states
  const [actionFilter, setActionFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [outcomeFilter, setOutcomeFilter] = useState('');
  const [actorTypeFilter, setActorTypeFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Selected event for details modal
  const [selectedEvent, setSelectedEvent] = useState<AuditEvent | null>(null);

  // Download states
  const [isExportingCsv, setIsExportingCsv] = useState(false);
  const [isExportingJson, setIsExportingJson] = useState(false);

  const queryParams = useMemo(() => {
    return {
      action: actionFilter || undefined,
      category: categoryFilter || undefined,
      outcome: outcomeFilter || undefined,
      actor_type: actorTypeFilter || undefined,
      date_from: dateFrom ? `${dateFrom}T00:00:00Z` : undefined,
      date_to: dateTo ? `${dateTo}T23:59:59Z` : undefined,
      limit,
      offset,
    };
  }, [actionFilter, categoryFilter, outcomeFilter, actorTypeFilter, dateFrom, dateTo, offset]);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['auditLogs', queryParams],
    queryFn: () => getAuditLogs(queryParams),
  });

  const events = data?.events || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit);

  const handleClearFilters = () => {
    setActionFilter('');
    setCategoryFilter('');
    setOutcomeFilter('');
    setActorTypeFilter('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  const activeFilterCount = [
    actionFilter,
    categoryFilter,
    outcomeFilter,
    actorTypeFilter,
    dateFrom,
    dateTo,
  ].filter(Boolean).length;

  const handleExport = async (format: 'csv' | 'json') => {
    if (format === 'csv') setIsExportingCsv(true);
    else setIsExportingJson(true);

    try {
      await downloadAuditExport({
        action: actionFilter || undefined,
        category: categoryFilter || undefined,
        outcome: outcomeFilter || undefined,
        actor_type: actorTypeFilter || undefined,
        date_from: dateFrom ? `${dateFrom}T00:00:00Z` : undefined,
        date_to: dateTo ? `${dateTo}T23:59:59Z` : undefined,
        format,
      });
    } catch (err) {
      alert(`Export failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      if (format === 'csv') setIsExportingCsv(false);
      else setIsExportingJson(false);
    }
  };

  const getOutcomeBadgeClass = (outcome: string) => {
    if (outcome === 'success') {
      return 'bg-emerald-50 text-emerald-700 border-emerald-200/60';
    }
    return 'bg-red-50 text-red-700 border-red-200/60';
  };

  const getCategoryBadgeClass = (category: string) => {
    switch (category) {
      case 'auth':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'settings':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'preset':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'schedule':
        return 'bg-indigo-50 text-indigo-700 border-indigo-200';
      case 'generation':
        return 'bg-teal-50 text-teal-700 border-teal-200';
      case 'retention':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      default:
        return 'bg-stone-50 text-stone-600 border-stone-200';
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="app-panel flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-100">
            <ClipboardList size={22} />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-stone-900 leading-none">System Audit Log</h1>
            <p className="mt-1 text-xs text-stone-500 font-medium">
              Trace settings modifications, test runs, generation pipelines, preset CRUD, and admin actions.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={isExportingCsv}
            onClick={() => handleExport('csv')}
            className="app-button-secondary h-9 px-3.5 text-xs disabled:opacity-50"
          >
            <Download size={13} />
            {isExportingCsv ? 'Exporting CSV...' : 'Export CSV'}
          </button>
          <button
            type="button"
            disabled={isExportingJson}
            onClick={() => handleExport('json')}
            className="app-button-secondary h-9 px-3.5 text-xs disabled:opacity-50"
          >
            <Download size={13} />
            {isExportingJson ? 'Exporting JSON...' : 'Export JSON'}
          </button>
        </div>
      </div>

      {/* Filter panel */}
      <FilterBar
        activeCount={activeFilterCount}
        onClear={handleClearFilters}
        clearLabel="Clear filters"
        bodyClassName="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4"
      >
        {/* Action */}
        <div>
          <label className="block text-[10px] font-bold text-stone-500 uppercase tracking-wider mb-1">Action</label>
          <input
            type="text"
            placeholder="e.g. settings.updated"
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value);
              setPage(1);
            }}
            className="app-control app-control-muted h-9 px-2.5 text-xs"
          />
        </div>

        {/* Category */}
        <div>
          <label className="block text-[10px] font-bold text-stone-500 uppercase tracking-wider mb-1">Category</label>
          <select
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setPage(1);
            }}
            className="app-control app-control-muted h-9 cursor-pointer px-2 text-xs"
          >
            <option value="">All Categories</option>
            <option value="auth">auth</option>
            <option value="settings">settings</option>
            <option value="preset">preset</option>
            <option value="schedule">schedule</option>
            <option value="generation">generation</option>
            <option value="retention">retention</option>
          </select>
        </div>

        {/* Outcome */}
        <div>
          <label className="block text-[10px] font-bold text-stone-500 uppercase tracking-wider mb-1">Outcome</label>
          <select
            value={outcomeFilter}
            onChange={(e) => {
              setOutcomeFilter(e.target.value);
              setPage(1);
            }}
            className="app-control app-control-muted h-9 cursor-pointer px-2 text-xs"
          >
            <option value="">All Outcomes</option>
            <option value="success">Success</option>
            <option value="failure">Failure</option>
          </select>
        </div>

        {/* Actor Type */}
        <div>
          <label className="block text-[10px] font-bold text-stone-500 uppercase tracking-wider mb-1">Actor Type</label>
          <input
            type="text"
            placeholder="e.g. admin, scheduler"
            value={actorTypeFilter}
            onChange={(e) => {
              setActorTypeFilter(e.target.value);
              setPage(1);
            }}
            className="app-control app-control-muted h-9 px-2.5 text-xs"
          />
        </div>

        {/* Date From */}
        <div>
          <label className="block text-[10px] font-bold text-stone-500 uppercase tracking-wider mb-1">Date From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value);
              setPage(1);
            }}
            className="app-control app-control-muted h-9 px-2.5 text-xs"
          />
        </div>

        {/* Date To */}
        <div>
          <label className="block text-[10px] font-bold text-stone-500 uppercase tracking-wider mb-1">Date To</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value);
              setPage(1);
            }}
            className="app-control app-control-muted h-9 px-2.5 text-xs"
          />
        </div>
      </FilterBar>

      {/* Audit Log Content Container */}
      <div className="flex flex-col gap-3">
        {/* Desktop Table View */}
        <div className="app-panel hidden overflow-hidden md:block">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-stone-200/60 bg-stone-50/50 text-[10px] font-bold uppercase tracking-wider text-stone-500">
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Actor</th>
                  <th className="px-4 py-3">Outcome</th>
                  <th className="px-4 py-3">Summary</th>
                  <th className="px-4 py-3 text-center">Details</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-stone-500 font-medium">
                      Loading audit events...
                    </td>
                  </tr>
                ) : events.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-stone-500 font-medium">
                      No audit log events found matching the criteria.
                    </td>
                  </tr>
                ) : (
                  events.map((event) => (
                    <tr
                      key={event.event_id}
                      onClick={() => setSelectedEvent(event)}
                      className="border-b border-stone-100 bg-white/40 hover:bg-emerald-50/10 transition cursor-pointer"
                    >
                      <td className="whitespace-nowrap px-4 py-3 text-stone-500 font-medium">
                        {formatDateTime(event.occurred_at)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 font-semibold text-stone-900 font-mono text-[11px]">
                        {event.action}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className={`inline-block rounded-md border px-1.5 py-0.5 text-[10px] font-bold ${getCategoryBadgeClass(event.category)}`}>
                          {event.category}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 font-medium text-stone-600">
                        {event.actor_type}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className={`inline-block rounded-md border px-1.5 py-0.5 text-[10px] font-bold ${getOutcomeBadgeClass(event.outcome)}`}>
                          {event.outcome}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-stone-700 font-medium max-w-xs md:max-w-md truncate">
                        {event.summary}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-center">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedEvent(event);
                          }}
                          className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-stone-200 bg-white text-stone-500 hover:text-emerald-700 hover:border-emerald-200 shadow-2xs transition"
                        >
                          <Eye size={13} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination footer - Desktop */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-stone-200/60 bg-stone-50/30 px-4 py-3">
              <span className="text-xs font-medium text-stone-500">
                Showing <span className="font-semibold text-stone-900">{offset + 1}</span> to{' '}
                <span className="font-semibold text-stone-900">{Math.min(offset + limit, total)}</span> of{' '}
                <span className="font-semibold text-stone-900">{total}</span> entries
              </span>

              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  disabled={page === 1 || isFetching}
                  onClick={() => setPage((p) => p - 1)}
                  className="app-button-secondary h-8 w-8 p-0 disabled:opacity-50"
                >
                  <ChevronLeft size={16} />
                </button>
                <span className="text-xs font-semibold text-stone-700 px-1">
                  Page {page} of {totalPages}
                </span>
                <button
                  type="button"
                  disabled={page === totalPages || isFetching}
                  onClick={() => setPage((p) => p + 1)}
                  className="app-button-secondary h-8 w-8 p-0 disabled:opacity-50"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Mobile Cards View */}
        <div className="flex flex-col gap-3 md:hidden" aria-label="System audit log mobile list">
          <div className="grid gap-3">
            {isLoading ? (
              <div className="app-surface p-6 text-center text-stone-500 font-medium">
                Loading audit events...
              </div>
            ) : events.length === 0 ? (
              <div className="app-surface p-6 text-center text-stone-500 font-medium">
                No audit log events found matching the criteria.
              </div>
            ) : (
              events.map((event) => (
                <div
                  key={event.event_id}
                  onClick={() => setSelectedEvent(event)}
                  className="app-surface p-4 flex flex-col gap-2.5 cursor-pointer hover:border-emerald-200/80 transition-colors"
                >
                  <div className="flex justify-between items-start gap-2">
                    <span className="font-mono text-xs font-semibold text-stone-900 truncate max-w-[200px]">{event.action}</span>
                    <span className={`inline-block rounded-md border px-1.5 py-0.5 text-[10px] font-bold ${getOutcomeBadgeClass(event.outcome)}`}>
                      {event.outcome}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className={`inline-block rounded-md border px-1.5 py-0.5 text-[10px] font-bold ${getCategoryBadgeClass(event.category)}`}>
                      {event.category}
                    </span>
                    <span className="text-[11px] text-stone-500 font-semibold">{event.actor_type}</span>
                  </div>
                  <p className="text-xs text-stone-700 font-medium leading-relaxed">{event.summary}</p>
                  <div className="flex justify-between items-center border-t border-stone-100/80 pt-2.5 text-[10px] text-stone-500 font-medium">
                    <span>{formatDateTime(event.occurred_at)}</span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedEvent(event);
                      }}
                      className="app-button-secondary h-7 px-3.5 text-xs"
                    >
                      Details
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Pagination footer - Mobile */}
          {!isLoading && totalPages > 1 && (
            <div className="app-surface flex flex-col gap-3.5 items-center justify-center p-4 text-center">
              <span className="text-xs font-medium text-stone-500">
                Showing <span className="font-semibold text-stone-900">{offset + 1}</span> to{' '}
                <span className="font-semibold text-stone-900">{Math.min(offset + limit, total)}</span> of{' '}
                <span className="font-semibold text-stone-900">{total}</span> entries
              </span>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={page === 1 || isFetching}
                  onClick={() => setPage((p) => p - 1)}
                  className="app-button-secondary h-9 w-9 p-0 disabled:opacity-50"
                >
                  <ChevronLeft size={16} />
                </button>
                <span className="text-xs font-bold text-stone-700 px-2">
                  {page} / {totalPages}
                </span>
                <button
                  type="button"
                  disabled={page === totalPages || isFetching}
                  onClick={() => setPage((p) => p + 1)}
                  className="app-button-secondary h-9 w-9 p-0 disabled:opacity-50"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Detail Modal Overlay */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-2xl rounded-2xl border border-stone-200 bg-white p-6 shadow-xl max-h-[90vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-stone-100 pb-3">
              <div>
                <span className="text-[10px] font-bold text-stone-400 uppercase tracking-wider font-mono">
                  Event: {selectedEvent.event_id}
                </span>
                <h2 className="text-base font-bold text-stone-900 font-mono mt-0.5">
                  {selectedEvent.action}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setSelectedEvent(null)}
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-stone-400 hover:bg-stone-100 hover:text-stone-700 transition"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Scrollable Body */}
            <div className="overflow-y-auto py-4 flex-1 flex flex-col gap-4">
              {/* Properties Grid */}
              <div className="grid gap-3 sm:grid-cols-2 bg-stone-50/50 rounded-xl border border-stone-200/50 p-3 text-xs">
                <div>
                  <span className="font-semibold text-stone-500 block">Occurred At</span>
                  <span className="text-stone-800 font-medium">{formatDateTime(selectedEvent.occurred_at)}</span>
                </div>
                <div>
                  <span className="font-semibold text-stone-500 block">Category</span>
                  <span className="text-stone-800 font-medium">{selectedEvent.category}</span>
                </div>
                <div>
                  <span className="font-semibold text-stone-500 block">Outcome</span>
                  <span className={`inline-block rounded-md border px-1.5 py-0.5 text-[10px] font-bold ${getOutcomeBadgeClass(selectedEvent.outcome)} mt-0.5`}>
                    {selectedEvent.outcome}
                  </span>
                </div>
                <div>
                  <span className="font-semibold text-stone-500 block">Actor Type</span>
                  <span className="text-stone-800 font-medium">{selectedEvent.actor_type}</span>
                </div>
                {selectedEvent.request_id && (
                  <div>
                    <span className="font-semibold text-stone-500 block">Request ID</span>
                    <span className="text-stone-800 font-mono text-[10px] break-all">{selectedEvent.request_id}</span>
                  </div>
                )}
                {selectedEvent.source_ip_hash && (
                  <div>
                    <span className="font-semibold text-stone-500 block">Client IP Hash</span>
                    <span className="text-stone-800 font-mono text-[10px] break-all">{selectedEvent.source_ip_hash}</span>
                  </div>
                )}
                {selectedEvent.target_type && (
                  <div>
                    <span className="font-semibold text-stone-500 block">Target Type / ID</span>
                    <span className="text-stone-800 font-medium">
                      {selectedEvent.target_type} ({selectedEvent.target_id})
                    </span>
                  </div>
                )}
                {selectedEvent.task_id && (
                  <div>
                    <span className="font-semibold text-stone-500 block">Task ID</span>
                    <span className="text-stone-800 font-mono text-[11px] break-all">{selectedEvent.task_id}</span>
                  </div>
                )}
                {selectedEvent.schedule_id !== undefined && selectedEvent.schedule_id !== null && (
                  <div>
                    <span className="font-semibold text-stone-500 block">Schedule ID</span>
                    <span className="text-stone-800 font-medium">#{selectedEvent.schedule_id}</span>
                  </div>
                )}
              </div>

              {/* Summary */}
              <div>
                <h3 className="text-xs font-bold text-stone-800 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                  <Info size={12} className="text-emerald-700" />
                  Summary Description
                </h3>
                <p className="text-xs font-medium text-stone-700 bg-stone-50 border border-stone-200/50 rounded-lg p-3">
                  {selectedEvent.summary}
                </p>
              </div>

              {/* Changes / Configuration Diff */}
              {selectedEvent.changes && Object.keys(selectedEvent.changes).length > 0 && (
                <div>
                  <h3 className="text-xs font-bold text-stone-800 uppercase tracking-wider mb-2">
                    Configuration Changes
                  </h3>
                  <div className="overflow-hidden border border-stone-200/60 rounded-lg">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-stone-50 border-b border-stone-200/60 text-[10px] font-bold text-stone-500 uppercase tracking-wider">
                          <th className="px-3 py-2">Field</th>
                          <th className="px-3 py-2">Original Value</th>
                          <th className="px-3 py-2">New Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(selectedEvent.changes).map(([field, change]) => {
                          const isConfidential = change.changed !== undefined;
                          return (
                            <tr key={field} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/50">
                              <td className="px-3 py-2 font-semibold text-stone-800 font-mono text-[11px]">
                                {field}
                              </td>
                              {isConfidential ? (
                                <td colSpan={2} className="px-3 py-2 text-stone-500 font-medium italic">
                                  Sensitive value modified (redacted)
                                </td>
                              ) : (
                                <>
                                  <td className="px-3 py-2 text-red-700 bg-red-50/30 line-through max-w-[180px] break-words">
                                    {change.from === null ? 'None' : typeof change.from === 'object' ? JSON.stringify(change.from) : String(change.from)}
                                  </td>
                                  <td className="px-3 py-2 text-emerald-800 bg-emerald-50/30 font-semibold max-w-[180px] break-words">
                                    {change.to === null ? 'None' : typeof change.to === 'object' ? JSON.stringify(change.to) : String(change.to)}
                                  </td>
                                </>
                              )}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Metadata JSON */}
              {selectedEvent.metadata && Object.keys(selectedEvent.metadata).length > 0 && (
                <div>
                  <h3 className="text-xs font-bold text-stone-800 uppercase tracking-wider mb-1.5">
                    Event Metadata
                  </h3>
                  <pre className="bg-stone-50 border border-stone-200/50 p-3 rounded-lg overflow-x-auto text-[10px] font-mono text-stone-700 leading-relaxed max-h-[160px]">
                    {JSON.stringify(selectedEvent.metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="border-t border-stone-100 pt-3 flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedEvent(null)}
                className="inline-flex h-9 items-center justify-center rounded-xl bg-stone-900 px-4 text-xs font-bold text-white transition hover:bg-stone-800"
              >
                Close Details
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
