import {Typography} from "@mui/material";
import Box from "@mui/material/Box";
import TusUploader from "./TusdUploader.tsx";


export const EpuImportComponent = () => {
    return (
        <div>
            <Typography variant="h6" gutterBottom>
                EPU Importer
            </Typography>
            <Typography variant="body2" color="textSecondary" paragraph>
                If you are using Docker, please select a directory from the MAGELLON_GPFS_PATH that was configured
                during installation in the .env file.
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
            <TusUploader
                endpoint="http://localhost:83/files/"
                onSuccess={(uploadUrl) => {
                    console.log('File available at:', uploadUrl);
                }}
            />
        </div>
    );
};