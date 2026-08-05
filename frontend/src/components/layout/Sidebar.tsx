import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  MapPin,
  Compass,
  TrendingUp,
  Activity,
  Bike,
} from 'lucide-react';
import { ROUTES } from '../../utils/constants';

interface NavItem {
  name: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { name: 'Overview', path: ROUTES.OVERVIEW, icon: LayoutDashboard },
  { name: 'Stations', path: ROUTES.STATIONS, icon: MapPin },
  { name: 'Regions', path: ROUTES.REGIONS, icon: Compass },
  { name: 'Demand Ranking', path: ROUTES.RANKING, icon: TrendingUp },
  { name: 'Pipeline Health', path: ROUTES.PIPELINES, icon: Activity },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col h-screen sticky top-0 border-r border-slate-800 shrink-0 overflow-y-auto">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 border-b border-slate-800 gap-3">
        <div className="p-2 rounded-lg bg-emerald-500 text-slate-950 font-bold">
          <Bike className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-sm font-bold text-white tracking-wide leading-tight">GBFS Intelligence</h1>
          <p className="text-[10px] text-slate-400 font-medium">Bike Sharing Platform</p>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold transition-all ${
                  isActive
                    ? 'bg-emerald-600/15 text-emerald-400 border border-emerald-500/20'
                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.name}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* System Footer */}
      <div className="p-4 border-t border-slate-800 text-[11px] text-slate-500">
        <p className="font-semibold text-slate-400">Read-only Operation</p>
        <p className="mt-0.5">Version 1.0.0 • React SPA</p>
      </div>
    </aside>
  );
};

export default Sidebar;
