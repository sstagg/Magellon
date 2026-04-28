import React, { useRef, useEffect } from 'react';
import {
    Box,
    Typography,
    Chip,
    IconButton,
    Tooltip,
    alpha,
    useTheme,
} from '@mui/material';
import { Delete, ArrowDownward } from '@mui/icons-material';
import { Terminal } from 'lucide-react';
import { useLogStore } from './useLogStore.ts';

const levelColors = {
    info: '#2196f3',
    warn: '#ff9800',
    error: '#f44336',
    debug: '#9e9e9e',
};

export const LogsPanel: React.FC = () => {
    const theme = useTheme();
    const scrollRef = useRef<HTMLDivElement>(null);
    const logs = useLogStore((s) => s.logs);
    const clearLogs = useLogStore((s) => s.clearLogs);

    // Auto-scroll to bottom when new logs arrive
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Header */}
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                px: 1.5,
                py: 0.5,
                borderBottom: `1px solid ${theme.palette.divider}`,
            }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Terminal size={14} />
                    <Typography variant="caption" sx={{
                        fontWeight: 600
                    }}>Logs</Typography>
                    <Chip label={logs.length} size="small" sx={{ height: 18, fontSize: '0.65rem' }} />
                </Box>
                <Box sx={{ display: 'flex', gap: 0.25 }}>
                    <Tooltip title="Scroll to bottom">
                        <IconButton size="small" sx={{ p: 0.25 }}
                            onClick={() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })}
                        >
                            <ArrowDownward sx={{ fontSize: 14 }} />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Clear logs">
                        <IconButton size="small" sx={{ p: 0.25 }} onClick={clearLogs}>
                            <Delete sx={{ fontSize: 14 }} />
                        </IconButton>
                    </Tooltip>
                </Box>
            </Box>
            {/* Log entries */}
            <Box
                ref={scrollRef}
                sx={{
                    flex: 1,
                    overflow: 'auto',
                    fontFamily: 'monospace',
                    fontSize: '0.7rem',
                    lineHeight: 1.8,
                    px: 1,
                    backgroundColor: alpha(theme.palette.common.black, theme.palette.mode === 'dark' ? 0.2 : 0.02),
                }}
            >
                {logs.length === 0 && (
                    <Box sx={{ p: 2, textAlign: 'center' }}>
                        <Typography
                            variant="caption"
                            sx={{
                                color: "text.secondary",
                                fontFamily: "monospace"
                            }}>
                            Waiting for events...
                        </Typography>
                    </Box>
                )}
                {logs.map((log) => (
                    <Box
                        key={log.id}
                        sx={{
                            display: 'flex',
                            gap: 1,
                            py: 0.15,
                            '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.04) },
                        }}
                    >
                        <Typography component="span" sx={{
                            fontSize: 'inherit',
                            fontFamily: 'inherit',
                            color: 'text.secondary',
                            flexShrink: 0,
                        }}>
                            {log.timestamp}
                        </Typography>
                        <Typography component="span" sx={{
                            fontSize: 'inherit',
                            fontFamily: 'inherit',
                            color: levelColors[log.level] || levelColors.info,
                            fontWeight: 600,
                            flexShrink: 0,
                            width: 36,
                            textTransform: 'uppercase',
                        }}>
                            {log.level}
                        </Typography>
                        {log.source && (
                            <Typography component="span" sx={{
                                fontSize: 'inherit',
                                fontFamily: 'inherit',
                                color: 'text.secondary',
                                flexShrink: 0,
                            }}>
                                [{log.source}]
                            </Typography>
                        )}
                        <Typography component="span" sx={{
                            fontSize: 'inherit',
                            fontFamily: 'inherit',
                            color: 'text.primary',
                            flex: 1,
                            minWidth: 0,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                        }}>
                            {log.message}
                        </Typography>
                    </Box>
                ))}
            </Box>
        </Box>
    );
};
