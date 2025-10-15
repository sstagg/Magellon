import { Outlet, Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Microscope } from "lucide-react";

export function AppLayout() {
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="flex h-screen w-screen flex-col bg-background">
      {/* Header */}
      <header className="w-full border-b bg-gradient-to-r from-background via-primary/5 to-background backdrop-blur-sm">
        <div className="flex h-16 items-center justify-between px-8">
          {/* Logo and Title */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary/70 shadow-lg">
              <Microscope className="h-6 w-6 text-primary-foreground" />
            </div>
            <div className="flex flex-col">
              <span className="text-xl font-bold bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                MagScope
              </span>
              <span className="text-xs text-muted-foreground">Control System</span>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex gap-2">
            <Link to="/microscopy">
              <button
                className={cn(
                  "relative px-6 py-2 rounded-lg font-medium text-sm transition-all duration-200",
                  isActive("/microscopy")
                    ? "bg-foreground text-background shadow-lg hover:bg-foreground/90"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                )}
              >
                Microscopy
                {isActive("/microscopy") && (
                  <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-1/2 h-0.5 bg-background/50 rounded-full" />
                )}
              </button>
            </Link>
            <Link to="/test-idea">
              <button
                className={cn(
                  "relative px-6 py-2 rounded-lg font-medium text-sm transition-all duration-200",
                  isActive("/test-idea")
                    ? "bg-foreground text-background shadow-lg hover:bg-foreground/90"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                )}
              >
                Settings
                {isActive("/test-idea") && (
                  <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-1/2 h-0.5 bg-background/50 rounded-full" />
                )}
              </button>
            </Link>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 w-full overflow-hidden bg-gradient-to-br from-background via-background to-muted/20">
        <Outlet />
      </main>
    </div>
  );
}
