from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from debug.kpi_video import (
    calculate_kpi_interval,
    load_kpi_review_frame,
    mark_kpi_review_frame,
    prepare_kpi_review_session,
    video_metadata,
)


def test_kpi_review_session_loads_video_metadata_and_first_frame(tmp_path) -> None:
    video_path = tmp_path / "review.avi"
    _write_kpi_video(video_path, total_frames=120)

    session = prepare_kpi_review_session(video_path, work_root=tmp_path / "review_work")
    frame = load_kpi_review_frame(session, frame_index=0)

    assert session["schema"] == "smarttest.kpi_manual_review.v1"
    assert session["fps"] == 30
    assert session["frame_count"] == 120
    assert frame["frame_index"] == 0
    assert Path(frame["image"]).exists()
    assert frame["image_data_url"].startswith("data:image/jpeg;base64,")
    assert frame["mark"] == ""


def test_kpi_review_clamps_frame_navigation(tmp_path) -> None:
    video_path = tmp_path / "clamp.avi"
    _write_kpi_video(video_path, total_frames=10)
    session = prepare_kpi_review_session(video_path, work_root=tmp_path / "review_work")

    first = load_kpi_review_frame(session, frame_index=-20)
    last = load_kpi_review_frame(session, frame_index=50)

    assert first["frame_index"] == 0
    assert last["frame_index"] == 9


def test_kpi_review_outputs_interval_when_start_end_pair_completed(tmp_path) -> None:
    video_path = tmp_path / "interval.avi"
    _write_kpi_video(video_path, total_frames=180)
    session = prepare_kpi_review_session(video_path, work_root=tmp_path / "review_work")

    start = mark_kpi_review_frame(session, frame_index=30, marker="start")
    end = mark_kpi_review_frame(session, frame_index=90, marker="end")

    assert start["pending_start_frame"] == 30
    assert end["pending_start_frame"] == -1
    assert end["completed_event"]["start_frame"] == 30
    assert end["completed_event"]["end_frame"] == 90
    assert end["completed_event"]["elapsed_frames"] == 60
    assert end["completed_event"]["elapsed_seconds"] == 2
    assert end["events"] == [end["completed_event"]]


def test_kpi_review_records_multiple_pairs_in_order(tmp_path) -> None:
    video_path = tmp_path / "multi.avi"
    _write_kpi_video(video_path, total_frames=240)
    session = prepare_kpi_review_session(video_path, work_root=tmp_path / "review_work")

    mark_kpi_review_frame(session, frame_index=10, marker="start")
    mark_kpi_review_frame(session, frame_index=40, marker="end")
    mark_kpi_review_frame(session, frame_index=100, marker="start")
    frame = mark_kpi_review_frame(session, frame_index=145, marker="end")

    assert [event["sequence"] for event in frame["events"]] == [1, 2]
    assert [event["elapsed_frames"] for event in frame["events"]] == [30, 45]


def test_kpi_review_requires_start_before_end(tmp_path) -> None:
    video_path = tmp_path / "missing_start.avi"
    _write_kpi_video(video_path, total_frames=80)
    session = prepare_kpi_review_session(video_path, work_root=tmp_path / "review_work")

    try:
        mark_kpi_review_frame(session, frame_index=20, marker="end")
    except ValueError as exc:
        assert "start frame" in str(exc)
    else:
        raise AssertionError("Expected missing start to fail")


def test_kpi_interval_uses_frame_delta_and_fps_seconds() -> None:
    event = calculate_kpi_interval(fps=25, start_frame=10, end_frame=60)

    assert event["elapsed_frames"] == 50
    assert event["elapsed_seconds"] == 2
    assert event["elapsed_ms"] == 2000


def test_kpi_video_metadata_reports_duration(tmp_path) -> None:
    video_path = tmp_path / "metadata.avi"
    _write_kpi_video(video_path, total_frames=75)

    metadata = video_metadata(video_path)

    assert metadata["frame_count"] == 75
    assert metadata["duration_seconds"] == 2.5


def _write_kpi_video(video_path, *, total_frames: int) -> None:
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 30, (320, 180))
    for frame_index in range(total_frames):
        frame = np.full((180, 320, 3), (45, 55, 65), np.uint8)
        cv2.putText(frame, str(frame_index), (90, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (230, 230, 230), 2)
        writer.write(frame)
    writer.release()
