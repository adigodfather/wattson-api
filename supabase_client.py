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


# ── Plansele din Storage ──────────────────────────────────────────────────────
# De la mutarea blob-urilor in Storage (etapa 2), `result_data.planuri[]` nu mai tine PDF-ul in
# rand, ci o referinta: `pdf_base64_path` + `pdf_base64_sha256` (amprenta OCTETILOR PDF, verificata
# pe toate cele 23 de planse din baza). Cititorii care doar AFISEAZA au fost mutati atunci; cei
# care CALCULEAZA au scapat, fiindca nu arata nimic cand raman fara date — se multumesc cu „lipsa"
# si trec mai departe. Asa a stat ramura geometrica din `/bom` fara sa se execute.
# Functia asta e singurul loc din backend care stie de unde vine o plansa.

BUCKET_PLANSE = "project-files"


def plansa_bytes(plansa: dict) -> Optional[bytes]:
    """Octetii PDF ai unei planse din `result_data.planuri[]`, din rand sau din Storage.

    Fail-safe prin contract: ORICE esec intoarce None, iar apelantul cade pe comportamentul lui de
    dinainte. Amprenta se verifica atunci cand randul o are — un fisier care nu e cel anuntat nu e
    mai bun decat lipsa lui.
    """
    if not isinstance(plansa, dict):
        return None
    b64 = plansa.get("pdf_base64") or ""
    if b64:
        try:
            import base64 as _b64
            return _b64.b64decode(b64.split(",", 1)[-1])
        except Exception:
            return None
    cale = plansa.get("pdf_base64_path")
    if not cale:
        return None
    sb = _sb()
    if sb is None:
        return None
    try:
        raw = sb.storage.from_(BUCKET_PLANSE).download(cale)
    except Exception as e:
        logger.warning("[plansa_bytes] descarcare esuata pentru %s: %r", cale, e)
        return None
    if not raw:
        return None
    amprenta = plansa.get("pdf_base64_sha256")
    if amprenta:
        import hashlib as _h
        real = _h.sha256(raw).hexdigest()
        if real != amprenta:
            logger.warning("[plansa_bytes] amprenta nu se potriveste pentru %s (rand %s, fisier %s)",
                           cale, str(amprenta)[:12], real[:12])
            return None
    return raw


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


# ── Plan elements (editor interactiv) ──────────────────────────────────────────

def save_plan_elements(project_id: str, elements: list) -> int:
    """Persista elementele de plan (becuri + intrerupatoare) in tabelul plan_elements.
    OPTIONAL + NON-BLOCANT: client lipsa / project_id gol / lista goala / orice eroare -> return 0,
    fara a propaga exception (la fel ca save_project_file/log_action).
    IDEMPOTENT: sterge intai elementele existente pt. (project_id, floor) -> re-generarea INLOCUIESTE,
    nu dubleaza. Stergerea e limitata STRICT la project_id + floor-urile din batch.
    Returneaza nr. de elemente inserate (0 daca s-a sarit/esuat)."""
    sb = _sb()
    if sb is None:
        logger.warning("[save_plan_elements] Supabase client not initialised — skip")
        return 0
    if not project_id or not elements:
        return 0

    # IDEMPOTENTA: sterge doar (project_id, floor) prezente in acest batch (de obicei un singur floor)
    floors = {str(e.get("floor") or "parter") for e in elements}
    try:
        for fl in floors:
            sb.table("plan_elements").delete().eq("project_id", project_id).eq("floor", fl).execute()
    except Exception as e:
        logger.error("[save_plan_elements] delete (idempotency) error: %s", e)
        # continuam: chiar daca delete esueaza, incercam insert (nu blocam)

    try:
        result = sb.table("plan_elements").insert(elements).execute()
        n = len(result.data or [])
        logger.info("[save_plan_elements] inserted %d elements for project %s", n, project_id)
        return n
    except Exception as e:
        logger.error("[save_plan_elements] insert error: %s", e)
        return 0
