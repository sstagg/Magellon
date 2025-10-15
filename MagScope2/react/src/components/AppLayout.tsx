import { Outlet, Link, useLocation } from "react-router-dom";
import { Microscope, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export function AppLayout() {
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden">
      {/* Header */}
      <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center justify-between border-b bg-background px-6">
        {/* Left: Logo and Title */}
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Microscope className="h-5 w-5" />
          </div>
          <div className="flex flex-col">
            <span className="text-lg font-semibold">MagScope Control System</span>
            <span className="text-xs text-muted-foreground">Electron Microscopy Platform</span>
          </div>
        </div>

        {/* Center: Navigation Links */}
        <nav className="flex items-center gap-1">
          <Link to="/microscopy">
            <Button
              variant={isActive("/microscopy") ? "secondary" : "ghost"}
              className={cn(
                "font-medium",
                isActive("/microscopy") && "bg-secondary"
              )}
            >
              Microscopy
            </Button>
          </Link>
          <Link to="/test-idea">
            <Button
              variant={isActive("/test-idea") ? "secondary" : "ghost"}
              className={cn(
                "font-medium",
                isActive("/test-idea") && "bg-secondary"
              )}
            >
              Test Idea
            </Button>
          </Link>
        </nav>

        {/* Right: Settings */}
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" title="Settings">
            <Settings className="h-5 w-5" />
          </Button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
