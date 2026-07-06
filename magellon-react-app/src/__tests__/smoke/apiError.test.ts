import axios from 'axios'
import { describe, expect, it } from 'vitest'

import { apiErrorMessage, toApiError } from '../../shared/api/apiError.ts'

describe('apiErrorMessage', () => {
  it('uses FastAPI detail text from Axios errors', () => {
    const error = new axios.AxiosError('Request failed', undefined, undefined, undefined, {
      config: { headers: new axios.AxiosHeaders() },
      data: { detail: 'plugin offline' },
      headers: {},
      status: 503,
      statusText: 'Service Unavailable',
    })

    expect(apiErrorMessage(error, 'fallback')).toBe('plugin offline')
    expect(toApiError(error).status).toBe(503)
  })

  it('uses FastAPI detail text from response-shaped errors', () => {
    const error = {
      response: {
        status: 503,
        data: { detail: 'ptolemy plugin offline' },
      },
    }

    expect(apiErrorMessage(error, 'fallback')).toBe('ptolemy plugin offline')
  })
})
