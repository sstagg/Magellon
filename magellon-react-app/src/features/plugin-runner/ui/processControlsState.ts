/**
 * Pure helper for the Start/Pause/Stop/Restart button gating.
 *
 * Extracted from InstalledPluginsView so the four independent input
 * signals (liveOnBus / supervisorRunning / isPaused / supportsPause /
 * busy) can be exercised in isolation. The matrix is non-trivial — five
 * booleans × four buttons = 80 cells — and the component code can't
 * easily be unit-tested without mounting react-query + MUI.
 *
 * Returns one boolean per button, ``true`` = disabled.
 */
export interface ProcessControlsInputs {
    /** Plugin is announcing on the bus (anyone — supervisor or
     * manually-launched dev plugin). */
    liveOnBus: boolean;
    /** Supervisor has a tracked PID for this plugin. */
    supervisorRunning: boolean;
    /** Plugin's lifecycle currently reports ``paused``. */
    isPaused: boolean;
    /** Backend lifecycle declares pause support (docker yes, uv no). */
    supportsPause: boolean;
    /** Docker container(s) named in ``install_state.json`` no longer
     *  exist on the host (operator ran ``docker rm`` outside Magellon).
     *  Disables Start/Restart — both would 500. Operator should
     *  Uninstall to clear the row. */
    containerMissing?: boolean;
    /** Any mutation in flight — disable every button to prevent
     * double-clicks. */
    busy: boolean;
}

export interface ProcessControlsDisabled {
    start: boolean;
    pause: boolean;
    stop: boolean;
    restart: boolean;
}

export const processControlsDisabled = (
    inputs: ProcessControlsInputs,
): ProcessControlsDisabled => {
    const { liveOnBus, supervisorRunning, isPaused, supportsPause, containerMissing, busy } =
        inputs;
    return {
        // Start: disabled when already announcing — would race the
        // existing instance for the port + queue. Also disabled when
        // the docker container is gone (Start would 500 with "No such
        // container"); operator must Uninstall first.
        start: busy || liveOnBus || !!containerMissing,
        // Pause: needs docker backend; if not paused, need something
        // running (supervisor OR bus-only) to pause. Missing container
        // can't be paused either.
        pause:
            busy ||
            !supportsPause ||
            !!containerMissing ||
            (!isPaused && !supervisorRunning && !liveOnBus),
        // Stop: we can only stop processes WE started (supervisor
        // tracks). A bus-only liveness signal means a dev plugin
        // launched elsewhere — operator must stop it where they
        // started it.
        stop: busy || !supervisorRunning || !!containerMissing,
        // Restart: if liveOnBus but no supervisor, restart can't
        // help (we can't kill the process we don't track). Otherwise
        // restart is acceptable — stop+start or plain start. Missing
        // container can't be restarted.
        restart: busy || !!containerMissing || (liveOnBus && !supervisorRunning),
    };
};
