/**
 * Wire shape of the CloudEvents-flavoured payload emitted by
 * CoreService on Socket.IO event name `step_event`.
 *
 * Kept in sync with `core.socketio_server.emit_step_event` in
 * CoreService and with `magellon_sdk.events` CloudEvents types.
 * Treat this as the contract boundary — don't fork.
 */

export type StepEventType =
    | 'magellon.step.started'
    | 'magellon.step.progress'
    | 'magellon.step.completed'
    | 'magellon.step.failed';

/** Base fields every step-event data dict carries. */
export interface StepEventDataBase {
    job_id: string;
    task_id?: string | null;
    step: string;
}

/** Progress-specific fields. Percent is 0..100. */
export interface StepProgressData extends StepEventDataBase {
    percent?: number;
    message?: string | null;
}

/** Completed-specific fields. */
export interface StepCompletedData extends StepEventDataBase {
    output_files?: string[] | null;
}

/** Failed-specific fields. */
export interface StepFailedData extends StepEventDataBase {
    error: string;
}

export type StepEventData =
    | StepEventDataBase
    | StepProgressData
    | StepCompletedData
    | StepFailedData;

export interface StepEvent {
    /** CloudEvents id — stable per logical event, useful for dedup. */
    id: string;
    type: StepEventType;
    source: string;
    subject: string;
    /** ISO-8601. */
    time: string | null;
    data: StepEventData;
}

export const STEP_EVENT_NAME = 'step_event';
export const JOIN_JOB_ROOM = 'join_job_room';
export const LEAVE_JOB_ROOM = 'leave_job_room';
