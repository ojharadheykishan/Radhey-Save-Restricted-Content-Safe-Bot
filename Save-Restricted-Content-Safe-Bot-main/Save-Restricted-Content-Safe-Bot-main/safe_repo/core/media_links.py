import json
import os
import re
import shutil
import uuid
import hashlib
import logging
from datetime import datetime as dt, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from urllib.parse import urlparse, urlunparse

from safe_repo.core import object_storage

logger = logging.getLogger(__name__)
_STREAM_CACHE_DIR = None
_WARNED_UNMOUNTED_RAILWAY_DATA = False
try:
    _CLEANUP_MAX_AGE_HOURS = max(1, int(os.environ.get("STREAM_CACHE_MAX_AGE_HOURS", "7")))
except (TypeError, ValueError):
    _CLEANUP_MAX_AGE_HOURS = 7


def _get_shared_repo_dir():
    configured_dir = os.environ.get("APP_DATA_DIR", "").strip()
    legacy_dir = Path(__file__).resolve().parent / "mongo"
    if not configured_dir:
        return legacy_dir

    global _WARNED_UNMOUNTED_RAILWAY_DATA
    data_dir = Path(configured_dir).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    if os.environ.get("RAILWAY_ENVIRONMENT") and not os.path.ismount(data_dir) and not _WARNED_UNMOUNTED_RAILWAY_DATA:
        logger.error("APP_DATA_DIR=%s is not a mounted Railway volume; media catalog and files may be lost on redeploy", data_dir)
        _WARNED_UNMOUNTED_RAILWAY_DATA = True

    for filename in ("stream_catalog.json", "stream_links.txt"):
        source = legacy_dir / filename
        destination = data_dir / filename
        if source.is_file() and not destination.exists():
            shutil.copy2(source, destination)

    legacy_cache = legacy_dir.parent / "stream_cache"
    persistent_cache = data_dir / "stream_cache"
    if legacy_cache.is_dir() and not persistent_cache.exists():
        shutil.copytree(legacy_cache, persistent_cache)
    return data_dir


def _get_cache_dir(cache_dir=None):
    global _STREAM_CACHE_DIR

    if cache_dir:
        _STREAM_CACHE_DIR = str(Path(cache_dir).expanduser())
        return _STREAM_CACHE_DIR

    if _STREAM_CACHE_DIR:
        return _STREAM_CACHE_DIR

    env_dir = os.environ.get("STREAM_CACHE_DIR")
    if env_dir:
        _STREAM_CACHE_DIR = str(Path(env_dir).expanduser())
        return _STREAM_CACHE_DIR

    app_data_dir = os.environ.get("APP_DATA_DIR", "").strip()
    if app_data_dir:
        cache_path = _get_shared_repo_dir() / "stream_cache"
        cache_path.mkdir(parents=True, exist_ok=True)
        _STREAM_CACHE_DIR = str(cache_path)
        return _STREAM_CACHE_DIR

    base_dir = Path(__file__).resolve().parent / "stream_cache"
    base_dir.mkdir(parents=True, exist_ok=True)
    _STREAM_CACHE_DIR = str(base_dir)
    return _STREAM_CACHE_DIR


def _get_base_url(base_url=None):
    if base_url:
        return base_url.rstrip("/")

    # Try to get base URL from environment variables
    # Priority order: explicit URLs first, then Render's auto-provided URL, then fallbacks
    env_url = (
        os.environ.get("PUBLIC_BASE_URL", "").strip()
        or os.environ.get("APP_URL", "").strip()
        or os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
        or os.environ.get("RAILWAY_STATIC_URL", "").strip()
        or os.environ.get("BASE_URL", "").strip()
        or os.environ.get("RENDER_EXTERNAL_URL", "").strip()
    )

    if env_url:
        # If user provided a host without scheme, assume https
        if not env_url.startswith(("http://", "https://")):
            env_url = "https://" + env_url

        # Railway's public domain already routes to the assigned internal port.
        # Never expose PORT in public links when a hosted URL is configured.
        port = os.environ.get("PORT") or os.environ.get("RAILWAY_PORT") or os.environ.get("SERVER_PORT")
        parsed = urlparse(env_url)
        is_local_url = parsed.hostname in {"127.0.0.1", "localhost"}
        if port and is_local_url:
            try:
                port_int = int(str(port))
            except Exception:
                port_int = None
            if port_int:
                # Only append if URL has no explicit port
                # e.g. https://example.com -> https://example.com:5000
                netloc = parsed.netloc
                if ":" not in netloc:
                    netloc = f"{netloc}:{port_int}"
                    parsed = parsed._replace(netloc=netloc)
                    env_url = urlunparse(parsed)

        return env_url.rstrip("/")

    # Fallback to localhost only if explicitly in development mode
    return "http://127.0.0.1:5000"


