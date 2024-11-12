import * as React from 'react';
import { styled, useTheme } from '@mui/material/styles';
import Drawer from '@mui/material/Drawer';
import List from '@mui/material/List';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import ImageIcon from '@mui/icons-material/Image';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import MailIcon from '@mui/icons-material/Mail';
import AppLink from "./AppLink.ts";
import {Link,useNavigate } from "react-router-dom";
import {blueGrey} from "@mui/material/colors";
import {AccountTree, Api, Extension, ImportExport, QuestionMark, Settings} from "@mui/icons-material";

const drawerWidth = 240;
const links: AppLink[] = [
    new AppLink("Images", "images", "images"),
    new AppLink("Run Job", "run-job", "plugins"),
    new AppLink("Plugins", "domains/plugins", "plugins"),
    new AppLink("Pipelines", "domains/plugins", "account-tree"),
    new AppLink("Leginon Import", "leginon-transfer", "import"),
    new AppLink("API", "api", "api"),
    new AppLink("Mrc Viewer", "mrc-viewer", "image"),
    // new AppLink("Blogs", "domains/blogs", "google-icon"),
    new AppLink("Settings", "domains/blogs", "settings"),
];
const DrawerHeader = styled('div')(({ theme }) => ({
    display: 'flex',
    alignItems: 'center',
    padding: theme.spacing(0, 1),
    // necessary for content to be below app bar
    ...theme.mixins.toolbar,
    justifyContent: 'flex-end',
}));
interface PanelDrawerProps {
    open: boolean;
    handleDrawerClose: () => void;
}

const getIconByName = (name: string): JSX.Element => {
    switch (name) {
        case 'images':
            return <ImageIcon />;
        case 'plugins':
            return <Extension />;
        case 'import':
            return <ImportExport />;
        case 'mail':
            return <MailIcon />;
        case 'account-tree':
            return <AccountTree />;
        case 'api':
            return <Api />;
        case 'settings':
            return <Settings />;
        case 'someOther':
            return <QuestionMark />;
        // Add more cases for other icon names as needed
        default:
            return <QuestionMark />; // Default to InboxIcon if the name is not recognized
    }
};

export const PanelDrawer : React.FC<PanelDrawerProps> = ({ open, handleDrawerClose }) => {
    const theme = useTheme();

    const navigate = useNavigate();
    const handlLinkClick = (url : string ) => {
        handleDrawerClose();
        navigate(url);
    };

    return (
            <Drawer
                sx={{
                    width: drawerWidth,
                    flexShrink: 0,
                    '& .MuiDrawer-paper': {
                        width: drawerWidth,
                        boxSizing: 'border-box',
                    },
                }}
                variant="persistent"
                anchor="left"
                open={open}
            >

                <DrawerHeader sx ={{backgroundColor: blueGrey}}>
                    <h3>Magellon</h3>
                    <IconButton onClick={handleDrawerClose}>
                        {theme.direction === 'ltr' ? <ChevronLeftIcon /> : <ChevronRightIcon />}
                    </IconButton>
                </DrawerHeader>


                <Divider />

                <Divider />
                <List>
                    {links.map((link, index) => (
                        <ListItem key={link.title} disablePadding>
                                        <ListItemButton onClick={() => handlLinkClick(link.url)}>
                                            <ListItemIcon>
                                                {getIconByName(link.icon)}
                                            </ListItemIcon>
                                            <ListItemText primary={link.title}/>
                                        </ListItemButton>
                        </ListItem>
                    ))}
                </List>
            </Drawer>

    );
};
