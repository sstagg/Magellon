// MetadataExplorer.tsx - Reusable metadata explorer component

import React, { useState, useMemo } from 'react';
import {
    Box,
    Paper,
    Typography,
    TextField,
    InputAdornment,
    IconButton,
    Chip,
    List,
    ListItemIcon,
    ListItemText,
    ListItemButton,
    Breadcrumbs,
    Link,
    Tooltip,
    Card,
    CardContent,
    Divider,
    Stack,
    Button,
    ButtonGroup,
    Alert,
    Skeleton,
    Zoom,
    useTheme,
    useMediaQuery,
    alpha,
    Collapse as MuiCollapse
} from '@mui/material';
import {
    Search,
    Clear,
    ChevronRight,
    Category,
    Description,
    Code,
    ContentCopy,
    Download,
    KeyboardArrowDown,
    Folder,
    FolderOpen,
    Terminal,
    Error as ErrorIcon
} from '@mui/icons-material';
import {
    Database,
    FileJson,
    TreePine,
} from 'lucide-react';
import { CategoryDto, MetadataDto } from "../../../entities/image/types.ts";
import JsonTreeViewer from "./JsonTreeViewer.tsx";

export interface MetadataExplorerProps {
    /** Metadata categories to display */
    categories: CategoryDto[] | null;
    /** Loading state */
    isLoading?: boolean;
    /** Error state */
    error?: Error | null;
    /** Callback to retry/refresh */
    onRefresh?: () => void;
}

