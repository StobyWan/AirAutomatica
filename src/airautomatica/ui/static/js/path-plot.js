/**
 * Shared path plot rendering for dashboard and session detail.
 * Renders lat/lon path with optional current position, home marker, and detection markers.
 */
(function (global) {
  'use strict';

  /**
   * Render path plot SVG.
   * @param {Array<{lat: number, lon: number}>} path - Path points
   * @param {{lat: number, lon: number}|null} current - Current position (green dot)
   * @param {Array<{lat: number, lon: number}>} detections - Detection markers (red dots)
   * @param {{lat: number, lon: number}|null} home - Home marker (amber dot), optional
   * @param {{width?: number, height?: number, currentStroke?: string}} opts - Dimensions and styling
   */
  function renderPathPlot(path, current, detections, home, opts) {
    opts = opts || {};
    const w = opts.width ?? 200;
    const h = opts.height ?? 180;
    const margin = 8;
    const plotW = w - 2 * margin;
    const plotH = h - 2 * margin;

    const points = (path || []).map((p) => ({ lat: p.lat, lon: p.lon }));
    if (current && current.lat != null && current.lon != null) {
      points.push({ lat: current.lat, lon: current.lon });
    }
    if (home && home.lat != null && home.lon != null) {
      points.push({ lat: home.lat, lon: home.lon });
    }
    if (points.length === 0) return '';

    const lats = points.map((p) => p.lat).filter((x) => x != null);
    const lons = points.map((p) => p.lon).filter((x) => x != null);
    if (lats.length === 0 || lons.length === 0) return '';

    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);
    const padLat = (maxLat - minLat) * 0.1 || 0.0001;
    const padLon = (maxLon - minLon) * 0.1 || 0.0001;

    const toX = (lon) =>
      margin +
      ((lon - (minLon - padLon)) / (maxLon + padLon - (minLon - padLon))) *
        plotW;
    const toY = (lat) =>
      h -
      margin -
      ((lat - (minLat - padLat)) / (maxLat + padLat - (minLat - padLat))) *
        plotH;

    const pathPoints = (path || []).filter(
      (p) => p.lat != null && p.lon != null
    );
    const pathD = pathPoints
      .map((p, i) => (i === 0 ? 'M' : 'L') + toX(p.lon) + ' ' + toY(p.lat))
      .join(' ');

    let svg =
      pathD &&
      `<path d="${pathD}" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>`;

    pathPoints.forEach((p, i) => {
      if (i === pathPoints.length - 1 && current) return;
      svg += `<circle cx="${toX(p.lon)}" cy="${toY(p.lat)}" r="2" fill="#3b82f6"/>`;
    });
    if (home && home.lat != null && home.lon != null) {
      svg += `<circle cx="${toX(home.lon)}" cy="${toY(home.lat)}" r="5" fill="#f59e0b" stroke="#0f172a" stroke-width="1"/>`;
    }
    (detections || [])
      .filter((d) => d.lat != null && d.lon != null)
      .forEach((d) => {
        svg += `<circle cx="${toX(d.lon)}" cy="${toY(d.lat)}" r="3" fill="#ef4444" opacity="0.8"/>`;
      });
    const currentStroke = opts.currentStroke ?? '#0f172a';
    if (current && current.lat != null && current.lon != null) {
      svg += `<circle cx="${toX(current.lon)}" cy="${toY(current.lat)}" r="4" fill="#22c55e" stroke="${currentStroke}" stroke-width="1"/>`;
    }
    return svg;
  }

  global.AiraPathPlot = {
    renderPathPlot,
  };
})(typeof window !== 'undefined' ? window : this);
