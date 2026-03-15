import { API_BASE } from '@/config'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly body?: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(
  path: string,
  options?: RequestInit & { body?: object }
): Promise<T> {
  const url = API_BASE ? API_BASE + path : path
  const { body, ...init } = options ?? {}
  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init.headers,
    },
    body: body ? JSON.stringify(body) : init.body,
  })
  const text = await res.text()
  if (!res.ok) {
    throw new ApiError(text || `HTTP ${res.status}`, res.status, text)
  }
  if (!text) return undefined as T
  try {
    return JSON.parse(text) as T
  } catch {
    throw new ApiError('Invalid JSON response', res.status, text)
  }
}

export async function get<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'GET' })
}

export async function post<T>(path: string, body?: object): Promise<T> {
  return request<T>(path, { method: 'POST', body })
}

export async function patch<T>(path: string, body?: object): Promise<T> {
  return request<T>(path, { method: 'PATCH', body })
}

export async function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE' })
}
