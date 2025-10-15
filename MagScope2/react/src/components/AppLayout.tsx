import { Outlet, Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";

export function AppLayout() {
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="flex h-screen w-screen flex-col">
      {/* Header */}
      <header className="flex h-14 w-full items-center gap-6 border-b bg-background px-6">
        <div className="font-semibold text-lg">MagScope</div>
        <nav className="flex gap-4">
          <Link
            to="/microscopy"
            className={cn(
              "text-sm font-medium transition-colors hover:text-primary",
              isActive("/microscopy")
                ? "text-foreground"
                : "text-muted-foreground"
            )}
          >
            Microscopy
          </Link>
          <Link
            to="/test-idea"
            className={cn(
              "text-sm font-medium transition-colors hover:text-primary",
              isActive("/test-idea")
                ? "text-foreground"
                : "text-muted-foreground"
            )}
          >
            Test Idea
          </Link>
        </nav>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 w-full overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
