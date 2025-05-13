
import "swagger-ui-react/swagger-ui.css"
import {settings} from "../../../core/settings.ts";
import {Card, CardContent, Container, Tabs, Typography} from "@mui/material";
import {useState} from "react";
import Box from "@mui/material/Box";
import Tab from "@mui/material/Tab";
import TabPanel from "@mui/lab/TabPanel";

import {MagellonImportComponent} from "../components/MagellonImportComponent.tsx";
import {EpuImportComponent} from "../components/EpuImportComponent.tsx";
import TabContext from "@mui/lab/TabContext";
import TabList from "@mui/lab/TabList";
import {LeginonImportComponent} from "../components/LeginonImportComponent.tsx";
import {ImportIcon} from "lucide-react";

const BASE_URL = settings.ConfigData.SERVER_API_URL ;

export const ImportPageView = () => {
    // console.log("ApisView");
    const [value, setValue] = useState('1');

    const handleChange = (event: React.SyntheticEvent, newValue: number) => {
        setValue(newValue);
    };

    return (
        <Container sx={{py: 4}}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
                <ImportIcon
                    width={48}
                    height={48}
                    color="#0000FF"
                    className="large-blue-icon"
                />
                <Typography variant="h4">
                    Magellon Data Importer
                </Typography>
            </Box>

            <Typography variant="body1" color="textSecondary">
                Select an importer to begin importing cryoem session data
            </Typography>

            <Box sx={{width: '100%', typography: 'body1', mt: 4}}>
                <TabContext value={value}>
                    <Box sx={{borderBottom: 1, borderColor: 'divider'}}>
                        <TabList onChange={handleChange} aria-label="import options">
                            <Tab label="Leginon" value="1"/>
                            <Tab label="Magellon" value="2"/>
                            <Tab label="EPU" value="3"/>
                        </TabList>
                    </Box>
                    <TabPanel value="1">
                        <Card>
                            <CardContent>
                                <LeginonImportComponent/>
                            </CardContent>
                        </Card>
                    </TabPanel>
                    <TabPanel value="2">
                        <Card>
                            <CardContent>
                                <MagellonImportComponent/>
                            </CardContent>
                        </Card>
                    </TabPanel>
                    <TabPanel value="3">
                        <Card>
                            <CardContent>
                                <EpuImportComponent/>
                            </CardContent>
                        </Card>
                    </TabPanel>
                </TabContext>
            </Box>
        </Container>
    );
};
