import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import {
  FileSearch,
  LogOut,
  Menu,
  Settings2,
  Shield,
  ShieldCheck,
  X,
} from 'lucide-react';
import { type RootState } from '@/app/store';
import { useAuth } from '@/hooks/useAuth';
import { getUserDisplayName, getUserInitial } from '@/utils/userDisplay';
import { Button } from '../ui/button';
import { ThemeToggle } from '../common/ThemeToggle';

interface AuditorLayoutProps {
  children: React.ReactNode;
}

const AUDIT_NAV = [
  { to: '/audit/logs', label: 'Audit Logs', icon: FileSearch },
];

export const AuditorLayout: React.FC<AuditorLayoutProps> = ({ children }) => {
  const { logout, activeOrganization } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useSelector((state: RootState) => state.auth);
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);

  const displayName = getUserDisplayName(user, 'Auditor');
  const initial = getUserInitial(user, displayName);

  const handleLogout = () => {
    void logout().finally(() => navigate('/login'));
  };

  const isRouteActive = (to: string) =>
    location.pathname === to || location.pathname.startsWith(`${to}/`);

  const linkClass = (to: string) =>
    [
      'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200',
      isRouteActive(to)
        ? 'bg-primary/10 text-primary ring-1 ring-primary/15'
        : 'text-muted-foreground hover:bg-accent hover:text-foreground',
    ].join(' ');

  const iconClass = (to: string) =>
    [
      'flex h-8 w-8 items-center justify-center rounded-lg transition-all duration-200',
      isRouteActive(to)
        ? 'bg-primary/12 text-primary'
        : 'bg-muted/70 text-muted-foreground group-hover:bg-background group-hover:text-foreground',
    ].join(' ');

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile header */}
      <header className="sticky top-0 z-50 flex h-16 items-center justify-between border-b border-border/70 bg-background/95 px-4 backdrop-blur-xl lg:hidden">
        <Link to="/" className="flex items-center gap-2">
          <Shield className="h-8 w-8 text-primary" />
          <span className="text-xl font-bold tracking-tight">CAVP</span>
        </Link>
        <Button variant="ghost" size="icon" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
          {mobileMenuOpen ? <X /> : <Menu />}
        </Button>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside
          className={[
            'fixed inset-y-0 left-0 z-40 w-64 transform border-r border-border/70 bg-background/95 shadow-xl transition-transform duration-300 lg:translate-x-0 lg:shadow-none xl:w-72',
            mobileMenuOpen ? 'translate-x-0' : '-translate-x-full',
          ].join(' ')}
        >
          <div className="flex h-full flex-col p-4">
            {/* Logo */}
            <div className="mb-8 hidden px-2 lg:block">
              <Link to="/" className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg">
                  <Shield className="h-6 w-6" />
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-primary">
                    Audit Portal
                  </p>
                  <p className="text-xl font-bold tracking-tight">CAVP</p>
                </div>
              </Link>
            </div>

            {/* Org context */}
            {activeOrganization && (
              <div className="mb-6">
                <p className="px-2 text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
                  Audit Scope
                </p>
                <div className="mt-2 rounded-xl border border-border/70 bg-card/50 px-3 py-2 text-sm font-medium">
                  {activeOrganization.name}
                </div>
              </div>
            )}

            {/* Notice */}
            <div className="mb-6 rounded-xl border border-amber-400/30 bg-amber-400/8 px-3 py-2.5">
              <p className="text-[11px] font-semibold text-amber-700 leading-relaxed">
                Audit access is read-only. You can view activity logs but cannot modify any records.
              </p>
            </div>

            {/* Navigation */}
            <nav className="flex-1 space-y-1">
              <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
                Audit Tools
              </p>
              {AUDIT_NAV.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={linkClass(item.to)}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <span className={iconClass(item.to)}>
                      <Icon className="h-4 w-4" />
                    </span>
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            {/* Footer */}
            <div className="mt-auto space-y-1 border-t border-border/70 pt-4">
              <div className="mb-4 flex items-center gap-3 px-3 py-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary text-xs font-bold">
                  {initial}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold">{displayName}</p>
                  <p className="text-[10px] text-muted-foreground">Auditor</p>
                </div>
              </div>
              <Link to="/settings" className={linkClass('/settings')}>
                <span className={iconClass('/settings')}>
                  <Settings2 className="h-4 w-4" />
                </span>
                Profile
              </Link>
              <Link to="/security" className={linkClass('/security')}>
                <span className={iconClass('/security')}>
                  <ShieldCheck className="h-4 w-4" />
                </span>
                Security
              </Link>
              <ThemeToggle className="w-full justify-start gap-3 rounded-xl border-0 bg-transparent px-3 py-2.5 font-medium hover:bg-accent" />
              <button
                onClick={handleLogout}
                className="flex w-full items-center gap-3 rounded-xl bg-destructive/10 px-3 py-2.5 text-sm font-semibold text-destructive transition-colors hover:bg-destructive/15"
              >
                <LogOut className="h-4 w-4" />
                Logout
              </button>
            </div>
          </div>
        </aside>

        {/* Mobile overlay */}
        {mobileMenuOpen && (
          <div
            className="fixed inset-0 z-30 bg-background/80 backdrop-blur-sm lg:hidden"
            onClick={() => setMobileMenuOpen(false)}
          />
        )}

        {/* Main content */}
        <main className="min-h-screen w-full lg:pl-64 xl:pl-72">
          <div className="p-4 md:p-6 lg:p-8">{children}</div>
        </main>
      </div>
    </div>
  );
};
