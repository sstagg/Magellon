/**
 * Matrix test for the ProcessControls button-gating logic.
 *
 * Five boolean inputs × four buttons = 80 cells. We don't test every
 * one — instead we pin the rows that operators care most about:
 *
 *  - cold plugin (nothing running) → Start enabled, others disabled
 *  - supervisor-managed running plugin → Stop/Restart/Pause enabled,
 *    Start disabled
 *  - bus-only running plugin (dev launched outside supervisor) →
 *    every button disabled, operator must stop where they started
 *  - paused docker plugin → Pause flips to Unpause (button stays
 *    enabled), others contextual
 *  - uv plugin → Pause greyed regardless of state
 *  - busy (mutation in flight) → every button disabled
 */
import { describe, it, expect } from 'vitest';
import {
    processControlsDisabled,
    type ProcessControlsInputs,
} from '../../features/plugin-runner/ui/processControlsState.ts';


const base = (): ProcessControlsInputs => ({
    liveOnBus: false,
    supervisorRunning: false,
    isPaused: false,
    supportsPause: true,
    busy: false,
});


describe('processControlsDisabled', () => {
    it('cold plugin: only Start is enabled', () => {
        const d = processControlsDisabled(base());
        expect(d.start).toBe(false); // enabled
        expect(d.pause).toBe(true);  // nothing running to pause
        expect(d.stop).toBe(true);   // nothing to stop
        expect(d.restart).toBe(false); // restart acts as start
    });

    it('supervisor-managed running plugin: Stop/Pause/Restart enabled, Start disabled', () => {
        const d = processControlsDisabled({
            ...base(),
            liveOnBus: true,
            supervisorRunning: true,
        });
        expect(d.start).toBe(true);  // already running
        expect(d.pause).toBe(false);
        expect(d.stop).toBe(false);
        expect(d.restart).toBe(false);
    });

    it('bus-only running plugin (no supervisor track): all disabled except Restart-as-warning', () => {
        // The dev plugin was launched outside the supervisor.
        // Start is disabled (would race), Stop is disabled (no PID
        // to kill), Restart is disabled (can't stop+start without PID),
        // Pause is enabled (docker can pause anyone's container).
        const d = processControlsDisabled({
            ...base(),
            liveOnBus: true,
            supervisorRunning: false,
        });
        expect(d.start).toBe(true);
        expect(d.pause).toBe(false); // docker can pause by name
        expect(d.stop).toBe(true);
        expect(d.restart).toBe(true);
    });

    it('paused docker plugin: Pause-as-Unpause enabled even without supervisor', () => {
        // Paused implies the container exists; unpause should work
        // regardless of supervisor tracking.
        const d = processControlsDisabled({
            ...base(),
            isPaused: true,
            supervisorRunning: false,
            liveOnBus: false,
        });
        expect(d.pause).toBe(false);
    });

    it('uv plugin (supports_pause=false): Pause greyed regardless of state', () => {
        for (const liveOnBus of [false, true]) {
            for (const supervisorRunning of [false, true]) {
                const d = processControlsDisabled({
                    ...base(),
                    supportsPause: false,
                    liveOnBus,
                    supervisorRunning,
                });
                expect(d.pause).toBe(true);
            }
        }
    });

    it('busy state disables every button', () => {
        const d = processControlsDisabled({
            ...base(),
            busy: true,
            liveOnBus: false,
            supervisorRunning: false,
        });
        expect(d.start).toBe(true);
        expect(d.pause).toBe(true);
        expect(d.stop).toBe(true);
        expect(d.restart).toBe(true);
    });

    it('busy overrides every otherwise-enabled button', () => {
        // Even a healthy "stop me please" state respects busy.
        const d = processControlsDisabled({
            liveOnBus: true,
            supervisorRunning: true,
            isPaused: false,
            supportsPause: true,
            busy: true,
        });
        expect(d.start).toBe(true);
        expect(d.pause).toBe(true);
        expect(d.stop).toBe(true);
        expect(d.restart).toBe(true);
    });

    it('Start disabled whenever liveOnBus, regardless of supervisor', () => {
        for (const supervisorRunning of [false, true]) {
            const d = processControlsDisabled({
                ...base(),
                liveOnBus: true,
                supervisorRunning,
            });
            expect(d.start).toBe(true);
        }
    });

    it('Stop only fires when supervisor tracks the process', () => {
        const supervised = processControlsDisabled({
            ...base(),
            supervisorRunning: true,
            liveOnBus: true,
        });
        const unsupervised = processControlsDisabled({
            ...base(),
            supervisorRunning: false,
            liveOnBus: true,
        });
        expect(supervised.stop).toBe(false);
        expect(unsupervised.stop).toBe(true);
    });
});
