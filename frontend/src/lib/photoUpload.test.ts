import { AxiosError, AxiosHeaders } from 'axios'
import { describe, expect, it, vi } from 'vitest'
import {
  OfflineUploadError,
  UPLOAD_MAX_ATTEMPTS,
  UPLOAD_RETRY_MAX_DELAY_MS,
  describeUploadFailures,
  describeUploadProgress,
  initialUploadProgress,
  isRetryableUploadError,
  uploadBatchWithRetry,
  uploadRetryDelayMs,
  uploadWithRetry,
  type UploadProgress,
} from './photoUpload'
import { ImageCompressionError } from './imageCompression'

function axiosErrorWithStatus(status?: number): AxiosError {
  const err = new AxiosError('Request failed', 'ERR_BAD_RESPONSE')
  if (status != null) {
    err.response = {
      status,
      statusText: '',
      data: {},
      headers: new AxiosHeaders(),
      config: { headers: new AxiosHeaders() },
    }
  }
  return err
}

const noSleep = () => Promise.resolve()
const online = () => false

describe('isRetryableUploadError', () => {
  it('retries network drops and timeouts (no response)', () => {
    expect(isRetryableUploadError(axiosErrorWithStatus())).toBe(true)
    expect(isRetryableUploadError(new Error('Network Error'))).toBe(true)
    expect(isRetryableUploadError(new Error('timeout of 120000ms exceeded'))).toBe(true)
  })

  it('retries 408/429 and 5xx', () => {
    for (const status of [408, 429, 500, 502, 503, 504]) {
      expect(isRetryableUploadError(axiosErrorWithStatus(status))).toBe(true)
    }
  })

  it('does not retry client errors', () => {
    for (const status of [400, 401, 403, 404, 413, 422]) {
      expect(isRetryableUploadError(axiosErrorWithStatus(status))).toBe(false)
    }
  })

  it('does not retry cancellations, compression or memory failures', () => {
    const canceled = new AxiosError('canceled', 'ERR_CANCELED')
    expect(isRetryableUploadError(canceled)).toBe(false)
    expect(isRetryableUploadError(new ImageCompressionError('too big'))).toBe(false)
    expect(isRetryableUploadError(new Error('Out of memory'))).toBe(false)
  })
})

describe('uploadRetryDelayMs', () => {
  it('backs off exponentially and caps', () => {
    expect(uploadRetryDelayMs(1, 800)).toBe(800)
    expect(uploadRetryDelayMs(2, 800)).toBe(1600)
    expect(uploadRetryDelayMs(3, 800)).toBe(3200)
    expect(uploadRetryDelayMs(10, 800)).toBe(UPLOAD_RETRY_MAX_DELAY_MS)
  })
})

describe('uploadWithRetry', () => {
  it('returns the first successful result without sleeping', async () => {
    const run = vi.fn().mockResolvedValue('ok')
    const sleep = vi.fn(noSleep)
    await expect(uploadWithRetry(run, { sleep, offline: online })).resolves.toBe('ok')
    expect(run).toHaveBeenCalledTimes(1)
    expect(sleep).not.toHaveBeenCalled()
  })

  it('retries a transient failure and then succeeds', async () => {
    const run = vi
      .fn()
      .mockRejectedValueOnce(axiosErrorWithStatus(503))
      .mockResolvedValue('ok')
    const onRetry = vi.fn()
    await expect(uploadWithRetry(run, { sleep: noSleep, offline: online, onRetry })).resolves.toBe('ok')
    expect(run).toHaveBeenCalledTimes(2)
    expect(onRetry).toHaveBeenCalledWith(1, expect.anything())
  })

  it('stops at the attempt limit and rethrows the last error', async () => {
    const run = vi.fn().mockRejectedValue(axiosErrorWithStatus(500))
    await expect(uploadWithRetry(run, { sleep: noSleep, offline: online })).rejects.toBeInstanceOf(AxiosError)
    expect(run).toHaveBeenCalledTimes(UPLOAD_MAX_ATTEMPTS)
  })

  it('honours a custom attempt budget', async () => {
    const run = vi.fn().mockRejectedValue(axiosErrorWithStatus(500))
    await expect(uploadWithRetry(run, { attempts: 5, sleep: noSleep, offline: online })).rejects.toBeTruthy()
    expect(run).toHaveBeenCalledTimes(5)
  })

  it('does not retry a permanent failure', async () => {
    const run = vi.fn().mockRejectedValue(axiosErrorWithStatus(422))
    await expect(uploadWithRetry(run, { sleep: noSleep, offline: online })).rejects.toBeTruthy()
    expect(run).toHaveBeenCalledTimes(1)
  })

  it('refuses to start while offline instead of firing requests', async () => {
    const run = vi.fn()
    await expect(uploadWithRetry(run, { sleep: noSleep, offline: () => true })).rejects.toBeInstanceOf(
      OfflineUploadError,
    )
    expect(run).not.toHaveBeenCalled()
  })

  it('stops retrying when the connection drops mid-run', async () => {
    const run = vi.fn().mockRejectedValue(axiosErrorWithStatus(503))
    let calls = 0
    const offline = () => {
      calls += 1
      return calls > 1 // online for the initial check, offline afterwards
    }
    await expect(uploadWithRetry(run, { sleep: noSleep, offline })).rejects.toBeInstanceOf(OfflineUploadError)
    expect(run).toHaveBeenCalledTimes(1)
  })

  it('waits with exponential backoff between attempts', async () => {
    const delays: number[] = []
    const run = vi.fn().mockRejectedValue(axiosErrorWithStatus(500))
    await expect(
      uploadWithRetry(run, {
        sleep: async ms => {
          delays.push(ms)
        },
        offline: online,
        baseDelayMs: 100,
      }),
    ).rejects.toBeTruthy()
    expect(delays).toEqual([100, 200])
  })
})

