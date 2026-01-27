import { Dialog, DialogTitle, DialogContent, DialogActions, Button, CircularProgress, Box, Typography } from "@mui/material";
import { useState, useEffect } from "react";
import { X } from "lucide-react";

interface MrcViewerProps {
    open: boolean;
    onClose: () => void;
    fileUrl: string;
    filename: string;
}

export const MrcViewer: React.FC<MrcViewerProps> = ({ open, onClose, fileUrl, filename }) => {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [canvas, setCanvas] = useState<HTMLCanvasElement | null>(null);

    useEffect(() => {
        if (!open || !fileUrl) {
            return;
        }

        setIsLoading(true);
        setError(null);

        const loadAndRenderMrc = async () => {
            try {
                // Get auth token from localStorage
                const token = localStorage.getItem('access_token');
                
                // Fetch the MRC file with auth token
                const headers: HeadersInit = {};
                if (token) {
                    headers['Authorization'] = `Bearer ${token}`;
                }
                
                const response = await fetch(fileUrl, { headers });
                if (!response.ok) {
                    throw new Error(`Failed to load file: ${response.statusText}`);
                }

                const arrayBuffer = await response.arrayBuffer();
                const view = new DataView(arrayBuffer);

                // Parse MRC header (first 1024 bytes)
                // MRC format: NX, NY, NZ (int32), MAPC, MAPR, MAPS (int32)
                const NX = view.getInt32(0, true);     // Number of columns (X)
                const NY = view.getInt32(4, true);     // Number of rows (Y)
                const NZ = view.getInt32(8, true);     // Number of sections (Z)
                const MAPC = view.getInt32(28, true);  // Column axis (1=X)
                const MAPR = view.getInt32(32, true);  // Row axis (2=Y)
                const MAPS = view.getInt32(36, true);  // Section axis (3=Z)

                // Data type: MODE
                // 0 = int8, 1 = int16, 2 = float32, 3 = complex int16, 4 = complex float32, 6 = uint16
                const MODE = view.getInt32(12, true);

                if (NX <= 0 || NY <= 0 || NZ <= 0) {
                    throw new Error(`Invalid MRC dimensions: ${NX}x${NY}x${NZ}`);
                }

                // Skip to image data (after header and extended header)
                const NXSTART = view.getInt32(16, true);
                const NYSTART = view.getInt32(20, true);
                const NZSTART = view.getInt32(24, true);
                const NXYZ = view.getInt32(40, true);
                const IMOD = view.getInt32(48, true);
                const EXTIND = view.getInt32(92, true);

                // Calculate where image data starts
                // Standard header is 1024 bytes + extended header (if any)
                let dataOffset = 1024;
                if (EXTIND > 0) {
                    const extendedHeaderSize = view.getInt32(92, true);
                    dataOffset += extendedHeaderSize * 1024;
                }

                // Get the first slice (Z=0)
                const bytesPerPixel = MODE === 1 ? 2 : MODE === 2 ? 4 : 1;
                const pixelsPerSlice = NX * NY;
                const bytesPerSlice = pixelsPerSlice * bytesPerPixel;

                // Extract the first slice data
                const sliceData = new Float32Array(pixelsPerSlice);
                const dataView = new DataView(arrayBuffer, dataOffset, bytesPerSlice);

                if (MODE === 1) {
                    // int16
                    for (let i = 0; i < pixelsPerSlice; i++) {
                        sliceData[i] = dataView.getInt16(i * 2, true);
                    }
                } else if (MODE === 2) {
                    // float32
                    for (let i = 0; i < pixelsPerSlice; i++) {
                        sliceData[i] = dataView.getFloat32(i * 4, true);
                    }
                } else {
                    // int8 or other
                    for (let i = 0; i < pixelsPerSlice; i++) {
                        sliceData[i] = view.getInt8(dataOffset + i);
                    }
                }

                // Find min/max for normalization
                let min = sliceData[0];
                let max = sliceData[0];
                for (let i = 1; i < pixelsPerSlice; i++) {
                    if (sliceData[i] < min) min = sliceData[i];
                    if (sliceData[i] > max) max = sliceData[i];
                }

                // Render to canvas
                const c = document.createElement('canvas');
                c.width = NX;
                c.height = NY;
                const ctx = c.getContext('2d');
                if (!ctx) throw new Error('Failed to get canvas context');

                const imageData = ctx.createImageData(NX, NY);
                const data = imageData.data;

                // Normalize and render
                const range = max - min || 1;
                for (let i = 0; i < pixelsPerSlice; i++) {
                    const normalized = ((sliceData[i] - min) / range) * 255;
                    const idx = i * 4;
                    data[idx] = normalized;     // R
                    data[idx + 1] = normalized; // G
                    data[idx + 2] = normalized; // B
                    data[idx + 3] = 255;        // A
                }

                ctx.putImageData(imageData, 0, 0);
                setCanvas(c);
            } catch (err: any) {
                console.error('Error loading MRC file:', err);
                setError(err.message || 'Failed to parse MRC file');
            } finally {
                setIsLoading(false);
            }
        };

        loadAndRenderMrc();
    }, [open, fileUrl]);

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="h6">View: {filename}</Typography>
                <Button onClick={onClose} size="small" sx={{ minWidth: 'auto' }}>
                    <X size={20} />
                </Button>
            </DialogTitle>
            <DialogContent sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400, p: 2 }}>
                {isLoading && (
                    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                        <CircularProgress />
                        <Typography variant="body2" color="textSecondary">
                            Loading MRC file...
                        </Typography>
                    </Box>
                )}
                {error && (
                    <Typography color="error">
                        Error: {error}
                    </Typography>
                )}
                {canvas && !isLoading && !error && (
                    <Box
                        component="canvas"
                        ref={(ref) => {
                            if (ref && canvas) {
                                const ctx = ref.getContext('2d');
                                if (ctx) {
                                    ctx.drawImage(canvas, 0, 0);
                                }
                            }
                        }}
                        sx={{
                            maxWidth: '100%',
                            maxHeight: 400,
                            border: '1px solid #ccc',
                            borderRadius: 1,
                            objectFit: 'contain'
                        }}
                        width={canvas.width}
                        height={canvas.height}
                    />
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} variant="contained">
                    Close
                </Button>
            </DialogActions>
        </Dialog>
    );
};
