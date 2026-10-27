import { useEffect, useState } from "react";
import { Alert, Box, Grid, Paper, Table, TableBody, TableCell, TableRow, Typography } from "@mui/material";
import { settings } from "../../../shared/config/settings.ts";
import getAxiosClient from '../../../shared/api/AxiosClient.ts';

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

/** The CTF plugin's TaskResultMessage, as relayed over the test WebSocket. */
export interface CtfTestData {
    code?: number;
    message?: string;
    output_files?: Array<{ name?: string; path: string }>;
    meta_data?: Array<{ key: string; value: string }>;
}

const PICTURES = /\.(png|jpe?g)$/i;

/** One output picture, fetched with the login token from /web/test-output. */
const OutputPicture = ({ taskId, path, label }: { taskId: string; path: string; label: string }) => {
    const [src, setSrc] = useState<string | null>(null);
    const [failed, setFailed] = useState(false);
    useEffect(() => {
        let url: string | null = null;
        const name = path.split('/').pop() as string;
        apiClient.get(`/web/test-output/${taskId}/${encodeURIComponent(name)}`, { responseType: 'blob' })
            .then((res) => { url = URL.createObjectURL(res.data); setSrc(url); })
            .catch(() => setFailed(true));
        return () => { if (url) URL.revokeObjectURL(url); };
    }, [taskId, path]);
    return (
        <Paper variant="outlined" sx={{ p: 1 }}>
            <Typography variant="caption" color="textSecondary">{label}</Typography>
            {src && <Box component="img" src={src} alt={label} sx={{ width: '100%', display: 'block', mt: 0.5 }} />}
            {failed && <Typography variant="body2" color="error">Could not load this picture.</Typography>}
        </Paper>
    );
};

/** Values and pictures of a single-file CTF test. */
export const CtfTestResult = ({ taskId, data }: { taskId: string; data: CtfTestData }) => {
    const failed = (data.code ?? 200) >= 400;
    let values: Record<string, unknown> = {};
    try {
        const ctf = data.meta_data?.find((m) => m.key === 'CTF');
        values = ctf ? JSON.parse(ctf.value) : {};
    } catch { /* no values */ }
    const rows = Object.entries(values).filter(([, v]) => typeof v === 'number' || typeof v === 'string');
    const pictures = (data.output_files ?? []).filter((f) => PICTURES.test(f.path));

    return (
        <Box sx={{ mb: 3 }}>
            <Alert severity={failed ? 'error' : 'success'} sx={{ mb: 2 }}>{data.message || (failed ? 'CTF failed' : 'CTF done')}</Alert>
            <Grid container spacing={2}>
                {rows.length > 0 && (
                    <Grid size={{ xs: 12, md: 4 }}>
                        <Paper variant="outlined">
                            <Table size="small">
                                <TableBody>
                                    {rows.map(([key, value]) => (
                                        <TableRow key={key}>
                                            <TableCell sx={{ fontWeight: 500 }}>{key}</TableCell>
                                            <TableCell>{typeof value === 'number' ? Number(value.toPrecision(5)) : value as string}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </Paper>
                    </Grid>
                )}
                {pictures.map((f) => (
                    <Grid key={f.path} size={{ xs: 12, md: rows.length ? 4 : 6 }}>
                        <OutputPicture taskId={taskId} path={f.path}
                            label={/powerspec/.test(f.path) ? 'Power spectrum' : /plots/.test(f.path) ? 'CTF fit plots' : (f.name || f.path)} />
                    </Grid>
                ))}
            </Grid>
        </Box>
    );
};
