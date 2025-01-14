import {Typography} from "@mui/material";
import Box from "@mui/material/Box";
import FileBrowser from "./FileBrowser.tsx";


export const MagellonImportComponent = () => {

    const handleFileSelect = (path: string) => {
        console.log('Selected session file:', path);
        // Handle the selected file path
    };

    return (
        <div>
            <Typography variant="h6" gutterBottom>
                Import Data from Magellan Microscope Sessions
            </Typography>
            <Typography variant="body2" color="textSecondary">
                If you are using Docker, please select a directory from the MAGELLON_GPFS_PATH that was configured
                during installation in the .env file.
            </Typography>
            <p className="text-sm text-gray-600">
                Browse and select a session.json file from your Magellan microscope sessions
            </p>
            <Box sx={{mt: 2}}>
                <FileBrowser
                    onSelect={handleFileSelect}
                    initialPath="c:/temp/test2"
                />
            </Box>
        </div>
    );
};