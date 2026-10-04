import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from safe_repo.core.media_links import read_stream_entries


def _get_catalog_path(catalog_path: Optional[str] = None) -> str:
    if catalog_path:
        return str(Path(catalog_path).expanduser())

    env_path = os.environ.get("STREAM_CATALOG_FILE")
    if env_path:
        return str(Path(env_path).expanduser())

    return str(Path(__file__).resolve().parent.parent / "core" / "mongo" / "stream_catalog.json")


def _read_catalog_entries(catalog_path: Optional[str] = None) -> List[Dict[str, Any]]:
    return [entry for entry in read_stream_entries(catalog_path) if isinstance(entry, dict)]


def _build_watch_url(token: str) -> str:
    token = str(token or "").strip()
    if not token:
        return "/study"
    return f"/study/watch/{token}"


def build_public_study_url(base_url: str, subject: Optional[str] = None, date: Optional[str] = None, q: Optional[str] = None, folder: Optional[str] = None, subfolder: Optional[str] = None) -> str:
    """Build a public study URL that defaults to the home page and only uses /study when filters are present."""
    base = (base_url or "/").rstrip("/")
    params = {}
    if subject:
        params["subject"] = subject
    if date:
        params["date"] = date
    if q:
        params["q"] = q
    if folder:
        params["folder"] = folder
    if subfolder:
        params["subfolder"] = subfolder

    if not params:
        return f"{base}/"

    if base.endswith("/study"):
        return f"{base}?{urlencode(params)}"
    return f"{base}/study?{urlencode(params)}"


def _extract_folder_name(description: str) -> str:
    text = (description or "").strip()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("folder:"):
            return line.split(":", 1)[1].strip() or "General"
        if line.lower().startswith("topic:"):
            return line.split(":", 1)[1].strip() or "General"
    return "General"


def _extract_subfolder_name(description: str) -> str:
    text = (description or "").strip()
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("subfolder:"):
            return line.split(":", 1)[1].strip()
    return ""


