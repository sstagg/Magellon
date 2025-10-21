import { Outlet, Link, useLocation } from "react-router-dom";
import { Microscope, History, Settings as SettingsIcon, Microscope as MicroscopeIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useMicroscopyHeader } from "@/contexts/MicroscopyHeaderContext";

export function AppLayout() {
  const location = useLocation();
  const microscopyHeader = useMicroscopyHeader();

  const isActive = (path: string) => location.pathname === path;

  // Get page title based on current route
  const getPageTitle = () => {
    switch (location.pathname) {
      case "/microscopy":
        return "Microscopy";
      case "/test-idea":
        return "Settings";
      default:
        return "MagScope";
    }
  };

  return (
    <div className="flex h-screen w-screen flex-col bg-background">
      {/* Header */}
      <header className="w-full border-b bg-gradient-to-r from-background via-primary/5 to-background backdrop-blur-sm">
        <div className="flex h-16 items-center justify-between px-8">
          {/* Logo and Title */}
          <div className="flex items-center gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary/70 shadow-lg">
              <Microscope className="h-6 w-6 text-primary-foreground" />
            </div>
            <div className="flex flex-col">
              <span className="text-xl font-bold bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                MagScope
              </span>
              <span className="text-xs text-muted-foreground">Control System</span>
            </div>
            <div className="h-8 w-px bg-border mx-2" />
            <span className="text-sm font-bold bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
              {getPageTitle()}
            </span>
          </div>

          {/* Right side: Microscopy controls + Navigation */}
          <div className="flex items-center gap-4">
            {/* Microscopy-specific header controls */}
            {location.pathname === "/microscopy" && (
              <div className="flex items-center gap-2 border-r pr-4">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => microscopyHeader.setShowHistory(true)}
                  title="Acquisition History"
                >
                  <Badge variant="secondary" className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 text-xs">
                    {microscopyHeader.acquisitionHistoryCount}
                  </Badge>
                  <History className="w-5 h-5" />
                </Button>

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => microscopyHeader.setShowMicroscopePanel(true)}
                  title="Microscope Details"
                >
                  <MicroscopeIcon className="w-5 h-5" />
                </Button>

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => microscopyHeader.setShowAdvancedSettings(true)}
                  title="Advanced Settings"
                >
                  <SettingsIcon className="w-5 h-5" />
                </Button>
              </div>
            )}

            {/* Navigation */}
            <nav className="flex gap-2">
              <Link to="/microscopy">
                <Button
                  variant={isActive("/microscopy") ? "default" : "ghost"}
                  size="default"
                  className="font-medium"
                >
                  Microscopy
                </Button>
              </Link>
              <Link to="/test-idea">
                <Button
                  variant={isActive("/test-idea") ? "default" : "ghost"}
                  size="default"
                  className="font-medium"
                >
                  Settings
                </Button>
              </Link>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 w-full overflow-hidden bg-gradient-to-br from-background via-background to-muted/20">
        <Outlet />
      </main>
    </div>
  );
}
