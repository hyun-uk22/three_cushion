from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


DATASET_ROOT_CANDIDATES = [
    Path(r"E:\password_data\dataset"),
    Path("/mnt/e/password_data/dataset"),
]
DEFAULT_DATASET_ROOT = next(
    (path for path in DATASET_ROOT_CANDIDATES if path.exists()),
    DATASET_ROOT_CANDIDATES[0],
)
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}


@dataclass(frozen=True)
class LabelRow:
    folder: Path
    line_no: int
    key: str
    position: str
    flag: str
    raw_line: str

    @property
    def expected_stem(self) -> str:
        return f"{self.key}-play"

    @property
    def expected_video_name(self) -> str:
        return f"{self.expected_stem}.mp4"


def parse_positions_file(path: Path) -> tuple[list[LabelRow], list[str]]:
    rows: list[LabelRow] = []
    errors: list[str] = []

    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue

        parts = [part.strip() for part in line.split("=")]
        if len(parts) != 3:
            errors.append(f"{path}:{line_no}: parse error: {line}")
            continue

        key, position, flag = parts
        if not key or not position or not flag:
            errors.append(f"{path}:{line_no}: empty field: {line}")
            continue

        rows.append(
            LabelRow(
                folder=path.parent,
                line_no=line_no,
                key=key,
                position=position,
                flag=flag,
                raw_line=line,
            )
        )

    return rows, errors


def iter_sample_folders(dataset_root: Path) -> list[Path]:
    return sorted(path for path in dataset_root.iterdir() if path.is_dir())


def collect_videos(folder: Path) -> dict[str, Path]:
    return {
        path.stem: path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    }


def verify_dataset(dataset_root: Path) -> int:
    if not dataset_root.exists():
        print(f"Dataset root not found: {dataset_root}")
        return 2

    folders = iter_sample_folders(dataset_root)
    total_videos = 0
    total_labels = 0
    parse_errors: list[str] = []
    missing_videos: list[LabelRow] = []
    unlabeled_videos: list[Path] = []
    missing_position_files: list[Path] = []

    for folder in folders:
        position_file = folder / "positions.txt"
        videos = collect_videos(folder)
        total_videos += len(videos)

        if not position_file.exists():
            missing_position_files.append(folder)
            unlabeled_videos.extend(videos.values())
            continue

        rows, errors = parse_positions_file(position_file)
        parse_errors.extend(errors)
        total_labels += len(rows)

        labeled_stems = {row.expected_stem for row in rows}
        missing_videos.extend(row for row in rows if row.expected_stem not in videos)
        unlabeled_videos.extend(path for stem, path in videos.items() if stem not in labeled_stems)

    print("=== Dataset Label Verification ===")
    print(f"dataset_root: {dataset_root}")
    print(f"folders: {len(folders)}")
    print(f"videos_total: {total_videos}")
    print(f"labels_total: {total_labels}")
    print(f"missing_positions_txt_folders: {len(missing_position_files)}")
    print(f"parse_errors: {len(parse_errors)}")
    print(f"labels_without_video: {len(missing_videos)}")
    print(f"videos_without_label: {len(unlabeled_videos)}")

    if missing_position_files:
        print("\n--- Missing positions.txt ---")
        for folder in missing_position_files:
            print(folder)

    if parse_errors:
        print("\n--- Parse Errors ---")
        for error in parse_errors:
            print(error)

    if missing_videos:
        print("\n--- Labels Without Video ---")
        for row in missing_videos:
            print(
                f"{row.folder / 'positions.txt'}:{row.line_no}: "
                f"{row.raw_line} -> missing {row.folder / row.expected_video_name}"
            )

    if unlabeled_videos:
        print("\n--- Videos Without Label ---")
        for video in unlabeled_videos:
            print(video)

    if (
        not missing_position_files
        and not parse_errors
        and not missing_videos
        and not unlabeled_videos
    ):
        print("\nOK: every video and positions.txt row is matched.")
        return 0

    return 1


def is_path_like_query(query: str) -> bool:
    return ':' in query or '\\' in query or '/' in query


