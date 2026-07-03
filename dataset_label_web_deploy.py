from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from check_dataset_labels import (
    VIDEO_EXTENSIONS,
    collect_videos,
    is_path_like_query,
    iter_sample_folders,
    parse_positions_file,
)

HOST = "0.0.0.0"
PORT = 8765
DEFAULT_DATASET_ROOT = Path("/home/hnvlab/three/dataset")


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
    button:disabled { cursor: not-allowed; opacity: 0.45; }


    .filter-panel {
      display: grid;
      grid-template-columns: repeat(4, minmax(140px, 1fr));
      gap: 8px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 12px;
      margin-bottom: 12px;
    }
    .filter-panel label {
      display: grid;
      gap: 4px;
      color: var(--muted);
      font-size: 12px;
    }
    .filter-panel label input,
    .filter-panel label select {
      font-size: 14px;
    }
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
    .video-preview {
      display: none;
      padding: 12px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfd;
    }
    .video-preview.active { display: block; }
    .video-preview video {
      width: 100%;
      max-height: 420px;
      background: #101418;
      border-radius: 8px;
    }
    .video-title {
      margin-bottom: 8px;
      color: var(--text);
      font-weight: 700;
      overflow-wrap: anywhere;
    }
    .video-meta {
      display: grid;
      grid-template-columns: 110px minmax(0, 1fr);
      gap: 6px 10px;
      margin-bottom: 10px;
      font-size: 13px;
    }
    .video-meta dt {
      color: var(--muted);
      margin: 0;
    }
    .video-meta dd {
      margin: 0;
      overflow-wrap: anywhere;
    }
    .video-link {
      display: inline;
      border: 0;
      background: transparent;
      color: var(--accent);
      padding: 0;
      height: auto;
      min-width: 0;
      text-align: left;
      font-weight: 650;
      text-decoration: underline;
      text-underline-offset: 2px;
    }
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
      .filter-panel { grid-template-columns: 1fr; }


    .content { grid-template-columns: 1fr; }
      .position-list { max-height: 260px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>ThreeCushion Dataset Labels</h1>
    <div class="root-path" id="rootPath">/home/hnvlab/three/dataset</div>
  </header>
  <main>
<section class="toolbar">
      <select id="mode">
        <option value="auto">자동 검색</option>
        <option value="video">영상명/경로</option>
        <option value="position">포지션</option>
        <option value="flag">1/0</option>
      </select>
      <input id="query" placeholder="예: 뒤돌리기 또는 00020002-y-play.mp4" autocomplete="off" />
      <button id="searchBtn">검색</button>
      <button class="secondary" id="verifyBtn">새로고침</button>
    </section>


    <section class="filter-panel">
      <label>폴더<select id="folderFilter"><option value="">전체 폴더</option></select></label>
      <label>영상<input id="videoFilter" placeholder="영상명/경로" /></label>
      <label>번호<input id="numberFilter" placeholder="예: 00010001" /></label>
      <label>색상<select id="colorFilter"><option value="">전체</option><option value="w">w</option><option value="y">y</option><option value="n">n</option></select></label>
      <label>포지션<input id="positionFilter" placeholder="예: 뒤돌리기" /></label>
      <label>1/0<select id="flagFilter"><option value="">전체</option><option value="1">1</option><option value="0">0</option></select></label>
      <label>원본라벨<input id="rawFilter" placeholder="라벨 텍스트" /></label>
      <label>정렬<select id="sortField">
        <option value="folder">폴더</option>
        <option value="video">영상</option>
        <option value="number">번호</option>
        <option value="color">색상</option>
        <option value="position">포지션</option>
        <option value="flag">1/0</option>
        <option value="raw">원본라벨</option>
      </select></label>
      <label>방향<select id="sortDir"><option value="asc">오름차순</option><option value="desc">내림차순</option></select></label>
    </section>
    <section class="content">
      <aside class="panel">
        <h2>포지션 목록</h2>
        <div class="position-list" id="positions"></div>
      </aside>
      <section class="panel">
        <div class="results-head">
          <div class="status-text" id="resultStatus">검색할 수 있습니다.</div>
          <div id="resultCount"></div>
        </div>
        <div class="video-preview" id="videoPreview">
          <div class="video-title" id="videoTitle"></div>
          <dl class="video-meta" id="videoMeta"></dl>
          <video id="videoPlayer" controls preload="metadata"></video>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>폴더</th>
                <th>영상</th>
                <th>번호</th>
                <th>색상</th>
                <th>포지션</th>
                <th>1/0</th>
                <th>원본 라벨</th>
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
    const searchBtn = document.getElementById('searchBtn');
    const verifyBtn = document.getElementById('verifyBtn');
    const positions = document.getElementById('positions');
    const mode = document.getElementById('mode');
    const query = document.getElementById('query');
    const results = document.getElementById('results');
    const resultStatus = document.getElementById('resultStatus');
    const resultCount = document.getElementById('resultCount');
    const videoPreview = document.getElementById('videoPreview');
    const videoTitle = document.getElementById('videoTitle');
    const videoMeta = document.getElementById('videoMeta');
    const videoPlayer = document.getElementById('videoPlayer');
    const fixedRoot = '/home/hnvlab/three/dataset';
    const folderFilter = document.getElementById('folderFilter');
    const videoFilter = document.getElementById('videoFilter');
    const numberFilter = document.getElementById('numberFilter');
    const colorFilter = document.getElementById('colorFilter');
    const positionFilter = document.getElementById('positionFilter');
    const flagFilter = document.getElementById('flagFilter');
    const rawFilter = document.getElementById('rawFilter');
    const sortField = document.getElementById('sortField');
    const sortDir = document.getElementById('sortDir');
    let allRows = [];
    let verifiedRoot = fixedRoot;

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


    function populateFolderFilter(rows) {
      const folders = Array.from(new Set(rows.map(row => row.folder).filter(Boolean))).sort();
      folderFilter.innerHTML = '<option value="">전체 폴더</option>' + folders.map(folder => `
        <option value="${escapeHtml(folder)}">${escapeHtml(folder)}</option>
      `).join('');
    }

    function includesText(value, needle) {
      if (!needle) return true;
      return String(value ?? '').toLowerCase().includes(needle.toLowerCase());
    }

    function compareRows(a, b, field) {
      const av = a[field] ?? '';
      const bv = b[field] ?? '';
      if (field === 'line') return Number(av || 0) - Number(bv || 0);
      return String(av).localeCompare(String(bv), 'ko', { numeric: true, sensitivity: 'base' });
    }

    function currentFilteredRows() {
      const q = query.value.trim();
      const selectedMode = mode.value;
      let rows = allRows.filter(row => {
        const queryOk = !q
          || (selectedMode === 'position' && includesText(row.position, q))
          || (selectedMode === 'video' && includesText(row.video, q))
          || (selectedMode === 'auto' && (
            includesText(row.video, q)
            || includesText(row.number, q)
            || includesText(row.color, q)
            || includesText(row.position, q)
            || includesText(row.flag, q)
            || includesText(row.raw, q)
            || includesText(row.folder, q)
          ));

        return queryOk
          && (!folderFilter.value || row.folder === folderFilter.value)
          && includesText(row.video, videoFilter.value.trim())
          && includesText(row.number, numberFilter.value.trim())
          && (!colorFilter.value || row.color === colorFilter.value)
          && includesText(row.position, positionFilter.value.trim())
          && (!flagFilter.value || String(row.flag) === flagFilter.value)
          && includesText(row.raw, rawFilter.value.trim());
      });

      rows.sort((a, b) => compareRows(a, b, sortField.value));
      if (sortDir.value === 'desc') rows.reverse();
      return rows;
    }

    function applyFilters() {
      if (!allRows.length) {
        results.innerHTML = '<tr><td colspan="7" class="empty">데이터셋을 불러오는 중입니다.</td></tr>';
        return;
      }
      const rows = currentFilteredRows();
      renderResults({ query: query.value.trim() || '전체', matches: rows, message: '필터 결과' });
    }
    function renderResults(data) {
      resultStatus.textContent = data.message || `${data.query} 검색 결과`;
      resultCount.textContent = `${data.matches.length}개`;
      if (!data.matches.length) {
        results.innerHTML = '<tr><td colspan="7" class="empty">검색 결과가 없습니다.</td></tr>';
        return;
      }
      results.innerHTML = data.matches.map((row, index) => `
        <tr>
          <td>${escapeHtml(row.folder || '')}</td>
          <td class="path"><button class="video-link" data-index="${index}">${escapeHtml(row.video)}</button></td>
          <td>${escapeHtml(row.number || '')}</td>
          <td><span class="pill">${escapeHtml(row.color || '')}</span></td>
          <td>${escapeHtml(row.position || '')}</td>
          <td><span class="pill">${escapeHtml(row.flag || '')}</span></td>
          <td class="raw">${escapeHtml(row.raw || '')}</td>
        </tr>
      `).join('');
      results.querySelectorAll('.video-link').forEach(button => {
        button.addEventListener('click', () => playVideo(data.matches[Number(button.dataset.index)]));
      });
    }

    function playVideo(row) {
      if (!row || !row.video_exists) {
        resultStatus.textContent = '재생할 영상 파일이 없습니다.';
        return;
      }
      const src = `/api/video?${rootQuery()}&path=${encodeURIComponent(row.video)}`;
      videoTitle.textContent = row.video;
      videoMeta.innerHTML = `
        <dt>번호</dt><dd>${escapeHtml(row.number || '')}</dd>
        <dt>색상</dt><dd>${escapeHtml(row.color || '')}</dd>
        <dt>포지션</dt><dd>${escapeHtml(row.position || '')}</dd>
        <dt>1/0</dt><dd>${escapeHtml(row.flag || '')}</dd>
        <dt>원본 라벨</dt><dd>${escapeHtml(row.raw || '')}</dd>
        <dt>positions.txt</dt><dd>${escapeHtml(row.positions_txt || '')}</dd>
      `;
      videoPlayer.src = src;
      videoPreview.classList.add('active');
      videoPlayer.play().catch(() => {});
    }

    function currentRoot() {
      return fixedRoot;
    }

    function rootQuery() {
      return `root=${encodeURIComponent(currentRoot())}`;
    }

    function setSearchEnabled(enabled) {
      searchBtn.disabled = !enabled;
      verifyBtn.disabled = !enabled;
      query.disabled = !enabled;
      mode.disabled = !enabled;
    }

    async function verify() {
      setSearchEnabled(false);
      verifiedRoot = fixedRoot;
      positions.innerHTML = '';
      videoPlayer.removeAttribute('src');
      videoMeta.innerHTML = '';
      videoPreview.classList.remove('active');
      results.innerHTML = '<tr><td colspan="7" class="empty">로딩중...</td></tr>';
      resultCount.textContent = '';
      rootPath.textContent = fixedRoot;
      resultStatus.textContent = '포지션 목록 로딩중...';

      try {
        const data = await loadJson(`/api/positions?${rootQuery()}`);
        renderPositions(data.positions);
        const labelData = await loadJson(`/api/labels?${rootQuery()}`);
        allRows = labelData.rows;
        populateFolderFilter(allRows);
        setSearchEnabled(true);
        resultStatus.textContent = `포지션 ${data.positions.length}개, 라벨 ${allRows.length}개를 불러왔습니다.`;
        applyFilters();
      } catch (err) {
        positions.innerHTML = '';
        resultStatus.textContent = err.message;
        results.innerHTML = '<tr><td colspan="7" class="empty">데이터셋을 불러오지 못했습니다.</td></tr>';
        setSearchEnabled(false);
      }
    }

    async function loadPositions() {
      const data = await loadJson(`/api/positions?${rootQuery()}`);
      renderPositions(data.positions);
    }

    async function search() {
      if (!verifiedRoot) {
        resultStatus.textContent = '데이터셋을 불러오는 중입니다.';
        return;
      }
      applyFilters();
    }
    searchBtn.addEventListener('click', search);
    verifyBtn.addEventListener('click', verify);
    query.addEventListener('keydown', event => {
      if (event.key === 'Enter') search();
    });

    
    [folderFilter, videoFilter, numberFilter, colorFilter, positionFilter, flagFilter, rawFilter, sortField, sortDir, mode].forEach(control => {
      control.addEventListener('input', applyFilters);
      control.addEventListener('change', applyFilters);
    });

    (async function init() {
      setSearchEnabled(false);
      rootPath.textContent = fixedRoot;
      positions.innerHTML = '<div class="empty">포지션 목록 로딩중...</div>';
      resultStatus.textContent = '포지션 목록 로딩중...';
      await verify();
    })();
  </script>
</body>
</html>
"""



def resolve_dataset_root(raw_root: str | None) -> Path:
    raw = (raw_root or str(DEFAULT_DATASET_ROOT)).strip().strip('"')
    if not raw:
        return DEFAULT_DATASET_ROOT

    normalized = raw.replace("/", "\\") if len(raw) >= 2 and raw[1] == ":" else raw
    candidates = [Path(raw), Path(normalized)]

    if len(raw) >= 3 and raw[1] == ":" and raw[2] in {"\\", "/"}:
        drive = raw[0].lower()
        rest = raw[3:].replace("\\", "/")
        candidates.append(Path(f"/mnt/{drive}/{rest}"))

    if raw.startswith("/mnt/") and len(raw) > 7:
        parts = raw.split("/")
        if len(parts) >= 4 and len(parts[2]) == 1:
            drive = parts[2].upper()
            rest = "\\".join(parts[3:])
            candidates.append(Path(f"{drive}:\\{rest}"))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def get_root_from_params(params: dict[str, list[str]]) -> Path:
    return resolve_dataset_root((params.get("root") or [None])[0])


def split_label_key(key: str) -> tuple[str, str]:
    number, separator, color = key.rpartition("-")
    if not separator:
        return key, ""
    return number, color


def label_to_dict(video_path: Path, row, video_exists: bool = True) -> dict[str, object]:
    number, color = split_label_key(row.key) if row else ("", "")
    return {
        "video": str(video_path),
        "folder": video_path.parent.name,
        "video_exists": video_exists,
        "positions_txt": str(row.folder / "positions.txt") if row else "",
        "line": row.line_no if row else "",
        "number": number,
        "color": color,
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



def resolve_video_file(dataset_root: Path, raw_video_path: str) -> Path | None:
    if not raw_video_path:
        return None

    video_path = resolve_dataset_root(raw_video_path)
    if not video_path.exists() or not video_path.is_file():
        return None

    if video_path.suffix.lower() not in VIDEO_EXTENSIONS:
        return None

    try:
        video_path.resolve().relative_to(dataset_root.resolve())
    except ValueError:
        return None

    return video_path

def all_label_rows(dataset_root: Path) -> list[dict[str, object]]:
    rows_out: list[dict[str, object]] = []
    for folder in iter_sample_folders(dataset_root):
        position_file = folder / "positions.txt"
        if not position_file.exists():
            continue
        rows, _ = parse_positions_file(position_file)
        for row in rows:
            video_path = row.folder / row.expected_video_name
            rows_out.append(label_to_dict(video_path, row, video_path.exists()))
    return rows_out
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

    def send_video_file(self, video_path: Path) -> None:
        file_size = video_path.stat().st_size
        content_type = mimetypes.guess_type(video_path.name)[0] or "application/octet-stream"
        range_header = self.headers.get("Range")

        start = 0
        end = file_size - 1
        status = HTTPStatus.OK

        if range_header and range_header.startswith("bytes="):
            status = HTTPStatus.PARTIAL_CONTENT
            range_value = range_header.removeprefix("bytes=").split(",", 1)[0]
            start_text, _, end_text = range_value.partition("-")
            if start_text:
                start = int(start_text)
            if end_text:
                end = int(end_text)
            end = min(end, file_size - 1)

        if start > end or start >= file_size:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.end_headers()
            return

        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.end_headers()

        with video_path.open("rb") as video_file:
            video_file.seek(start)
            remaining = length
            while remaining > 0:
                chunk = video_file.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_html()
            return

        if parsed.path == "/api/video":
            params = parse_qs(parsed.query)
            root = get_root_from_params(params)
            if not root.exists():
                self.send_json({"error": f"Dataset root not found: {root}"}, HTTPStatus.BAD_REQUEST)
                return

            raw_video_path = (params.get("path") or [""])[0]
            video_path = resolve_video_file(root, raw_video_path)
            if video_path is None:
                self.send_json({"error": "video file not found or not allowed"}, HTTPStatus.NOT_FOUND)
                return

            self.send_video_file(video_path)
            return
        if parsed.path == "/api/status":
            params = parse_qs(parsed.query)
            root = get_root_from_params(params)
            data = dataset_status(root)
            self.send_json(data, HTTPStatus.OK if data.get("ok") else HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/positions":
            params = parse_qs(parsed.query)
            root = get_root_from_params(params)
            if not root.exists():
                self.send_json({"error": f"Dataset root not found: {root}"}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json({"positions": position_counts(root)})
            return

        if parsed.path == "/api/labels":
            params = parse_qs(parsed.query)
            root = get_root_from_params(params)
            if not root.exists():
                self.send_json({"error": f"Dataset root not found: {root}"}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json({"rows": all_label_rows(root)})
            return
        if parsed.path == "/api/search":
            params = parse_qs(parsed.query)
            root = get_root_from_params(params)
            if not root.exists():
                self.send_json({"error": f"Dataset root not found: {root}"}, HTTPStatus.BAD_REQUEST)
                return

            query = (params.get("q") or [""])[0].strip()
            mode = (params.get("mode") or ["auto"])[0]
            if not query:
                self.send_json({"error": "query is required"}, HTTPStatus.BAD_REQUEST)
                return

            if mode == "video" or (mode == "auto" and looks_like_video_query(query)):
                matches = search_video_rows(root, query)
                label = "video"
            else:
                matches = search_position_rows(root, query)
                label = "position"

            self.send_json({"type": label, "query": query, "matches": matches, "message": f"{query} 검색 결과"})
            return

        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), DatasetLabelHandler)
    print("웹 UI 서버를 시작합니다.")
    print(f"http://127.0.0.1:{PORT}")
    print(f"listening on {HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

















