import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    Box,
    Typography,
    CircularProgress,
    TextField,
    InputAdornment,
    Paper,
    Chip,
    Stack
} from '@mui/material';
import { Folder, Image as ImageIcon, Search } from '@mui/icons-material';
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import type ImageInfoDto from '../../../entities/image/types.ts';
import { useAllSessionImages } from '../api/usePagedImagesHook';
import { imagePath, openImagePath } from '../lib/imagePath';
import { makeImageMatcher } from '../lib/imageFilter';
import { useImageViewerStore } from '../model/imageViewerStore';

interface TreeViewerProps {
    sessionName: string;
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
    title?: string;
}

interface TreeNode {
    image: ImageInfoDto;
    label: string;
    children: TreeNode[];
}

/** The tree the images' parent links make. The list's order is kept, so related images come first. */
const buildTree = (images: ImageInfoDto[]): TreeNode[] => {
    const nodes = new Map(images.map((image) => [image.oid, { image, label: image.name ?? 'Unnamed Image', children: [] as TreeNode[] }]));
    const roots: TreeNode[] = [];
    nodes.forEach((node) => {
        const parent = node.image.parent_id ? nodes.get(node.image.parent_id) : undefined;
        if (parent) {
            // Child names repeat the parent's: show the part that differs.
            const prefix = `${parent.image.name}_`;
            if (node.label.startsWith(prefix)) node.label = node.label.slice(prefix.length);
            parent.children.push(node);
        } else {
            roots.push(node);
        }
    });
    return roots;
};

/** The images that pass, and the ones above them. */
const pruneTree = (nodes: TreeNode[], keep: (image: ImageInfoDto) => boolean): TreeNode[] =>
    nodes.flatMap((node) => {
        const children = pruneTree(node.children, keep);
        return keep(node.image) || children.length > 0 ? [{ ...node, children }] : [];
    });

const allIds = (nodes: TreeNode[]): string[] =>
    nodes.flatMap((node) => (node.children.length > 0 ? [node.image.oid, ...allIds(node.children)] : []));

/**
 * The session's images by their real parent and child links.
 */
export const HierarchyBrowser: React.FC<TreeViewerProps> = ({ sessionName, onImageClick, title = 'Image Tree' }) => {
    const [expandedItems, setExpandedItems] = useState<string[]>([]);
    const [searchText, setSearchText] = useState('');
    const { currentImage, imageColumns, imageFilter } = useImageViewerStore();
    const { images, isLoading, isLoadingMore } = useAllSessionImages(sessionName);

    const tree = useMemo(() => buildTree(images), [images]);
    const search = searchText.trim().toLowerCase();
    const matcher = useMemo(() => makeImageMatcher(imageFilter), [imageFilter]);
    const shownTree = useMemo(() => (search || matcher
        ? pruneTree(tree, (image) => (!matcher || matcher(image)) && (!search || !!image.name?.toLowerCase().includes(search)))
        : tree), [tree, search, matcher]);
    const relatedRoots = useMemo(() => tree.filter((node) => node.children.length > 0).length, [tree]);

    // Open the top level once, and whatever a search finds.
    const expandedOnce = useRef(false);
    useEffect(() => {
        if (!expandedOnce.current && tree.length > 0) {
            expandedOnce.current = true;
            setExpandedItems(tree.filter((node) => node.children.length > 0).map((node) => node.image.oid));
        }
    }, [tree]);
    useEffect(() => {
        if (search || matcher) setExpandedItems(allIds(shownTree));
    }, [search, matcher, shownTree]);

    // The way down to an image opened elsewhere.
    useEffect(() => {
        if (currentImage) {
            const parents = imagePath(currentImage, images).slice(0, -1).map((image) => image.oid);
            if (parents.length > 0) setExpandedItems((prev) => Array.from(new Set([...prev, ...parents])));
        }
    }, [currentImage?.oid, images]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleSelected = (_event: React.SyntheticEvent | null, itemId: string | null) => {
        const image = images.find((item) => item.oid === itemId);
        if (image && image.oid !== currentImage?.oid) {
            openImagePath(image, images, imageColumns.length, onImageClick);
        }
    };

    const renderTreeItems = (nodes: TreeNode[]): React.ReactNode =>
        nodes.map((node) => (
            <TreeItem
                key={node.image.oid}
                itemId={node.image.oid}
                label={
                    <Box sx={{ display: 'flex', alignItems: 'center', py: 0.5, gap: 1 }}>
                        {node.children.length > 0
                            ? <Folder sx={{ fontSize: 16, color: 'warning.main' }} />
                            : <ImageIcon sx={{ fontSize: 16, color: 'primary.main' }} />}
                        <Typography variant="body2" noWrap sx={{ flexGrow: 1 }} title={node.image.name}>
                            {node.label}
                        </Typography>
                        {node.image.resolution != null && (
                            <Typography variant="caption" sx={{ color: 'text.secondary', flexShrink: 0 }}>
                                {node.image.resolution.toFixed(1)} Å
                            </Typography>
                        )}
                        {node.children.length > 0 && (
                            <Chip label={node.children.length} size="small" variant="outlined" sx={{ height: 20, fontSize: '0.6rem' }} />
                        )}
                    </Box>
                }
            >
                {renderTreeItems(node.children)}
            </TreeItem>
        ));

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
                <CircularProgress />
            </Box>
        );
    }

    if (images.length === 0) {
        return (
            <Paper elevation={1} sx={{ p: 3, textAlign: 'center' }}>
                <Typography variant="h6" gutterBottom>{title}</Typography>
                <Typography sx={{ color: "text.secondary" }}>No images available</Typography>
            </Paper>
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
                    slotProps={{
                        input: {
                            startAdornment: (
                                <InputAdornment position="start">
                                    <Search fontSize="small" />
                                </InputAdornment>
                            )
                        }
                    }}
                />
                <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                    <Chip label={`${relatedRoots} with children`} size="small" variant="outlined" color="primary" />
                    <Chip label={`${images.length} images${isLoadingMore ? '...' : ''}`} size="small" variant="outlined" color="secondary" />
                </Stack>
            </Box>
            <Paper elevation={1} sx={{ flex: 1, minHeight: 0, mx: 2, mb: 2, overflow: 'auto', borderRadius: 2 }}>
                <SimpleTreeView
                    expandedItems={expandedItems}
                    onExpandedItemsChange={(_event, itemIds) => setExpandedItems(itemIds)}
                    selectedItems={currentImage?.oid ?? null}
                    onSelectedItemsChange={handleSelected}
                    multiSelect={false}
                    sx={{ p: 1, pb: 7 }}
                >
                    {renderTreeItems(shownTree)}
                </SimpleTreeView>
            </Paper>
        </Box>
    );
};

export default HierarchyBrowser;
