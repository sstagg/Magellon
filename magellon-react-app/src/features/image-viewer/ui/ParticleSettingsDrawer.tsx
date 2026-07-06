import React, { useCallback, useMemo, useState } from 'react';
import {
    Box,
    Typography,
    CircularProgress,
    Chip,
    Alert,
    LinearProgress,
    IconButton,
    alpha,
    useTheme,
} from '@mui/material';
import { ArrowBack as BackIcon } from '@mui/icons-material';
import { SchemaForm, type BrowseFileRequest } from '../../../shared/ui/SchemaForm.tsx';
import { ImagePickerDialog } from '../../plugin-runner/ui/ImagePickerDialog.tsx';
import { API_URL, validateParams } from '../model/particleSettingsCore.ts';
import type { ParticleSettingsDrawerProps, TrainedModel } from '../model/particleSettingsTypes.ts';
import { useParticleBackends } from '../model/useParticleBackends.ts';
import { usePickerSchema } from '../model/usePickerSchema.ts';
import { useDispatchProgress } from '../model/useDispatchProgress.ts';
import { useDrawerRunState } from '../model/useDrawerRunState.ts';
import { usePickerPreview } from '../model/usePickerPreview.ts';
import { BackendSelector } from './particle-settings/BackendSelector.tsx';
import { ConfigureActions } from './particle-settings/ConfigureActions.tsx';
import { PreviewActions } from './particle-settings/PreviewActions.tsx';
import { ResultsActions } from './particle-settings/ResultsActions.tsx';
import { DispatchStatus } from './particle-settings/DispatchStatus.tsx';
import { ValidationErrorsAlert } from './particle-settings/ValidationErrorsAlert.tsx';
import { PreviewTunePanel } from './particle-settings/PreviewTunePanel.tsx';

export type { DrawerState, ParticleSettingsDrawerProps } from '../model/particleSettingsTypes.ts';

// ---------------------------------------------------------------------------
// Component — renders as a plain Box (no Drawer), meant to be placed
// inside the SidePanelArea alongside JobsPanel / LogsPanel.
// ---------------------------------------------------------------------------

