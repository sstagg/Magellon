import {Typography} from "@mui/material";
import Box from "@mui/material/Box";


export const EpuImportComponent = () => {
    return (
        <div>
            <Typography variant="h6" gutterBottom>
                EPU Importer
            </Typography>
            <Typography variant="body2" color="textSecondary" paragraph>
                Import data from EPU microscope sessions
            </Typography>
            <Box sx={{mt: 2}}>
                <input
                    type="file"
                    webkitdirectory=""
                    style={{
                        width: '100%',
                        padding: '10px',
                        marginTop: '8px'
                    }}
                />
            </Box>
        </div>
    );
};