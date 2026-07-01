from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from check_dataset_labels import (
    DEFAULT_DATASET_ROOT,
    VIDEO_EXTENSIONS,
    collect_videos,
    is_path_like_query,
    iter_sample_folders,
    parse_positions_file,
)

HOST = "127.0.0.1"
PORT = 8765


HTML = r"""
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ThreeCushion Dataset Labels</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --line: #d9dee7;
      --text: #1c2430;
      --muted: #687386;
      --accent: #176b87;
      --accent-2: #7b5e2b;
      --bad: #b42318;
      --ok: #16784b;
      --shadow: 0 1px 2px rgba(20, 31, 46, 0.08);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    header {
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      padding: 18px 24px 14px;
    }

    h1 {
      margin: 0 0 4px;
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0;
    }

    .root-path { color: var(--muted); overflow-wrap: anywhere; }
    main { padding: 18px 24px 28px; max-width: 1440px; margin: 0 auto; }

    .summary {
      display: grid;
      grid-template-columns: repeat(6, minmax(130px, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }

    .metric {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 12px;
      min-height: 74px;
    }

    .metric span { display: block; color: var(--muted); font-size: 12px; }
    .metric strong { display: block; margin-top: 5px; font-size: 22px; }
    .metric.ok strong { color: var(--ok); }
    .metric.bad strong { color: var(--bad); }

    .toolbar {
      display: grid;
      grid-template-columns: 170px minmax(220px, 1fr) auto auto;
      gap: 8px;
      align-items: center;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 12px;
      margin-bottom: 12px;
    }

    select, input, button {
      height: 38px;
      border-radius: 7px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      font: inherit;
      padding: 0 10px;
    }

    input { width: 100%; }
    button {
      cursor: pointer;
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
      font-weight: 650;
      min-width: 76px;
    }
    button.secondary { background: #fff; color: var(--accent); }

    .content {
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      gap: 12px;
      align-items: start;
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      min-width: 0;
    }

    .panel h2 {
      margin: 0;
      padding: 12px;
      border-bottom: 1px solid var(--line);
      font-size: 14px;
    }

    .position-list { max-height: 620px; overflow: auto; }
    .position-item {
      width: 100%;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      border: 0;
      border-bottom: 1px solid #edf0f4;
      border-radius: 0;
      background: #fff;
      color: var(--text);
      min-height: 36px;
      text-align: left;
      padding: 8px 12px;
      font-weight: 500;
    }
    .position-item:hover { background: #f3f7f9; }
    .position-item .count { color: var(--accent-2); font-variant-numeric: tabular-nums; }

    .results-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 12px;
      border-bottom: 1px solid var(--line);
      color: var(--muted);
    }

    .status-text { overflow-wrap: anywhere; }
    .table-wrap { overflow: auto; max-height: 650px; }
    table { width: 100%; border-collapse: collapse; min-width: 980px; }
    th, td {
      border-bottom: 1px solid #edf0f4;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }
    th {
      position: sticky;
      top: 0;
      background: #f9fafb;
      color: #334155;
      font-size: 12px;
      z-index: 1;
    }
    td.path { white-space: normal; overflow-wrap: anywhere; min-width: 360px; }
    td.raw { white-space: normal; overflow-wrap: anywhere; min-width: 220px; }
    .pill {
      display: inline-flex;
      min-width: 34px;
      justify-content: center;
      border-radius: 999px;
      padding: 2px 7px;
      background: #eef6f8;
      color: var(--accent);
      font-weight: 650;
    }
    .empty { padding: 28px 12px; color: var(--muted); text-align: center; }

    @media (max-width: 920px) {
      header, main { padding-left: 14px; padding-right: 14px; }
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .toolbar { grid-template-columns: 1fr; }
      .content { grid-template-columns: 1fr; }
      .position-list { max-height: 260px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>ThreeCushion Dataset Labels</h1>
    <div class="root-path" id="rootPath">점검중...</div>
  </header>
  <main>
    <section class="summary" id="summary"></section>

    <section class="toolbar">
      <select id="mode">
        <option value="auto">자동 검색</option>
        <option value="video">영상명/경로</option>
        <option value="position">포지션</option>
      </select>
      <input id="query" placeholder="예: 뒤돌리기 또는 00020002-y-play.mp4" autocomplete="off" />
      <button id="searchBtn">검색</button>
      <button class="secondary" id="verifyBtn">재점검</button>
    </section>

    <section class="content">
      <aside class="panel">
        <h2>포지션 목록</h2>
        <div class="position-list" id="positions"></div>
      </aside>
      <section class="panel">
        <div class="results-head">
          <div class="status-text" id="resultStatus">점검 후 검색할 수 있습니다.</div>
          <div id="resultCount"></div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>영상</th>
                <th>포지션</th>
                <th>flag</th>
                <th>라인</th>
                <th>key</th>
                <th>원본 라벨</th>
                <th>영상 존재</th>
              </tr>
            </thead>
            <tbody id="results"><tr><td colspan="7" class="empty">검색어를 입력하세요.</td></tr></tbody>
          </table>
        </div>
      </section>
    </section>
  </main>

  <script>
    const rootPath = document.getElementById('rootPath');
    const summary = document.getElementById('summary');
    const positions = document.getElementById('positions');
    const mode = document.getElementById('mode');
    const query = document.getElementById('query');
    const results = document.getElementById('results');
    const resultStatus = document.getElementById('resultStatus');
    const resultCount = document.getElementById('resultCount');

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>'"]/g, ch => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
      }[ch]));
    }

    async function loadJson(url) {
      const res = await fetch(url);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.statusText);
      return data;
    }

    function renderSummary(data) {
      rootPath.textContent = data.dataset_root;
      const metrics = [
        ['폴더', data.folders],
        ['영상', data.videos_total],
        ['라벨', data.labels_total],
        ['라벨만 있음', data.labels_without_video, data.labels_without_video === 0],
        ['영상만 있음', data.videos_without_label, data.videos_without_label === 0],
        ['파싱 오류', data.parse_errors, data.parse_errors === 0],
      ];
      summary.innerHTML = metrics.map(([label, value, ok]) => `
        <div class="metric ${ok === undefined ? '' : ok ? 'ok' : 'bad'}">
          <span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong>
        </div>
      `).join('');
      resultStatus.textContent = data.ok ? '점검 성공. 검색할 수 있습니다.' : '점검 실패. 문제 항목을 확인하세요.';
    }

    function renderPositions(items) {
      positions.innerHTML = items.map(item => `
        <button class="position-item" data-position="${escapeHtml(item.position)}">
          <span>${escapeHtml(item.position)}</span><span class="count">${item.count}</span>
        </button>
      `).join('');
      positions.querySelectorAll('button').forEach(btn => {
        btn.addEventListener('click', () => {
          mode.value = 'position';
          query.value = btn.dataset.position;
          search();
        });
      });
    }

    function renderResults(data) {
      resultStatus.textContent = data.message || `${data.query} 검색 결과`;
      resultCount.textContent = `${data.matches.length}개`;
      if (!data.matches.length) {
        results.innerHTML = '<tr><td colspan="7" class="empty">검색 결과가 없습니다.</td></tr>';
        return;
      }
      results.innerHTML = data.matches.map(row => `
        <tr>
          <td class="path">${escapeHtml(row.video)}</td>
          <td>${escapeHtml(row.position || '')}</td>
          <td><span class="pill">${escapeHtml(row.flag || '')}</span></td>
          <td>${escapeHtml(row.line || '')}</td>
          <td>${escapeHtml(row.key || '')}</td>
          <td class="raw">${escapeHtml(row.raw || '')}</td>
          <td>${row.video_exists ? 'True' : 'False'}</td>
        </tr>
      `).join('');
    }

    async function verify() {
      resultStatus.textContent = '점검중...';
      const data = await loadJson('/api/status');
      renderSummary(data);
    }

    async function loadPositions() {
      const data = await loadJson('/api/positions');
      renderPositions(data.positions);
    }

    async function search() {
      const q = query.value.trim();
      if (!q) return;
      resultStatus.textContent = '검색중...';
      resultCount.textContent = '';
      try {
        const data = await loadJson(`/api/search?mode=${encodeURIComponent(mode.value)}&q=${encodeURIComponent(q)}`);
        renderResults(data);
      } catch (err) {
        resultStatus.textContent = err.message;
        results.innerHTML = '<tr><td colspan="7" class="empty">검색 실패</td></tr>';
      }
    }

    document.getElementById('searchBtn').addEventListener('click', search);
    document.getElementById('verifyBtn').addEventListener('click', verify);
    query.addEventListener('keydown', event => {
      if (event.key === 'Enter') search();
    });

    (async function init() {
      try {
        await verify();
        await loadPositions();
      } catch (err) {
        rootPath.textContent = err.message;
        resultStatus.textContent = '점검 실패';
      }
    })();
  </script>
</body>
</html>
"""


