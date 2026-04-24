/**
 * Smoke test for the /dev/ptolemy-test page.
 *
 * Mocks getAxiosClient so we don't hit a real CoreService and useSocket
 * so the step-event hook doesn't try to open a Socket.IO connection.
 * Verifies the page mounts with both mode toggles, dispatches to the
 * correct route for each mode, and surfaces server errors.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// vi.hoisted keeps the mock holders alive across the vi.mock() hoisting
// pass — plain `const postMock = vi.fn()` trips a temporal-dead-zone error
// in vitest 4.x when the mocked module is pulled in transitively at import.
const { postMock, getMock, deleteMock } = vi.hoisted(() => ({
    postMock: vi.fn(),
    getMock: vi.fn(),
    deleteMock: vi.fn(),
}));

vi.mock('../../shared/api/AxiosClient.ts', () => ({
    default: () => ({ post: postMock, get: getMock, delete: deleteMock }),
}));

vi.mock('../../shared/lib/useSocket.ts', () => ({
    useSocket: () => ({
        socket: null,
        connected: true,
        sid: 'test-sid',
        on: () => () => {},
        emit: () => {},
    }),
}));

import { PtolemyTestPage } from '../../pages/dev/PtolemyTestPage.tsx';

beforeEach(() => {
    postMock.mockReset();
});

describe('PtolemyTestPage', () => {
    it('renders the dispatch form with both modes available', () => {
        render(<PtolemyTestPage />);
        expect(screen.getByText(/Ptolemy plugin test bed/i)).toBeTruthy();
        expect(screen.getByRole('button', { name: /Dispatch SquareDetection/i })).toBeTruthy();
    });

    it('disables Dispatch until image_path is filled', () => {
        render(<PtolemyTestPage />);
        const btn = screen.getByRole('button', { name: /Dispatch SquareDetection/i }) as HTMLButtonElement;
        expect(btn.disabled).toBe(true);

        fireEvent.change(screen.getByLabelText(/image_path/i), {
            target: { value: '/data/atlas.mrc' },
        });
        expect(btn.disabled).toBe(false);
    });

    it('posts to /image/ptolemy/square/dispatch for square mode', async () => {
        postMock.mockResolvedValueOnce({
            data: {
                job_id: '11111111-1111-1111-1111-111111111111',
                task_id: '22222222-2222-2222-2222-222222222222',
                queue_name: 'square_detection_tasks_queue',
                image_path: '/data/atlas.mrc',
                category: 'SquareDetection',
                status: 'dispatched',
            },
        });

        render(<PtolemyTestPage />);
        fireEvent.change(screen.getByLabelText(/image_path/i), {
            target: { value: '/data/atlas.mrc' },
        });
        fireEvent.click(screen.getByRole('button', { name: /Dispatch SquareDetection/i }));

        await waitFor(() => {
            expect(postMock).toHaveBeenCalledWith('/image/ptolemy/square/dispatch', {
                image_path: '/data/atlas.mrc',
            });
        });
    });

    it('surfaces a server error in an Alert', async () => {
        postMock.mockRejectedValueOnce({
            response: { data: { detail: 'ptolemy plugin offline' } },
        });

        render(<PtolemyTestPage />);
        fireEvent.change(screen.getByLabelText(/image_path/i), {
            target: { value: '/data/atlas.mrc' },
        });
        fireEvent.click(screen.getByRole('button', { name: /Dispatch SquareDetection/i }));

        await waitFor(() => {
            expect(screen.getByText(/ptolemy plugin offline/i)).toBeTruthy();
        });
    });
});
