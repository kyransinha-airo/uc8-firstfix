// Thin fetch wrapper. Everything goes through /api (see vite.config.ts).
export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(API_BASE + path, init)
  } catch {
    throw new ApiError(0, 'Cannot reach the backend. Is it running on port 8008?')
  }
  const text = await res.text()
  let body: unknown = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    throw new ApiError(res.status, `The backend sent a response that isn't JSON (${res.status})`)
  }
  if (!res.ok) {
    const b = body as { error?: { message?: string }; detail?: unknown } | null
    const msg = b?.error?.message ?? b?.detail ?? `Request failed (${res.status})`
    throw new ApiError(res.status, typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return body as T
}

export const get = <T,>(path: string) => request<T>(path)
export const postJson = <T,>(path: string, body: unknown) =>
  request<T>(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
export const postForm = <T,>(path: string, form: FormData) =>
  request<T>(path, { method: 'POST', body: form })
