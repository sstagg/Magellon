import React from "react";
import {
    Alert,
    Skeleton,
    Stack,
} from "@mui/material";

export interface FrameAlignmentPanelProps {
    faoOneUrl: string | null;
    isFaoOneLoading: boolean;
    faoTwoUrl: string | null;
    isFaoTwoLoading: boolean;
    imageStyle: React.CSSProperties;
    isMobile: boolean;
}

export const FrameAlignmentPanel: React.FC<FrameAlignmentPanelProps> = ({
    faoOneUrl,
    isFaoOneLoading,
    faoTwoUrl,
    isFaoTwoLoading,
    imageStyle,
    isMobile,
}) => {
    return (
        <Stack spacing={2} alignItems="center">
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
