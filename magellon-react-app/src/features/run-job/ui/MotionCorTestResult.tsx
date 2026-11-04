import React, { useEffect, useRef } from "react";
import { Box, useTheme } from "@mui/material";
import { settings } from "../../../shared/config/settings.ts";
import { useAuthenticatedImage } from "../../../shared/lib/useAuthenticatedImage.ts";
import { FrameAlignmentPanel } from "../../image-viewer/ui/FrameAlignmentPanel.tsx";

/** The MotionCor plugin's TaskResultMessage, as relayed over the test WebSocket. */
export interface MotionCorTestData {
    output_files?: Array<{ name?: string; path: string }>;
    run_command?: string | null;
}

const pictureUrl = (taskId: string, files: MotionCorTestData["output_files"], suffix: string): string | null => {
    const name = files?.find((f) => f.path?.endsWith(suffix))?.path.split("/").pop();
    return name ? `${settings.ConfigData.SERVER_API_URL}/web/test-output/${taskId}/${encodeURIComponent(name)}` : null;
};

/** A single-file MotionCor test's results, laid out as the Frame Alignment tab. */
export const MotionCorTestResult: React.FC<{ taskId: string; data: MotionCorTestData }> = ({ taskId, data }) => {
    const theme = useTheme();
    const one = useAuthenticatedImage(pictureUrl(taskId, data.output_files, "_mco_one.jpg"));
    const two = useAuthenticatedImage(pictureUrl(taskId, data.output_files, "_mco_two.jpg"));
    const top = useRef<HTMLDivElement>(null);

    // The results are below a long form: bring them into view.
    useEffect(() => {
        top.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, [taskId]);

    // Failed before MotionCor ran: the error above says why.
    if (!data.run_command) return null;

    return (
        <Box ref={top} sx={{ mt: 3 }} data-testid="motioncor-test-result">
            <FrameAlignmentPanel
                faoOneUrl={one.imageUrl}
                isFaoOneLoading={one.isLoading}
                faoTwoUrl={two.imageUrl}
                isFaoTwoLoading={two.isLoading}
                command={data.run_command}
                isCommandLoading={false}
                isCommandError={false}
                imageStyle={{
                    width: "100%",
                    height: "auto",
                    borderRadius: "12px",
                    objectFit: "contain",
                    border: `2px solid ${theme.palette.divider}`,
                }}
                isMobile={false}
            />
        </Box>
    );
};
