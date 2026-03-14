/**
 * Shared formatters for dashboard and session detail templates.
 * Single source of truth to avoid drift between templates.
 */
(function (global) {
  'use strict';

  const fmt = (v) => v == null || v === '' ? '<span class="na">—</span>' : String(v);
  const fmtNum = (v) => v == null || (typeof v === 'number' && isNaN(v)) ? '<span class="na">—</span>' : String(v);
  const fmtNumPrec = (v, decimals) => v == null || (typeof v === 'number' && isNaN(v)) ? '<span class="na">—</span>' : Number(v).toFixed(decimals);
  const fmtRate = (v) => v != null && typeof v === 'number' && isFinite(v) ? (v * 100).toFixed(1) + '%' : null;
  const fmtHeading = (v) => {
    if (v == null || (typeof v === 'number' && isNaN(v))) return '<span class="na">—</span>';
    const n = Number(v);
    if (n < 0 || n > 360 || !isFinite(n) || Math.abs(n) > 1e6) return '<span class="na">—</span>';
    return n.toFixed(0);
  };

  function fmtDate(s) {
    if (!s) return '—';
    try { return new Date(s).toLocaleString(); } catch { return s; }
  }

  function fmtDuration(started, ended) {
    if (!started || !ended) return '—';
    try {
      const sec = Math.round((new Date(ended) - new Date(started)) / 1000);
      if (sec < 60) return sec + ' s';
      if (sec < 3600) return Math.floor(sec / 60) + ' m';
      return Math.floor(sec / 3600) + ' h ' + Math.floor((sec % 3600) / 60) + ' m';
    } catch { return '—'; }
  }

  function formatDuration(sec) {
    if (sec == null || (typeof sec === 'number' && isNaN(sec))) return '—';
    const s = Math.round(Number(sec));
    if (s < 60) return s + ' s';
    if (s < 3600) return Math.floor(s / 60) + ' m';
    return Math.floor(s / 3600) + ' h ' + Math.floor((s % 3600) / 60) + ' m';
  }

  function fmtTs(ts) {
    return ts ? new Date(ts).toLocaleString() : '—';
  }

  function fmtTsTime(ts) {
    return ts ? new Date(ts).toLocaleTimeString() : '—';
  }

  function labelAutopilot(s) {
    const a = s.autopilot;
    if (a === 'mock' || (s.connection_mode === 'mock' && !a)) return 'Mock session';
    if (a === 'ardupilot') return 'ArduPilot';
    if (a === 'inav') return 'iNav';
    if (a === 'generic') return 'iNav/Generic';
    return 'Unknown autopilot';
  }

  function labelMode(s) {
    const m = s.connection_mode || (s.telemetry_backend === 'mock' ? 'mock' : null);
    if (m === 'mock') return 'Mock';
    if (m === 'ardupilot') return 'ArduPilot';
    if (m === 'inav') return 'iNav';
    return m || '—';
  }

  function labelSource(s) {
    if (s.connection_mode === 'mock' || s.telemetry_backend === 'mock') return 'Mock session';
    if (s.source_port) return s.source_port + (s.baud ? ' @ ' + s.baud : '');
    return 'No port';
  }

  function formatMetersOrKm(m) {
    if (m == null || (typeof m === 'number' && isNaN(m))) return '—';
    const n = Number(m);
    if (n >= 1000) return (n / 1000).toFixed(1) + ' km';
    return n.toFixed(0) + ' m';
  }

  function formatDistance(m) {
    if (m == null || !isFinite(m) || m < 0) return '—';
    if (m < 1000) return m.toFixed(0) + ' m';
    return (m / 1000).toFixed(2) + ' km';
  }

  function formatWatts(w) {
    if (w == null || (typeof w === 'number' && isNaN(w))) return '—';
    return Number(w).toFixed(1) + ' W';
  }

  function formatVolts(v) {
    if (v == null || (typeof v === 'number' && isNaN(v))) return '—';
    return Number(v).toFixed(2) + ' V';
  }

  function fmtSourceBackend(source) {
    if (source == null || source === '') return '<span class="na">—</span>';
    const s = String(source);
    const map = {
      aihat: 'AI HAT one-shot',
      ai_hat_recording: 'AI HAT recording',
      mock: 'Mission (mock)',
      ollama: 'Mission (Ollama)',
    };
    return map[s] != null ? map[s] : s;
  }

  global.AiraFormatters = {
    fmt,
    fmtNum,
    fmtNumPrec,
    fmtRate,
    fmtHeading,
    fmtDate,
    fmtDuration,
    formatDuration,
    fmtTs,
    fmtTsTime,
    fmtSourceBackend,
    labelAutopilot,
    labelMode,
    labelSource,
    formatMetersOrKm,
    formatDistance,
    formatWatts,
    formatVolts,
  };
})(typeof window !== 'undefined' ? window : this);
