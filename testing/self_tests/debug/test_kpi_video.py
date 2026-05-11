from __future__ import annotations

import cv2
import numpy as np

from debug.kpi_video import analyze_kpi_video


def test_kpi_video_analysis_detects_one_red_light_to_playback_event(tmp_path) -> None:
    video_path = tmp_path / "single_event.avi"
    _write_kpi_video(video_path, event_starts=[30])

    result = analyze_kpi_video(video_path)

    assert result["events"]
    event = result["events"][0]
    assert 30 <= event["start_frame"] <= 36
    assert 82 <= event["end_frame"] <= 88
    assert 46 <= event["elapsed_frames"] <= 58


def test_kpi_video_analysis_detects_multiple_repeated_events(tmp_path) -> None:
    video_path = tmp_path / "multi_event.avi"
    _write_kpi_video(video_path, event_starts=[30, 150])

    result = analyze_kpi_video(video_path)

    assert len(result["events"]) >= 2
    assert [event["start_frame"] for event in result["events"][:2]] == sorted(
        event["start_frame"] for event in result["events"][:2]
    )
    assert 30 <= result["events"][0]["start_frame"] <= 36
    assert 150 <= result["events"][1]["start_frame"] <= 156


def test_kpi_video_analysis_ignores_static_red_object(tmp_path) -> None:
    video_path = tmp_path / "static_red.avi"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 30, (320, 180))
    for _ in range(120):
        frame = _menu_frame()
        cv2.circle(frame, (250, 120), 5, (0, 0, 255), -1)
        writer.write(frame)
    writer.release()

    result = analyze_kpi_video(video_path)

    assert result["events"] == []


def _write_kpi_video(video_path, event_starts: list[int]) -> None:
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 30, (320, 180))
    total_frames = max(event_starts) + 110
    for frame_index in range(total_frames):
        frame = _menu_frame()
        for start in event_starts:
            if start <= frame_index < start + 5:
                cv2.circle(frame, (250, 120), 5, (0, 0, 255), -1)
            if start + 8 <= frame_index < start + 50:
                frame = _loading_frame()
            if frame_index >= start + 50:
                frame = _playback_frame(frame_index)
        writer.write(frame)
    writer.release()


def _menu_frame() -> np.ndarray:
    frame = np.full((180, 320, 3), (55, 75, 115), np.uint8)
    cv2.rectangle(frame, (80, 45), (240, 130), (130, 100, 70), -1)
    cv2.rectangle(frame, (110, 60), (150, 95), (210, 120, 80), -1)
    return frame


def _loading_frame() -> np.ndarray:
    frame = np.full((180, 320, 3), (30, 30, 35), np.uint8)
    cv2.circle(frame, (160, 90), 10, (90, 80, 70), -1)
    return frame


def _playback_frame(frame_index: int) -> np.ndarray:
    frame = np.full((180, 320, 3), (40, 150, 50), np.uint8)
    cv2.rectangle(frame, (20 + (frame_index % 20), 30), (260, 150), (90, 210, 70), -1)
    return frame
