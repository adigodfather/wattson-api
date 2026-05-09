from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)

_client: Optional[Client] = None


def _sb() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if url and key:
            _client = create_client(url, key)
    return _client  # type: ignore[return-value]


class _LazyClient:
    """Proxy that forwards attribute access to the lazily-initialized client."""
    def __getattr__(self, name: str):
        client = _sb()
        if client is None:
            raise RuntimeError("Supabase client not initialised — set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        return getattr(client, name)


supabase = _LazyClient()


# ── Settings cache ────────────────────────────────────────────────────────────

_settings_cache: dict[str, Any] = {}
_settings_ts: float = 0.0
_SETTINGS_TTL = 300  # seconds


def _refresh_settings() -> None:
    global _settings_cache, _settings_ts
    sb = _sb()
    if sb is None:
        return
    try:
        rows = sb.table("app_settings").select("key,value").execute().data or []
        _settings_cache = {r["key"]: r["value"] for r in rows}
        _settings_ts = time.time()
    except Exception:
        pass


def get_app_setting(key: str, default: Any = None) -> Any:
    if time.time() - _settings_ts > _SETTINGS_TTL:
        _refresh_settings()
    return _settings_cache.get(key, default)


# ── Norme tables ──────────────────────────────────────────────────────────────

def get_norme_prize() -> dict:
    sb = _sb()
    if sb is None:
        return {}
    try:
        rows = sb.table("norme_prize").select("*").execute().data or []
        return {r["destination"]: r for r in rows}
    except Exception:
        return {}


def get_norme_iluminat() -> dict:
    sb = _sb()
    if sb is None:
        return {}
    try:
        rows = sb.table("norme_iluminat").select("*").execute().data or []
        return {r["destination"]: r for r in rows}
    except Exception:
        return {}


def get_norme_alimentari() -> dict:
    sb = _sb()
    if sb is None:
        return {}
    try:
        rows = sb.table("norme_alimentari").select("*").execute().data or []
        return {r["destination"]: r for r in rows}
    except Exception:
        return {}


def get_reguli_cablu() -> dict:
    sb = _sb()
    if sb is None:
        return {}
    try:
        rows = sb.table("reguli_cablu").select("*").execute().data or []
        return {r["breaker_a"]: r for r in rows}
    except Exception:
        return {}


def get_reguli_protectie() -> dict:
    sb = _sb()
    if sb is None:
        return {}
    try:
        rows = sb.table("reguli_protectie").select("*").execute().data or []
        return {r["circuit_type"]: r for r in rows}
    except Exception:
        return {}


def get_tip_cladire(cod: str) -> dict:
    sb = _sb()
    if sb is None:
        return {}
    try:
        rows = (
            sb.table("tip_cladire")
            .select("*")
            .eq("cod", cod)
            .limit(1)
            .execute()
            .data or []
        )
        return rows[0] if rows else {}
    except Exception:
        return {}


# ── Project persistence ───────────────────────────────────────────────────────

def save_project(user_id: str, project_data: dict) -> str:
    logger.info("=== SAVE PROJECT ===")
    logger.info(f"user_id: {repr(user_id)}")
    logger.info(f"project_data keys: {list(project_data.keys())}")

    sb = _sb()
    if sb is None:
        logger.error("[save_project] Supabase client not initialised")
        return str(uuid.uuid4())

    # Try "circuits" first (n8n response key), then "circuits_all" (FastAPI direct)
    circuits = (
        project_data.get("circuits")
        or project_data.get("circuits_all")
        or []
    )
    if not isinstance(circuits, list):
        circuits = []
    logger.info(f"circuits count: {len(circuits)}")

    # BOM
    bom = project_data.get("bom", [])
    if not isinstance(bom, list):
        bom = []

    power_summary = project_data.get("power_summary", {})
    project_info = project_data.get("project_info") or {}
    logger.info(f"project_info keys: {list(project_info.keys())}")

    # Building type — try multiple field names
    tip_cladire = (
        project_data.get("tip_cladire_ro")
        or project_data.get("building_type")
        or project_data.get("buildingType")
        or project_info.get("tip_cladire")
        or "cultural"
    )
    logger.info(f"tip_cladire resolved: {repr(tip_cladire)}")

    # Faza — strip "+PT" compound values, keep just first part
    faza_raw = (
        project_data.get("output_phase")
        or project_data.get("phase")
        or project_info.get("faza")
        or "DTAC"
    )
    faza = faza_raw.split("+")[0] if "+" in str(faza_raw) else faza_raw
    logger.info(f"faza resolved: {repr(faza)}")

    payload = {
        "user_id": user_id,
        "project_info": project_info,
        "power_summary": power_summary,
        "circuits": circuits,
        "bom": bom,
        "tip_cladire_ro": tip_cladire,
        "faza": faza,
        "status": "completed",
    }

    logger.info(f"inserting payload with {len(circuits)} circuits")

    try:
        result = sb.table("projects").insert(payload).execute()
        project_id = result.data[0]["id"]
        logger.info(f"saved project_id: {project_id}")
        return project_id
    except Exception as e:
        logger.error("[save_project] Supabase error: %s", e)
        return project_data.get("project_id", str(uuid.uuid4()))


def save_project_file(
    project_id: str,
    tip: str,
    pdf_base64: str,
    plansa_nr: Optional[str] = None,
    page_format: Optional[str] = None,
) -> None:
    sb = _sb()
    if sb is None:
        return
    try:
        sb.table("project_files").insert({
            "project_id": project_id,
            "tip": tip,
            "pdf_base64": pdf_base64,
            "plansa_nr": plansa_nr,
            "page_format": page_format,
        }).execute()
    except Exception:
        pass


# ── Audit log ─────────────────────────────────────────────────────────────────

def log_action(
    user_id: Optional[str],
    actiune: str,
    proiect_id: Optional[str] = None,
    tokens: Optional[int] = None,
    durata_ms: Optional[int] = None,
    succes: bool = True,
    eroare: Optional[str] = None,
) -> None:
    sb = _sb()
    if sb is None:
        return
    try:
        sb.table("audit_log").insert({
            "user_id": user_id,
            "actiune": actiune,
            "proiect_id": proiect_id,
            "tokens": tokens,
            "durata_ms": durata_ms,
            "succes": succes,
            "eroare": eroare,
        }).execute()
    except Exception:
        pass
