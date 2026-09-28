import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from flask import request, session, redirect, render_template, abort, jsonify
from safe_repo.web.study import load_catalog_entries
from safe_repo.core.media_links import get_stream_cache_stats

ADMIN_USERNAME = os.environ.get("STUDY_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("STUDY_ADMIN_PASSWORD", "admin123")
ROLE_LEVELS = {"viewer": 1, "editor": 2, "owner": 3}


def _get_catalog_path(catalog_path: Optional[str] = None) -> str:
    if catalog_path:
        return str(Path(catalog_path).expanduser())
    env_path = os.environ.get("STREAM_CATALOG_FILE")
    if env_path:
        return str(Path(env_path).expanduser())
    return str(Path(__file__).resolve().parent.parent / "core" / "mongo" / "stream_catalog.json")


def _load_entries(catalog_path: Optional[str] = None) -> List[Dict[str, Any]]:
    return load_catalog_entries(catalog_path)


def _save_entries(entries: List[Dict[str, Any]], catalog_path: Optional[str] = None) -> None:
    path = Path(_get_catalog_path(catalog_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def is_admin() -> bool:
    return bool(session.get("is_admin"))


def require_admin(minimum_role="editor"):
    if not is_admin():
        abort(403)
    role = session.get("admin_role", "owner")
    if ROLE_LEVELS.get(role, 0) < ROLE_LEVELS.get(minimum_role, ROLE_LEVELS["owner"]):
        abort(403)


def _authenticate_admin(username, password):
    configured = os.environ.get("STUDY_ADMIN_USERS", "").strip()
    if configured:
        try:
            accounts = json.loads(configured)
        except json.JSONDecodeError:
            return None
        account = accounts.get(username) if isinstance(accounts, dict) else None
        if isinstance(account, dict) and account.get("password") == password:
            role = str(account.get("role") or "viewer").lower()
            return role if role in ROLE_LEVELS else "viewer"
        return None
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return "owner"
    return None


def admin_login_view():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        role = _authenticate_admin(username, password)
        if role:
            session["is_admin"] = True
            session["admin_role"] = role
            return redirect("/admin/dashboard")
        error = "Invalid credentials"
    else:
        error = None
    
    return render_template('admin/login.html', error=error)


def admin_dashboard_view():
    require_admin("viewer")
    entries = _load_entries()
    
    # Get unique folders and count
    folders = {}
    completion_count = 0
    for entry in entries:
        folder = entry.get('folder', 'General')
        if folder not in folders:
            folders[folder] = 0
        folders[folder] += 1
        completion_count += int(entry.get("completion_count") or 0)
    
    return render_template('admin/dashboard.html', entries=entries, folders=folders, completion_count=completion_count, admin_role=session.get("admin_role", "owner"), cache_stats=get_stream_cache_stats())


def edit_entry_view(token):
    require_admin()
    entries = _load_entries()
    entry = next((item for item in entries if str(item.get("token")) == str(token)), None)
    if not entry:
        abort(404)
    folder_options = sorted({str(item.get("folder") or "General") for item in entries})
    subfolder_options = sorted({str(item.get("subfolder") or "") for item in entries if item.get("subfolder")})
    edit_context = {"entry": entry, "admin_role": session.get("admin_role", "owner"), "folder_options": folder_options, "subfolder_options": subfolder_options}

    if request.method == "POST":
        subtitles = (request.form.get("subtitles") or "").strip()
        if len(subtitles) > 262144 or (subtitles and not subtitles.startswith("WEBVTT")):
            return render_template("admin/edit.html", **edit_context, error="Subtitles must be valid WEBVTT text under 256 KB."), 400
        approval_values = request.form.getlist("approved")
        approved = "on" in approval_values
        if approval_values and approved != bool(entry.get("approved", True)):
            require_admin("owner")
        try:
            sort_order = int(request.form.get("sort_order") or 0)
        except ValueError:
            return render_template("admin/edit.html", **edit_context, error="Playlist order must be a whole number."), 400
        entry["title"] = (request.form.get("title") or "Untitled").strip() or "Untitled"
        entry["subject"] = (request.form.get("subject") or "General").strip() or "General"
        entry["category"] = (request.form.get("category") or "General").strip() or "General"
        entry["folder"] = (request.form.get("folder") or "General").strip() or "General"
        entry["subfolder"] = (request.form.get("subfolder") or "").strip()
        entry["description"] = (request.form.get("description") or "").strip()
        entry["transcript"] = (request.form.get("transcript") or "").strip()[:200000]
        entry["subtitles"] = subtitles
        entry["playlist"] = (request.form.get("playlist") or "").strip()[:120]
        entry["sort_order"] = sort_order
        if approval_values:
            entry["approved"] = approved
        _save_entries(entries)
        return redirect("/admin/dashboard")

    return render_template('admin/edit.html', **edit_context)


def admin_logout_view():
    session.pop("is_admin", None)
    return redirect("/admin/login")


def toggle_featured_view(token):
    require_admin()
    entries = _load_entries()
    for entry in entries:
        if str(entry.get("token")) == str(token):
            entry["featured"] = not bool(entry.get("featured"))
            break
    _save_entries(entries)
    return redirect("/admin/dashboard")


def toggle_trending_view(token):
    require_admin()
    entries = _load_entries()
    for entry in entries:
        if str(entry.get("token")) == str(token):
            entry["trending"] = not bool(entry.get("trending"))
            break
    _save_entries(entries)
    return redirect("/admin/dashboard")


def delete_entry_view(token):
    require_admin("owner")
    entries = _load_entries()
    entries = [entry for entry in entries if str(entry.get("token")) != str(token)]
    _save_entries(entries)
    return redirect("/admin/dashboard")


def bulk_action_view():
    require_admin()
    data = request.get_json(silent=True) or {}
    action = str(data.get("action") or "").strip()
    tokens = data.get("tokens")
    if action not in {"featured", "trending", "delete", "approve", "unapprove", "folder", "subject", "playlist", "sort_order"}:
        return jsonify({"success": False, "error": "Unsupported bulk action"}), 400
    if not isinstance(tokens, list) or not tokens:
        return jsonify({"success": False, "error": "Select at least one item"}), 400

    selected_tokens = {str(token).strip() for token in tokens if str(token).strip()}
    if action in {"delete", "approve", "unapprove"}:
        require_admin("owner")
    entries = _load_entries()
    if action == "delete":
        remaining = [entry for entry in entries if str(entry.get("token")) not in selected_tokens]
        updated_count = len(entries) - len(remaining)
        entries = remaining
    elif action in {"featured", "trending"}:
        updated_count = 0
        for entry in entries:
            if str(entry.get("token")) in selected_tokens:
                entry[action] = not bool(entry.get(action))
                updated_count += 1
    else:
        value = data.get("value")
        if action == "sort_order":
            try:
                value = int(value or 0)
            except (TypeError, ValueError):
                return jsonify({"success": False, "error": "sort_order must be an integer"}), 400
        else:
            value = str(value or "").strip()[:120]
        updated_count = 0
        for entry in entries:
            if str(entry.get("token")) in selected_tokens:
                if action in {"approve", "unapprove"}:
                    entry["approved"] = action == "approve"
                else:
                    entry[action] = value
                updated_count += 1

    _save_entries(entries)
    return jsonify({"success": True, "action": action, "updated": updated_count})