def search_video(dataset_root: Path, query: str) -> int:
    if not dataset_root.exists():
        print(f"Dataset root not found: {dataset_root}")
        return 2

    query_lower = query.lower()
    path_like = is_path_like_query(query)
    matches: list[tuple[Path, LabelRow | None]] = []

    for folder in iter_sample_folders(dataset_root):
        videos = collect_videos(folder)
        matched_videos = [
            video
            for video in videos.values()
            if (
                query_lower == str(video).lower()
                or (
                    query_lower in str(video).lower()
                    if path_like
                    else query_lower in video.name.lower()
                )
            )
        ]

        if not matched_videos:
            continue

        rows_by_stem: dict[str, LabelRow] = {}
        position_file = folder / "positions.txt"
        if position_file.exists():
            rows, _ = parse_positions_file(position_file)
            rows_by_stem = {row.expected_stem: row for row in rows}

        for video in matched_videos:
            matches.append((video, rows_by_stem.get(video.stem)))

    if not matches:
        print(f"No video found for query: {query}")
        return 1

    print("=== Video Label Search ===")
    print(f"query: {query}")
    print(f"matches: {len(matches)}")

    for video, row in matches:
        print("\n--- Match ---")
        print(f"video: {video}")
        if row is None:
            print("label: NOT FOUND")
            print(f"positions_txt: {video.parent / 'positions.txt'}")
            continue

        print(f"positions_txt: {row.folder / 'positions.txt'}")
        print(f"line: {row.line_no}")
        print(f"key: {row.key}")
        print(f"position: {row.position}")
        print(f"flag: {row.flag}")
        print(f"raw: {row.raw_line}")

    return 0


def search_position(dataset_root: Path, position_query: str) -> int:
    if not dataset_root.exists():
        print(f"Dataset root not found: {dataset_root}")
        return 2

    matches: list[tuple[Path, LabelRow, bool]] = []

    for folder in iter_sample_folders(dataset_root):
        position_file = folder / "positions.txt"
        if not position_file.exists():
            continue

        rows, _ = parse_positions_file(position_file)
        for row in rows:
            if row.position != position_query:
                continue

            video_path = row.folder / row.expected_video_name
            matches.append((video_path, row, video_path.exists()))

    if not matches:
        print(f"No labels found for position: {position_query}")
        return 1

    print("=== Position Label Search ===")
    print(f"position: {position_query}")
    print(f"matches: {len(matches)}")

    for video, row, video_exists in matches:
        print("\n--- Match ---")
        print(f"video: {video}")
        print(f"video_exists: {video_exists}")
        print(f"positions_txt: {row.folder / 'positions.txt'}")
        print(f"line: {row.line_no}")
        print(f"key: {row.key}")
        print(f"flag: {row.flag}")
        print(f"raw: {row.raw_line}")

    return 0

def looks_like_video_query(query: str) -> bool:
    lowered = query.lower()
    return lowered.endswith(tuple(VIDEO_EXTENSIONS)) or "-play" in lowered or is_path_like_query(query)


def interactive_search_loop(dataset_root: Path) -> int:
    print("\n점검 성공. 이제 검색할 수 있습니다.")
    print("영상명/영상경로 또는 포지션명을 입력하세요.")
    print("예: 00020002-y-play.mp4")
    print("예: 뒤돌리기")
    print("종료: q, quit, exit")

    while True:
        try:
            query = input("\n검색어> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            return 0

        if not query:
            continue

        if query.lower() in {"q", "quit", "exit"}:
            print("종료합니다.")
            return 0

        if query.startswith("video "):
            search_video(dataset_root, query.removeprefix("video ").strip())
        elif query.startswith("position "):
            search_position(dataset_root, query.removeprefix("position ").strip())
        elif looks_like_video_query(query):
            search_video(dataset_root, query)
        else:
            search_position(dataset_root, query)

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify dataset videos against positions.txt labels, or search one video label."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help=f"dataset root path. default: {DEFAULT_DATASET_ROOT}",
    )
    parser.add_argument(
        "--video",
        help="video file name or partial name to search. Example: 00020002-y-play.mp4",
    )
    parser.add_argument(
        "--position",
        help="exact position label to search. Example: 뒤돌리기",
    )
    args = parser.parse_args()

    if args.video:
        return search_video(args.root, args.video)

    if args.position:
        return search_position(args.root, args.position)

    print("점검중...")
    status = verify_dataset(args.root)
    if status != 0:
        print("\n점검 실패. 위 문제를 먼저 확인하세요.")
        return status

    return interactive_search_loop(args.root)


if __name__ == "__main__":
    raise SystemExit(main())







