/** Sparkline rendering. Port of sparklines.js. Returns data for Vue to render. */

export interface SparklineSeries {
  label: string
  points: string
  empty: boolean
}

function sparkPoints(
  arr: number[],
  minVal?: number,
  maxVal?: number
): string {
  if (arr.length === 0) return ''
  const m = minVal ?? Math.min(...arr)
  const M = maxVal ?? Math.max(...arr)
  const range = M - m || 1
  const w = 140
  const h = 32
  return arr
    .map((v, i) => {
      const x = (i / (arr.length - 1 || 1)) * w
      const y = h - ((v - m) / range) * h
      return x + ',' + y
    })
    .join(' ')
}

export function renderTrends(
  voltage: number[],
  relAlt: number[],
  groundspeed: number[],
  heartbeat: number[]
): SparklineSeries[] {
  const series: [string, number[], number?, number?][] = [
    ['Voltage (V)', voltage, 0, 20],
    ['Alt (m)', relAlt, 0],
    ['Groundspeed (m/s)', groundspeed, 0],
    ['Heartbeat age (s)', heartbeat, 0],
  ]
  return series.map(([label, arr, minV, maxV]) => {
    const pts = sparkPoints(arr, minV, maxV)
    return {
      label,
      points: pts,
      empty: !pts,
    }
  })
}
