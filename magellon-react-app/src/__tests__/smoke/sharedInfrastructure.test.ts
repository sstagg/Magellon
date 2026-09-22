import axios from 'axios';
import { describe, expect, it, beforeEach } from 'vitest';

import { ApiError, getApiErrorMessage, toApiError } from '../../shared/api/errors';
import { clearAuthStorage, getAccessToken, setAccessToken } from '../../shared/auth/tokenStore';

describe('shared API error normalization', () => {
  it('preserves the backend error code and details', () => {
    const error = new axios.AxiosError('Request failed', undefined, undefined, undefined, {
      config: { headers: new axios.AxiosHeaders() },
      data: { code: 'PLUGIN_UNAVAILABLE', message: 'Plugin is offline', details: { plugin: 'demo' } },
      headers: {},
      status: 503,
      statusText: 'Service Unavailable',
    });

    const normalized = toApiError(error);
    expect(normalized).toBeInstanceOf(ApiError);
    expect(normalized.code).toBe('PLUGIN_UNAVAILABLE');
    expect(normalized.details).toEqual({ plugin: 'demo' });
    expect(getApiErrorMessage(error)).toBe('Plugin is offline');
  });

  it('returns a stable fallback for unknown thrown values', () => {
    expect(getApiErrorMessage(null, 'Try again later')).toBe('An unexpected error occurred');
  });
});

describe('auth token store', () => {
  beforeEach(() => localStorage.clear());

  it('reads and writes the access token through one boundary', () => {
    expect(getAccessToken()).toBeNull();
    setAccessToken('token-1');
    expect(getAccessToken()).toBe('token-1');
  });

  it('clears current and legacy auth keys together', () => {
    for (const key of ['access_token', 'currentUser', 'currentUserId', 'user']) {
      localStorage.setItem(key, 'value');
    }
    clearAuthStorage();
    expect(localStorage.length).toBe(0);
  });
});

