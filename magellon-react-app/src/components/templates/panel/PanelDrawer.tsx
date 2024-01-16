import * as React from 'react';
import { styled, useTheme } from '@mui/material/styles';
import Drawer from '@mui/material/Drawer';
import List from '@mui/material/List';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import InboxIcon from '@mui/icons-material/MoveToInbox';
import MailIcon from '@mui/icons-material/Mail';
import AppLink from "./AppLink.ts";
import {Link,useNavigate } from "react-router-dom";
import {blueGrey} from "@mui/material/colors";

const drawerWidth = 240;
const links: AppLink[] = [
    new AppLink("Images", "images", "google-icon"),
    new AppLink("Plugins", "domains/plugins", "facebook-icon"),
    new AppLink("Processes", "leginon-transfer", "facebook-icon"),
    new AppLink("Leginon Import", "leginon-transfer", "facebook-icon"),
    new AppLink("API", "api", "twitter-icon"),
    new AppLink("Blogs", "domains/blogs", "google-icon"),
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
                <List>
                    {['Inbox', 'Starred', 'Send email', 'Drafts'].map((text, index) => (
                        <ListItem key={text} disablePadding>
                            <ListItemButton>
                                <ListItemIcon>
                                    {index % 2 === 0 ? <InboxIcon /> : <MailIcon />}
                                </ListItemIcon>
                                <ListItemText primary={text} />
                            </ListItemButton>
                        </ListItem>
                    ))}
                </List>
                <Divider />
                <List>
                    {links.map((link, index) => (
                        <ListItem key={link.title} disablePadding>
                                        <ListItemButton onClick={() => handlLinkClick(link.url)}>
                                            <ListItemIcon>
                                            </ListItemIcon>
                                            <ListItemText primary={link.title}/>
                                        </ListItemButton>
                        </ListItem>
                    ))}
                </List>
            </Drawer>

    );
};
