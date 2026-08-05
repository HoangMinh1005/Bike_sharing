import React from 'react';

interface PageContainerProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}

export const PageContainer: React.FC<PageContainerProps> = ({
  title,
  description,
  action,
  children,
}) => {
  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">{title}</h1>
          {description && <p className="text-xs text-slate-500 mt-1">{description}</p>}
        </div>
        {action && <div className="flex items-center gap-3">{action}</div>}
      </div>

      {/* Main Page Content */}
      <div>{children}</div>
    </div>
  );
};

export default PageContainer;
