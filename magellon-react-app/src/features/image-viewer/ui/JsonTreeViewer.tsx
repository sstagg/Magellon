import React, { useState } from 'react';
import {
    Box,
    IconButton,
    Typography,
    Chip,
    Tooltip,
    useTheme,
    alpha,
} from '@mui/material';
import {
    ChevronRight,
    ContentCopy,
    KeyboardArrowDown,
    CheckCircle,
} from '@mui/icons-material';
import {
    Hash,
    FileText,
    Layers,
    Braces,
} from 'lucide-react';

/** Determines the display type, icon, and color for a JSON value. */
export const getValueTypeInfo = (value: any): { type: string; icon: React.ReactNode; color: string } => {
    if (value === null) return { type: 'null', icon: <Hash size={14} />, color: '#757575' };
    if (value === undefined) return { type: 'undefined', icon: <Hash size={14} />, color: '#757575' };
    if (typeof value === 'boolean') return { type: 'boolean', icon: <CheckCircle fontSize="small" />, color: '#4caf50' };
    if (typeof value === 'number') return { type: 'number', icon: <Hash size={14} />, color: '#2196f3' };
    if (typeof value === 'string') return { type: 'string', icon: <FileText size={14} />, color: '#ff9800' };
    if (Array.isArray(value)) return { type: 'array', icon: <Layers size={14} />, color: '#9c27b0' };
    if (typeof value === 'object') return { type: 'object', icon: <Braces size={14} />, color: '#00bcd4' };
    return { type: 'unknown', icon: <Hash size={14} />, color: '#757575' };
};

export interface JsonTreeViewerProps {
    data: Record<string, unknown>;
    level?: number;
}

/** A generic, standalone component that renders a JSON object as an expandable tree. */
const JsonTreeViewer: React.FC<JsonTreeViewerProps> = ({ data, level = 0 }) => {
    const [expanded, setExpanded] = useState<Record<string, boolean>>({});
    const theme = useTheme();

    const toggleExpand = (key: string) => {
        setExpanded(prev => ({ ...prev, [key]: !prev[key] }));
    };

    const renderValue = (key: string, value: any, path: string): React.ReactNode => {
        const typeInfo = getValueTypeInfo(value);
        const isExpandable = typeof value === 'object' && value !== null;
        const isExpanded = expanded[path];

        return (
            <Box key={path} sx={{ ml: level * 3 }}>
                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        py: 0.5,
                        px: 1,
                        borderRadius: 1,
                        cursor: isExpandable ? 'pointer' : 'default',
                        '&:hover': {
                            backgroundColor: alpha(theme.palette.primary.main, 0.08)
                        }
                    }}
                    onClick={() => isExpandable && toggleExpand(path)}
                >
                    {isExpandable && (
                        <IconButton size="small" sx={{ p: 0, mr: 0.5 }}>
                            {isExpanded ? <KeyboardArrowDown fontSize="small" /> : <ChevronRight fontSize="small" />}
                        </IconButton>
                    )}

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1 }}>
                        <Typography
                            variant="body2"
                            sx={{
                                fontFamily: 'monospace',
                                fontWeight: 600,
                                color: theme.palette.primary.main
                            }}
                        >
                            {key}:
                        </Typography>

                        <Chip
                            label={typeInfo.type}
                            size="small"
                            icon={typeInfo.icon as any}
                            sx={{
                                height: 20,
                                fontSize: '0.65rem',
                                backgroundColor: alpha(typeInfo.color, 0.1),
                                color: typeInfo.color,
                                '& .MuiChip-icon': {
                                    color: typeInfo.color,
                                    marginLeft: '4px'
                                }
                            }}
                        />

                        {!isExpandable && (
                            <Typography
                                variant="body2"
                                sx={{
                                    fontFamily: 'monospace',
                                    color: typeInfo.color,
                                    maxWidth: '60%',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap'
                                }}
                            >
                                {JSON.stringify(value)}
                            </Typography>
                        )}
                    </Box>

                    <Tooltip title="Copy value">
                        <IconButton
                            size="small"
                            onClick={(e) => {
                                e.stopPropagation();
                                navigator.clipboard.writeText(JSON.stringify(value, null, 2));
                            }}
                            sx={{ ml: 'auto' }}
                        >
                            <ContentCopy fontSize="small" />
                        </IconButton>
                    </Tooltip>
                </Box>

                {isExpandable && isExpanded && (
                    <Box sx={{ ml: 2, mt: 0.5 }}>
                        {Object.entries(value).map(([k, v]) => renderValue(k, v, `${path}.${k}`))}
                    </Box>
                )}
            </Box>
        );
    };

    return (
        <Box>
            {Object.entries(data).map(([key, value]) => renderValue(key, value, key))}
        </Box>
    );
};

export default JsonTreeViewer;
