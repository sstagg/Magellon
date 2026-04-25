/**
 * Smoke test for /dev/topaz-test.
 *
 * Mirror of PtolemyTestPage.test.tsx — mocks getAxiosClient + useSocket
 * so the page can mount in isolation. Verifies the form gates dispatch,
 * routes to the right URL per mode, and surfaces errors.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

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

import { TopazTestPage } from '../../pages/dev/TopazTestPage.tsx';

beforeEach(() => {
    postMock.mockReset();
});

describe('TopazTestPage', () => {
    it('renders the dispatch form with both modes available', () => {
        render(<TopazTestPage />);
        expect(screen.getByText(/Topaz plugin test bed/i)).toBeTruthy();
        expect(screen.getByRole('button', { name: /Dispatch TopazPick/i })).toBeTruthy();
    });

    it('disables Dispatch until image_path is filled', () => {
        render(<TopazTestPage />);
        const btn = screen.getByRole('button', { name: /Dispatch TopazPick/i }) as HTMLButtonElement;
        expect(btn.disabled).toBe(true);

        fireEvent.change(screen.getByLabelText(/image_path/i), {
            target: { value: '/data/expo.mrc' },
        });
        expect(btn.disabled).toBe(false);
    });

    it('posts to /image/topaz/pick/dispatch for pick mode', async () => {
        postMock.mockResolvedValueOnce({
            data: {
                job_id: '11111111-1111-1111-1111-111111111111',
                task_id: '22222222-2222-2222-2222-222222222222',
                queue_name: 'topaz_pick_tasks_queue',
                image_path: '/data/expo.mrc',
                category: 'TopazParticlePicking',
                status: 'dispatched',
            },
        });

        render(<TopazTestPage />);
        fireEvent.change(screen.getByLabelText(/image_path/i), {
            target: { value: '/data/expo.mrc' },
        });
        fireEvent.click(screen.getByRole('button', { name: /Dispatch TopazPick/i }));

        await waitFor(() => {
            expect(postMock).toHaveBeenCalledWith('/image/topaz/pick/dispatch', {
                image_path: '/data/expo.mrc',
            });
        });
    });

    it('surfaces a server error in an Alert', async () => {
        postMock.mockRejectedValueOnce({
            response: { data: { detail: 'topaz plugin offline' } },
        });

        render(<TopazTestPage />);
        fireEvent.change(screen.getByLabelText(/image_path/i), {
            target: { value: '/data/expo.mrc' },
        });
        fireEvent.click(screen.getByRole('button', { name: /Dispatch TopazPick/i }));

        await waitFor(() => {
            expect(screen.getByText(/topaz plugin offline/i)).toBeTruthy();
        });
    });
});
