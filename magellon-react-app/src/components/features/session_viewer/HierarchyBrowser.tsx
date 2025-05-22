import React, { useState, useEffect, useMemo } from 'react';
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
import {
    ExpandMore,
    ChevronRight,
    Folder,
    Image as ImageIcon,
    Search
} from '@mui/icons-material';
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import ImageInfoDto, { PagedImageResponse } from './ImageInfoDto';
import { InfiniteData } from 'react-query';
import { useImageViewerStore } from './store/imageViewerStore';

interface TreeViewerProps {
    images: InfiniteData<PagedImageResponse> | null;
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
    title?: string;
}

// Simplified tree node structure
interface TreeNode {
    id: string;
    name: string;
    level: number;
    children: TreeNode[];
    isImage: boolean;
    imageData?: ImageInfoDto;
    childrenCount?: number;
}

/**
 * TreeViewer displays images in a hierarchical tree structure using Material UI TreeView.
 */
export const HierarchyBrowser: React.FC<TreeViewerProps> = ({
                                                          images,
                                                          onImageClick,
                                                          title = 'Image Tree'
                                                      }) => {
    const [expandedItems, setExpandedItems] = useState<string[]>([]);
    const [selectedItems, setSelectedItems] = useState<string[]>([]);
    const [searchText, setSearchText] = useState('');

    const { currentImage, currentSession } = useImageViewerStore();
    const sessionName = currentSession?.name || '';

    // Extract all images from the paginated data
    const allImages = images?.pages?.flatMap(page => page.result) || [];

    // Build tree hierarchy from flat data
    const treeData = useMemo(() => {
        if (!allImages || allImages.length === 0) {
            return [];
        }

        // Group images by the first part of their name (before the first underscore)
        const groupedImages: Record<string, ImageInfoDto[]> = {};

        allImages.forEach(image => {
            if (!image.name) return;

            // Extract group name (e.g., "24jun28a" from "24jun28a_Valle001-01_00009gr")
            const parts = image.name.split('_');
            const groupName = parts[0] || 'Unknown';

            if (!groupedImages[groupName]) {
                groupedImages[groupName] = [];
            }

            groupedImages[groupName].push(image);
        });

        // Convert grouped images to tree structure
        const treeNodes: TreeNode[] = Object.entries(groupedImages).map(([groupName, groupImages]) => {
            // Further group by the second part (e.g., "Valle001-01")
            const subGroups: Record<string, ImageInfoDto[]> = {};

            groupImages.forEach(image => {
                if (!image.name) return;

                const parts = image.name.split('_');
                const subGroupName = parts.length >= 2 ? parts[1] : 'Unknown';

                if (!subGroups[subGroupName]) {
                    subGroups[subGroupName] = [];
                }

                subGroups[subGroupName].push(image);
            });

            // Create children for each subgroup
            const children: TreeNode[] = Object.entries(subGroups).map(([subGroupName, subGroupImages]) => {
                // Create leaf nodes for each image
                const imageNodes: TreeNode[] = subGroupImages.map(image => ({
                    id: image.oid || `image-${image.name}`,
                    name: image.name?.split('_')[2] || image.name || 'Unknown Image',
                    level: 2,
                    children: [],
                    isImage: true,
                    imageData: image
                }));

                return {
                    id: `${groupName}_${subGroupName}`,
                    name: subGroupName,
                    level: 1,
                    children: imageNodes,
                    isImage: false,
                    childrenCount: imageNodes.length
                };
            });

            return {
                id: groupName,
                name: groupName,
                level: 0,
                children,
                isImage: false,
                childrenCount: groupImages.length
            };
        });

        return treeNodes;
    }, [allImages]);

    // Filter tree data based on search text
    const filteredTreeData = useMemo(() => {
        if (!searchText.trim()) {
            return treeData;
        }

        const searchLower = searchText.toLowerCase();

        // Helper function to filter nodes recursively
        const filterNodes = (nodes: TreeNode[]): TreeNode[] => {
            return nodes
                .map(node => {
                    // Check if this node matches
                    const nodeMatches = node.name.toLowerCase().includes(searchLower);

                    // Filter children
                    const filteredChildren = filterNodes(node.children);

                    // Keep this node if it matches or has matching children
                    if (nodeMatches || filteredChildren.length > 0) {
                        return {
                            ...node,
                            children: filteredChildren
                        };
                    }

                    return null;
                })
                .filter(node => node !== null) as TreeNode[];
        };

        return filterNodes(treeData);
    }, [treeData, searchText]);

    // Handle item expansion
    const handleExpandedItemsChange = (event: React.SyntheticEvent, itemIds: string[]) => {
        setExpandedItems(itemIds);
    };

    // Handle item selection - This is the key change to match ThumbImage behavior
    const handleSelectedItemsChange = (event: React.SyntheticEvent, itemIds: string[]) => {
        setSelectedItems(itemIds);

        // Find the selected node and trigger image click if it's an image
        const findNode = (nodes: TreeNode[], id: string): TreeNode | null => {
            for (const node of nodes) {
                if (node.id === id) return node;
                const found = findNode(node.children, id);
                if (found) return found;
            }
            return null;
        };

        if (itemIds.length > 0) {
            const selectedNode = findNode(filteredTreeData, itemIds[0]);
            if (selectedNode && selectedNode.isImage && selectedNode.imageData) {
                // Only trigger image click if this is a different image than currently selected
                // This matches the logic in ThumbImage component
                if (!currentImage || currentImage.oid !== selectedNode.imageData.oid) {
                    // Create a copy of the image with level set, exactly like ThumbImage does
                    const imageWithLevel = { ...selectedNode.imageData, level: selectedNode.level };

                    // Call onImageClick with the same parameters as ThumbImage
                    // ThumbImage calls: onImageClick(imageWithLevel, level);
                    // We'll use level 0 for tree view since it's not hierarchical columns
                    onImageClick(imageWithLevel, 0);
                }
            }
        }
    };

    // Handle direct image click (when user clicks on tree item content)
    const handleImageClick = (node: TreeNode) => {
        if (node.isImage && node.imageData) {
            // Create a copy of the image with level set, exactly like ThumbImage does
            const imageWithLevel = { ...node.imageData, level: node.level };

            // Update local selection state
            setSelectedItems([node.id]);

            // Call the parent callback with level 0 (tree view doesn't use column hierarchy)
            onImageClick(imageWithLevel, 0);
        }
    };

    // Recursively render tree items
    const renderTreeItems = (nodes: TreeNode[]): React.ReactNode => {
        return nodes.map((node) => (
            <TreeItem
                key={node.id}
                itemId={node.id}
                label={
                    <Box
                        sx={{
                            display: 'flex',
                            alignItems: 'center',
                            py: 0.5,
                            gap: 1,
                            cursor: node.isImage ? 'pointer' : 'default'
                        }}
                        onClick={(e) => {
                            // Handle image click when clicking on the label content
                            if (node.isImage) {
                                e.preventDefault();
                                e.stopPropagation();
                                handleImageClick(node);
                            }
                        }}
                    >
                        {node.isImage ? (
                            <ImageIcon sx={{ fontSize: 16, color: 'primary.main' }} />
                        ) : (
                            <Folder sx={{ fontSize: 16, color: 'warning.main' }} />
                        )}
                        <Typography variant="body2" sx={{ flexGrow: 1 }}>
                            {node.name}
                        </Typography>
                        {!node.isImage && node.childrenCount && (
                            <Chip
                                label={node.childrenCount}
                                size="small"
                                variant="outlined"
                                sx={{ height: 20, fontSize: '0.6rem' }}
                            />
                        )}
                        {/* Add visual indicator for selected image */}
                        {node.isImage && currentImage && currentImage.oid === node.imageData?.oid && (
                            <Box
                                sx={{
                                    width: 8,
                                    height: 8,
                                    borderRadius: '50%',
                                    backgroundColor: 'primary.main',
                                    ml: 1
                                }}
                            />
                        )}
                    </Box>
                }
                sx={{
                    '& .MuiTreeItem-content': {
                        borderRadius: 1,
                        '&:hover': {
                            backgroundColor: 'action.hover',
                        },
                        '&.Mui-selected': {
                            backgroundColor: node.isImage && currentImage && currentImage.oid === node.imageData?.oid
                                ? 'primary.light'
                                : 'action.selected',
                            '&:hover': {
                                backgroundColor: node.isImage && currentImage && currentImage.oid === node.imageData?.oid
                                    ? 'primary.light'
                                    : 'action.selected',
                            }
                        }
                    },
                    '& .MuiTreeItem-label': {
                        fontSize: '0.875rem',
                    }
                }}
            >
                {node.children.length > 0 && renderTreeItems(node.children)}
            </TreeItem>
        ));
    };

    // Auto-expand first level when data loads
    useEffect(() => {
        if (filteredTreeData.length > 0 && expandedItems.length === 0) {
            // Auto-expand the first group to show subgroups
            const firstLevelIds = filteredTreeData.map(node => node.id);
            setExpandedItems(firstLevelIds);
        }
    }, [filteredTreeData, expandedItems.length]);

    // Update selection when current image changes (from store)
    useEffect(() => {
        if (currentImage) {
            const imageId = currentImage.oid || `image-${currentImage.name}`;

            // Only update if the current selection is different
            if (!selectedItems.includes(imageId)) {
                setSelectedItems([imageId]);

                // Auto-expand parent nodes to make the selected image visible
                const findParentPath = (nodes: TreeNode[], targetId: string, path: string[] = []): string[] | null => {
                    for (const node of nodes) {
                        const currentPath = [...path, node.id];

                        if (node.id === targetId) {
                            return currentPath.slice(0, -1); // Return parent path, not including the target
                        }

                        if (node.children.length > 0) {
                            const found = findParentPath(node.children, targetId, currentPath);
                            if (found) return found;
                        }
                    }
                    return null;
                };

                const parentPath = findParentPath(filteredTreeData, imageId);
                if (parentPath && parentPath.length > 0) {
                    setExpandedItems(prev => {
                        const newExpanded = new Set([...prev, ...parentPath]);
                        return Array.from(newExpanded);
                    });
                }
            }
        } else {
            // Clear selection if no image is selected
            setSelectedItems([]);
        }
    }, [currentImage, filteredTreeData]); // Removed selectedItems from dependencies to prevent infinite loops

    if (!images) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
                <CircularProgress />
            </Box>
        );
    }

    if (allImages.length === 0) {
        return (
            <Paper elevation={1} sx={{ p: 3, textAlign: 'center' }}>
                <Typography variant="h6" gutterBottom>{title}</Typography>
                <Typography color="text.secondary">No images available</Typography>
            </Paper>
        );
    }

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Typography variant="h6" gutterBottom sx={{ px: 2, pt: 2 }}>
                {title}
            </Typography>

            {/* Search field */}
            <Box sx={{ px: 2, pb: 2 }}>
                <TextField
                    fullWidth
                    size="small"
                    placeholder="Search images..."
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                    InputProps={{
                        startAdornment: (
                            <InputAdornment position="start">
                                <Search fontSize="small" />
                            </InputAdornment>
                        )
                    }}
                />
            </Box>

            {/* Statistics */}
            <Box sx={{ px: 2, pb: 2 }}>
                <Stack direction="row" spacing={1}>
                    <Chip
                        label={`${treeData.length} Groups`}
                        size="small"
                        variant="outlined"
                        color="primary"
                    />
                    <Chip
                        label={`${allImages.length} Images`}
                        size="small"
                        variant="outlined"
                        color="secondary"
                    />
                    {searchText && (
                        <Chip
                            label={`${filteredTreeData.length} Filtered`}
                            size="small"
                            variant="filled"
                            color="info"
                        />
                    )}
                </Stack>
            </Box>

            {/* Tree view */}
            <Paper
                elevation={1}
                sx={{
                    flex: 1,
                    mx: 2,
                    mb: 2,
                    overflow: 'auto',
                    borderRadius: 2
                }}
            >
                <SimpleTreeView
                    expandedItems={expandedItems}
                    onExpandedItemsChange={handleExpandedItemsChange}
                    selectedItems={selectedItems}
                    onSelectedItemsChange={handleSelectedItemsChange}
                    multiSelect={false}
                    sx={{
                        p: 1,
                        minHeight: 400,
                        '& .MuiTreeItem-root': {
                            '& .MuiTreeItem-content': {
                                borderRadius: 1,
                                marginBottom: 0.5,
                                padding: '4px 8px',
                            }
                        }
                    }}
                >
                    {renderTreeItems(filteredTreeData)}
                </SimpleTreeView>
            </Paper>
        </Box>
    );
};

export default HierarchyBrowser;