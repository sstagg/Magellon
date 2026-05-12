/**
 * PluginLogsPanel — combined one-shot tail + live stream of a plugin's
 * stdout/stderr.
 *
 * Two flavours via the ``compact`` prop:
 *   - Compact (false): full-tab view with controls (clear, pause), the
 *     full 2000-line buffer, and a follow-on-new-line autoscroll.
 *   - Compact (true): inline preview rendered on a card when Healthy
 *     is False — last 12 lines, monospace, no controls.
 *
 * Pause toggles the Socket.IO subscription so a noisy plugin can't
 * keep the operator from reading what's already there.
 */
import React, { useEffect, useRef, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    IconButton,
    Stack,
    Tooltip,
    Typography,
} from '@mui/material';
import { Eraser, Pause, Play, ScrollText } from 'lucide-react';
import { usePluginLogs } from '../api/installerApi.ts';
import { usePluginLogStream, type PluginLogLine } from '../hooks/usePluginLogStream.ts';

interface PluginLogsPanelProps {
    pluginId: string;
    /** Inline-on-card mode: smaller, no controls, fewer lines. */
    compact?: boolean;
    /** Override the initial-tail size. Default 200 for full view, 12
     *  for compact. */
    initialTail?: number;
}

export const PluginLogsPanel: React.FC<PluginLogsPanelProps> = ({
    pluginId, compact = false, initialTail,
}) => {
    const tail = initialTail ?? (compact ? 12 : 200);
    const oneShot = usePluginLogs(pluginId, tail);
    const [paused, setPaused] = useState(false);
    const { lines: streamed, connected, clear } = usePluginLogStream(
        pluginId, { paused, bufferSize: compact ? 50 : 2000 },
    );
    const scrollRef = useRef<HTMLDivElement | null>(null);
    const [autoscroll, setAutoscroll] = useState(true);

    // Autoscroll on new content unless the user has scrolled up.
    useEffect(() => {
        if (!autoscroll || !scrollRef.current) return;
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [streamed, oneShot.data, autoscroll]);

    const onScroll: React.UIEventHandler<HTMLDivElement> = (e) => {
        const el = e.currentTarget;
        const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 16;
        setAutoscroll(atBottom);
    };

    if (oneShot.isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                <CircularProgress size={20} />
            </Box>
        );
    }

    if (oneShot.isError) {
        const err = oneShot.error as { response?: { status?: number } };
        if (err?.response?.status === 404) {
            return (
                <Alert severity="info" sx={{ py: 0.5 }}>
                    No log source — plugin not installed (or never started).
                </Alert>
            );
        }
        return (
            <Alert severity="warning" sx={{ py: 0.5 }}>
                Could not fetch logs.
            </Alert>
        );
    }

    const initialLines = oneShot.data?.lines ?? [];
    // Display = initial one-shot lines (numbered from -N) then live
    // stream lines (numbered up from 0). Stable React keys per group.
    const renderLine = (text: string, key: string, isError = false) => (
        <Box
            key={key}
            component="div"
            sx={{
                fontFamily: 'monospace',
                fontSize: compact ? 11 : 12,
                whiteSpace: 'pre',
                color: isError ? 'error.main' : 'text.primary',
                lineHeight: 1.4,
            }}
        >
            {text || ' ' /* nbsp so empty lines still take a row */}
        </Box>
    );

    return (
        <Box>
            {!compact && (
                <Stack
                    direction="row"
                    spacing={1}
                    sx={{ alignItems: 'center', mb: 1, flexWrap: 'wrap' }}
                >
                    <ScrollText size={16} />
                    <Typography variant="body2" sx={{ flex: 1 }}>
                        Last {tail} lines + live tail
                    </Typography>
                    <Chip
                        size="small"
                        label={connected ? 'live' : 'disconnected'}
                        color={connected ? 'success' : 'default'}
                        variant={connected ? 'filled' : 'outlined'}
                    />
                    <Tooltip title={paused ? 'Resume live tail' : 'Pause live tail'}>
                        <IconButton
                            size="small"
                            onClick={() => setPaused((p) => !p)}
                            aria-label={paused ? 'resume' : 'pause'}
                        >
                            {paused ? <Play size={14} /> : <Pause size={14} />}
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Clear streamed lines (keeps initial tail)">
                        <IconButton
                            size="small" onClick={clear} aria-label="clear"
                        >
                            <Eraser size={14} />
                        </IconButton>
                    </Tooltip>
                    {!autoscroll && (
                        <Button
                            size="small"
                            onClick={() => setAutoscroll(true)}
                        >
                            jump to latest
                        </Button>
                    )}
                </Stack>
            )}

            <Box
                ref={scrollRef}
                onScroll={onScroll}
                sx={{
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1,
                    p: 1,
                    bgcolor: 'background.default',
                    maxHeight: compact ? 180 : 480,
                    minHeight: compact ? 60 : 200,
                    overflow: 'auto',
                }}
            >
                {initialLines.length === 0 && streamed.length === 0 ? (
                    <Typography
                        variant="caption" sx={{ color: 'text.secondary' }}
                    >
                        No log output yet.
                    </Typography>
                ) : (
                    <>
                        {initialLines.map((line, i) =>
                            renderLine(line, `init-${i}`),
                        )}
                        {streamed.map((entry: PluginLogLine) =>
                            renderLine(entry.line, `live-${entry.id}`, entry.error),
                        )}
                    </>
                )}
            </Box>
        </Box>
    );
};
