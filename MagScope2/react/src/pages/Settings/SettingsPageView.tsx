import React, { useState } from 'react';
import MicroscopeColumn from './MicroscopeColumn';
import PropertyExplorer from './PropertyExplorer';
import { PresetsEditor } from './PresetsEditor';
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable';
import { Button } from '@/components/ui/button';
import { BookmarkPlus } from 'lucide-react';

const SettingsPageView: React.FC = () => {
    const [showPresetsEditor, setShowPresetsEditor] = useState(false);

    return (
        <div className="h-full bg-background">
            {/* Floating Presets Button */}
            <div className="absolute top-4 right-4 z-10">
                <Button onClick={() => setShowPresetsEditor(true)}>
                    <BookmarkPlus className="w-4 h-4 mr-2" />
                    Manage Presets
                </Button>
            </div>

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

            {/* Presets Editor Modal */}
            <PresetsEditor
                open={showPresetsEditor}
                onOpenChange={setShowPresetsEditor}
            />
        </div>
    );
};

export default SettingsPageView;
