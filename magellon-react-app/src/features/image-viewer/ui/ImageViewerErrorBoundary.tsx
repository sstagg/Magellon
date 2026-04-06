import React from 'react';
import { Box, Typography, Button, Alert } from '@mui/material';
import { AlertCircle } from 'lucide-react';

interface Props {
    children: React.ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

export class ImageViewerErrorBoundary extends React.Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error('ImageViewer error:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <Box sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    gap: 2,
                    p: 4,
                }}>
                    <AlertCircle size={48} />
                    <Typography variant="h6">Something went wrong</Typography>
                    <Alert severity="error" sx={{ maxWidth: 500 }}>
                        {this.state.error?.message || 'An unexpected error occurred in the image viewer.'}
                    </Alert>
                    <Button
                        variant="outlined"
                        onClick={() => this.setState({ hasError: false, error: null })}
                    >
                        Try Again
                    </Button>
                </Box>
            );
        }

        return this.props.children;
    }
}
