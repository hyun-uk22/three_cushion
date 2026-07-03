from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
from ultralytics import YOLO


# 기본 테스트 영상. WSL/Linux 기준 경로입니다.
DEFAULT_SOURCE = Path(
    "/mnt/e/password_data/dataset/9328_99178133037742335_71136/00180002-y-play.mp4"
)

# YOLO26 가중치 파일명 또는 직접 학습한 당구공 모델 경로.
DEFAULT_MODEL = "yolo26.pt"

# COCO 계열 YOLO에서 sports ball class id는 32입니다.
# 직접 학습한 당구공 모델이면 None으로 바꾸거나 해당 class id로 바꾸세요.
DEFAULT_CLASSES = "32"

DEFAULT_OUTPUT = Path("runs/billiard_ball_tracking")
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}




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

    fallback = Path(__file__).resolve().parent / "yolo26n.pt"
    message = [
        f"Model file not found: {model}",
        "일반 YOLO26을 쓰려면 yolo26.pt 파일이 필요합니다.",
        f"프로젝트 폴더에 yolo26.pt를 넣거나 --model /path/to/yolo26.pt 로 지정하세요.",
    ]
    if fallback.exists():
        message.append(f"참고: 현재 있는 모델은 {fallback} 입니다. nano 모델로 실행하려면 --model {fallback} 를 쓰세요.")
    raise SystemExit("\n".join(message))
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


def draw_ball_centers(frame, boxes, names) -> None:
    if boxes is None or len(boxes) == 0:
        return

    xywh = boxes.xywh.cpu().tolist()
    class_ids = boxes.cls.cpu().tolist() if boxes.cls is not None else []
    track_ids = boxes.id.cpu().tolist() if getattr(boxes, "id", None) is not None else [None] * len(xywh)

    for idx, (cx, cy, box_w, box_h) in enumerate(xywh):
        class_id = int(class_ids[idx]) if idx < len(class_ids) else -1
        class_name = names.get(class_id, str(class_id))
        track_id = track_ids[idx] if idx < len(track_ids) else None
        label = f"{class_name}"
        if track_id is not None:
            label += f" #{int(track_id)}"

        center = (int(cx), int(cy))
        radius = max(3, int(max(box_w, box_h) / 2))
        cv2.circle(frame, center, radius, (0, 255, 255), 2)
        cv2.circle(frame, center, 3, (0, 0, 255), -1)
        cv2.putText(
            frame,
            label,
            (center[0] + 6, center[1] - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )


def track_billiard_balls(
    model: YOLO,
    video_path: Path,
    output_dir: Path,
    conf: float,
    iou: float,
    imgsz: int,
    device: str | None,
    tracker: str,
    classes: list[int] | None,
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
    annotated_path = output_dir / f"{stem}_billiard_balls_tracked.mp4"
    csv_path = output_dir / f"{stem}_billiard_balls_tracks.csv"

    writer = cv2.VideoWriter(
        str(annotated_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    detections = 0

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
            draw_ball_centers(annotated, result.boxes, model.names)
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
                    track_id = track_ids[idx] if idx < len(track_ids) else None
                    x1, y1, x2, y2 = coords
                    cx, cy, box_w, box_h = xywh[idx]
                    csv_writer.writerow(
                        [
                            frame_idx,
                            "" if track_id is None else int(track_id),
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
        print("  If yolo26.pt is COCO-pretrained, billiard balls may be too small/not learned well.")
        print("  Use a billiard-ball-trained .pt model or lower --conf, e.g. --conf 0.05.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Track billiard balls in videos with YOLO26/Ultralytics.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, type=Path, help=f"video file or directory. default: {DEFAULT_SOURCE}")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="model name or .pt path. default: yolo26.pt")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    parser.add_argument("--conf", default=0.15, type=float)
    parser.add_argument("--iou", default=0.5, type=float)
    parser.add_argument("--imgsz", default=960, type=int)
    parser.add_argument("--device", default=None, help="example: 0, cuda:0, cpu")
    parser.add_argument("--tracker", default="bytetrack.yaml", help="bytetrack.yaml or botsort.yaml")
    parser.add_argument("--classes", default=DEFAULT_CLASSES, help="class ids to track. COCO sports ball is 32. Use 'all' for no filter.")
    args = parser.parse_args()

    videos = iter_videos(args.source)
    if not videos:
        raise SystemExit(f"No videos found: {args.source}")

    classes = parse_classes(args.classes)
    model_path = resolve_model_path(args.model)
    model = YOLO(model_path)

    print(f"source: {args.source}")
    print(f"model: {model_path}")
    print(f"target classes: {classes if classes is not None else 'all'}")
    print(f"model names: {model.names}")
    print(f"videos: {len(videos)}")
    print(f"output: {args.output}")

    for video in videos:
        track_billiard_balls(
            model=model,
            video_path=video,
            output_dir=args.output,
            conf=args.conf,
            iou=args.iou,
            imgsz=args.imgsz,
            device=args.device,
            tracker=args.tracker,
            classes=classes,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())




