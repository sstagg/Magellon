import React, { useState } from "react";
import {
    Alert,
    Box,
    Button,
    Skeleton,
    Stack,
    Typography,
} from "@mui/material";
import type { SxProps, Theme } from "@mui/material";

export interface RunCommandProps {
    title: string;
    command: string | null;
    isLoading: boolean;
    isError: boolean;
    sx?: SxProps<Theme>;
}

/** The command that produced an image's results, as recorded in its run log. */
export const RunCommand: React.FC<RunCommandProps> = ({ title, command, isLoading, isError, sx }) => {
    const [copied, setCopied] = useState(false);

    const copy = async () => {
        if (!command) return;
        await navigator.clipboard.writeText(command);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
    };

    return (
        <Box sx={[{ width: "100%" }, ...(Array.isArray(sx) ? sx : [sx])]} data-testid="run-command">
            <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", mb: 0.5 }}>
                <Typography variant="subtitle2">{title}</Typography>
                {command && (
                    <Button size="small" onClick={copy} sx={{ textTransform: "none" }}>
                        {copied ? "Copied" : "Copy"}
                    </Button>
                )}
            </Stack>
            {isLoading ? (
                <Skeleton variant="rectangular" height={64} />
            ) : isError ? (
                <Alert severity="warning">The command could not be loaded.</Alert>
            ) : command ? (
                <Box
                    component="pre"
                    sx={{
                        m: 0,
                        p: 1.5,
                        borderRadius: 1,
                        bgcolor: "action.hover",
                        fontFamily: "monospace",
                        fontSize: "0.8rem",
                        whiteSpace: "pre-wrap",
                        overflowWrap: "anywhere",
                    }}
                >
                    {command}
                </Box>
            ) : (
                <Alert severity="info">
                    No command was recorded for this image. Images processed before run logs were added don't have one.
                </Alert>
            )}
        </Box>
    );
};

export default RunCommand;
