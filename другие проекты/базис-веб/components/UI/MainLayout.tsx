import React, { ReactNode } from 'react';

interface MainLayoutProps {
  navBar: ReactNode;
  toolbar?: ReactNode;
  sidePanel?: ReactNode;
  rightPanel?: ReactNode;
  mainContent: ReactNode;
  statusBar?: ReactNode;
  showSidePanel?: boolean;
  showRightPanel?: boolean;
}

export const MainLayout: React.FC<MainLayoutProps> = ({
  navBar,
  toolbar,
  sidePanel,
  rightPanel,
  mainContent,
  statusBar,
  showSidePanel = true,
  showRightPanel = true
}) => {
  return (
    <div className="h-screen w-full flex flex-col bg-slate-900 text-slate-100 overflow-hidden">
      {/* Navigation Bar */}
      <div className="flex-shrink-0">
        {navBar}
      </div>

      {/* Toolbar */}
      {toolbar && <div className="flex-shrink-0">{toolbar}</div>}

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Side Panel */}
        {showSidePanel && <div className="flex-shrink-0 overflow-hidden">{sidePanel}</div>}

        {/* Main Workspace */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Center Content */}
          <div className="flex-1 overflow-auto bg-slate-800">
            {mainContent}
          </div>

          {/* Bottom Status Bar */}
          {statusBar && <div className="flex-shrink-0">{statusBar}</div>}
        </div>

        {/* Right Panel */}
        {showRightPanel && <div className="flex-shrink-0 border-l border-slate-700 overflow-hidden">{rightPanel}</div>}
      </div>
    </div>
  );
};