def label_to_dict(video_path: Path, row, video_exists: bool = True) -> dict[str, object]:
    return {
        "video": str(video_path),
        "video_exists": video_exists,
        "positions_txt": str(row.folder / "positions.txt") if row else "",
        "line": row.line_no if row else "",
        "key": row.key if row else "",
        "position": row.position if row else "",
        "flag": row.flag if row else "",
        "raw": row.raw_line if row else "",
    }


def dataset_status(dataset_root: Path) -> dict[str, object]:
    if not dataset_root.exists():
        return {"ok": False, "error": f"Dataset root not found: {dataset_root}", "dataset_root": str(dataset_root)}

    folders = iter_sample_folders(dataset_root)
    total_videos = 0
    total_labels = 0
    parse_errors = []
    missing_videos = []
    unlabeled_videos = []
    missing_position_files = []

    for folder in folders:
        position_file = folder / "positions.txt"
        videos = collect_videos(folder)
        total_videos += len(videos)

        if not position_file.exists():
            missing_position_files.append(str(folder))
            unlabeled_videos.extend(str(path) for path in videos.values())
            continue

        rows, errors = parse_positions_file(position_file)
        parse_errors.extend(errors)
        total_labels += len(rows)

        labeled_stems = {row.expected_stem for row in rows}
        missing_videos.extend(
            f"{position_file}:{row.line_no}: {row.raw_line} -> {row.folder / row.expected_video_name}"
            for row in rows
            if row.expected_stem not in videos
        )
        unlabeled_videos.extend(str(path) for stem, path in videos.items() if stem not in labeled_stems)

    ok = not missing_position_files and not parse_errors and not missing_videos and not unlabeled_videos
    return {
        "ok": ok,
        "dataset_root": str(dataset_root),
        "folders": len(folders),
        "videos_total": total_videos,
        "labels_total": total_labels,
        "missing_positions_txt_folders": len(missing_position_files),
        "parse_errors": len(parse_errors),
        "labels_without_video": len(missing_videos),
        "videos_without_label": len(unlabeled_videos),
        "details": {
            "missing_position_files": missing_position_files,
            "parse_errors": parse_errors,
            "missing_videos": missing_videos,
            "unlabeled_videos": unlabeled_videos,
        },
    }