def load_catalog_entries(catalog_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Normalize stored stream links into study-site video entries."""
    entries: List[Dict[str, Any]] = []
    for raw_entry in _read_catalog_entries(catalog_path):
        token = str(raw_entry.get("token") or raw_entry.get("id") or "").strip()
        subject = str(raw_entry.get("subject") or "General").strip() or "General"
        category = str(raw_entry.get("category") or raw_entry.get("class") or "General").strip() or "General"
        title = str(raw_entry.get("title") or subject or "Untitled").strip() or "Untitled"
        description = str(raw_entry.get("description") or "").strip()
        folder_name = str(raw_entry.get("folder") or _extract_folder_name(description)).strip() or "General"
        subfolder_name = str(raw_entry.get("subfolder") or _extract_subfolder_name(description)).strip()
        stream_url = str(raw_entry.get("stream_url") or "").strip()
        player_url = str(raw_entry.get("player_url") or "").strip()

        entries.append(
            {
                "token": token,
                "title": title,
                "description": description,
                "folder": folder_name,
                "subfolder": subfolder_name,
                "subject": subject,
                "category": category,
                "timestamp": str(raw_entry.get("timestamp") or ""),
                "date": str(raw_entry.get("date") or str(raw_entry.get("timestamp") or "").replace("T", " ").split(" ", 1)[0]),
                "featured": bool(raw_entry.get("featured")),
                "trending": bool(raw_entry.get("trending")),
                "views": int(raw_entry.get("views") or 0),
                "completion_count": int(raw_entry.get("completion_count") or 0),
                "player_url": player_url,
                "stream_url": stream_url,
                "thumbnail_url": str(raw_entry.get("thumbnail_url") or (f"/thumbnail/{token}" if token else "")),
                "media_type": str(raw_entry.get("media_type") or "video").lower(),
                "approved": bool(raw_entry.get("approved", True)),
                "transcript": str(raw_entry.get("transcript") or ""),
                "subtitles": str(raw_entry.get("subtitles") or ""),
                "playlist": str(raw_entry.get("playlist") or ""),
                "sort_order": int(raw_entry.get("sort_order") or 0),
                "pdf_text": str(raw_entry.get("pdf_text") or ""),
                "content_hash": str(raw_entry.get("content_hash") or ""),
                "watch_url": _build_watch_url(token),
            }
        )

    return entries


def build_video_index(catalog_path: Optional[str] = None, subject: Optional[str] = None, date: Optional[str] = None, q: Optional[str] = None, folder: Optional[str] = None, subfolder: Optional[str] = None, playlist: Optional[str] = None, media_type: Optional[str] = None, include_pending: bool = False) -> Dict[str, Any]:
    """Build a study-site index from catalog entries and optional filters."""
    all_videos = load_catalog_entries(catalog_path)
    videos = all_videos if include_pending else [video for video in all_videos if video.get("approved", True)]

    subject_param = (subject or "").strip()
    date_param = (date or "").strip()
    query_param = (q or "").strip()
    folder_param = (folder or "").strip()
    subfolder_param = (subfolder or "").strip()
    playlist_param = (playlist or "").strip()
    media_type_param = (media_type or "").strip().lower()
    subject_filter = subject_param.lower()
    date_filter = date_param
    search_query = query_param.lower()
    folder_filter = folder_param.lower()
    subfolder_filter = subfolder_param.lower()

    filtered = []
    for video in videos:
        title = str(video.get("title", "") or "").lower()
        subject_name = str(video.get("subject", "") or "").lower()
        description = str(video.get("description", "") or "").lower()
        searchable_text = " ".join((description, str(video.get("pdf_text", "") or ""), str(video.get("transcript", "") or ""))).lower()
        folder_name = str(video.get("folder") or "General").lower()
        subfolder_name = str(video.get("subfolder") or "").lower()
        if search_query and search_query not in title and search_query not in subject_name and search_query not in searchable_text:
            continue
        if subject_filter and subject_filter != str(video.get("subject", "")).lower():
            continue
        if date_filter and str(video.get("date", "")) != date_filter:
            continue
        if folder_filter and folder_filter != folder_name:
            continue
        if subfolder_filter and subfolder_filter != subfolder_name:
            continue
        if playlist_param:
            default_playlist = f"{video.get('subject') or 'General'} / {video.get('folder') or 'General'}"
            if video.get("subfolder"):
                default_playlist += f" / {video['subfolder']}"
            if playlist_param.lower() != str(video.get("playlist") or default_playlist).lower():
                continue
        if media_type_param and media_type_param != str(video.get("media_type") or "video").lower():
            continue
        filtered.append(video)

    featured = [video for video in filtered if video.get("featured")]
    latest = sorted(filtered, key=lambda item: item.get("timestamp", ""), reverse=True)
    trending = sorted(
        [video for video in filtered if video.get("trending") or video.get("views", 0) > 0],
        key=lambda item: (item.get("views", 0), item.get("timestamp", "")),
        reverse=True,
    )
    videos_by_date: Dict[str, List[Dict[str, Any]]] = {}
    for video in latest:
        videos_by_date.setdefault(video.get("date") or "Date not set", []).append(video)
    date_order = sorted((day for day in videos_by_date if day != "Date not set"), reverse=True)
    if "Date not set" in videos_by_date:
        date_order.append("Date not set")
    date_groups = [{"date": day, "videos": videos_by_date[day]} for day in date_order]

    subject_counts: Dict[str, int] = {}
    subject_weights: Dict[str, int] = {}
    for video in videos:
        subject = video.get("subject") or "General"
        subject_counts[subject] = subject_counts.get(subject, 0) + 1
        weight = 1
        if video.get("featured"):
            weight += 10
        if video.get("trending"):
            weight += 6
        weight += max(0, int(video.get("views") or 0) // 10)
        subject_weights[subject] = subject_weights.get(subject, 0) + weight

    subjects = [
        {"name": name, "count": subject_counts[name], "weight": subject_weights.get(name, 0)}
        for name in subject_counts.keys()
    ]
    subjects.sort(key=lambda item: (-item["weight"], -item["count"], item["name"]))
    for subject in subjects:
        subject.pop("weight", None)

    categories: Dict[str, int] = {}
    folders: Dict[str, int] = {}
    folder_tree_map: Dict[str, Dict[str, Any]] = {}
    for video in videos:
        category = video.get("category") or "General"
        categories[category] = categories.get(category, 0) + 1
        folder = video.get("folder") or "General"
        folders[folder] = folders.get(folder, 0) + 1
        folder_tree_map.setdefault(folder, {"name": folder, "count": 0, "subfolders": {}, "thumbnails": []})
        folder_tree_map[folder]["count"] += 1
        thumbnail_url = video.get("thumbnail_url")
        if thumbnail_url and len(folder_tree_map[folder]["thumbnails"]) < 4:
            folder_tree_map[folder]["thumbnails"].append(thumbnail_url)
        subfolder = video.get("subfolder") or ""
        if subfolder:
            subfolders = folder_tree_map[folder]["subfolders"]
            subfolder_data = subfolders.setdefault(subfolder, {"count": 0, "thumbnails": []})
            subfolder_data["count"] += 1
            if thumbnail_url and len(subfolder_data["thumbnails"]) < 4:
                subfolder_data["thumbnails"].append(thumbnail_url)

    playlists = []
    playlist_map = {}
    for video in videos:
        subject_name = video.get("subject") or "General"
        folder_name = video.get("folder") or "General"
        subfolder_name = video.get("subfolder") or ""
        default_name = f"{subject_name} / {folder_name}" + (f" / {subfolder_name}" if subfolder_name else "")
        playlist_name = video.get("playlist") or default_name
        playlist_map.setdefault(playlist_name, []).append(video)
    for playlist_name, subject_videos in sorted(playlist_map.items(), key=lambda item: item[0].lower()):
        first_item = subject_videos[0]
        has_custom_order = any(int(item.get("sort_order") or 0) for item in subject_videos)
        subject_videos_sorted = sorted(
            subject_videos,
            key=lambda item: (int(item.get("sort_order") or 0), item.get("timestamp", "")),
            reverse=not has_custom_order,
        )
        playlists.append({
            "name": playlist_name,
            "subject": first_item.get("subject") or "General",
            "folder": first_item.get("folder") or "General",
            "subfolder": first_item.get("subfolder") or "",
            "count": len(subject_videos),
            "videos": subject_videos_sorted[:6],
        })

    return {
        "videos": filtered,
        "date_groups": date_groups,
        "featured": featured[:6],
        "latest": latest[:8],
        "trending": trending[:8],
        "subjects": subjects,
        "categories": [
            {"name": name, "count": count}
            for name, count in sorted(categories.items(), key=lambda item: (-item[1], item[0]))
        ],
        "folders": [
            {"name": name, "count": count}
            for name, count in sorted(folders.items(), key=lambda item: (-item[1], item[0]))
        ],
        "folder_tree": [
            {
                "name": name,
                "count": data["count"],
                "thumbnails": data["thumbnails"],
                "subfolders": [
                    {
                        "name": subfolder,
                        "count": subfolder_data["count"],
                        "thumbnails": subfolder_data["thumbnails"],
                    }
                    for subfolder, subfolder_data in sorted(
                        data["subfolders"].items(),
                        key=lambda item: (-item[1]["count"], item[0]),
                    )
                ],
            }
            for name, data in sorted(folder_tree_map.items(), key=lambda item: (-item[1]["count"], item[0]))
        ],
        "playlists": playlists[:8],
        "filter_summary": {
            "subject": subject_param if subject_param else "",
            "date": date_param if date_param else "",
            "q": query_param if query_param else "",
            "folder": folder_param if folder_param else "",
            "subfolder": subfolder_param if subfolder_param else "",
            "playlist": playlist_param if playlist_param else "",
            "media_type": media_type_param if media_type_param else "",
        },
    }
