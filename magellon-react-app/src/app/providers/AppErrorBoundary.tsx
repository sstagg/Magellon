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

/**
 * Last-resort boundary wrapping the whole app. Feature-local boundaries
 * (e.g. the image viewer's) catch first; anything that escapes them
 * renders this fallback instead of a white screen.
 */
export class AppErrorBoundary extends React.Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error('Unhandled application error:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <Box sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100vh',
                    gap: 2,
                    p: 4,
                }}>
                    <AlertCircle size={48} />
                    <Typography variant="h6">Something went wrong</Typography>
                    <Alert severity="error" sx={{ maxWidth: 500 }}>
                        {this.state.error?.message || 'An unexpected error occurred.'}
                    </Alert>
                    <Button
                        variant="outlined"
                        onClick={() => window.location.reload()}
                    >
                        Reload
                    </Button>
                </Box>
            );
        }

        return this.props.children;
    }
}
