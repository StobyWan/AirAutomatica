/**
 * Shared sparkline rendering for dashboard and session detail.
 */
(function (global) {
  'use strict';

  function sparkPoints(arr, minVal, maxVal) {
    if (arr.length === 0) return '';
    const m = minVal ?? Math.min(...arr);
    const M = maxVal ?? Math.max(...arr);
    const range = M - m || 1;
    const w = 140;
    const h = 32;
    return arr
      .map((v, i) => {
        const x = (i / (arr.length - 1 || 1)) * w;
        const y = h - ((v - m) / range) * h;
        return x + ',' + y;
      })
      .join(' ');
  }

  function renderTrends(voltage, relAlt, groundspeed, heartbeat) {
    const series = [
      ['Voltage (V)', voltage, 0, 20],
      ['Alt (m)', relAlt, 0],
      ['Groundspeed (m/s)', groundspeed, 0],
      ['Heartbeat age (s)', heartbeat, 0],
    ];
    return series
      .map(([label, arr, minV, maxV]) => {
        const pts = sparkPoints(arr, minV, maxV);
        return pts
          ? `<div class="flex flex-col gap-0.5">
            <span class="text-xs text-slate-500">${label}</span>
            <svg class="sparkline" viewBox="0 0 140 32" preserveAspectRatio="none">
              <polyline fill="none" stroke="#3b82f6" stroke-width="1" points="${pts}"/>
            </svg>
          </div>`
          : `<div><span class="text-xs text-slate-500">${label}</span><div class="text-slate-600 text-xs">—</div></div>`;
      })
      .join('');
  }

  global.AiraSparklines = {
    sparkPoints,
    renderTrends,
  };
})(typeof window !== 'undefined' ? window : this);
