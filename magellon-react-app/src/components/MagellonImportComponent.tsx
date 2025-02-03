import { Typography } from "@mui/material";
import Box from "@mui/material/Box";
import { useState, useEffect } from "react";
import { FileManager } from "@cubone/react-file-manager";
import "@cubone/react-file-manager/dist/style.css";

type FileItem = {
    id: number;
    name: string;
    is_directory: boolean;
    path: string;
    parent_id?: number;
    size?: number;
    mime_type?: string;
    created_at: string;
    updated_at: string;
};

// Convert API response to FileManager format
const convertToFileManagerFormat = (items: FileItem[]) => {
    return items.map(item => ({
        name: item.name,
        isDirectory: item.is_directory,
        path: item.path,
        updatedAt: item.updated_at,
        size: item.size,
    }));
};

export const MagellonImportComponent = () => {
    const [files, setFiles] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [currentPath, setCurrentPath] = useState("/gpfs");
    // const [currentPath, setCurrentPath] = useState("c:/temp/test2");

    const fetchDirectory = async (path: string) => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(
                `http://localhost:8000/web/files/browse?path=${encodeURIComponent(path)}`
            );
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            setFiles(convertToFileManagerFormat(data));
            setCurrentPath(path);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDirectory(currentPath);
    }, []);

    const handleFileSelect = (file: File) => {
        console.log('Selected session file:', file);
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
            {error && (
                <Typography color="error" sx={{ mt: 1 }}>
                    Error: {error}
                </Typography>
            )}
            <Box sx={{ mt: 2 }}>
                {loading ? (
                    <Typography>Loading...</Typography>
                ) : (
                    <FileManager
                        onFileOpen={handleFileSelect}
                        files={files}
                        acceptedFileTypes={".json"}
                        enableFilePreview={false}
                    />
                )}
            </Box>
        </div>
    );
};
// https://www.npmjs.com/package/@codetez/react-file-manager-ctz