import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    Box,
    Button,
    Chip,
    CircularProgress,
    InputAdornment,
    Paper,
    Stack,
    TextField,
    Typography,
} from '@mui/material';
import { Folder, Image as ImageIcon, Search } from '@mui/icons-material';
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import type ImageInfoDto from '../../../entities/image/types.ts';
import { useDebouncedValue, useImageListQuery } from '../api/usePagedImagesHook';
import { fetchImagePath, type ImageQuery } from '../api/imagesApiReactQuery';
import { countActiveFilters, type FilterGroup } from '../lib/imageFilter';
import { openPath } from '../lib/imagePath';
import { useImageViewerStore } from '../model/imageViewerStore';

interface TreeViewerProps {
    sessionName: string;
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
    title?: string;
}

const PAGE_SIZE = 100;

interface TreeContext {
    sessionName: string;
    query: ImageQuery;
    expanded: Set<string>;
    filtering: boolean;
    /** Where each shown image sits, to open it with its parents. */
    paths: Map<string, ImageInfoDto[]>;
    onLoaded: (images: ImageInfoDto[]) => void;
}

/** One level of the tree, loaded from the server a page at a time. */
const TreeLevel: React.FC<{ parent: ImageInfoDto | null; path: ImageInfoDto[]; ctx: TreeContext }> = ({ parent, path, ctx }) => {
    const { data, isLoading, hasNextPage, isFetchingNextPage, fetchNextPage } = useImageListQuery({
        sessionName: ctx.sessionName,
        parentId: parent?.oid ?? null,
        pageSize: PAGE_SIZE,
        level: path.length,
        query: ctx.query,
    });
    const images = useMemo(() => data?.pages.flatMap((page) => page.result ?? []) ?? [], [data]);
    const { onLoaded } = ctx;
    useEffect(() => {
        if (images.length > 0) onLoaded(images);
    }, [images, onLoaded]);

    const key = parent?.oid ?? 'root';
    if (isLoading) return <TreeItem itemId={`${key}:loading`} label="Loading..." disabled />;
    return (
        <>
            {images.map((image) => (
                <TreeNode key={image.oid} image={image} parent={parent} path={path} ctx={ctx} />
            ))}
            {hasNextPage && (
                <TreeItem
                    itemId={`${key}:more`}
                    label={
                        <Button size="small" disabled={isFetchingNextPage} onClick={(e) => { e.stopPropagation(); fetchNextPage(); }}>
                            {isFetchingNextPage ? 'Loading...' : 'Load more'}
                        </Button>
                    }
                />
            )}
        </>
    );
};

const TreeNode: React.FC<{ image: ImageInfoDto; parent: ImageInfoDto | null; path: ImageInfoDto[]; ctx: TreeContext }> = ({ image, parent, path, ctx }) => {
    ctx.paths.set(image.oid, [...path, image]);
    const hasChildren = (image.children_count || 0) > 0;
    // Child names repeat the parent's: show the part that differs.
    const prefix = parent?.name ? `${parent.name}_` : '';
    const label = prefix && image.name?.startsWith(prefix) ? image.name.slice(prefix.length) : image.name ?? 'Unnamed Image';
    return (
        <TreeItem
            itemId={image.oid}
            label={
                <Box sx={{ display: 'flex', alignItems: 'center', py: 0.5, gap: 1 }}>
                    {hasChildren
                        ? <Folder sx={{ fontSize: 16, color: 'warning.main' }} />
                        : <ImageIcon sx={{ fontSize: 16, color: 'primary.main' }} />}
                    <Typography variant="body2" noWrap sx={{ flexGrow: 1 }} title={image.name}>{label}</Typography>
                    {image.resolution != null && (
                        <Typography variant="caption" sx={{ color: 'text.secondary', flexShrink: 0 }}>
                            {image.resolution.toFixed(1)} Å
                        </Typography>
                    )}
                    {hasChildren && !ctx.filtering && (
                        <Chip label={image.children_count} size="small" variant="outlined" sx={{ height: 20, fontSize: '0.6rem' }} />
                    )}
                </Box>
            }
        >
            {hasChildren && (ctx.expanded.has(image.oid)
                ? <TreeLevel parent={image} path={[...path, image]} ctx={ctx} />
                : <TreeItem itemId={`${image.oid}:placeholder`} label="..." disabled />)}
        </TreeItem>
    );
};

