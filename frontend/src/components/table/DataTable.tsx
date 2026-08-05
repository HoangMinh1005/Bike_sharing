import React, { useState, useEffect } from 'react';
import EmptyState from '../common/EmptyState';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T, index: number) => React.ReactNode;
  align?: 'left' | 'center' | 'right';
  width?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  keyExtractor: (row: T, index: number) => string | number;
  pageSize?: number;
}

export function DataTable<T>({
  columns,
  data,
  onRowClick,
  emptyMessage = 'No matching records found.',
  keyExtractor,
  pageSize,
}: DataTableProps<T>) {
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Reset to first page whenever data length or data identity changes
  useEffect(() => {
    setCurrentPage(1);
  }, [data]);

  if (!data || data.length === 0) {
    return <EmptyState message={emptyMessage} height="h-48" />;
  }

  const isPaginated = pageSize && pageSize > 0 && data.length > pageSize;
  const totalPages = isPaginated ? Math.ceil(data.length / pageSize) : 1;
  const startIndex = isPaginated ? (currentPage - 1) * pageSize : 0;
  const endIndex = isPaginated ? Math.min(startIndex + pageSize, data.length) : data.length;
  const displayedData = isPaginated ? data.slice(startIndex, endIndex) : data;

  return (
    <div className="w-full bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
      <div className="w-full overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`py-3 px-4 font-semibold text-slate-600 uppercase tracking-wider ${
                    col.align === 'center' ? 'text-center' : col.align === 'right' ? 'text-right' : 'text-left'
                  }`}
                  style={{ width: col.width }}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {displayedData.map((row, idx) => {
              const globalIndex = startIndex + idx;
              return (
                <tr
                  key={keyExtractor(row, globalIndex)}
                  onClick={() => onRowClick && onRowClick(row)}
                  className={`transition-colors ${
                    onRowClick ? 'cursor-pointer hover:bg-slate-50/80' : 'hover:bg-slate-50/50'
                  }`}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`py-3 px-4 text-slate-700 whitespace-nowrap ${
                        col.align === 'center' ? 'text-center' : col.align === 'right' ? 'text-right' : 'text-left'
                      }`}
                    >
                      {col.render ? col.render(row, globalIndex) : (row as any)[col.key] ?? '-'}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer Controls */}
      {isPaginated && (
        <div className="px-5 py-3.5 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-600 font-medium">
          <div>
            Showing <span className="font-semibold text-slate-900">{startIndex + 1}</span> to{' '}
            <span className="font-semibold text-slate-900">{endIndex}</span> of{' '}
            <span className="font-semibold text-slate-900">{data.length}</span> entries
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-700 font-semibold hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
              <span>Previous</span>
            </button>

            <span className="px-2 text-slate-500 font-medium">
              Page <strong className="text-slate-800">{currentPage}</strong> of <strong className="text-slate-800">{totalPages}</strong>
            </span>

            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-700 font-semibold hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <span>Next</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default DataTable;
