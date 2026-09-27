"""storage.py — settings / playlist / history / cache as .dpj, plus legacy migrate."""
from __future__ import annotations

import json
import os
import re
import shutil

from core import (
    APP_VERSION,
    TIME_FORMAT_MM_SS,
    TIME_FORMAT_MM_SS_CC,
    app_dir,
    data_path,
    log,
)

SETTINGS_FILE = data_path("settings.dpj")
PLAYLIST_FILE = data_path("play_list.dpj")
HISTORY_FILE = data_path("play_history.dpj")
CACHE_FILE = data_path("cache.dpj")

BACKGROUND_DIR = os.path.join(app_dir(), "Background")
CUSTOM_BACKGROUND_FILENAME = "custom_background.png"
BG_MAX_BYTES = 5 * 1024 * 1024
BG_MAX_DIM = 3840

# legacy names (app root and data/)
_LEGACY = [
    os.path.join(app_dir(), "settings.dpst"),
    os.path.join(app_dir(), "play_list.dppls"),
    os.path.join(app_dir(), "play_history_counts.dpphc"),
    os.path.join(app_dir(), "cache.dpch"),
    data_path("settings.dpst"),
    data_path("play_list.dppls"),
    data_path("play_history_counts.dpphc"),
    data_path("cache.dpch"),
]

OLD_CACHE_JSON = os.path.join(app_dir(), "Cache.json")
OLD_CACHE_ALT = os.path.join(app_dir(), "Cache_old2.json")
OLD_DATA_JSON = os.path.join(app_dir(), "data.json")
OLD_DATA_JSON_ALT = os.path.join(app_dir(), "data_old2.json")
OLD_DATA_TXT = os.path.join(app_dir(), "data.txt")
OLD_DATA_TXT_ALT = os.path.join(app_dir(), "data_old2.txt")
OLD_LIST_TXT = os.path.join(app_dir(), "list.txt")
OLD_LIST_TXT_ALT = os.path.join(app_dir(), "list_old2.txt")
OLD_LOVE_TXT = os.path.join(app_dir(), "love.txt")
OLD_LOVE_TXT_ALT = os.path.join(app_dir(), "love_old2.txt")

DEFAULT_SETTINGS = {
    "version": APP_VERSION,
    "theme_index": 0,
    "show_play_counts": True,
    "log_enabled": True,
    "log_level": 20,
    "show_duration": True,
    "audio_level_mode": "all",
    "show_cover_art": True,
    "show_audio_level": False,
    "audio_level_source": "file",
    "loop_mode": 0,
    "volume": 50,
    "window_mode": 0,
    "background_mode": "transparent",
    "custom_background_path": "",
    "always_on_top": False,
    "time_format": TIME_FORMAT_MM_SS_CC,
    "output_device": "",
    "show_advanced_audio": False,
    "engine_mode": "auto",
}