/**
 * The session's images by their parent links, a level at a time from the
 * server. With a filter or a search, only the matches and the images above them.
 */
export const HierarchyBrowser: React.FC<TreeViewerProps> = ({ sessionName, onImageClick, title = 'Image Tree' }) => {
    const [expandedItems, setExpandedItems] = useState<string[]>([]);
    const [searchText, setSearchText] = useState('');
    const search = useDebouncedValue(searchText.trim());
    const { currentImage, imageColumns, imageFilter } = useImageViewerStore();
    const paths = useRef(new Map<string, ImageInfoDto[]>()).current;

    // The search is one more condition, sent with the session's filter.
    const filter = useMemo<FilterGroup>(() => ({
        kind: 'group', id: 'tree', combinator: 'and', not: false,
        rules: [imageFilter, ...(search ? [{ kind: 'rule' as const, id: 'tree-search', field: 'name' as const, operator: 'contains' as const, value: search }] : [])],
    }), [imageFilter, search]);
    const filtering = countActiveFilters(filter) > 0;
    const query = useMemo<ImageQuery>(() => ({ filter, includeAncestors: true }), [filter]);

    // While filtering, open every branch that leads to a match.
    const onLoaded = useCallback((images: ImageInfoDto[]) => {
        if (!filtering) return;
        const branches = images.filter((image) => (image.children_count || 0) > 0).map((image) => image.oid);
        setExpandedItems((prev) => (branches.every((id) => prev.includes(id)) ? prev : Array.from(new Set([...prev, ...branches]))));
    }, [filtering]);

    // The way down to an image opened elsewhere.
    useEffect(() => {
        if (!currentImage?.parent_id) return;
        let cancelled = false;
        fetchImagePath(currentImage.oid).then((path) => {
            if (!cancelled) setExpandedItems((prev) => Array.from(new Set([...prev, ...path.slice(0, -1).map((image) => image.oid)])));
        }).catch(() => undefined);
        return () => { cancelled = true; };
    }, [currentImage?.oid, currentImage?.parent_id]);

    const ctx: TreeContext = { sessionName, query, expanded: new Set(expandedItems), filtering, paths, onLoaded };

    const handleSelected = (_event: React.SyntheticEvent | null, itemId: string | null) => {
        const path = itemId ? paths.get(itemId) : undefined;
        if (path && itemId !== currentImage?.oid) openPath(path, imageColumns.length, onImageClick);
    };

    const roots = useImageListQuery({ sessionName, parentId: null, pageSize: PAGE_SIZE, level: 0, query });
    const rootTotal = roots.data?.pages[0]?.total_count ?? 0;

    if (roots.isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box sx={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', pt: 1 }} data-testid="image-tree">
            <Box sx={{ px: 2, pb: 1, flexShrink: 0 }}>
                <TextField
                    fullWidth
                    size="small"
                    placeholder="Search images..."
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                    slotProps={{ input: { startAdornment: <InputAdornment position="start"><Search fontSize="small" /></InputAdornment> } }}
                />
                <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                    <Chip label={`${rootTotal} top-level images${filtering ? ' lead to a match' : ''}`} size="small" variant="outlined" color="primary" />
                </Stack>
            </Box>
            <Paper elevation={1} sx={{ flex: 1, minHeight: 0, mx: 2, mb: 2, overflow: 'auto', borderRadius: 2 }}>
                {rootTotal === 0 ? (
                    <Typography sx={{ p: 3, color: 'text.secondary', textAlign: 'center' }}>
                        {filtering ? 'No images match' : `No images available in ${title}`}
                    </Typography>
                ) : (
                    <SimpleTreeView
                        expandedItems={expandedItems}
                        onExpandedItemsChange={(_event, itemIds) => setExpandedItems(itemIds)}
                        selectedItems={currentImage?.oid ?? null}
                        onSelectedItemsChange={handleSelected}
                        multiSelect={false}
                        sx={{ p: 1, pb: 7 }}
                    >
                        <TreeLevel parent={null} path={[]} ctx={ctx} />
                    </SimpleTreeView>
                )}
            </Paper>
        </Box>
    );
};

export default HierarchyBrowser;