// Main component
const MetadataExplorer: React.FC<MetadataExplorerProps> = ({ categories, isLoading = false, error = null, onRefresh }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // State management
    const [selectedCategory, setSelectedCategory] = useState<CategoryDto | null>(null);
    const [selectedMeta, setSelectedMeta] = useState<MetadataDto | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [viewMode, setViewMode] = useState<'tree' | 'json' | 'raw'>('tree');
    const [showRawData, setShowRawData] = useState(false);
    const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
    const [filterAnchor, setFilterAnchor] = useState<null | HTMLElement>(null);
    const [sortBy, setSortBy] = useState<'name' | 'type'>('name');
    const [breadcrumbs, setBreadcrumbs] = useState<{ id: string; name: string }[]>([]);

    // Calculate statistics
    const stats = useMemo(() => {
        if (!categories) return { totalCategories: 0, totalMetadata: 0 };

        let totalCategories = 0;
        let totalMetadata = 0;

        const countRecursive = (cats: CategoryDto[]) => {
            cats.forEach(cat => {
                totalCategories++;
                totalMetadata += cat.metadata?.length || 0;
                if (cat.children) countRecursive(cat.children);
            });
        };

        countRecursive(categories);
        return { totalCategories, totalMetadata };
    }, [categories]);

    // Filter categories based on search
    const filteredCategories = useMemo(() => {
        if (!categories || !searchQuery) return categories || [];

        const filterRecursive = (cats: CategoryDto[]): CategoryDto[] => {
            return cats.filter(cat => {
                const matchesSearch = cat.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                    cat.metadata?.some(m => m.name.toLowerCase().includes(searchQuery.toLowerCase()));
                const hasMatchingChildren = cat.children ? filterRecursive(cat.children).length > 0 : false;
                return matchesSearch || hasMatchingChildren;
            });
        };

        return filterRecursive(categories);
    }, [categories, searchQuery]);

    // Handle category selection
    const handleCategoryClick = (category: CategoryDto, parents: CategoryDto[] = []) => {
        setSelectedCategory(category);
        setSelectedMeta(null);

        // Update breadcrumbs
        const newBreadcrumbs = parents.map(p => ({ id: p.oid, name: p.name }));
        newBreadcrumbs.push({ id: category.oid, name: category.name });
        setBreadcrumbs(newBreadcrumbs);
    };

    // Toggle category expansion
    const toggleCategoryExpansion = (categoryId: string, event: React.MouseEvent) => {
        event.stopPropagation();
        setExpandedCategories(prev => {
            const next = new Set(prev);
            if (next.has(categoryId)) {
                next.delete(categoryId);
            } else {
                next.add(categoryId);
            }
            return next;
        });
    };

    // Render category tree
    const renderCategoryTree = (cats: CategoryDto[], level = 0, parents: CategoryDto[] = []): React.ReactNode => {
        return cats.map(category => {
            const isExpanded = expandedCategories.has(category.oid);
            const isSelected = selectedCategory?.oid === category.oid;
            const hasChildren = category.children && category.children.length > 0;
            const metadataCount = category.metadata?.length || 0;

            return (
                <Box key={category.oid}>
                    <ListItemButton
                        sx={{
                            pl: level * 2 + 1,
                            borderRadius: 1,
                            mb: 0.5,
                            backgroundColor: isSelected ? alpha(theme.palette.primary.main, 0.12) : 'transparent',
                            '&:hover': {
                                backgroundColor: alpha(theme.palette.primary.main, 0.08)
                            }
                        }}
                        onClick={() => handleCategoryClick(category, parents)}
                    >
                        {hasChildren && (
                            <IconButton
                                size="small"
                                onClick={(e) => toggleCategoryExpansion(category.oid, e)}
                                sx={{ mr: 0.5 }}
                            >
                                {isExpanded ? <KeyboardArrowDown /> : <ChevronRight />}
                            </IconButton>
                        )}

                        <ListItemIcon sx={{ minWidth: 36 }}>
                            {isExpanded ? <FolderOpen color={theme.palette.primary.main} /> : <Folder />}
                        </ListItemIcon>

                        <ListItemText
                            primary={category.name}
                            secondary={`${metadataCount} items`}
                            primaryTypographyProps={{
                                fontWeight: isSelected ? 600 : 400,
                                fontSize: '0.875rem'
                            }}
                        />

                        {metadataCount > 0 && (
                            <Chip
                                label={metadataCount}
                                size="small"
                                sx={{
                                    height: 20,
                                    fontSize: '0.7rem',
                                    backgroundColor: alpha(theme.palette.primary.main, 0.1)
                                }}
                            />
                        )}
                    </ListItemButton>

                    {hasChildren && (
                        <MuiCollapse in={isExpanded}>
                            {renderCategoryTree(category.children, level + 1, [...parents, category])}
                        </MuiCollapse>
                    )}
                </Box>
            );
        });
    };

    // Loading state
    if (isLoading) {
        return (
            <Box sx={{ p: 3 }}>
                <Stack spacing={2}>
                    <Skeleton variant="rectangular" height={60} />
                    <Skeleton variant="rectangular" height={400} />
                </Stack>
            </Box>
        );
    }

    // Error state
    if (error) {
        return (
            <Alert
                severity="error"
                icon={<ErrorIcon />}
                action={
                    onRefresh ? (
                        <Button color="inherit" size="small" onClick={() => onRefresh()}>
                            Retry
                        </Button>
                    ) : undefined
                }
            >
                Error loading metadata: {error.message}
            </Alert>
        );
    }

    // Empty state
    if (!categories || categories.length === 0) {
        return (
            <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: 400,
                gap: 2
            }}>
                <Database size={64} color={theme.palette.text.secondary} />
                <Typography variant="h6" color="text.secondary">
                    No metadata available
                </Typography>
                <Typography variant="body2" color="text.secondary">
                    Select an image to view its metadata
                </Typography>
            </Box>
        );
    }

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Header with stats and controls */}
            <Paper elevation={0} sx={{ p: 2, mb: 2, borderRadius: 2, backgroundColor: alpha(theme.palette.primary.main, 0.03) }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Box sx={{
                            width: 48,
                            height: 48,
                            borderRadius: 2,
                            backgroundColor: alpha(theme.palette.primary.main, 0.1),
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                        }}>
                            <Database color={theme.palette.primary.main} />
                        </Box>
                        <Box>
                            <Typography variant="h6" sx={{ fontWeight: 600 }}>
                                Metadata Explorer
                            </Typography>
                            <Stack direction="row" spacing={1}>
                                <Chip
                                    icon={<Category />}
                                    label={`${stats.totalCategories} Categories`}
                                    size="small"
                                    variant="outlined"
                                />
                                <Chip
                                    icon={<Description />}
                                    label={`${stats.totalMetadata} Records`}
                                    size="small"
                                    variant="outlined"
                                />
                            </Stack>
                        </Box>
                    </Box>

                    {/* View mode toggle */}
                    <ButtonGroup size="small" variant="outlined">
                        <Tooltip title="Tree View">
                            <Button
                                onClick={() => setViewMode('tree')}
                                variant={viewMode === 'tree' ? 'contained' : 'outlined'}
                            >
                                <TreePine size={16} />
                            </Button>
                        </Tooltip>
                        <Tooltip title="JSON View">
                            <Button
                                onClick={() => setViewMode('json')}
                                variant={viewMode === 'json' ? 'contained' : 'outlined'}
                            >
                                <Code />
                            </Button>
                        </Tooltip>
                        <Tooltip title="Raw View">
                            <Button
                                onClick={() => setViewMode('raw')}
                                variant={viewMode === 'raw' ? 'contained' : 'outlined'}
                            >
                                <Terminal />
                            </Button>
                        </Tooltip>
                    </ButtonGroup>
                </Box>
            </Paper>

            {/* Main content area */}
            <Box sx={{ flex: 1, display: 'flex', gap: 2, overflow: 'hidden' }}>
                {/* Left panel - Category tree */}
                <Paper
                    elevation={1}
                    sx={{
                        width: isMobile ? '100%' : 350,
                        display: 'flex',
                        flexDirection: 'column',
                        borderRadius: 2,
                        overflow: 'hidden'
                    }}
                >
                    {/* Search bar */}
                    <Box sx={{ p: 2, borderBottom: `1px solid ${theme.palette.divider}` }}>
                        <TextField
                            fullWidth
                            size="small"
                            placeholder="Search metadata..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            InputProps={{
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <Search fontSize="small" />
                                    </InputAdornment>
                                ),
                                endAdornment: searchQuery && (
                                    <InputAdornment position="end">
                                        <IconButton size="small" onClick={() => setSearchQuery('')}>
                                            <Clear fontSize="small" />
                                        </IconButton>
                                    </InputAdornment>
                                )
                            }}
                        />
                    </Box>

                    {/* Category list */}
                    <Box sx={{ flex: 1, overflow: 'auto', p: 1 }}>
                        <List dense>
                            {renderCategoryTree(filteredCategories)}
                        </List>
                    </Box>
                </Paper>

                {/* Right panel - Metadata details */}
                {!isMobile && (
                    <Paper
                        elevation={1}
                        sx={{
                            flex: 1,
                            display: 'flex',
                            flexDirection: 'column',
                            borderRadius: 2,
                            overflow: 'hidden'
                        }}
                    >
                        {selectedCategory ? (
                            <>
                                {/* Breadcrumbs */}
                                <Box sx={{ p: 2, borderBottom: `1px solid ${theme.palette.divider}` }}>
                                    <Breadcrumbs separator={<ChevronRight size={16} />}>
                                        <Link
                                            component="button"
                                            variant="body2"
                                            onClick={() => {
                                                setSelectedCategory(null);
                                                setBreadcrumbs([]);
                                            }}
                                            underline="hover"
                                        >
                                            Root
                                        </Link>
                                        {breadcrumbs.map((crumb, index) => (
                                            <Typography
                                                key={crumb.id}
                                                variant="body2"
                                                color={index === breadcrumbs.length - 1 ? 'primary' : 'text.primary'}
                                                sx={{ fontWeight: index === breadcrumbs.length - 1 ? 600 : 400 }}
                                            >
                                                {crumb.name}
                                            </Typography>
                                        ))}
                                    </Breadcrumbs>
                                </Box>

                                {/* Metadata list */}
                                {selectedCategory.metadata && selectedCategory.metadata.length > 0 ? (
                                    <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
                                        <Stack spacing={1}>
                                            {selectedCategory.metadata.map((meta) => (
                                                <Card
                                                    key={meta.oid}
                                                    variant="outlined"
                                                    sx={{
                                                        cursor: 'pointer',
                                                        transition: 'all 0.2s',
                                                        '&:hover': {
                                                            backgroundColor: alpha(theme.palette.primary.main, 0.05),
                                                            transform: 'translateY(-2px)',
                                                            boxShadow: 2
                                                        },
                                                        ...(selectedMeta?.oid === meta.oid && {
                                                            backgroundColor: alpha(theme.palette.primary.main, 0.08),
                                                            borderColor: theme.palette.primary.main
                                                        })
                                                    }}
                                                    onClick={() => setSelectedMeta(meta)}
                                                >
                                                    <CardContent sx={{ py: 1.5 }}>
                                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                            <FileJson size={20} color={theme.palette.primary.main} />
                                                            <Typography variant="subtitle2" sx={{ fontWeight: 500, flex: 1 }}>
                                                                {meta.name}
                                                            </Typography>
                                                            {meta.data_json && (
                                                                <Chip
                                                                    label="JSON"
                                                                    size="small"
                                                                    color="primary"
                                                                    sx={{ height: 20, fontSize: '0.65rem' }}
                                                                />
                                                            )}
                                                        </Box>
                                                    </CardContent>
                                                </Card>
                                            ))}
                                        </Stack>
                                    </Box>
                                ) : (
                                    <Box sx={{
                                        flex: 1,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        p: 3
                                    }}>
                                        <Typography variant="body2" color="text.secondary">
                                            No metadata in this category
                                        </Typography>
                                    </Box>
                                )}
                            </>
                        ) : (
                            <Box sx={{
                                flex: 1,
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                justifyContent: 'center',
                                gap: 2,
                                p: 3
                            }}>
                                <Folder size={48} color={theme.palette.text.secondary} />
                                <Typography variant="body1" color="text.secondary">
                                    Select a category to view metadata
                                </Typography>
                            </Box>
                        )}
                    </Paper>
                )}
            </Box>

            {/* Bottom panel - Selected metadata details */}
            {selectedMeta && (
                <Zoom in={true}>
                    <Paper
                        elevation={3}
                        sx={{
                            position: 'absolute',
                            bottom: 0,
                            left: 0,
                            right: 0,
                            maxHeight: '50%',
                            display: 'flex',
                            flexDirection: 'column',
                            borderTopLeftRadius: 16,
                            borderTopRightRadius: 16,
                            overflow: 'hidden'
                        }}
                    >
                        {/* Header */}
                        <Box sx={{
                            p: 2,
                            backgroundColor: alpha(theme.palette.primary.main, 0.05),
                            borderBottom: `1px solid ${theme.palette.divider}`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between'
                        }}>
                            <Typography variant="h6" sx={{ fontWeight: 600 }}>
                                {selectedMeta.name}
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 1 }}>
                                <Tooltip title="Copy to clipboard">
                                    <IconButton
                                        size="small"
                                        onClick={() => {
                                            const content = selectedMeta.data_json
                                                ? JSON.stringify(selectedMeta.data_json, null, 2)
                                                : selectedMeta.data;
                                            navigator.clipboard.writeText(content);
                                        }}
                                    >
                                        <ContentCopy fontSize="small" />
                                    </IconButton>
                                </Tooltip>
                                <Tooltip title="Download">
                                    <IconButton size="small">
                                        <Download fontSize="small" />
                                    </IconButton>
                                </Tooltip>
                                <Tooltip title="Close">
                                    <IconButton
                                        size="small"
                                        onClick={() => setSelectedMeta(null)}
                                    >
                                        <Clear fontSize="small" />
                                    </IconButton>
                                </Tooltip>
                            </Box>
                        </Box>

                        {/* Content */}
                        <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
                            {viewMode === 'tree' && selectedMeta.data_json ? (
                                <JsonTreeViewer data={selectedMeta.data_json} />
                            ) : viewMode === 'json' && selectedMeta.data_json ? (
                                <Paper
                                    variant="outlined"
                                    sx={{
                                        p: 2,
                                        backgroundColor: alpha(theme.palette.background.default, 0.5),
                                        fontFamily: 'monospace',
                                        fontSize: '0.875rem',
                                        overflow: 'auto'
                                    }}
                                >
                                    <pre>{JSON.stringify(selectedMeta.data_json, null, 2)}</pre>
                                </Paper>
                            ) : (
                                <TextField
                                    fullWidth
                                    multiline
                                    rows={10}
                                    value={selectedMeta.data_json ? JSON.stringify(selectedMeta.data_json, null, 2) : selectedMeta.data}
                                    InputProps={{
                                        readOnly: true,
                                        sx: { fontFamily: 'monospace', fontSize: '0.875rem' }
                                    }}
                                />
                            )}
                        </Box>
                    </Paper>
                </Zoom>
            )}
        </Box>
    );
};

export default MetadataExplorer;
