import React, { useState } from "react";
import {
    Alert,
    Box,
    Button,
    Skeleton,
    Stack,
    Typography,
} from "@mui/material";

export interface FrameAlignmentPanelProps {
    faoOneUrl: string | null;
    isFaoOneLoading: boolean;
    faoTwoUrl: string | null;
    isFaoTwoLoading: boolean;
    command: string | null;
    isCommandLoading: boolean;
    isCommandError: boolean;
    imageStyle: React.CSSProperties;
    isMobile: boolean;
}

const MotionCorCommand: React.FC<{ command: string | null; isLoading: boolean; isError: boolean; isMobile: boolean }> = ({
    command,
    isLoading,
    isError,
    isMobile,
}) => {
    const [copied, setCopied] = useState(false);

    const copy = async () => {
        if (!command) return;
        await navigator.clipboard.writeText(command);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
    };

    return (
        <Box sx={{ width: "100%", maxWidth: isMobile ? "100%" : 900 }} data-testid="motioncor-command">
            <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", mb: 0.5 }}>
                <Typography variant="subtitle2">MotionCor command</Typography>
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
                    No command was recorded for this image. Images processed before MotionCor run logs were added don't have one.
                </Alert>
            )}
        </Box>
    );
};

export const FrameAlignmentPanel: React.FC<FrameAlignmentPanelProps> = ({
    faoOneUrl,
    isFaoOneLoading,
    faoTwoUrl,
    isFaoTwoLoading,
    command,
    isCommandLoading,
    isCommandError,
    imageStyle,
    isMobile,
}) => {
    return (
        <Stack spacing={2} sx={{
            alignItems: "center"
        }}>
            <MotionCorCommand command={command} isLoading={isCommandLoading} isError={isCommandError} isMobile={isMobile} />
            {isFaoOneLoading ? (
                <Skeleton variant="rectangular" width={isMobile ? 300 : 900} height={400} />
            ) : faoOneUrl ? (
                <img
                    src={faoOneUrl}
                    alt="Frame alignment - image one"
                    style={{
                        ...imageStyle,
                        maxWidth: isMobile ? '100%' : '900px'
                    }}
                />
            ) : (
                <Alert severity="info">Frame alignment image one not available</Alert>
            )}
            {isFaoTwoLoading ? (
                <Skeleton variant="rectangular" width={isMobile ? 300 : 900} height={400} />
            ) : faoTwoUrl ? (
                <img
                    src={faoTwoUrl}
                    alt="Frame alignment - image two"
                    style={{
                        ...imageStyle,
                        maxWidth: isMobile ? '100%' : '900px'
                    }}
                />
            ) : (
                <Alert severity="info">Frame alignment image two not available</Alert>
            )}
        </Stack>
    );
};

export default FrameAlignmentPanel;
