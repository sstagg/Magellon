import React from 'react';
import { Camera } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/card';

export const LiveView: React.FC = () => {
    return (
        <Card className="h-full flex flex-col">
            <CardHeader>
                <div className="flex items-center gap-2">
                    <Camera className="w-5 h-5" />
                    <h3 className="text-lg font-semibold">Live View</h3>
                </div>
            </CardHeader>
            <CardContent className="flex-1 flex items-center justify-center bg-muted/20">
                <div className="text-center text-muted-foreground">
                    <Camera className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>Live camera feed will appear here</p>
                </div>
            </CardContent>
        </Card>
    );
};
