"""Real-time Socket.IO dashboard updates."""

from airautomatica.realtime.publisher import DashboardPublisher
from airautomatica.realtime.socketio_app import sio, wrap_app

__all__ = ["DashboardPublisher", "sio", "wrap_app"]