describe('uploadBatchWithRetry', () => {
  const items = [{ file: 'a', label: 'Front' }, { file: 'b', label: 'Back' }]

  it('reports preparing → uploading X of Y → complete', async () => {
    const phases: Array<[UploadProgress['phase'], string]> = []
    const result = await uploadBatchWithRetry(items, async () => 'ok', {
      sleep: noSleep,
      offline: online,
      onProgress: p => phases.push([p.phase, p.message]),
    })
    expect(result).toEqual({ uploaded: 2, failures: [] })
    expect(phases.map(p => p[0])).toEqual(['uploading', 'uploading', 'complete'])
    expect(phases[0][1]).toBe('Uploading photo 1 of 2…')
    expect(phases[1][1]).toBe('Uploading photo 2 of 2…')
    expect(phases[2][1]).toBe('All 2 photos uploaded.')
  })

  it('surfaces a retrying state and still completes', async () => {
    const upload = vi
      .fn()
      .mockRejectedValueOnce(axiosErrorWithStatus(503))
      .mockResolvedValue('ok')
    const messages: string[] = []
    const result = await uploadBatchWithRetry([{ file: 'a' }], upload, {
      sleep: noSleep,
      offline: online,
      onProgress: p => messages.push(p.message),
    })
    expect(result.uploaded).toBe(1)
    expect(messages).toContain('Connection problem — retrying photo 1 of 1 (attempt 2)…')
  })

  it('keeps going after one photo fails permanently', async () => {
    const upload = vi
      .fn()
      .mockRejectedValueOnce(axiosErrorWithStatus(422))
      .mockResolvedValue('ok')
    const result = await uploadBatchWithRetry(items, upload, { sleep: noSleep, offline: online })
    expect(result.uploaded).toBe(1)
    expect(result.failures).toHaveLength(1)
    expect(result.failures[0].item.label).toBe('Front')
  })

  it('marks the remaining photos failed once offline rather than retrying each', async () => {
    const upload = vi.fn().mockRejectedValue(new Error('Network Error'))
    const result = await uploadBatchWithRetry(items, upload, {
      sleep: noSleep,
      offline: () => true,
      onProgress: () => {},
    })
    expect(upload).not.toHaveBeenCalled()
    expect(result.uploaded).toBe(0)
    expect(result.failures).toHaveLength(2)
    expect(describeUploadFailures(result.failures)).toContain('you went offline')
  })

  it('handles an empty batch', async () => {
    const progress: UploadProgress[] = []
    const result = await uploadBatchWithRetry([], async () => 'ok', { onProgress: p => progress.push(p) })
    expect(result).toEqual({ uploaded: 0, failures: [] })
    expect(progress[0].phase).toBe('complete')
  })
})

describe('describeUploadProgress', () => {
  it('describes each phase for a live region', () => {
    const base = initialUploadProgress(3)
    expect(describeUploadProgress({ ...base, phase: 'preparing' })).toBe('Preparing 3 photos…')
    expect(describeUploadProgress({ ...base, phase: 'uploading', completed: 1 })).toBe('Uploading photo 2 of 3…')
    expect(describeUploadProgress({ ...base, phase: 'complete', completed: 3 })).toBe('All 3 photos uploaded.')
    expect(describeUploadProgress({ ...base, phase: 'complete', completed: 2, failed: 1 })).toBe(
      '2 of 3 photos uploaded — 1 failed.',
    )
    expect(describeUploadProgress({ ...base, phase: 'failed', failed: 3 })).toBe(
      'Photo upload failed — 0 of 3 uploaded.',
    )
  })
})

describe('describeUploadFailures', () => {
  it('returns null when nothing failed', () => {
    expect(describeUploadFailures([])).toBeNull()
  })

  it('tells the user the ticket exists and photos can be added later', () => {
    const msg = describeUploadFailures([{ item: { file: 'a', label: 'Front' }, error: axiosErrorWithStatus(500) }])
    expect(msg).toContain('Front')
    expect(msg).toContain('add the photos from the job page')
  })
})
