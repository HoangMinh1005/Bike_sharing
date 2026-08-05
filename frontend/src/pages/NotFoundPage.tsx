import React from 'react';
import { useNavigate } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import { Home } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <PageContainer title="404 — Page Not Found">
      <div className="flex flex-col items-center justify-center h-80 bg-white rounded-xl border border-slate-200 p-8 text-center">
        <h2 className="text-4xl font-extrabold text-slate-800 tracking-tight mb-2">404</h2>
        <p className="text-sm font-semibold text-slate-700 mb-1">Page Not Found</p>
        <p className="text-xs text-slate-500 max-w-sm mb-6">
          The dashboard route you requested does not exist or has been moved.
        </p>
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-700 transition-colors shadow-sm"
        >
          <Home className="w-4 h-4" />
          Back to Overview
        </button>
      </div>
    </PageContainer>
  );
};

export default NotFoundPage;