def position_counts(dataset_root: Path) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    for folder in iter_sample_folders(dataset_root):
        position_file = folder / "positions.txt"
        if not position_file.exists():
            continue
        rows, _ = parse_positions_file(position_file)
        for row in rows:
            counts[row.position] = counts.get(row.position, 0) + 1
    return [
        {"position": position, "count": count}
        for position, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def looks_like_video_query(query: str) -> bool:
    lowered = query.lower()
    return lowered.endswith(tuple(VIDEO_EXTENSIONS)) or "-play" in lowered or is_path_like_query(query)


def search_video_rows(dataset_root: Path, query: str) -> list[dict[str, object]]:
    query_lower = query.lower()
    path_like = is_path_like_query(query)
    matches = []

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

        rows_by_stem = {}
        position_file = folder / "positions.txt"
        if position_file.exists():
            rows, _ = parse_positions_file(position_file)
            rows_by_stem = {row.expected_stem: row for row in rows}

        for video in matched_videos:
            matches.append(label_to_dict(video, rows_by_stem.get(video.stem), video.exists()))

    return matches


def search_position_rows(dataset_root: Path, position_query: str) -> list[dict[str, object]]:
    matches = []
    for folder in iter_sample_folders(dataset_root):
        position_file = folder / "positions.txt"
        if not position_file.exists():
            continue
        rows, _ = parse_positions_file(position_file)
        for row in rows:
            if row.position != position_query:
                continue
            video_path = row.folder / row.expected_video_name
            matches.append(label_to_dict(video_path, row, video_path.exists()))
    return matches


class DatasetLabelHandler(BaseHTTPRequestHandler):
    dataset_root = DEFAULT_DATASET_ROOT

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, payload: dict[str, object], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self) -> None:
        body = HTML.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_html()
            return

        if parsed.path == "/api/status":
            data = dataset_status(self.dataset_root)
            self.send_json(data, HTTPStatus.OK if data.get("ok") else HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/positions":
            self.send_json({"positions": position_counts(self.dataset_root)})
            return

        if parsed.path == "/api/search":
            params = parse_qs(parsed.query)
            query = (params.get("q") or [""])[0].strip()
            mode = (params.get("mode") or ["auto"])[0]
            if not query:
                self.send_json({"error": "query is required"}, HTTPStatus.BAD_REQUEST)
                return

            if mode == "video" or (mode == "auto" and looks_like_video_query(query)):
                matches = search_video_rows(self.dataset_root, query)
                label = "video"
            else:
                matches = search_position_rows(self.dataset_root, query)
                label = "position"

            self.send_json({"type": label, "query": query, "matches": matches, "message": f"{query} 검색 결과"})
            return

        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), DatasetLabelHandler)
    print(f"점검중... dataset_root={DatasetLabelHandler.dataset_root}")
    status = dataset_status(DatasetLabelHandler.dataset_root)
    if not status.get("ok"):
        print("점검 실패. 웹 UI는 실행하지만 상태 화면에서 문제를 확인하세요.")
    else:
        print("점검 성공. 웹 UI를 시작합니다.")
    print(f"http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
