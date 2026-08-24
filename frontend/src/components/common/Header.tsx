import React, { useEffect, useState, useRef } from 'react';
import { useLocation, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { getHealth, getReady } from '../../services/metrics';
import { Search, Refresh, Notifications, Settings } from '../../components/common/MaterialIcons';
import { Menu, LogOut, User as UserIcon, Keyboard } from 'lucide-react';

interface HeaderProps {
  onToggleMobileSidebar: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onToggleMobileSidebar }) => {
  const { user, logout } = useAuth();
  const { addToast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsProfileOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    async function checkHealth() {
      try {
        const h = await getHealth();
        const r = await getReady();
        setIsHealthy(h.status === 'healthy' && r.status === 'ready');
      } catch {
        setIsHealthy(false);
      }
    }
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  const emailPrefix = user?.email ? user.email.split('@')[0] : 'User';
  const initials = emailPrefix.substring(0, 1).toUpperCase();

  const path = location.pathname;
  let activeTab = 'Dashboard';
  if (path.startsWith('/queues')) activeTab = 'Queues';
  else if (path.startsWith('/jobs')) activeTab = 'Jobs';
  else if (path.startsWith('/workers')) activeTab = 'Workers';
  else if (path.startsWith('/platform')) activeTab = 'Platform';

  return (
    <div className="flex flex-col w-full sticky top-0 z-40">
      {/* TopNavBar Component */}
      <header className="bg-[#10131a] flex justify-between items-center h-14 px-6 border-b border-[#424754]/30">
        {/* Navigation Links */}
        <div className="flex gap-6 h-full items-center">
          <button
            onClick={onToggleMobileSidebar}
            className="md:hidden text-[#c2c6d6] hover:text-white p-1"
          >
            <Menu className="w-5 h-5" />
          </button>
          <Link
            to="/dashboard"
            className={`h-full flex items-center text-xs font-semibold uppercase tracking-wider ${
              activeTab === 'Dashboard'
                ? 'text-[#adc6ff] border-b-2 border-[#adc6ff]'
                : 'text-[#c2c6d6] hover:text-[#e1e2ec]'
            }`}
          >
            Dashboard
          </Link>
          <Link
            to="/platform"
            className={`h-full flex items-center text-xs font-semibold uppercase tracking-wider ${
              activeTab === 'Platform'
                ? 'text-[#adc6ff] border-b-2 border-[#adc6ff]'
                : 'text-[#c2c6d6] hover:text-[#e1e2ec]'
            }`}
          >
            Overview
          </Link>
        </div>

        {/* Actions & Profile */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/jobs')}
            className="bg-transparent border border-[#424754]/50 text-[#e1e2ec] px-3 py-1.5 rounded text-xs hover:bg-[#272a31] transition-colors flex items-center gap-2 font-medium"
          >
            <Search className="text-[16px]" />
            Explorer
          </button>
          <button
            onClick={() => window.location.reload()}
            className="bg-[#adc6ff] text-[#002e6a] px-3 py-1.5 rounded text-xs font-medium hover:brightness-110 transition-colors flex items-center gap-2"
          >
            <Refresh className="text-[16px]" />
            Refresh
          </button>

          <div className="flex items-center gap-2 border-l border-[#424754]/40 pl-4 ml-2">
            <button
              onClick={() => addToast('No unread notifications', 'info')}
              className="text-[#c2c6d6] hover:text-[#e1e2ec] transition-colors w-8 h-8 flex items-center justify-center rounded hover:bg-[#272a31]"
            >
              <Notifications className="text-[20px]" />
            </button>
            <button
              onClick={() => addToast('System configuration active', 'info')}
              className="text-[#c2c6d6] hover:text-[#e1e2ec] transition-colors w-8 h-8 flex items-center justify-center rounded hover:bg-[#272a31]"
            >
              <Settings className="text-[20px]" />
            </button>

            {/* Profile Avatar & Dropdown */}
            {user && (
              <div className="relative ml-2" ref={dropdownRef}>
                <button
                  onClick={() => setIsProfileOpen(!isProfileOpen)}
                  className="w-8 h-8 rounded-full bg-[#272a31] border border-[#424754]/50 flex items-center justify-center overflow-hidden text-xs font-mono font-bold text-[#c2c6d6] hover:border-[#adc6ff] transition-all"
                >
                  {initials}
                </button>

                {isProfileOpen && (
                  <div className="absolute right-0 mt-2 w-64 rounded-2xl bg-[#191b23] border border-[#424754]/50 shadow-2xl p-2 z-50">
                    <div className="p-3 border-b border-[#424754]/30 space-y-1">
                      <div className="text-xs font-bold text-white capitalize">{emailPrefix}</div>
                      <p className="text-[11px] text-[#c2c6d6] font-mono truncate">{user.email}</p>
                    </div>

                    <div className="py-1 space-y-0.5">
                      <button
                        onClick={() => {
                          setIsProfileOpen(false);
                          addToast(`User ID: ${user.id}`, 'info');
                        }}
                        className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-[#c2c6d6] hover:text-white hover:bg-[#272a31] rounded transition-colors text-left"
                      >
                        <UserIcon className="h-3.5 w-3.5" />
                        <span>Profile Details</span>
                      </button>

                      <button
                        onClick={() => {
                          setIsProfileOpen(false);
                          addToast('Shortcuts: Cmd+K Search | G+D Dashboard', 'info');
                        }}
                        className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-[#c2c6d6] hover:text-white hover:bg-[#272a31] rounded transition-colors text-left"
                      >
                        <Keyboard className="h-3.5 w-3.5" />
                        <span>Shortcuts</span>
                      </button>
                    </div>

                    <div className="pt-1 border-t border-[#424754]/30">
                      <button
                        onClick={() => {
                          setIsProfileOpen(false);
                          logout();
                        }}
                        className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-rose-400 hover:bg-rose-950/40 rounded transition-colors text-left"
                      >
                        <LogOut className="h-3.5 w-3.5" />
                        <span>Sign Out</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* SystemStatusBanner Component */}
      <div className="bg-[#191b23] border-b border-[#424754]/30 flex items-center justify-center py-1 w-full relative z-30">
        <div className="flex items-center gap-2 text-[11px] font-bold tracking-wider uppercase text-[#4cd7f6]">
          <span className={`w-2 h-2 rounded-full ${isHealthy === false ? 'bg-rose-500' : 'bg-[#4cd7f6] animate-pulse'}`} />
          {isHealthy === false ? 'SYSTEM ALERT — CONNECTION DISCONNECTED' : 'ALL SYSTEMS OPERATIONAL'}
        </div>
      </div>
    </div>
  );
};

