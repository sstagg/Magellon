/**
 * Smoke test for the /dev/fft-test page.
 *
 * Mocks getAxiosClient so we don't hit a real CoreService and useSocket
 * so StepEventsPanel doesn't try to open a Socket.IO connection. The
 * page is the dev-only test bed for the FFT plugin's RMQ → Socket.IO
 * roundtrip — this verifies it mounts, dispatches, and renders the
 * subscribed events panel after a successful response.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// vi.mock is hoisted above this file's top-level declarations, so the
// mock factory can't close over a regular ``const``. Use vi.hoisted to
// expose the mock to both vi.mock and the test body.
const { postMock } = vi.hoisted(() => ({ postMock: vi.fn() }));

vi.mock('../../shared/api/AxiosClient.ts', () => ({
    default: () => ({ post: postMock }),
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

import { FftTestPage } from '../../pages/dev/FftTestPage.tsx';

beforeEach(() => {
    postMock.mockReset();
});

describe('FftTestPage', () => {
    it('renders the dispatch form', () => {
        render(<FftTestPage />);
        expect(screen.getByText(/FFT plugin test bed/i)).toBeTruthy();
        expect(screen.getByRole('button', { name: /Dispatch FFT/i })).toBeTruthy();
    });

    it('disables Dispatch until image_path is filled', () => {
        render(<FftTestPage />);
        const btn = screen.getByRole('button', { name: /Dispatch FFT/i }) as HTMLButtonElement;
        expect(btn.disabled).toBe(true);

        fireEvent.change(screen.getByLabelText(/image_path/i), {
            target: { value: '/data/sample.mrc' },
        });
        expect(btn.disabled).toBe(false);
    });

    it('posts to /fft/dispatch and shows the StepEventsPanel after success', async () => {
        postMock.mockResolvedValueOnce({
            data: {
                job_id: '11111111-1111-1111-1111-111111111111',
                task_id: '22222222-2222-2222-2222-222222222222',
                queue_name: 'fft_tasks_queue',
                image_path: '/data/sample.mrc',
                target_path: '/data/sample_FFT.png',
                status: 'dispatched',
            },
        });

        render(<FftTestPage />);
        fireEvent.change(screen.getByLabelText(/image_path/i), {
            target: { value: '/data/sample.mrc' },
        });
        fireEvent.click(screen.getByRole('button', { name: /Dispatch FFT/i }));

        await waitFor(() => {
            expect(postMock).toHaveBeenCalledWith('/image/fft/dispatch', {
                image_path: '/data/sample.mrc',
            });
        });

        await waitFor(() => {
            expect(screen.getByTestId('step-events-panel')).toBeTruthy();
        });
    });

    it('surfaces a server error in an Alert', async () => {
        postMock.mockRejectedValueOnce({
            response: { data: { detail: 'plugin offline' } },
        });

        render(<FftTestPage />);
        fireEvent.change(screen.getByLabelText(/image_path/i), {
            target: { value: '/data/sample.mrc' },
        });
        fireEvent.click(screen.getByRole('button', { name: /Dispatch FFT/i }));

        await waitFor(() => {
            expect(screen.getByText(/plugin offline/i)).toBeTruthy();
        });
    });
});
