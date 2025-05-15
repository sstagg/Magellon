import React, { useState, useEffect } from 'react';
import { Box, Typography, CircularProgress, TextField, InputAdornment } from '@mui/material';
import ImageInfoDto, { PagedImageResponse } from './ImageInfoDto';
import { InfiniteData } from 'react-query';
import { useImageViewerStore } from './store/imageViewerStore';
import { Tree, NodeRendererProps } from 'react-arborist';
import { ChevronDown, ChevronRight, Folder, FileImage, Search, Loader } from 'lucide-react';

interface TreeViewerProps {
    images: InfiniteData<PagedImageResponse> | null;
    onImageClick: (imageInfo: ImageInfoDto, column: number) => void;
    title?: string;
}

// Recursive type for tree nodes
interface TreeNode {
    id: string;
    name: string;
    level: number;
    children: TreeNode[];
    isImage: boolean;
    imageData?: ImageInfoDto;
    isLoading?: boolean;
}

/**
 * TreeViewer displays images in a hierarchical tree structure.
 */
export const TreeViewer: React.FC<TreeViewerProps> = ({
                                                          images,
                                                          onImageClick,
                                                          title = 'Image Tree'
                                                      }) => {
    const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
    const [selectedNode, setSelectedNode] = useState<string | null>(null);
    const [searchText, setSearchText] = useState('');
    const [treeData, setTreeData] = useState<TreeNode[]>([]);

    const { currentImage, currentSession } = useImageViewerStore();
    const sessionName = currentSession?.name || '';

    // Extract all images from the paginated data
    const allImages = images?.pages?.flatMap(page => page.result) || [];

    // Build tree hierarchy from flat data
    useEffect(() => {
        if (!allImages || allImages.length === 0) {
            setTreeData([]);
            return;
        }

        // Group images by the first part of their name (before the first underscore)
        const groupedImages: Record<string, ImageInfoDto[]> = {};

        allImages.forEach(image => {
            if (!image.name) return;

            // Extract group name (e.g., "24jun28a" from "24jun28a_Valle001-01_00009gr")
            const parts = image.name.split('_');
            const groupName = parts[0];

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
                if (parts.length < 2) return;

                const subGroupName = parts[1];

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
                    name: image.name?.split('_')[2] || '',  // Get the third part of the name (e.g., "00009gr")
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
                    isImage: false
                };
            });

            return {
                id: groupName,
                name: groupName,
                level: 0,
                children,
                isImage: false
            };
        });

        setTreeData(treeNodes);
    }, [allImages]);

    // Filter tree data based on search text
    const filteredTreeData = React.useMemo(() => {
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

                    // Skip this node
                    return null;
                })
                .filter(node => node !== null) as TreeNode[];
        };

        return filterNodes(treeData);
    }, [treeData, searchText]);

    // Node renderer for customizing tree appearance
    const NodeRenderer = ({ node, style, dragHandle }: NodeRendererProps<TreeNode>) => {
        const isExpanded = expandedNodes.has(node.id);
        const isSelected = selectedNode === node.id;

        const handleToggle = () => {
            setExpandedNodes(prev => {
                const newSet = new Set(prev);
                if (newSet.has(node.id)) {
                    newSet.delete(node.id);
                } else {
                    newSet.add(node.id);
                }
                return newSet;
            });
        };

        const handleSelect = () => {
            setSelectedNode(node.id);

            if (node.isImage && node.imageData) {
                onImageClick(node.imageData, 0);
            }
        };

        return (
            <Box
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '4px 8px',
                    cursor: 'pointer',
                    borderRadius: '4px',
                    backgroundColor: isSelected ? 'rgba(25, 118, 210, 0.12)' : 'transparent',
                    '&:hover': {
                        backgroundColor: isSelected ? 'rgba(25, 118, 210, 0.18)' : 'rgba(0, 0, 0, 0.04)'
                    },
                    paddingLeft: `${8 + node.level * 20}px`
                }}
                style={style}
                ref={dragHandle}
                onClick={handleSelect}
            >
                {!node.isImage && (
                    <Box sx={{ display: 'flex', mr: 1 }} onClick={handleToggle}>
                        {isExpanded ? (
                            <ChevronDown size={16} />
                        ) : (
                            <ChevronRight size={16} />
                        )}
                    </Box>
                )}

                <Box sx={{ display: 'flex', mr: 1 }}>
                    {node.isLoading ? (
                        <Loader size={16} />
                    ) : node.isImage ? (
                        <FileImage size={16} />
                    ) : (
                        <Folder size={16} />
                    )}
                </Box>

                <Typography variant="body2" noWrap>
                    {node.name}
                </Typography>
            </Box>
        );
    };

    // Handle node opening
    const handleOpenNode = (node: TreeNode) => {
        setExpandedNodes(prev => {
            const newSet = new Set(prev);
            newSet.add(node.id);
            return newSet;
        });
    };

    if (!images) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
                <CircularProgress />
            </Box>
        );
    }

    if (allImages.length === 0) {
        return (
            <Box sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>{title}</Typography>
                <Typography color="text.secondary">No images available</Typography>
            </Box>
        );
    }

    return (
        <Box sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>{title}</Typography>

            <Box sx={{ mb: 2 }}>
                <TextField
                    fullWidth
                    size="small"
                    placeholder="Search images..."
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                    InputProps={{
                        startAdornment: (
                            <InputAdornment position="start">
                                <Search size={18} />
                            </InputAdornment>
                        )
                    }}
                />
            </Box>

            <Box sx={{ height: 600, overflow: 'auto', border: '1px solid rgba(0, 0, 0, 0.12)', borderRadius: 1 }}>
                <Tree
                    data={filteredTreeData}
                    openByDefault={false}
                    width="100%"
                    height={600}
                    indent={20}
                    rowHeight={32}
                    overscanCount={5}
                    paddingTop={8}
                    paddingBottom={8}
                    onToggle={handleOpenNode}
                >
                    {NodeRenderer}
                </Tree>
            </Box>
        </Box>
    );
};

export default TreeViewer;