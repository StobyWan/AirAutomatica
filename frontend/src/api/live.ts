import { post } from './client'

export function setLiveHome(options: {
  lat?: number
  lon?: number
  use_current?: boolean
  clear?: boolean
}): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>('/live/home', options)
}
