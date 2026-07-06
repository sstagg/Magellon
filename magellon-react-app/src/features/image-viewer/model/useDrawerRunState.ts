import { useEffect, useRef, useState } from 'react';
import type { DrawerState } from './particleSettingsTypes.ts';

interface UseDrawerRunStateArgs {
    isRunning: boolean;
    resultCount: number | null;
    ippName?: string;
}

/** Drawer-state machine synced against the external `isRunning` flag. */
export function useDrawerRunState({ isRunning, resultCount, ippName }: UseDrawerRunStateArgs) {
    const [drawerState, setDrawerState] = useState<DrawerState>('configure');
    // Remember the ippName we dispatched with so we can detect when the
    // RMQ poll lands a matching IPP in the store and flip drawerState to
    // 'results' (mirrors what the sync onRun path does).
    const [dispatchedIppName, setDispatchedIppName] = useState<string | null>(null);

    // Sync external running state. We must distinguish "just entered
    // dispatched" (isRunning still false because dispatchPick hasn't
    // toggled it yet) from "dispatched and now done" (isRunning went
    // true→false). The dispatch flow only fires the results/configure
    // transition on the second of those — gated by a wasRunning ref.
    const wasRunningRef = useRef(false);
    useEffect(() => {
        const wasRunning = wasRunningRef.current;
        wasRunningRef.current = isRunning;
        if (isRunning && drawerState !== 'running' && drawerState !== 'dispatched') {
            setDrawerState('running');
            return;
        }
        if (!isRunning && drawerState === 'running') {
            setDrawerState(resultCount !== null ? 'results' : 'configure');
            return;
        }
        if (!isRunning && wasRunning && drawerState === 'dispatched') {
            if (dispatchedIppName && ippName === dispatchedIppName) {
                setDrawerState('results');
                setDispatchedIppName(null);
            } else {
                setDrawerState('configure');
                setDispatchedIppName(null);
            }
        }
    }, [isRunning, resultCount, ippName, dispatchedIppName]); // eslint-disable-line react-hooks/exhaustive-deps

    return { drawerState, setDrawerState, dispatchedIppName, setDispatchedIppName };
}
