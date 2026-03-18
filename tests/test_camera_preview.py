"""Tests for camera preview stream (Phase 3: CSI camera index)."""

from unittest.mock import MagicMock, patch

from airautomatica.camera import CameraDescriptor
from airautomatica.services.camera_preview import stream_preview_frames


def test_preview_no_camera_index_when_selector_returns_none() -> None:
    """When CameraSelector returns None, rpicam-vid args have no -c (preserve default)."""
    mock_proc = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stdout.read.return_value = b""
    mock_proc.poll.return_value = None

    def is_recording() -> bool:
        return False

    with patch(
        "airautomatica.services.camera_preview._get_rpicam_vid",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_preview.CameraSelector"
        ) as mock_selector_cls:
            mock_selector = MagicMock()
            mock_selector.resolve.return_value = None
            mock_selector_cls.return_value = mock_selector
            with patch(
                "airautomatica.services.camera_preview.subprocess.Popen",
                return_value=mock_proc,
            ) as mock_popen:
                chunks = list(stream_preview_frames(is_recording))
    assert mock_popen.called
    args = mock_popen.call_args[0][0]
    assert "-c" not in args


def test_preview_includes_csi0_when_selector_returns_csi0() -> None:
    """When CameraSelector returns csi:0, rpicam-vid args include -c 0."""
    mock_proc = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stdout.read.return_value = b""
    mock_proc.poll.return_value = None

    desc = CameraDescriptor(
        id="csi:0",
        source_type="csi",
        display_name="CSI Camera 0",
        path=None,
    )

    def is_recording() -> bool:
        return False

    with patch(
        "airautomatica.services.camera_preview._get_rpicam_vid",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_preview.CameraSelector"
        ) as mock_selector_cls:
            mock_selector = MagicMock()
            mock_selector.resolve.return_value = desc
            mock_selector_cls.return_value = mock_selector
            with patch(
                "airautomatica.services.camera_preview.subprocess.Popen",
                return_value=mock_proc,
            ) as mock_popen:
                chunks = list(stream_preview_frames(is_recording))
    assert mock_popen.called
    args = mock_popen.call_args[0][0]
    assert "-c" in args
    idx = args.index("-c")
    assert args[idx + 1] == "0"


def test_preview_includes_csi1_when_selector_returns_csi1() -> None:
    """When CameraSelector returns csi:1, rpicam-vid args include -c 1."""
    mock_proc = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stdout.read.return_value = b""
    mock_proc.poll.return_value = None

    desc = CameraDescriptor(
        id="csi:1",
        source_type="csi",
        display_name="CSI Camera 1",
        path=None,
    )

    def is_recording() -> bool:
        return False

    with patch(
        "airautomatica.services.camera_preview._get_rpicam_vid",
        return_value="rpicam-vid",
    ):
        with patch(
            "airautomatica.services.camera_preview.CameraSelector"
        ) as mock_selector_cls:
            mock_selector = MagicMock()
            mock_selector.resolve.return_value = desc
            mock_selector_cls.return_value = mock_selector
            with patch(
                "airautomatica.services.camera_preview.subprocess.Popen",
                return_value=mock_proc,
            ) as mock_popen:
                chunks = list(stream_preview_frames(is_recording))
    assert mock_popen.called
    args = mock_popen.call_args[0][0]
    assert "-c" in args
    idx = args.index("-c")
    assert args[idx + 1] == "1"
