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
    Beaker, BrainCircuit, ArrowRightFromLine
} from "lucide-react";
import { Box, Collapse, Typography, useMediaQuery } from '@mui/material';
import { ExpandLess, ExpandMore } from '@mui/icons-material';

const DRAWER_WIDTH = 240;

// Styled components
const DrawerHeader = styled('div')(({ theme }) => ({
    display: 'flex',
    alignItems: 'center',
    padding: theme.spacing(0, 1),
    ...theme.mixins.toolbar,
    justifyContent: 'center',
    backgroundColor: '#0a1929', // Dark navy color
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
        icon: <ArrowRightFromLine size={20} />
    },
    // {
    //     title: "Processing",
    //     url: "processing",
    //     icon: <Layers size={20} />,
    //     children: [
    //         {
    //             title: "Run Job",
    //             url: "run-job",
    //             icon: <Beaker size={20} />
    //         },
    //         {
    //             title: "2D Classification",
    //             url: "2d-assess",
    //             icon: <PanelLeft size={20} />
    //         },
    //         {
    //             title: "MRC Viewer",
    //             url: "mrc-viewer",
    //             icon: <BarChart2 size={20} />
    //         }
    //     ]
    // },
    // {
    //     title: "Test",
    //     url: "test",
    //     icon: <Beaker size={20} />
    // },
    // {
    //     title: "API",
    //     url: "api",
    //     icon: <BrainCircuit size={20} />
    // },
    // {
    //     title: "Settings",
    //     url: "settings",
    //     icon: <Settings size={20} />
    // },
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
                                backgroundColor: (isActive || isChildActive) ? 'rgba(103, 232, 249, 0.1)' : 'transparent',
                                borderRadius: 1,
                                my: 0.5,
                                '&:hover': {
                                    backgroundColor: 'rgba(255, 255, 255, 0.08)'
                                }
                            }}
                        >
                            <ListItemIcon sx={{
                                minWidth: 0,
                                mr: 3,
                                color: (isActive || isChildActive) ? '#67e8f9' : 'rgba(255, 255, 255, 0.7)'
                            }}>
                                {item.icon}
                            </ListItemIcon>
                            <ListItemText
                                primary={
                                    <Typography
                                        variant="body1"
                                        sx={{
                                            fontWeight: (isActive || isChildActive) ? 600 : 400,
                                            color: (isActive || isChildActive) ? '#67e8f9' : 'rgba(255, 255, 255, 0.85)'
                                        }}
                                    >
                                        {item.title}
                                    </Typography>
                                }
                            />
                            {hasChildren && (
                                isExpanded ? <ExpandLess sx={{ color: 'rgba(255, 255, 255, 0.7)' }} /> : <ExpandMore sx={{ color: 'rgba(255, 255, 255, 0.7)' }} />
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
                    boxShadow: 3,
                    backgroundColor: '#0a1929', // Dark navy background
                    color: 'rgba(255, 255, 255, 0.8)', // Slightly softer white text
                },
            }}
            variant={isMobile ? "temporary" : "persistent"}
            anchor="left"
            open={open}
            onClose={handleDrawerClose}
        >
            <DrawerHeader>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 4.5C10.6193 4.5 9.5 5.61929 9.5 7C9.5 8.38071 10.6193 9.5 12 9.5C13.3807 9.5 14.5 8.38071 14.5 7C14.5 5.61929 13.3807 4.5 12 4.5Z"
                              stroke="#67e8f9" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M4.5 15C4.5 16.3807 5.61929 17.5 7 17.5C8.38071 17.5 9.5 16.3807 9.5 15C9.5 13.6193 8.38071 12.5 7 12.5C5.61929 12.5 4.5 13.6193 4.5 15Z"
                              stroke="#67e8f9" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M14.5 15C14.5 16.3807 15.6193 17.5 17 17.5C18.3807 17.5 19.5 16.3807 19.5 15C19.5 13.6193 18.3807 12.5 17 12.5C15.6193 12.5 14.5 13.6193 14.5 15Z"
                              stroke="#67e8f9" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M9.5 7.5V12.5" stroke="#67e8f9" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M14.5 7.5V12.5" stroke="#67e8f9" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M9.5 15H14.5" stroke="#67e8f9" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    <Typography variant="h6" sx={{ fontWeight: 'bold', color: '#fff' }}>
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