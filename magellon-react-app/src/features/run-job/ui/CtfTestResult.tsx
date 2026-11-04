import { useEffect, useRef } from "react";
import { Alert, Box } from "@mui/material";
import { settings } from "../../../shared/config/settings.ts";
import { useAuthenticatedImage } from "../../../shared/lib/useAuthenticatedImage.ts";
import { CTFAnalysisPanel } from "../../image-viewer/ui/CTFAnalysisPanel.tsx";
import type { CtfData } from "../../image-viewer/ui/CTFAnalysisPanel.tsx";
import { RunCommand } from "../../image-viewer/ui/RunCommand.tsx";

/** The CTF plugin's TaskResultMessage, as relayed over the test WebSocket. */
export interface CtfTestData {
    code?: number;
    message?: string;
    output_files?: Array<{ name?: string; path: string }>;
    meta_data?: Array<{ key: string; value: string }>;
    run_command?: string | null;
}

const pictureUrl = (taskId: string, files: CtfTestData["output_files"], suffix: string): string | null => {
    const name = files?.find((f) => f.path?.endsWith(suffix))?.path.split("/").pop();
    return name ? `${settings.ConfigData.SERVER_API_URL}/web/test-output/${taskId}/${encodeURIComponent(name)}` : null;
};

/** The plugin's values, in the units the CTF tab shows (as /web/ctf-info converts them). */
const ctfValues = (data: CtfTestData): CtfData | null => {
    try {
        const ctf = data.meta_data?.find((m) => m.key === "CTF");
        if (!ctf) return null;
        const v = JSON.parse(ctf.value);
        return {
            defocus1: Number(v.defocus1) * 1e6,
            defocus2: Number(v.defocus2) * 1e6,
            angleAstigmatism: (Number(v.angle_astigmatism) * 180) / Math.PI,
            resolution: v.resolution_50_percent != null ? Number(v.resolution_50_percent) : null,
        };
    } catch {
        return null;
    }
};

/** A single-file CTF test's results, laid out as the CTF tab. */
export const CtfTestResult = ({ taskId, data }: { taskId: string; data: CtfTestData }) => {
    const failed = (data.code ?? 200) >= 400;
    const values = ctfValues(data);
    const powerspec = useAuthenticatedImage(pictureUrl(taskId, data.output_files, "-powerspec.jpg"));
    const plots = useAuthenticatedImage(pictureUrl(taskId, data.output_files, "-plots.png"));
    const top = useRef<HTMLDivElement>(null);

    // The results are below a long form: bring them into view.
    useEffect(() => {
        top.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, [taskId]);

    return (
        <Box ref={top} sx={{ mt: 3 }} data-testid="ctf-test-result">
            {failed && <Alert severity="error" sx={{ mb: 2 }}>{data.message || "CTF failed"}</Alert>}
            {values ? (
                <CTFAnalysisPanel
                    ctfData={values}
                    isLoading={false}
                    error={null}
                    powerspecUrl={powerspec.imageUrl}
                    isPowerspecLoading={powerspec.isLoading}
                    plotsUrl={plots.imageUrl}
                    isPlotsLoading={plots.isLoading}
                    command={data.run_command ?? null}
                    isCommandLoading={false}
                    isCommandError={false}
                    isMobile={false}
                />
            ) : data.run_command ? (
                <RunCommand title="CTFFIND command" command={data.run_command} isLoading={false} isError={false} />
            ) : null}
        </Box>
    );
};
