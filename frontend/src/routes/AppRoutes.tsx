import React from 'react';
import { Routes, Route } from 'react-router-dom';
import DashboardLayout from '../components/layout/DashboardLayout';
import SystemOverviewPage from '../pages/SystemOverviewPage';
import StationsPage from '../pages/StationsPage';
import StationDetailPage from '../pages/StationDetailPage';
import RegionsPage from '../pages/RegionsPage';
import RegionDetailPage from '../pages/RegionDetailPage';
import DemandRankingPage from '../pages/DemandRankingPage';
import PipelineHealthPage from '../pages/PipelineHealthPage';
import NotFoundPage from '../pages/NotFoundPage';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<DashboardLayout />}>
        <Route index element={<SystemOverviewPage />} />
        <Route path="stations" element={<StationsPage />} />
        <Route path="stations/:stationId" element={<StationDetailPage />} />
        <Route path="regions" element={<RegionsPage />} />
        <Route path="regions/:regionId" element={<RegionDetailPage />} />
        <Route path="ranking" element={<DemandRankingPage />} />
        <Route path="pipelines" element={<PipelineHealthPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
};

export default AppRoutes;