def _get_max_stream_file_size_bytes(max_size_mb=None):
    if max_size_mb is not None:
        try:
            return int(max_size_mb) * 1024 * 1024
        except (TypeError, ValueError):
            return 5000 * 1024 * 1024

    env_value = os.environ.get("MAX_STREAM_FILE_SIZE_MB", "5000")
    try:
        return int(env_value) * 1024 * 1024
    except (TypeError, ValueError):
        return 5000 * 1024 * 1024


def _create_media_thumbnail(source_path, output_path):
    """Create a JPEG preview for videos and PDFs when no source thumbnail exists."""
    try:
        if Path(source_path).suffix.lower() == ".pdf":
            import fitz

            with fitz.open(source_path) as document:
                if not document.page_count:
                    return False
                pixmap = document[0].get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
                pixmap.save(str(output_path))
                return output_path.exists() and output_path.stat().st_size > 0

        import cv2

        capture = cv2.VideoCapture(str(source_path))
        if not capture.isOpened():
            capture.release()
            return False
        frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        fps = capture.get(cv2.CAP_PROP_FPS)
        minute_frame = int(fps * 60) if fps > 0 else 0
        if frame_count > minute_frame > 0:
            capture.set(cv2.CAP_PROP_POS_FRAMES, minute_frame)
        elif frame_count > 0:
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_count / 2))
        success, frame = capture.read()
        capture.release()
        if not success or frame is None:
            return False
        height, width = frame.shape[:2]
        scale = min(1, 640 / max(width, height))
        if scale < 1:
            frame = cv2.resize(frame, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
        return bool(cv2.imwrite(str(output_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85]))
    except Exception:
        return False


def _store_stream_thumbnail(source_path, token, cache_path, thumbnail_path=None):
    target = cache_path / f"{token}.thumb.jpg"
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            import cv2

            image = cv2.imread(str(thumbnail_path))
            if image is not None and cv2.imwrite(str(target), image, [cv2.IMWRITE_JPEG_QUALITY, 85]):
                return target
        except Exception:
            pass
    if _create_media_thumbnail(source_path, target):
        return target
    return None


def store_stream_thumbnail(token, source_path):
    """Validate and replace a cached item's thumbnail with an admin-selected image."""
    entry = get_stream_file(token)
    if not entry or not source_path or not os.path.exists(source_path):
        return None
    try:
        import cv2

        image = cv2.imread(str(source_path))
        if image is None:
            return None
        height, width = image.shape[:2]
        scale = min(1, 640 / max(width, height))
        if scale < 1:
            image = cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
        target = Path(entry["file_path"]).parent / f"{token}.thumb.jpg"
        if not cv2.imwrite(str(target), image, [cv2.IMWRITE_JPEG_QUALITY, 88]):
            return None
        metadata = get_stream_entry(token) or {}
        thumbnail_key = metadata.get("thumbnail_storage_key")
        if thumbnail_key and object_storage.is_configured():
            object_storage.upload_file(thumbnail_key, target, "image/jpeg")
        return str(target)
    except Exception:
        return None


def get_file_sha256(source_path):
    digest = hashlib.sha256()
    with open(source_path, "rb") as media_file:
        for chunk in iter(lambda: media_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_pdf_text(source_path, max_chars=200000):
    """Extract PDF text, using local Tesseract OCR for scanned pages when installed."""
    if Path(source_path).suffix.lower() != ".pdf":
        return ""
    try:
        import fitz

        with fitz.open(source_path) as document:
            extracted = []
            extracted_length = 0
            for page in document:
                text = page.get_text()
                if not text.strip():
                    try:
                        import pytesseract
                        from PIL import Image

                        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csRGB, alpha=False)
                        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                        text = pytesseract.image_to_string(image, lang=os.environ.get("PDF_OCR_LANG", "eng"))
                    except Exception:
                        text = ""
                extracted.append(text)
                extracted_length += len(text)
                if extracted_length >= max_chars:
                    break
            return "\n".join(extracted)[:max_chars]
    except Exception:
        return ""


def find_duplicate_media(source_path, catalog_path=None):
    """Find an existing catalog record with the same SHA-256 content hash."""
    if not source_path or not os.path.isfile(source_path):
        return None
    content_hash = get_file_sha256(source_path)
    for entry in read_stream_entries(catalog_path):
        if entry.get("content_hash") == content_hash:
            return entry
    return None


def get_stream_cache_stats(cache_dir=None):
    cache_path = Path(_get_cache_dir(cache_dir))
    media_files = 0
    total_bytes = 0
    if cache_path.exists():
        for path in cache_path.iterdir():
            if path.is_file():
                try:
                    total_bytes += path.stat().st_size
                    if not path.name.endswith(".thumb.jpg"):
                        media_files += 1
                except OSError:
                    continue
    try:
        quota_bytes = int(float(os.environ.get("STREAM_CACHE_MAX_GB", "0")) * 1024 ** 3)
    except (TypeError, ValueError):
        quota_bytes = 0
    return {
        "media_files": media_files,
        "used_bytes": total_bytes,
        "quota_bytes": max(0, quota_bytes),
        "retention_hours": _CLEANUP_MAX_AGE_HOURS,
    }


def save_stream_file(source_path, base_url=None, cache_dir=None, max_size_mb=None, thumbnail_path=None) -> Optional[Dict[str, str]]:
    """Copy a local media file into a public cache directory and return stream URLs."""
    import logging
    logger = logging.getLogger(__name__)
    
    if not source_path or not os.path.exists(source_path):
        logger.warning(f"save_stream_file: source_path does not exist: {source_path}")
        return None

    max_bytes = _get_max_stream_file_size_bytes(max_size_mb)
    file_size = os.path.getsize(source_path)
    
    if file_size > max_bytes:
        logger.warning(f"save_stream_file: file too large ({file_size} bytes, max {max_bytes} bytes): {source_path}")
        return None

    try:
        cache_path = Path(_get_cache_dir(cache_dir))
        cache_path.mkdir(parents=True, exist_ok=True)
        cache_stats = get_stream_cache_stats(str(cache_path))
        if cache_stats["quota_bytes"] and cache_stats["used_bytes"] + file_size > cache_stats["quota_bytes"]:
            logger.warning("save_stream_file: configured cache quota would be exceeded")
            return None

        token = uuid.uuid4().hex
        safe_name = os.path.basename(source_path).replace(" ", "_")
        target_path = cache_path / f"{token}_{safe_name}"
        shutil.copy2(source_path, target_path)
        stored_thumbnail = _store_stream_thumbnail(source_path, token, cache_path, thumbnail_path)
        storage_key = None
        thumbnail_storage_key = None
        if object_storage.is_configured():
            import mimetypes

            storage_key = object_storage.object_key("media", f"{token}_{safe_name}")
            object_storage.upload_file(storage_key, target_path, mimetypes.guess_type(safe_name)[0])
            if stored_thumbnail:
                thumbnail_storage_key = object_storage.object_key("thumbnails", f"{token}.thumb.jpg")
                object_storage.upload_file(thumbnail_storage_key, stored_thumbnail, "image/jpeg")
        content_hash = get_file_sha256(source_path)
        pdf_text = extract_pdf_text(source_path)

        base_url = _get_base_url(base_url)
        result = {
            "token": token,
            "file_path": str(target_path),
            "stream_url": f"{base_url}/stream/{token}",
            "player_url": f"{base_url}/player/{token}",
            "content_hash": content_hash,
        }
        if storage_key:
            result["storage_key"] = storage_key
        if thumbnail_storage_key:
            result["thumbnail_storage_key"] = thumbnail_storage_key
        if pdf_text:
            result["pdf_text"] = pdf_text
        if stored_thumbnail:
            result["thumbnail_url"] = f"{base_url}/thumbnail/{token}"
        logger.info(f"save_stream_file: successfully saved {source_path} to {target_path} with URLs: {result['stream_url']}")
        return result
    except Exception as e:
        logger.error(f"save_stream_file: error copying file {source_path} to cache: {e}", exc_info=True)
        return None


def get_archive_path(archive_path=None):
    """Return the path used for storing generated stream links."""
    if archive_path:
        return str(Path(archive_path).expanduser())

    env_path = os.environ.get("STREAM_LINKS_FILE")
    if env_path:
        return str(Path(env_path).expanduser())

    repo_dir = _get_shared_repo_dir()
    repo_dir.mkdir(parents=True, exist_ok=True)
    return str(repo_dir / "stream_links.txt")


def get_catalog_path(catalog_path=None):
    """Return the path used for storing structured stream-link catalog entries."""
    if catalog_path:
        return str(Path(catalog_path).expanduser())

    env_path = os.environ.get("STREAM_CATALOG_FILE")
    if env_path:
        return str(Path(env_path).expanduser())

    repo_dir = _get_shared_repo_dir()
    repo_dir.mkdir(parents=True, exist_ok=True)
    return str(repo_dir / "stream_catalog.json")


def append_stream_link(player_url, stream_url, label="stream", archive_path=None, catalog_path=None, subject=None, description=None, title=None, token=None, thumbnail_url=None, media_type="video", content_hash=None, pdf_text=None, transcript="", subtitles="", playlist="", sort_order=0, approved=True, folder=None, subfolder=None, category=None, media_date=None, storage_key=None, thumbnail_storage_key=None):
    """Append a generated stream link to a text archive file and save structured metadata."""
    archive_file = Path(get_archive_path(archive_path))
    archive_file.parent.mkdir(parents=True, exist_ok=True)
    stamp = dt.now().strftime("%Y-%m-%d %H:%M:%S")
    with archive_file.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {label}\n")
        handle.write(f"Player: {player_url}\n")
        handle.write(f"Stream: {stream_url}\n\n")
    if catalog_path is None and object_storage.is_configured():
        object_storage.upload_file(object_storage.object_key("catalog", "stream_links.txt"), archive_file, "text/plain; charset=utf-8")

    catalog_file = Path(get_catalog_path(catalog_path))
    catalog_file.parent.mkdir(parents=True, exist_ok=True)
    entries = read_stream_entries(catalog_path=catalog_path)

    entry = {
        "timestamp": stamp,
        "date": str(media_date or dt.now().strftime("%Y-%m-%d"))[:10],
        "label": label,
        "subject": subject or "General",
        "category": category or "General",
        "folder": folder or "",
        "subfolder": subfolder or "",
        "description": description or "",
        "title": title or (subject or "Untitled"),
        "token": token or os.path.basename(player_url).split("/")[-1],
        "player_url": player_url,
        "stream_url": stream_url,
        "thumbnail_url": thumbnail_url or "",
        "storage_key": storage_key or "",
        "thumbnail_storage_key": thumbnail_storage_key or "",
        "media_type": media_type or "video",
        "content_hash": content_hash or "",
        "pdf_text": (pdf_text or "")[:200000],
        "transcript": transcript or "",
        "subtitles": subtitles or "",
        "playlist": playlist or "",
        "sort_order": int(sort_order or 0),
        "approved": bool(approved),
    }
    entries.append(entry)
    write_stream_entries(entries, catalog_path=catalog_path)

    return str(archive_file)


def _mongo_catalog_coll():
    try:
        from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available
        if not is_mongo_available():
            return None
        db = get_mongo_db()
        if db is None:
            return None
        return db["stream_catalog"]
    except Exception:
        return None


async def read_stream_entries_async(catalog_path=None):
    """Read structured stream-link entries from MongoDB (primary) or catalog file."""
    coll = _mongo_catalog_coll()
    if coll is not None:
        docs = await coll.find({}).sort("timestamp", -1).to_list(length=100000)
        entries = []
        for doc in docs:
            doc.pop("_id", None)
            entries.append(doc)
        if entries:
            return entries

    return read_stream_entries(catalog_path)


async def _mongo_write_catalog(entries):
    """Write all catalog entries to MongoDB, replacing existing documents."""
    coll = _mongo_catalog_coll()
    if coll is None:
        return
    await coll.delete_many({})
    if entries:
        try:
            await coll.insert_many(entries, ordered=False)
        except Exception:
            for entry in entries:
                try:
                    await coll.insert_one(entry)
                except Exception:
                    pass


async def write_stream_entries_async(entries, catalog_path=None):
    """Write catalog entries to MongoDB (primary) and local JSON (backup)."""
    coll = _mongo_catalog_coll()
    if coll is not None:
        await coll.delete_many({})
        if entries:
            try:
                await coll.insert_many(entries, ordered=False)
            except Exception:
                for entry in entries:
                    try:
                        await coll.insert_one(entry)
                    except Exception:
                        pass

    write_stream_entries(entries, catalog_path=catalog_path)


def read_stream_entries(catalog_path=None):
    """Read structured stream-link entries from MongoDB (primary) or catalog file."""
    if catalog_path is None:
        coll = _mongo_catalog_coll()
        if coll is not None:
            try:
                from safe_repo.core.mongo.mongo_client import _run_async as _run
                docs = _run(coll.find({}).sort("timestamp", -1).to_list(length=100000))
                entries = []
                for doc in docs:
                    doc.pop("_id", None)
                    entries.append(doc)
                if entries:
                    return entries
            except Exception:
                pass

    catalog_file = Path(get_catalog_path(catalog_path))
    if catalog_path is None and object_storage.is_configured():
        key = object_storage.object_key("catalog", "stream_catalog.json")
        remote_data = object_storage.get_bytes(key)
        if remote_data is not None:
            catalog_file.parent.mkdir(parents=True, exist_ok=True)
            catalog_file.write_bytes(remote_data)
            try:
                data = json.loads(remote_data.decode("utf-8"))
                return data if isinstance(data, list) else []
            except (UnicodeDecodeError, json.JSONDecodeError):
                logger.error("Object storage catalog is not valid JSON: %s", key)
                return []

    if not catalog_file.exists():
        return []
    try:
        data = json.loads(catalog_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            if catalog_path is None and object_storage.is_configured():
                object_storage.put_bytes(
                    object_storage.object_key("catalog", "stream_catalog.json"),
                    json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"),
                    "application/json",
                )
            return data
    except Exception:
        pass
    return []


def write_stream_entries(entries, catalog_path=None):
    """Write catalog locally and mirror it to persistent object storage when configured."""
    if catalog_path is None:
        try:
            from safe_repo.core.mongo.mongo_client import is_mongo_available, _run_async as _run
            if is_mongo_available():
                _run(_mongo_write_catalog(entries))
        except Exception:
            pass

    catalog_file = Path(get_catalog_path(catalog_path))
    catalog_file.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(entries, indent=2, ensure_ascii=False).encode("utf-8")
    if catalog_path is None and object_storage.is_configured():
        object_storage.put_bytes(object_storage.object_key("catalog", "stream_catalog.json"), payload, "application/json")
    temporary_file = catalog_file.with_suffix(catalog_file.suffix + ".tmp")
    temporary_file.write_bytes(payload)
    temporary_file.replace(catalog_file)
    return str(catalog_file)


def read_stream_links(archive_path=None):
    """Read the text archive of generated stream links."""
    archive_file = Path(get_archive_path(archive_path))
    if archive_path is None and object_storage.is_configured():
        key = object_storage.object_key("catalog", "stream_links.txt")
        remote_data = object_storage.get_bytes(key)
        if remote_data is not None:
            archive_file.parent.mkdir(parents=True, exist_ok=True)
            archive_file.write_bytes(remote_data)
            return remote_data.decode("utf-8")
        if archive_file.is_file():
            object_storage.upload_file(key, archive_file, "text/plain; charset=utf-8")
    if not archive_file.exists():
        return ""
    return archive_file.read_text(encoding="utf-8")


def get_stream_file(token):
    """Fetch a previously stored stream file by token."""
    if not token:
        return None

    cache_dir = Path(_get_cache_dir())
    cache_dir.mkdir(parents=True, exist_ok=True)

    for path in cache_dir.glob(f"{token}_*"):
        if path.is_file():
            return {"token": token, "file_path": str(path)}

    entry = get_stream_entry(token)
    storage_key = (entry or {}).get("storage_key")
    if storage_key and object_storage.is_configured():
        filename = Path(storage_key).name
        path = cache_dir / filename
        try:
            if object_storage.download_file(storage_key, path):
                return {"token": token, "file_path": str(path), "storage_key": storage_key}
        except Exception:
            logger.exception("Failed to restore media object %s", storage_key)

    return None


def migrate_local_media_to_object_storage():
    """Back up cached media/thumbnail files that still exist in local storage."""
    if not object_storage.is_configured():
        raise RuntimeError("Configure all OBJECT_STORAGE_* settings before running a media backup")

    cache_dir = Path(_get_cache_dir())
    entries = read_stream_entries()
    uploaded = 0
    missing = 0
    changed = False
    for entry in entries:
        token = str(entry.get("token") or "").strip()
        if not token:
            continue
        media_path = next((path for path in cache_dir.glob(f"{token}_*") if path.is_file()), None)
        if not media_path:
            if not entry.get("storage_key"):
                missing += 1
            continue

        if not entry.get("storage_key"):
            media_key = object_storage.object_key("media", media_path.name)
            import mimetypes

            object_storage.upload_file(media_key, media_path, mimetypes.guess_type(media_path.name)[0])
            entry["storage_key"] = media_key
            uploaded += 1
            changed = True

        thumbnail_path = cache_dir / f"{token}.thumb.jpg"
        if thumbnail_path.is_file() and not entry.get("thumbnail_storage_key"):
            thumbnail_key = object_storage.object_key("thumbnails", thumbnail_path.name)
            object_storage.upload_file(thumbnail_key, thumbnail_path, "image/jpeg")
            entry["thumbnail_storage_key"] = thumbnail_key
            changed = True

    if changed:
        write_stream_entries(entries)
    archive_path = Path(get_archive_path())
    if archive_path.is_file():
        object_storage.upload_file(object_storage.object_key("catalog", "stream_links.txt"), archive_path, "text/plain; charset=utf-8")
    return {"uploaded": uploaded, "missing": missing, "total": len(entries)}


def get_stream_entry(token, catalog_path=None):
    """Fetch the catalog metadata entry for a stream token if present."""
    if not token:
        return None

    for entry in read_stream_entries(catalog_path=catalog_path):
        if str(entry.get("token", "")) == str(token):
            return entry
    return None


def get_stream_thumbnail(token):
    """Return a cached thumbnail, generating one for older cached video/PDF files."""
    entry = get_stream_file(token)
    if not entry:
        return None
    cache_path = Path(entry["file_path"]).parent
    thumbnail_path = cache_path / f"{token}.thumb.jpg"
    if thumbnail_path.is_file():
        return str(thumbnail_path)
    entry_meta = get_stream_entry(token)
    thumbnail_key = (entry_meta or {}).get("thumbnail_storage_key")
    if thumbnail_key and object_storage.is_configured():
        try:
            if object_storage.download_file(thumbnail_key, thumbnail_path):
                return str(thumbnail_path)
        except Exception:
            logger.exception("Failed to restore thumbnail object %s", thumbnail_key)
    if _create_media_thumbnail(entry["file_path"], thumbnail_path):
        return str(thumbnail_path)
    return None


def cleanup_old_stream_files(max_age_hours=None, cache_dir=None):
    """Remove cached stream files older than max_age_hours."""
    import logging
    logger = logging.getLogger(__name__)

    if max_age_hours is None:
        try:
            max_age_hours = int(os.environ.get("STREAM_CACHE_MAX_AGE_HOURS", _CLEANUP_MAX_AGE_HOURS))
        except (TypeError, ValueError):
            max_age_hours = _CLEANUP_MAX_AGE_HOURS

    cache_path = Path(_get_cache_dir(cache_dir))
    if not cache_path.exists():
        return 0

    cutoff = dt.now().timestamp() - (max_age_hours * 3600)
    removed = 0

    for path in cache_path.iterdir():
        if not path.is_file():
            continue
        try:
            mtime = path.stat().st_mtime
            if mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        except Exception as e:
            logger.debug(f"Failed to cleanup cache file {path}: {e}")

    if removed:
        logger.info(f"Cleaned up {removed} old stream cache files (older than {max_age_hours}h)")
    return removed


def cleanup_old_catalog_entries(max_age_hours=None, catalog_path=None):
    """Remove catalog entries older than max_age_hours."""
    import logging
    logger = logging.getLogger(__name__)

    if max_age_hours is None:
        max_age_hours = _CLEANUP_MAX_AGE_HOURS

    catalog_file = Path(get_catalog_path(catalog_path))
    if catalog_path is not None and not catalog_file.exists():
        return 0

    cutoff = dt.now() - timedelta(hours=max_age_hours)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    try:
        entries = read_stream_entries(catalog_path=catalog_path)
        original_count = len(entries)
        filtered = []
        for entry in entries:
            ts = entry.get("timestamp", "")
            try:
                entry_time = dt.strptime(ts, "%Y-%m-%d %H:%M:%S")
                if entry_time >= cutoff:
                    filtered.append(entry)
            except Exception:
                filtered.append(entry)

        if len(filtered) < original_count:
            write_stream_entries(filtered, catalog_path=catalog_path)
            logger.info(f"Pruned {original_count - len(filtered)} old catalog entries (older than {max_age_hours}h)")
            return original_count - len(filtered)
    except Exception as e:
        logger.error(f"Failed to cleanup catalog: {e}")
    return 0


def cleanup_old_archive_entries(max_age_hours=None, archive_path=None):
    """Remove old entries from the stream links text archive."""
    import logging
    logger = logging.getLogger(__name__)

    if max_age_hours is None:
        max_age_hours = _CLEANUP_MAX_AGE_HOURS

    archive_file = Path(get_archive_path(archive_path))
    if not archive_file.exists():
        return 0

    cutoff = dt.now() - timedelta(hours=max_age_hours)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    try:
        content = archive_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        kept = []
        current_block = []
        current_ts = None
        entry_pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")

        for line in lines:
            match = entry_pattern.match(line)
            if match:
                ts_str = match.group(1)
                if current_block and current_ts and current_ts >= cutoff_str:
                    kept.extend(current_block)
                    kept.append("")
                current_block = [line]
                current_ts = ts_str
            else:
                current_block.append(line)

        if current_block and current_ts and current_ts >= cutoff_str:
            kept.extend(current_block)
            kept.append("")

        new_content = "\n".join(kept).strip() + "\n" if kept else ""
        if len(new_content) < len(content):
            archive_file.write_text(new_content, encoding="utf-8")
            removed_lines = len(lines) - len(new_content.splitlines())
            logger.info(f"Pruned old archive entries (older than {max_age_hours}h)")
            return removed_lines
    except Exception as e:
        logger.error(f"Failed to cleanup archive: {e}")
    return 0


def cleanup_orphaned_temp_files(max_age_hours=2, work_dir=None):
    """Remove orphaned temp media files from the working directory."""
    import logging
    logger = logging.getLogger(__name__)

    if work_dir is None:
        work_dir = Path.cwd()
    else:
        work_dir = Path(work_dir)

    cutoff = dt.now().timestamp() - (max_age_hours * 3600)
    removed = 0
    patterns = ("stream_",)

    try:
        for path in work_dir.iterdir():
            if not path.is_file():
                continue
            try:
                if any(str(path.name).startswith(p) for p in patterns):
                    mtime = path.stat().st_mtime
                    if mtime < cutoff:
                        path.unlink(missing_ok=True)
                        removed += 1
            except Exception as e:
                logger.debug(f"Failed to cleanup temp file {path}: {e}")
    except Exception as e:
        logger.error(f"Failed to scan work dir for temp files: {e}")

    if removed:
        logger.info(f"Cleaned up {removed} orphaned temp files (older than {max_age_hours}h)")
    return removed


def run_full_cleanup(max_age_hours=None):
    """Run all cleanup tasks. Returns total removed items."""
    if max_age_hours is None:
        max_age_hours = _CLEANUP_MAX_AGE_HOURS
    total = 0
    total += cleanup_old_stream_files(max_age_hours=max_age_hours)
    total += cleanup_old_catalog_entries(max_age_hours=max_age_hours)
    total += cleanup_old_archive_entries(max_age_hours=max_age_hours)
    total += cleanup_orphaned_temp_files(max_age_hours=max(1, max_age_hours // 3))
    return total
