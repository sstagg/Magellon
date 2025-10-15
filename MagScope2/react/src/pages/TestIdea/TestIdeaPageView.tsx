import React from 'react';
import MicroscopeColumn from './MicroscopeColumn';
import PropertyExplorer from './PropertyExplorer';
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable';

const TestIdeaPageView: React.FC = () => {
    return (
        <div className="fixed inset-0 bg-background">
            <ResizablePanelGroup direction="horizontal" className="h-full">
                {/* Main Microscope Column Area */}
                <ResizablePanel defaultSize={75} minSize={50}>
                    <div className="h-full overflow-auto">
                        <MicroscopeColumn />
                    </div>
                </ResizablePanel>

                <ResizableHandle withHandle />

                {/* Property Explorer Sidebar */}
                <ResizablePanel defaultSize={25} minSize={20} maxSize={40}>
                    <div className="h-full overflow-hidden">
                        <PropertyExplorer />
                    </div>
                </ResizablePanel>
            </ResizablePanelGroup>
        </div>
    );
};

export default TestIdeaPageView;
