from __future__ import annotations

import argparse
import csv
from collections import defaultdict, deque
from pathlib import Path

import cv2
from ultralytics import YOLO


DEFAULT_SOURCE = Path(
    "/mnt/e/password_data/dataset/9328_99178133037742335_71136/00010001-w-play.mp4"
)
DEFAULT_MODEL = "yolo26n.pt"
DEFAULT_OUTPUT = Path("runs/three_ball_yolo26n_tracking")

# COCO pretrained YOLO에서 sports ball class id는 32입니다.
# 직접 학습한 당구공 모델이면 --classes all 또는 해당 class id로 바꾸세요.
DEFAULT_CLASSES = "32"
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}
TRAIL_COLORS = [
    (0, 0, 255),      # red
    (0, 255, 255),    # yellow
    (255, 255, 255),  # white
    (255, 128, 0),
    (255, 0, 255),
    (0, 255, 0),
]


def resolve_model_path(model: str) -> str:
    model_path = Path(model)
    candidates = [model_path]

    if not model_path.is_absolute():
        script_dir = Path(__file__).resolve().parent
        candidates.append(script_dir / model)
        candidates.append(Path.cwd() / model)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    raise SystemExit(
        f"Model file not found: {model}\n"
        "프로젝트 폴더에 yolo26n.pt를 두거나 --model /path/to/yolo26n.pt 로 지정하세요."
    )