def _safe_read_json(path):
    if not os.path.exists(path):
        return None
    for enc in ("utf-8-sig", "utf-8", "gbk", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                data = json.load(f)
            if enc != "utf-8-sig":
                log(f"[Data] Read {path} using {enc}", 20)
            return data
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError as e:
            log(f"[Data] JSON parse error in {path}: {e}", 40)
            return None
        except Exception as e:
            log(f"[Data] Failed to read {path}: {e}", 40)
            return None
    log(f"[Data] Could not decode {path}", 40)
    return None


def _safe_write_json(path, payload):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        os.replace(tmp, path)
        return True
    except Exception as e:
        log(f"[Data] Failed to write {path}: {e}", 40)
        return False


def _rename_with_fallback(src, dst):
    if not os.path.exists(src):
        return False
    final = dst
    if os.path.exists(final):
        i = 2
        while os.path.exists(f"{dst}.{i}"):
            i += 1
        final = f"{dst}.{i}"
    try:
        os.rename(src, final)
        log(f"[Migrate] Renamed {src} -> {final}", 20)
        return True
    except Exception as e:
        log(f"[Migrate] Failed to rename {src}: {e}", 30)
        return False


def load_settings():
    data = _safe_read_json(SETTINGS_FILE)
    if not isinstance(data, dict):
        return dict(DEFAULT_SETTINGS)
    for k, v in DEFAULT_SETTINGS.items():
        if k not in data:
            data[k] = v
    if data.get("engine_mode") in ("vlc", "bass", "normal", None):
        data["engine_mode"] = "auto"
    if not data.get("output_device"):
        data["output_device"] = data.get("vlc_device") or data.get("bass_device") or ""
    data["version"] = APP_VERSION
    if data.get("time_format") not in (TIME_FORMAT_MM_SS, TIME_FORMAT_MM_SS_CC):
        data["time_format"] = TIME_FORMAT_MM_SS_CC
    return data


def save_settings(settings):
    settings = dict(settings)
    settings["version"] = APP_VERSION
    return _safe_write_json(SETTINGS_FILE, settings)


def load_playlist_data():
    data = _safe_read_json(PLAYLIST_FILE)
    if not isinstance(data, dict):
        return {"source_paths": [], "favorites": {}}

    source_paths = data.get("source_paths")
    if source_paths is None:
        source_paths = data.get("list", [])
        if source_paths:
            log("[Data] play_list uses legacy key 'list' -> source_paths", 20)

    favorites = data.get("favorites")
    if favorites is None:
        favorites = data.get("love_lists", {})
        if favorites:
            log("[Data] play_list uses legacy key 'love_lists' -> favorites", 20)

    return {
        "source_paths": source_paths or [],
        "favorites": favorites or {},
    }


def save_playlist_data(source_paths, favorites):
    return _safe_write_json(PLAYLIST_FILE, {
        "version": APP_VERSION,
        "source_paths": source_paths,
        "favorites": favorites,
    })


def load_history_data():
    data = _safe_read_json(HISTORY_FILE)
    if not isinstance(data, dict):
        return {"history": [], "play_counts": {}}
    return {
        "history": data.get("history", []) or [],
        "play_counts": data.get("play_counts", {}) or {},
    }


def save_history_data(history_paths, play_counts):
    return _safe_write_json(HISTORY_FILE, {
        "version": APP_VERSION,
        "history": history_paths[:100] if history_paths else [],
        "play_counts": play_counts if play_counts else {},
    })


def load_cache():
    data = _safe_read_json(CACHE_FILE)
    if isinstance(data, dict):
        return data
    for fallback in (OLD_CACHE_JSON, OLD_CACHE_ALT, os.path.join(app_dir(), "cache.dpch")):
        data = _safe_read_json(fallback)
        if isinstance(data, dict):
            log(f"[Migrate] Loaded cache from {fallback}", 20)
            save_cache(data)
            return data
    return {}


def save_cache(cache_dict):
    return _safe_write_json(CACHE_FILE, cache_dict)


def _parse_old_data_txt_path(path):
    source_paths = []
    favorites = {}
    history_paths = []
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        log(f"[Migrate] Cannot read {path}: {e}", 30)
        return source_paths, favorites, history_paths

    current_section = None
    current_items = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("list = ["):
            start = line.index("[") + 1
            end = line.index("]")
            source_paths = [p.strip() for p in line[start:end].split("|") if p.strip()]
            current_section = None
            continue
        m = re.match(r"love_list(\d{3}) = \[", line)
        if m:
            current_section = m.group(1)
            current_items = []
            if line.rstrip().endswith("]"):
                inner = line[line.index("[") + 1:line.rindex("]")]
                paths = [p.strip().rstrip("|") for p in inner.split("\n") if p.strip()]
                favorites[current_section] = [p for p in paths if p]
                current_section = None
            continue
        if line.startswith("history = ["):
            current_section = "history"
            current_items = []
            if line.rstrip().endswith("]"):
                inner = line[line.index("[") + 1:line.rindex("]")]
                paths = [p.strip().rstrip("|") for p in inner.split("\n") if p.strip()]
                history_paths = [p for p in paths if p]
                current_section = None
            continue
        if current_section:
            if line == "]":
                if current_section == "history":
                    history_paths = current_items
                else:
                    favorites[current_section] = current_items
                current_section = None
                current_items = []
            else:
                p = line.rstrip("|").strip()
                if p:
                    current_items.append(p)
    return source_paths, favorites, history_paths


def _parse_legacy_txt_paths(list_path, love_path):
    source_paths = []
    favorites = {}
    if list_path and os.path.exists(list_path):
        with open(list_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            for line in f:
                line = line.strip().rstrip(",").strip()
                if line:
                    source_paths.append(line)
    if love_path and os.path.exists(love_path):
        love_paths = []
        with open(love_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line:
                    love_paths.append(line)
        if love_paths:
            favorites["001"] = love_paths
    return source_paths, favorites, []


def migrate_old_files_if_needed():
    log(f"[Migrate] app_dir = {app_dir()}", 20)
    log(f"[Migrate] SETTINGS_FILE = {SETTINGS_FILE}", 20)

    new_settings_exists = os.path.exists(SETTINGS_FILE)
    new_playlist_exists = os.path.exists(PLAYLIST_FILE)
    new_history_exists = os.path.exists(HISTORY_FILE)

    # copy leftover .dpst / .dppls sitting next to the exe (or in data/) into data/*.dpj
    mapping = {
        "settings.dpst": SETTINGS_FILE,
        "play_list.dppls": PLAYLIST_FILE,
        "play_history_counts.dpphc": HISTORY_FILE,
        "cache.dpch": CACHE_FILE,
    }
    for old_name, new_path in mapping.items():
        for candidate in (
            os.path.join(app_dir(), old_name),
            os.path.join(app_dir(), "data", old_name),
        ):
            if not os.path.exists(candidate):
                continue
            if not os.path.exists(new_path):
                data = _safe_read_json(candidate)
                if isinstance(data, dict):
                    _safe_write_json(new_path, data)
                    log(f"[Migrate] {candidate} -> {new_path}", 20)
            _rename_with_fallback(candidate, candidate + ".bak")

    new_settings_exists = os.path.exists(SETTINGS_FILE)
    new_playlist_exists = os.path.exists(PLAYLIST_FILE)
    new_history_exists = os.path.exists(HISTORY_FILE)
    if new_settings_exists and new_playlist_exists and new_history_exists:
        log("[Migrate] All primary data files exist", 20)
        return load_settings()

    old_data = None
    for candidate in (OLD_DATA_JSON, OLD_DATA_JSON_ALT):
        if os.path.exists(candidate):
            d = _safe_read_json(candidate)
            if isinstance(d, dict):
                old_data = d
                log(f"[Migrate] Loaded old data from {candidate}", 20)
                break

    legacy_sources, legacy_favorites, legacy_hist = [], {}, []
    if old_data is None:
        for candidate in (OLD_DATA_TXT, OLD_DATA_TXT_ALT):
            if os.path.exists(candidate):
                legacy_sources, legacy_favorites, legacy_hist = _parse_old_data_txt_path(candidate)
                if legacy_sources or legacy_favorites or legacy_hist:
                    log(f"[Migrate] Loaded legacy data from {candidate}", 20)
                    break
        if not legacy_sources and not legacy_favorites:
            list_src = next((c for c in (OLD_LIST_TXT, OLD_LIST_TXT_ALT) if os.path.exists(c)), None)
            love_src = next((c for c in (OLD_LOVE_TXT, OLD_LOVE_TXT_ALT) if os.path.exists(c)), None)
            if list_src or love_src:
                legacy_sources, legacy_favorites, legacy_hist = _parse_legacy_txt_paths(list_src, love_src)

    if old_data:
        source_paths = old_data.get("list", []) or []
        favorites = old_data.get("love_lists", {}) or {}
        history_paths = old_data.get("history", []) or []
        play_counts = old_data.get("play_counts", {}) or {}
        settings = dict(DEFAULT_SETTINGS)
        for key in DEFAULT_SETTINGS:
            if key in old_data:
                settings[key] = old_data[key]
        settings["engine_mode"] = "auto"
        settings["output_device"] = old_data.get("output_device") or old_data.get("vlc_device") or ""
    else:
        source_paths = legacy_sources
        favorites = legacy_favorites
        history_paths = legacy_hist
        play_counts = {}
        settings = dict(DEFAULT_SETTINGS)

    if not new_settings_exists:
        save_settings(settings)
    if not new_playlist_exists:
        save_playlist_data(source_paths, favorites)
    if not new_history_exists:
        save_history_data(history_paths, play_counts)

    for old_name in (OLD_DATA_JSON, OLD_DATA_TXT, OLD_LIST_TXT, OLD_LOVE_TXT):
        if os.path.exists(old_name):
            if old_name.endswith(".json"):
                new_name = old_name.replace(".json", "_old2.json")
            else:
                new_name = old_name.replace(".txt", "_old2.txt")
            _rename_with_fallback(old_name, new_name)

    return load_settings()
