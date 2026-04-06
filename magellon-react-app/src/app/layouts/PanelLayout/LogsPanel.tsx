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

interface LogEntry {
    id: string;
    timestamp: string;
    level: 'info' | 'warn' | 'error' | 'debug';
    message: string;
    source?: string;
}

const MOCK_LOGS: LogEntry[] = [
    { id: '1', timestamp: '10:42:01', level: 'info', message: 'Session 24DEC03A loaded — 47 images', source: 'session' },
    { id: '2', timestamp: '10:42:03', level: 'info', message: 'Atlas images fetched (3 atlases)', source: 'atlas' },
    { id: '3', timestamp: '10:42:05', level: 'debug', message: 'Image columns initialized: GR → SQ → HL → EX', source: 'viewer' },
    { id: '4', timestamp: '10:42:08', level: 'info', message: 'CTF estimation started for 24dec03a_00017gr', source: 'job' },
    { id: '5', timestamp: '10:42:12', level: 'warn', message: 'FFT image not available for grid-level image', source: 'viewer' },
    { id: '6', timestamp: '10:42:15', level: 'error', message: 'CTF info fetch failed: 404 Not Found', source: 'api' },
    { id: '7', timestamp: '10:42:18', level: 'info', message: 'Particle picking session loaded — 142 particles', source: 'picking' },
    { id: '8', timestamp: '10:42:22', level: 'info', message: 'Motion correction completed in 1m 23s', source: 'job' },
    { id: '9', timestamp: '10:42:25', level: 'debug', message: 'Image hierarchy refreshed for level 0', source: 'viewer' },
];

const levelColors = {
    info: '#2196f3',
    warn: '#ff9800',
    error: '#f44336',
    debug: '#9e9e9e',
};

export const LogsPanel: React.FC = () => {
    const theme = useTheme();
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, []);

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
                    <Typography variant="caption" fontWeight={600}>Logs</Typography>
                    <Chip label={MOCK_LOGS.length} size="small" sx={{ height: 18, fontSize: '0.65rem' }} />
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
                        <IconButton size="small" sx={{ p: 0.25 }}>
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
                {MOCK_LOGS.map((log) => (
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
                            color: levelColors[log.level],
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
