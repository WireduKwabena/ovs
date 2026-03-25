import React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useSelector } from "react-redux";
import {
  Shield,
  LayoutDashboard,
  Building2,
  CreditCard,
  Activity,
  FileSearch,
  LogOut,
  Settings2,
  ShieldCheck,
  Menu,
  X,
  Brain,
} from "lucide-react";
import { type RootState } from "@/app/store";
import { useAuth } from "@/hooks/useAuth";
import { getPlatformAdminPath } from "@/utils/appPaths";
import { getUserDisplayName, getUserInitial } from "@/utils/userDisplay";
import { Button } from "../ui/button";
import { ThemeToggle } from "../common/ThemeToggle";

interface SystemAdminLayoutProps {
  children: React.ReactNode;
}

export const SystemAdminLayout: React.FC<SystemAdminLayoutProps> = ({
  children,
}) => {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useSelector((state: RootState) => state.auth);
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);

  const displayName = getUserDisplayName(user, "System Admin");
  const initial = getUserInitial(user, displayName);

  const navItems = [
    {
      to: getPlatformAdminPath("dashboard"),
      label: "Platform Dashboard",
      icon: LayoutDashboard,
    },
    {
      to: "/admin/platform/ai-engine",
      label: "AI Infrastructure",
      icon: Brain,
    },
    {
      to: "/admin/platform/registry",
      label: "Organization Registry",
      icon: Building2,
    },
    {
      to: "/admin/platform/billing",
      label: "Billing & Plans",
      icon: CreditCard,
    },
    { to: "/admin/platform/health", label: "System Health", icon: Activity },
    {
      to: "/admin/platform/logs",
      label: "Platform Audit Logs",
      icon: FileSearch,
    },
  ];

  const handleLogout = () => {
    void logout().finally(() => navigate("/login"));
  };

  const isRouteActive = (to: string) => {
    return location.pathname === to || location.pathname.startsWith(`${to}/`);
  };

  const sidebarLinkClass = (to: string) =>
    [
      "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
      isRouteActive(to)
        ? "bg-primary/10 text-primary ring-1 ring-primary/15"
        : "text-muted-foreground hover:bg-accent hover:text-foreground",
    ].join(" ");

  const sidebarIconClass = (to: string) =>
    [
      "flex h-8 w-8 items-center justify-center rounded-lg transition-all duration-200",
      isRouteActive(to)
        ? "bg-primary/12 text-primary"
        : "bg-muted/70 text-muted-foreground group-hover:bg-background group-hover:text-foreground",
    ].join(" ");

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile Header */}
      <header className="sticky top-0 z-50 flex h-16 items-center justify-between border-b border-border/70 bg-background/95 px-4 backdrop-blur-xl lg:hidden">
        <Link
          to={getPlatformAdminPath("dashboard")}
          className="flex items-center gap-2"
        >
          <Shield className="h-8 w-8 text-primary" />
          <span className="text-xl font-bold tracking-tight">PLATFORM</span>
        </Link>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        >
          {mobileMenuOpen ? <X /> : <Menu />}
        </Button>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside
          className={[
            "fixed inset-y-0 left-0 z-40 w-64 transform border-r border-border/70 bg-background/95 shadow-xl transition-transform duration-300 lg:translate-x-0 lg:shadow-none xl:w-72",
            mobileMenuOpen ? "translate-x-0" : "-translate-x-full",
          ].join(" ")}
        >
          <div className="flex h-full flex-col overflow-y-auto overflow-x-hidden pr-2 p-4">
            {/* Logo */}
            <div className="mb-8 hidden px-2 lg:block">
              <Link
                to={getPlatformAdminPath("dashboard")}
                className="flex items-center gap-3"
              >
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-linear-to-br from-indigo-500 via-purple-500 to-pink-500 text-white shadow-lg">
                  <Shield className="h-6 w-6" />
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-primary">
                    System Admin
                  </p>
                  <p className="text-xl font-bold tracking-tight">OVS REDO</p>
                </div>
              </Link>
            </div>

            {/* User Profile Summary */}
            <div className="mb-6 rounded-2xl border border-border/70 bg-card/50 p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary font-bold">
                  {initial}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold">
                    {displayName}
                  </p>
                  <p className="truncate text-[11px] text-muted-foreground uppercase tracking-wider">
                    Superuser Access
                  </p>
                </div>
              </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 space-y-1">
              <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
                Main Platform
              </p>
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={sidebarLinkClass(item.to)}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <span className={sidebarIconClass(item.to)}>
                      <Icon className="h-4 w-4" />
                    </span>
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            {/* Footer Utilities */}
            <div className="mt-auto space-y-1 pt-4 border-t border-border/70">
              <Link to="/settings" className={sidebarLinkClass("/settings")}>
                <span className={sidebarIconClass("/settings")}>
                  <Settings2 className="h-4 w-4" />
                </span>
                Profile
              </Link>
              <Link to="/security" className={sidebarLinkClass("/security")}>
                <span className={sidebarIconClass("/security")}>
                  <ShieldCheck className="h-4 w-4" />
                </span>
                Security
              </Link>
              <ThemeToggle className="w-full justify-start gap-3 rounded-xl border-0 bg-transparent px-3 py-2.5 font-medium hover:bg-accent" />
              <button
                onClick={handleLogout}
                className="flex w-full items-center gap-3 rounded-xl bg-destructive/10 px-3 py-2.5 text-sm font-semibold text-destructive hover:bg-destructive/15 transition-colors"
              >
                <LogOut className="h-4 w-4" />
                Logout
              </button>
            </div>
          </div>
        </aside>

        {/* Overlay for mobile */}
        {mobileMenuOpen && (
          <div
            className="fixed inset-0 z-30 bg-background/80 backdrop-blur-sm lg:hidden"
            onClick={() => setMobileMenuOpen(false)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setMobileMenuOpen(false);
            }}
            role="button"
            tabIndex={0}
            aria-label="Close mobile menu"
          />
        )}

        {/* Main Content Area */}
        <main className="min-h-screen w-full lg:pl-64 xl:pl-72">
          {/* Aesthetic Background Accents */}
          <div className="pointer-events-none fixed inset-0 z-[-1] overflow-hidden">
            <div className="absolute top-[-10%] left-[-10%] h-[40%] w-[40%] rounded-full bg-primary/5 blur-[120px]" />
            <div className="absolute bottom-[-10%] right-[-10%] h-[40%] w-[40%] rounded-full bg-indigo-500/5 blur-[120px]" />
          </div>

          <div className="relative p-4 md:p-6 lg:p-8">{children}</div>
        </main>
      </div>
    </div>
  );
};
