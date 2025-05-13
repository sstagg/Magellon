import * as React from 'react';
import { styled, useTheme } from '@mui/material/styles';
import Drawer from '@mui/material/Drawer';
import List from '@mui/material/List';
import Divider from '@mui/material/Divider';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import { useLocation, useNavigate } from "react-router-dom";
import { blueGrey } from "@mui/material/colors";
import {
    BarChart2,
    Image as ImageIcon,
    Settings,
    FileUp,
    Layers,
    PanelLeft,
    Home,
    Beaker, BrainCircuit
} from "lucide-react";
import { Box, Collapse, Typography, useMediaQuery } from '@mui/material';
import { ExpandLess, ExpandMore, ImportExport } from '@mui/icons-material';

const DRAWER_WIDTH = 240;

// Styled components
const DrawerHeader = styled('div')(({ theme }) => ({
    display: 'flex',
    alignItems: 'center',
    padding: theme.spacing(0, 1),
    ...theme.mixins.toolbar,
    justifyContent: 'center',
    backgroundColor: blueGrey[700],
    color: 'white',
}));

// Navigation links structure with nested items capability
interface NavLink {
    title: string;
    url: string;
    icon: React.ReactNode;
    children?: NavLink[];
}

// Main navigation links
const navLinks: NavLink[] = [
    {
        title: "Dashboard",
        url: "dashboard",
        icon: <Home size={20} />
    },
    {
        title: "Images",
        url: "images",
        icon: <ImageIcon size={20} />
    },
    {
        title: "Import",
        url: "import-job",
        icon: <ImportExport size={20} />
    },
    {
        title: "Processing",
        url: "processing",
        icon: <Layers size={20} />,
        children: [
            {
                title: "Run Job",
                url: "run-job",
                icon: <Beaker size={20} />
            },
            {
                title: "2D Classification",
                url: "2d-assess",
                icon: <PanelLeft size={20} />
            },
            {
                title: "MRC Viewer",
                url: "mrc-viewer",
                icon: <BarChart2 size={20} />
            }
        ]
    },
    {
        title: "Test",
        url: "test",
        icon: <Beaker size={20} />
    },
    {
        title: "API",
        url: "api",
        icon: <BrainCircuit size={20} />
    },
    {
        title: "Settings",
        url: "settings",
        icon: <Settings size={20} />
    },
];

// Types
interface PanelDrawerProps {
    open: boolean;
    handleDrawerClose: () => void;
}

export const PanelDrawer: React.FC<PanelDrawerProps> = ({ open, handleDrawerClose }) => {
    const theme = useTheme();
    const navigate = useNavigate();
    const location = useLocation();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // State to track expanded menu items
    const [expandedItems, setExpandedItems] = React.useState<Record<string, boolean>>({});

    // Handle navigation
    const handleNavigation = (url: string) => {
        if (isMobile) {
            handleDrawerClose();
        }
        navigate(url);
    };

    // Toggle expanded state for menu items with children
    const toggleExpand = (title: string) => {
        setExpandedItems(prev => ({
            ...prev,
            [title]: !prev[title]
        }));
    };

    // Check if a link is currently active
    const isLinkActive = (url: string): boolean => {
        const currentPath = location.pathname;
        return currentPath.includes(`/panel/${url}`);
    };

    // Render navigation items recursively
    const renderNavItems = (items: NavLink[], level = 0) => {
        return items.map((item) => {
            const isActive = isLinkActive(item.url);
            const hasChildren = item.children && item.children.length > 0;
            const isExpanded = expandedItems[item.title] || false;

            // Check if any child is active to highlight the parent
            const isChildActive = hasChildren && item.children?.some(child => isLinkActive(child.url));

            return (
                <React.Fragment key={item.title}>
                    <ListItem
                        disablePadding
                        sx={{
                            display: 'block',
                            pl: level * 2 // Indent based on level
                        }}
                    >
                        <ListItemButton
                            onClick={() => hasChildren ? toggleExpand(item.title) : handleNavigation(item.url)}
                            sx={{
                                minHeight: 48,
                                px: 2.5,
                                backgroundColor: (isActive || isChildActive) ? 'rgba(0, 0, 0, 0.08)' : 'transparent',
                                '&:hover': {
                                    backgroundColor: 'rgba(0, 0, 0, 0.12)'
                                }
                            }}
                        >
                            <ListItemIcon sx={{
                                minWidth: 0,
                                mr: 3,
                                color: (isActive || isChildActive) ? theme.palette.primary.main : 'inherit'
                            }}>
                                {item.icon}
                            </ListItemIcon>
                            <ListItemText
                                primary={
                                    <Typography
                                        variant="body1"
                                        sx={{
                                            fontWeight: (isActive || isChildActive) ? 600 : 400,
                                            color: (isActive || isChildActive) ? theme.palette.primary.main : 'inherit'
                                        }}
                                    >
                                        {item.title}
                                    </Typography>
                                }
                            />
                            {hasChildren && (
                                isExpanded ? <ExpandLess /> : <ExpandMore />
                            )}
                        </ListItemButton>
                    </ListItem>

                    {/* Render children if this item has any */}
                    {hasChildren && (
                        <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                            <List component="div" disablePadding>
                                {renderNavItems(item.children, level + 1)}
                            </List>
                        </Collapse>
                    )}
                </React.Fragment>
            );
        });
    };

    return (
        <Drawer
            sx={{
                width: DRAWER_WIDTH,
                flexShrink: 0,
                '& .MuiDrawer-paper': {
                    width: DRAWER_WIDTH,
                    boxSizing: 'border-box',
                    border: 'none',
                    boxShadow: 3
                },
            }}
            variant={isMobile ? "temporary" : "persistent"}
            anchor="left"
            open={open}
            onClose={handleDrawerClose}
        >
            <DrawerHeader>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <FileUp size={24} />
                    <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                        Magellon
                    </Typography>
                </Box>
            </DrawerHeader>

            <Divider />

            {/* Main navigation list */}
            <List sx={{ p: 1 }}>
                {renderNavItems(navLinks)}
            </List>

            {/* App version at bottom of drawer */}
            <Box sx={{
                mt: 'auto',
                p: 2,
                borderTop: '1px solid rgba(0, 0, 0, 0.12)',
                textAlign: 'center'
            }}>
                <Typography variant="caption" color="text.secondary">
                    Magellon v0.1.0
                </Typography>
            </Box>
        </Drawer>
    );
};