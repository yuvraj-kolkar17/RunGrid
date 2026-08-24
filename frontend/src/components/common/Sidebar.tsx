import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, ListAlt, SearchCheck, Hub, Analytics, 
  Monitoring, Layers, AccountTree, Speed, ErrorOutline, Cloud, CheckCircle2, X 
} from '../../components/common/MaterialIcons';
import { useAuth } from '../../context/AuthContext';

interface SidebarProps {
  isMobileOpen: boolean;
  onCloseMobile: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isMobileOpen, onCloseMobile }) => {
  const { user } = useAuth();
  const orgName = user?.organization_id ? 'Acme Cloud' : 'Acme Cloud';

  const navItems = [
    { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { label: 'Queues', path: '/queues', icon: ListAlt },
    { label: 'Jobs Explorer', path: '/jobs', icon: SearchCheck },
    { label: 'Worker Cluster', path: '/workers', icon: Hub },
    { label: 'Platform Overview', path: '/platform', icon: Analytics },
    { label: 'Observability', path: '/platform/observability', icon: Monitoring },
    { label: 'Batch Submissions', path: '/platform/batches', icon: Layers },
    { label: 'Workflows', path: '/platform/workflows', icon: AccountTree },
    { label: 'Rate Limiting', path: '/platform/rate-limits', icon: Speed },
    { label: 'Failure Analysis', path: '/platform/failures', icon: ErrorOutline },
  ];

  const content = (
    <div className="flex h-full flex-col justify-between bg-[#0b0e15] border-r border-[#424754]/30 w-[240px] z-50">
      <div className="flex flex-col">
        {/* Brand Header */}
        <div className="px-6 py-6 border-b border-[#424754]/30 flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded bg-[#4d8eff] flex items-center justify-center text-[#002e6a] font-bold text-sm">
                DS
              </div>
              <h1 className="font-bold text-[#e1e2ec] text-base tracking-tight leading-tight">
                Distributed Scheduler
              </h1>
            </div>
            <button onClick={onCloseMobile} className="md:hidden text-slate-400 hover:text-white">
              <X className="w-5 h-5" />
            </button>
          </div>
          <p className="text-[13px] text-[#c2c6d6] font-mono pl-11">V2.4.1-stable</p>
        </div>

        {/* Navigation List */}
        <div className="py-4 flex flex-col gap-1 px-3 overflow-y-auto max-h-[calc(100vh-160px)]">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/dashboard' || item.path === '/platform'}
                onClick={onCloseMobile}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded transition-colors duration-150 text-[14px] ${
                    isActive
                      ? 'bg-[#571bc1]/90 text-[#c4abff] font-semibold'
                      : 'text-[#c2c6d6] hover:text-[#e1e2ec] hover:bg-[#272a31]/80'
                  }`
                }
              >
                <Icon className="text-[20px]" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </div>
      </div>

      {/* Footer Environment Tabs */}
      <div className="p-4 border-t border-[#424754]/30 flex flex-col gap-2 bg-[#0b0e15]">
        <div className="flex items-center gap-2 text-[#c2c6d6] text-[13px] px-2">
          <Cloud className="text-[16px]" />
          <span>{orgName}</span>
        </div>
        <div className="flex items-center gap-2 text-[#4cd7f6] text-[13px] px-2 font-medium">
          <CheckCircle2 className="text-[16px]" />
          <span>System Operational</span>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <nav className="hidden md:flex h-screen fixed left-0 top-0 z-50">
        {content}
      </nav>

      {/* Mobile Drawer */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm" onClick={onCloseMobile} />
          <nav className="fixed inset-y-0 left-0 z-50">
            {content}
          </nav>
        </div>
      )}
    </>
  );
};