def iter_videos(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    return sorted(
        path
        for path in source.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )


def safe_output_stem(video: Path) -> str:
    return f"{video.parent.name}__{video.stem}"


def parse_classes(value: str | None) -> list[int] | None:
    if value is None or value == "":
        return None
    if value.lower() in {"none", "all"}:
        return None
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def track_color(track_id: int | None, index: int) -> tuple[int, int, int]:
    if track_id is None:
        return TRAIL_COLORS[index % len(TRAIL_COLORS)]
    return TRAIL_COLORS[int(track_id) % len(TRAIL_COLORS)]


def draw_trails(frame, trails: dict[int, deque[tuple[int, int]]], thickness: int) -> None:
    for track_id, points_deque in trails.items():
        points = list(points_deque)
        if len(points) < 2:
            continue
        color = track_color(track_id, 0)
        for idx in range(1, len(points)):
            alpha = idx / max(1, len(points) - 1)
            line_thickness = max(1, int(thickness * alpha))
            cv2.line(frame, points[idx - 1], points[idx], color, line_thickness, cv2.LINE_AA)


def draw_ball_centers(frame, boxes, names, trails: dict[int, deque[tuple[int, int]]], trail_length: int) -> None:
    if boxes is None or len(boxes) == 0:
        return

    xywh = boxes.xywh.cpu().tolist()
    class_ids = boxes.cls.cpu().tolist() if boxes.cls is not None else []
    track_ids = boxes.id.cpu().tolist() if getattr(boxes, "id", None) is not None else [None] * len(xywh)

    for idx, (cx, cy, box_w, box_h) in enumerate(xywh):
        class_id = int(class_ids[idx]) if idx < len(class_ids) else -1
        class_name = names.get(class_id, str(class_id))
        raw_track_id = track_ids[idx] if idx < len(track_ids) else None
        track_id = None if raw_track_id is None else int(raw_track_id)
        color = track_color(track_id, idx)

        center = (int(cx), int(cy))
        if track_id is not None:
            trails[track_id].append(center)
            while len(trails[track_id]) > trail_length:
                trails[track_id].popleft()

        radius = max(3, int(max(box_w, box_h) / 2))
        label = class_name if track_id is None else f"{class_name} #{track_id}"
        cv2.circle(frame, center, radius, color, 2)
        cv2.circle(frame, center, 3, (0, 0, 255), -1)
        cv2.putText(
            frame,
            label,
            (center[0] + 6, center[1] - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )


def track_video(
    model: YOLO,
    video_path: Path,
    output_dir: Path,
    conf: float,
    iou: float,
    imgsz: int,
    device: str | None,
    tracker: str,
    classes: list[int] | None,
    trail_length: int,
    trail_thickness: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    stem = safe_output_stem(video_path)
    annotated_path = output_dir / f"{stem}_yolo26n_three_balls_tracked.mp4"
    csv_path = output_dir / f"{stem}_yolo26n_three_balls_tracks.csv"

    writer = cv2.VideoWriter(
        str(annotated_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    detections = 0
    trails: dict[int, deque[tuple[int, int]]] = defaultdict(deque)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(
            [
                "frame",
                "track_id",
                "class_id",
                "class_name",
                "confidence",
                "x1",
                "y1",
                "x2",
                "y2",
                "cx",
                "cy",
                "width",
                "height",
            ]
        )

        frame_idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            results = model.track(
                frame,
                persist=True,
                conf=conf,
                iou=iou,
                imgsz=imgsz,
                device=device,
                tracker=tracker,
                classes=classes,
                verbose=False,
            )
            result = results[0]

            annotated = result.plot()
            draw_ball_centers(annotated, result.boxes, model.names, trails, trail_length)
            draw_trails(annotated, trails, trail_thickness)
            writer.write(annotated)

            if result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes
                xyxy = boxes.xyxy.cpu().tolist()
                xywh = boxes.xywh.cpu().tolist()
                confs = boxes.conf.cpu().tolist() if boxes.conf is not None else []
                class_ids = boxes.cls.cpu().tolist() if boxes.cls is not None else []
                track_ids = (
                    boxes.id.cpu().tolist()
                    if getattr(boxes, "id", None) is not None
                    else [None] * len(xyxy)
                )

                detections += len(xyxy)

                for idx, coords in enumerate(xyxy):
                    class_id = int(class_ids[idx]) if idx < len(class_ids) else -1
                    class_name = model.names.get(class_id, str(class_id))
                    confidence = confs[idx] if idx < len(confs) else ""
                    raw_track_id = track_ids[idx] if idx < len(track_ids) else None
                    track_id = "" if raw_track_id is None else int(raw_track_id)
                    x1, y1, x2, y2 = coords
                    cx, cy, box_w, box_h = xywh[idx]
                    csv_writer.writerow(
                        [
                            frame_idx,
                            track_id,
                            class_id,
                            class_name,
                            confidence,
                            x1,
                            y1,
                            x2,
                            y2,
                            cx,
                            cy,
                            box_w,
                            box_h,
                        ]
                    )

            frame_idx += 1
            if frame_idx == 1 or frame_idx % 100 == 0:
                total_text = total_frames if total_frames else "?"
                print(f"  frame {frame_idx}/{total_text}, detections={detections}")

    cap.release()
    writer.release()

    print(f"[DONE] {video_path}")
    print(f"  detections: {detections}")
    print(f"  tracked video: {annotated_path}")
    print(f"  track csv:     {csv_path}")

    if detections == 0:
        print("  WARNING: YOLO did not detect any ball candidates.")
        print("  yolo26n.pt가 COCO 사전학습 모델이면 당구공 3개를 안정적으로 못 잡을 수 있습니다.")
        print("  먼저 --conf 0.05 처럼 낮춰보고, 정확도가 필요하면 당구공 전용 학습 모델이 필요합니다.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Track billiard balls in videos with YOLO26n/Ultralytics.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, type=Path, help=f"video file or directory. default: {DEFAULT_SOURCE}")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="model name or .pt path. default: yolo26n.pt")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    parser.add_argument("--conf", default=0.15, type=float)
    parser.add_argument("--iou", default=0.5, type=float)
    parser.add_argument("--imgsz", default=960, type=int)
    parser.add_argument("--device", default=None, help="example: 0, cuda:0, cpu")
    parser.add_argument("--tracker", default="bytetrack.yaml", help="bytetrack.yaml or botsort.yaml")
    parser.add_argument("--classes", default=DEFAULT_CLASSES, help="class ids to track. COCO sports ball is 32. Use 'all' for no filter.")
    parser.add_argument("--trail-length", default=240, type=int, help="number of recent track points to draw")
    parser.add_argument("--trail-thickness", default=4, type=int, help="maximum trail line thickness")
    args = parser.parse_args()

    videos = iter_videos(args.source)
    if not videos:
        raise SystemExit(f"No videos found: {args.source}")

    classes = parse_classes(args.classes)
    model_path = resolve_model_path(args.model)
    model = YOLO(model_path)

    print("tracking target: YOLO sports ball candidates")
    print(f"source: {args.source}")
    print(f"model: {model_path}")
    print(f"target classes: {classes if classes is not None else 'all'}")
    print(f"model names: {model.names}")
    print(f"videos: {len(videos)}")
    print(f"output: {args.output}")
    print(f"trail_length: {args.trail_length}")

    for video in videos:
        track_video(
            model=model,
            video_path=video,
            output_dir=args.output,
            conf=args.conf,
            iou=args.iou,
            imgsz=args.imgsz,
            device=args.device,
            tracker=args.tracker,
            classes=classes,
            trail_length=args.trail_length,
            trail_thickness=args.trail_thickness,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
