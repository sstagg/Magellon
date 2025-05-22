import "swagger-ui-react/swagger-ui.css"
import {settings} from "../../../core/settings.ts";
import {Card, CardContent, Tabs, Typography, useTheme, useMediaQuery} from "@mui/material";
import {useState, useEffect} from "react";
import Box from "@mui/material/Box";
import Tab from "@mui/material/Tab";
import TabPanel from "@mui/lab/TabPanel";

import {MagellonImportComponent} from "../components/MagellonImportComponent.tsx";
import {EpuImportComponent} from "../components/EpuImportComponent.tsx";
import TabContext from "@mui/lab/TabContext";
import TabList from "@mui/lab/TabList";
import {LeginonImportComponent} from "../components/LeginonImportComponent.tsx";
import {ImportIcon} from "lucide-react";

const BASE_URL = settings.ConfigData.SERVER_API_URL;
const DRAWER_WIDTH = 240;

export const ImportPageView = () => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    const [value, setValue] = useState('1');

    // Track drawer state from localStorage to adjust layout
    const [isDrawerOpen, setIsDrawerOpen] = useState(() => {
        const savedState = localStorage.getItem('drawerOpen');
        return savedState ? JSON.parse(savedState) : false;
    });

    // Listen for drawer state changes
    useEffect(() => {
        const handleStorageChange = () => {
            const savedState = localStorage.getItem('drawerOpen');
            setIsDrawerOpen(savedState ? JSON.parse(savedState) : false);
        };

        window.addEventListener('storage', handleStorageChange);
        const interval = setInterval(handleStorageChange, 100);

        return () => {
            window.removeEventListener('storage', handleStorageChange);
            clearInterval(interval);
        };
    }, []);

    const handleChange = (event: React.SyntheticEvent, newValue: string) => {
        setValue(newValue);
    };

    // Calculate left margin based on drawer state
    const leftMargin = isDrawerOpen ? DRAWER_WIDTH : 0;

    return (
        <Box sx={{
            position: 'fixed',
            top: 64, // Account for header
            left: leftMargin,
            right: 0,
            bottom: 0,
            zIndex: 1050, // Below drawer but above content
            backgroundColor: 'background.default',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            transition: theme.transitions.create(['left'], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
            }),
        }}>
            {/* Scrollable Content Container */}
            <Box sx={{
                flex: 1,
                overflow: 'auto',
                p: { xs: 2, sm: 3, md: 4 }
            }}>
                {/* Header Section */}
                <Box sx={{
                    display: 'flex',
                    flexDirection: { xs: 'column', sm: 'row' },
                    alignItems: { xs: 'flex-start', sm: 'center' },
                    gap: { xs: 1, sm: 2 },
                    mb: { xs: 2, sm: 3, md: 4 }
                }}>
                    <ImportIcon
                        width={isMobile ? 36 : 48}
                        height={isMobile ? 36 : 48}
                        color="#0000FF"
                        className="large-blue-icon"
                    />
                    <Box>
                        <Typography
                            variant={isMobile ? "h5" : "h4"}
                            sx={{
                                fontWeight: 600,
                                fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' }
                            }}
                        >
                            Magellon Data Importer
                        </Typography>
                        <Typography
                            variant="body1"
                            color="textSecondary"
                            sx={{
                                mt: 0.5,
                                fontSize: { xs: '0.875rem', sm: '1rem' }
                            }}
                        >
                            Select an importer to begin importing cryoem session data
                        </Typography>
                    </Box>
                </Box>

                {/* Main Content Area */}
                <Box sx={{
                    width: '100%',
                    maxWidth: '100%',
                    mx: 'auto'
                }}>
                    <TabContext value={value}>
                        {/* Tab Navigation */}
                        <Box sx={{
                            borderBottom: 1,
                            borderColor: 'divider',
                            mb: { xs: 2, sm: 3 }
                        }}>
                            <TabList
                                onChange={handleChange}
                                aria-label="import options"
                                variant={isMobile ? "fullWidth" : "standard"}
                                sx={{
                                    '& .MuiTab-root': {
                                        fontSize: { xs: '0.875rem', sm: '1rem' },
                                        minHeight: { xs: 40, sm: 48 },
                                        textTransform: 'none',
                                        fontWeight: 500
                                    }
                                }}
                            >
                                <Tab label="Leginon" value="1"/>
                                <Tab label="Magellon" value="2"/>
                                <Tab label="EPU" value="3"/>
                            </TabList>
                        </Box>

                        {/* Tab Content Panels */}
                        <Box sx={{
                            width: '100%',
                            '& .MuiTabPanel-root': {
                                p: 0
                            }
                        }}>
                            <TabPanel value="1">
                                <Card
                                    elevation={1}
                                    sx={{
                                        borderRadius: 2,
                                        border: `1px solid ${theme.palette.divider}`,
                                        overflow: 'hidden'
                                    }}
                                >
                                    <CardContent sx={{
                                        p: { xs: 2, sm: 3, md: 4 },
                                        '&:last-child': { pb: { xs: 2, sm: 3, md: 4 } }
                                    }}>
                                        <LeginonImportComponent/>
                                    </CardContent>
                                </Card>
                            </TabPanel>

                            <TabPanel value="2">
                                <Card
                                    elevation={1}
                                    sx={{
                                        borderRadius: 2,
                                        border: `1px solid ${theme.palette.divider}`,
                                        overflow: 'hidden'
                                    }}
                                >
                                    <CardContent sx={{
                                        p: { xs: 2, sm: 3, md: 4 },
                                        '&:last-child': { pb: { xs: 2, sm: 3, md: 4 } }
                                    }}>
                                        <MagellonImportComponent/>
                                    </CardContent>
                                </Card>
                            </TabPanel>

                            <TabPanel value="3">
                                <Card
                                    elevation={1}
                                    sx={{
                                        borderRadius: 2,
                                        border: `1px solid ${theme.palette.divider}`,
                                        overflow: 'hidden'
                                    }}
                                >
                                    <CardContent sx={{
                                        p: { xs: 2, sm: 3, md: 4 },
                                        '&:last-child': { pb: { xs: 2, sm: 3, md: 4 } }
                                    }}>
                                        <EpuImportComponent/>
                                    </CardContent>
                                </Card>
                            </TabPanel>
                        </Box>
                    </TabContext>
                </Box>
            </Box>
        </Box>
    );
};

export default ImportPageView;