export const ParticleSettingsPanel: React.FC<ParticleSettingsDrawerProps> = ({
    open,
    pickerParams,
    onPickerParamsChange,
    onRun: _onRun,
    onDispatch,
    onRunBatch,
    isRunning,
    onPreviewParticles,
    onAcceptParticles,
    onDiscardParticles,
    imageName,
    sessionName,
    autoPickingProgress: _autoPickingProgress,
    resultCount,
    ippName,
    currentParticleCount,
    currentParticles = [],
}) => {
    const theme = useTheme();
    const [runtimeError, setRuntimeError] = useState<string | null>(null);
    const [showErrors, setShowErrors] = useState(false);
    const [trainedModel, setTrainedModel] = useState<TrainedModel | null>(null);

    const { drawerState, setDrawerState, setDispatchedIppName } = useDrawerRunState({
        isRunning,
        resultCount,
        ippName,
    });

    // Backend selection
    const {
        backends,
        backendsLoading,
        selectedBackend,
        setSelectedBackend,
        backendEnabled,
        canPreview,
        isTopazBackend,
    } = useParticleBackends(open);

    const {
        setDispatchJobId,
        socketConnected,
        dispatchPercent,
        dispatchMessage,
        dispatchCompleted,
        dispatchFailed,
    } = useDispatchProgress();

    const manualTrainingParticles = useMemo(
        () => currentParticles.filter((p) => p.type === 'manual'),
        [currentParticles],
    );

    // GPFS picker state — driven by the SchemaForm's onBrowseFile
    // callback. Same pattern the plugin test panel uses; templates
    // path field gets the picker for free since template_paths is in
    // the schema's file_path heuristic whitelist.
    const [pickerRequest, setPickerRequest] = useState<BrowseFileRequest | null>(null);
    const handleBrowseFile = useCallback(
        (req: BrowseFileRequest) => setPickerRequest(req),
        [],
    );

    const { schema, schemaLoading, schemaError, resetSchema } = usePickerSchema({
        open,
        selectedBackend,
        onPickerParamsChange,
        setTrainedModel,
    });

    const validationErrors = useMemo(
        () => (schema ? validateParams(schema, pickerParams, imageName) : []),
        [schema, pickerParams, imageName],
    );
    const isValid = validationErrors.length === 0;

    const {
        previewCount,
        scoreMapPng,
        retuning,
        training,
        handlePreview,
        handleTrainSession,
        handleRetune,
        clearPreview,
        clearScoreMap,
    } = usePickerPreview({
        isValid,
        pickerParams,
        imageName,
        sessionName,
        selectedBackend,
        isTopazBackend,
        manualTrainingParticles,
        onPreviewParticles,
        onPickerParamsChange,
        setTrainedModel,
        setDrawerState,
        setShowErrors,
        setRuntimeError,
    });

    // --- Run (RMQ dispatch) ---
    const handleRun = async () => {
        if (!isValid) { setShowErrors(true); return; }
        setShowErrors(false);
        clearPreview();
        const name = ippName || `Auto-pick ${new Date().toISOString().slice(0, 16)}`;
        setDispatchedIppName(name);
        setDrawerState('dispatched');
        const result = await onDispatch(selectedBackend, name);
        if (result?.job_id) {
            setDispatchJobId(result.job_id);
        } else {
            setDrawerState('configure');
            setDispatchedIppName(null);
        }
    };

    // --- Accept / Discard ---
    const handleAccept = () => {
        clearPreview();
        clearScoreMap();
        onAcceptParticles();
        setDrawerState('configure');
    };

    const handleDiscard = () => {
        clearPreview();
        clearScoreMap();
        onDiscardParticles();
        setDrawerState('configure');
    };

    if (!open) return null;

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* ============ TOOLBAR ============ */}
            <Box sx={{
                px: 1.5, py: 1,
                borderBottom: `1px solid ${theme.palette.divider}`,
                backgroundColor: alpha(theme.palette.primary.main, 0.03),
                flexShrink: 0,
            }}>
                {/* Title row */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    {(drawerState === 'preview' || drawerState === 'results') && (
                        <IconButton size="small" onClick={handleDiscard} sx={{ mr: 0.5 }}>
                            <BackIcon fontSize="small" />
                        </IconButton>
                    )}
                    <Typography
                        variant="caption"
                        sx={{
                            fontWeight: 600,
                            flex: 1
                        }}>
                        {{
                            configure: 'Algorithm Settings',
                            previewing: 'Computing Preview...',
                            preview: 'Preview & Tune',
                            running: 'Running...',
                            dispatched: 'Task Queued',
                            results: 'Results',
                        }[drawerState]}
                    </Typography>
                    {schema && drawerState === 'configure' && (
                        <Chip label={selectedBackend} size="small" variant="outlined" sx={{ fontSize: '0.6rem', height: 20 }} />
                    )}
                </Box>

                {/* Backend selector — shown in configure state */}
                {drawerState === 'configure' && (
                    <BackendSelector
                        backends={backends}
                        selectedBackend={selectedBackend}
                        backendsLoading={backendsLoading}
                        onSelect={(backendId) => {
                            setSelectedBackend(backendId);
                            resetSchema(); // will re-fetch for new backend
                        }}
                    />
                )}

                {/* CONFIGURE: Preview + Run + Run Batch */}
                {drawerState === 'configure' && (
                    <ConfigureActions
                        canPreview={canPreview}
                        backendEnabled={backendEnabled}
                        isTopazBackend={isTopazBackend}
                        training={training}
                        manualTrainingCount={manualTrainingParticles.length}
                        trainedModel={trainedModel}
                        isValid={isValid}
                        validationErrorCount={validationErrors.length}
                        onToggleErrors={() => setShowErrors(!showErrors)}
                        onPreview={handlePreview}
                        onTrainSession={handleTrainSession}
                        onRun={handleRun}
                        onRunBatch={onRunBatch ? () => {
                            if (!isValid) { setShowErrors(true); return; }
                            setShowErrors(false);
                            onRunBatch();
                        } : undefined}
                    />
                )}

                {/* PREVIEW: pick count + actions */}
                {drawerState === 'preview' && (
                    <PreviewActions
                        previewCount={previewCount}
                        retuning={retuning}
                        onDiscard={handleDiscard}
                        onRun={handleRun}
                        onAccept={handleAccept}
                    />
                )}

                {/* RUNNING — indeterminate: the sync endpoint doesn't stream
                    progress, and showing a fake 0→100 was misleading. */}
                {drawerState === 'running' && (
                    <Box sx={{ mt: 0.5 }}>
                        <LinearProgress sx={{ height: 4, borderRadius: 1 }} />
                        <Typography
                            variant="caption"
                            sx={{
                                color: "text.secondary",
                                mt: 0.5,
                                display: 'block',
                                fontSize: '0.7rem'
                            }}>
                            Running...
                        </Typography>
                    </Box>
                )}

                {/* DISPATCHED — task sent to RMQ, polling for result */}
                {drawerState === 'dispatched' && (
                    <DispatchStatus
                        variant="toolbar"
                        selectedBackend={selectedBackend}
                        dispatchPercent={dispatchPercent}
                        dispatchMessage={dispatchMessage}
                        dispatchCompleted={dispatchCompleted}
                        dispatchFailed={dispatchFailed}
                        socketConnected={socketConnected}
                    />
                )}

                {/* RESULTS */}
                {drawerState === 'results' && (
                    <ResultsActions
                        count={resultCount ?? currentParticleCount ?? 0}
                        onDiscard={handleDiscard}
                        onAccept={handleAccept}
                    />
                )}

                {/* PREVIEWING spinner */}
                {drawerState === 'previewing' && (
                    <Box sx={{ textAlign: 'center', py: 0.5 }}>
                        <CircularProgress size={20} />
                    </Box>
                )}
            </Box>
            {/* ============ VALIDATION ERRORS ============ */}
            <ValidationErrorsAlert
                open={showErrors && validationErrors.length > 0 && drawerState === 'configure'}
                errors={validationErrors}
            />
            {/* ============ BODY (scrollable) ============ */}
            <Box sx={{ flex: 1, overflow: 'auto', px: 1.5, py: 1 }}>

                {schemaLoading && (
                    <Box sx={{ textAlign: 'center', py: 4 }}>
                        <CircularProgress size={24} />
                        <Typography
                            variant="caption"
                            sx={{
                                display: "block",
                                color: "text.secondary",
                                mt: 1
                            }}>Loading...</Typography>
                    </Box>
                )}

                {schemaError && (
                    <Box sx={{ p: 1.5, borderRadius: 1, mb: 1, backgroundColor: alpha(theme.palette.error.main, 0.08) }}>
                        <Typography variant="caption" color="error">{schemaError}</Typography>
                        <Typography
                            variant="caption"
                            sx={{
                                display: "block",
                                color: "text.secondary",
                                mt: 0.5
                            }}>
                            Backend: {API_URL}
                        </Typography>
                    </Box>
                )}

                {runtimeError && (
                    <Alert
                        severity="error"
                        onClose={() => setRuntimeError(null)}
                        sx={{ mb: 1, py: 0.5, '& .MuiAlert-message': { fontSize: '0.75rem' } }}
                    >
                        {runtimeError}
                    </Alert>
                )}

                {/* CONFIGURE: full form */}
                {drawerState === 'configure' && schema && (
                    <SchemaForm schema={schema} values={pickerParams} onChange={onPickerParamsChange}
                        defaultExpanded={['Templates', 'Auto-picking Settings', 'Topaz']} collapseAdvanced
                        onBrowseFile={handleBrowseFile} />
                )}

                {/* PREVIEW: score map + tunable sliders */}
                {drawerState === 'preview' && schema && (
                    <PreviewTunePanel
                        scoreMapPng={scoreMapPng}
                        schema={schema}
                        values={pickerParams}
                        onChange={handleRetune}
                        onBrowseFile={handleBrowseFile}
                    />
                )}

                {/* RUNNING */}
                {drawerState === 'running' && (
                    <Box sx={{ textAlign: 'center', py: 3 }}>
                        <CircularProgress size={32} />
                        <Typography
                            variant="caption"
                            sx={{
                                color: "text.secondary",
                                mt: 1.5,
                                display: 'block'
                            }}>
                            Running template matching...
                        </Typography>
                    </Box>
                )}

                {/* DISPATCHED — task queued via RMQ */}
                {drawerState === 'dispatched' && (
                    <DispatchStatus
                        variant="body"
                        selectedBackend={selectedBackend}
                        dispatchPercent={dispatchPercent}
                        dispatchMessage={dispatchMessage}
                        dispatchCompleted={dispatchCompleted}
                        dispatchFailed={dispatchFailed}
                        socketConnected={socketConnected}
                    />
                )}

                {/* RESULTS */}
                {drawerState === 'results' && (
                    <Box sx={{ py: 1 }}>
                        <Typography variant="caption" sx={{
                            color: "text.secondary"
                        }}>
                            {resultCount ?? currentParticleCount ?? 0} particles detected
                            {ippName ? ` and saved as “${ippName}”` : ''}.
                            {' '}Click <strong>Accept</strong> to keep or <strong>Discard</strong> to remove.
                        </Typography>
                    </Box>
                )}
            </Box>

            {/* GPFS browser dialog — opens when SchemaForm's file_path /
                file_path_list widgets request a browse. Templates path
                field qualifies via the heuristic in the shared SchemaForm
                (template_paths in FILE_PATH_FIELD_NAMES). */}
            {pickerRequest && (
                pickerRequest.multiple ? (
                    <ImagePickerDialog
                        open
                        multiple
                        title={`Pick ${pickerRequest.fieldTitle}`}
                        allowedExts={pickerRequest.allowedExts}
                        onClose={() => setPickerRequest(null)}
                        onPick={(paths: string[]) => {
                            pickerRequest.onPick(paths);
                            setPickerRequest(null);
                        }}
                    />
                ) : (
                    <ImagePickerDialog
                        open
                        title={`Pick ${pickerRequest.fieldTitle}`}
                        allowedExts={pickerRequest.allowedExts}
                        onClose={() => setPickerRequest(null)}
                        onPick={(path: string) => {
                            pickerRequest.onPick(path);
                            setPickerRequest(null);
                        }}
                    />
                )
            )}
        </Box>
    );
};

// Backward-compat export name
export const ParticleSettingsDrawer = ParticleSettingsPanel;
