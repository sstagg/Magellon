import React from 'react';
import { Settings } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export const ControlPanel: React.FC = () => {
    return (
        <Card className="h-full flex flex-col">
            <CardHeader>
                <div className="flex items-center gap-2">
                    <Settings className="w-5 h-5" />
                    <h3 className="text-lg font-semibold">Control Panel</h3>
                </div>
            </CardHeader>
            <CardContent className="flex-1">
                <div className="space-y-4">
                    <div className="text-sm text-muted-foreground">
                        Control panel for microscope operations
                    </div>
                    <div className="grid gap-2">
                        <Button variant="outline" size="sm">Stage Control</Button>
                        <Button variant="outline" size="sm">Beam Settings</Button>
                        <Button variant="outline" size="sm">Focus Control</Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};
