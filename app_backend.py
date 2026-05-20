import json
import hashlib
import os
import re
import shutil
import time
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import cgi

from openai import OpenAI

from generate_resume import (
    BASE_RESUME,
    create_template_from_profile,
    extract_job_metadata,
    flatten_generated_text,
    generate_resume_from_jd,
    make_template_from_resume,
    metadata_value_is_bad,
)
from monitoring import (
    add_monitoring_breadcrumb,
    capture_monitoring_exception,
    init_monitoring,
    monitor_span,
    monitor_transaction,
    monitoring_enabled,
    set_monitoring_context,
)


ROOT = Path(__file__).parent.resolve()
PUBLIC_DIR = ROOT / "web"
UPLOAD_DIR = ROOT / "uploads"
RUN_DIR = ROOT / "runs"
DATA_DIR = ROOT / "data"
HISTORY_FILE = DATA_DIR / "history.json"
JD_CACHE_FILE = DATA_DIR / "jd_intelligence_cache.json"


def load_local_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env()
init_monitoring("hone-backend")

OUTPUT_ROOT = Path(os.environ.get("OUTPUT_ROOT", DATA_DIR / "generated")).resolve()

UPLOAD_DIR.mkdir(exist_ok=True)
RUN_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

RESULTS: dict[str, dict] = {}
JD_INTELLIGENCE_VERSION = 6
BUILD_COMMIT = os.environ.get("RENDER_GIT_COMMIT", "")
BUILD_TIMESTAMP = os.environ.get("RENDER_DEPLOYED_AT", "")


MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    request_id = getattr(handler, "request_id", "")
    if request_id and "request_id" not in payload:
        payload = {**payload, "request_id": request_id}
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    if request_id:
        handler.send_header("X-Request-ID", request_id)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class AppError(Exception):
    status = HTTPStatus.BAD_REQUEST


class RegenerationError(AppError):
    status = HTTPStatus.BAD_REQUEST


def read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {"users": {}}
    return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))


def save_history(data: dict) -> None:
    HISTORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_jd_cache() -> dict:
    if not JD_CACHE_FILE.exists():
        return {}
    try:
        return json.loads(JD_CACHE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_jd_cache(data: dict) -> None:
    JD_CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def jd_cache_key(jd_text: str) -> str:
    return hashlib.sha256((jd_text or "").encode("utf-8")).hexdigest()


def user_key(email: str) -> str:
    return (email or "local@identity-os").strip().lower()


def upsert_user(profile: dict) -> dict:
    email = user_key(profile.get("email", ""))
    data = load_history()
    users = data.setdefault("users", {})
    record = users.setdefault(email, {"profile": {}, "items": []})
    record["profile"] = {
        "name": profile.get("name", ""),
        "email": email,
        "avatar": profile.get("avatar", ""),
    }
    save_history(data)
    return record["profile"]


def save_profile(email: str, profile: dict) -> dict:
    key = user_key(email)
    data = load_history()
    record = data.setdefault("users", {}).setdefault(key, {"profile": {"email": key}, "items": []})
    existing = record.get("base_resume", {})
    if not profile_has_content(profile) and profile_has_content(existing):
        return {
            "profile": existing,
            "warning": "Saved profile was kept. Empty draft was not allowed to overwrite your base resume.",
        }
    record["base_resume"] = profile
    save_history(data)
    return {"profile": profile, "warning": ""}


def item_has_content(item) -> bool:
    if isinstance(item, str):
        return bool(item.strip())
    if isinstance(item, dict):
        meaningful_keys = {
            "company", "role", "title", "duration", "location", "school", "degree",
            "date", "description", "name", "issuer", "credential",
        }
        return any(item_has_content(value) for key, value in item.items() if key in meaningful_keys) or any(
            item_has_content(value) for value in item.get("bullets", []) if isinstance(item.get("bullets", []), list)
        )
    if isinstance(item, list):
        return any(item_has_content(value) for value in item)
    return bool(item)


def get_profile(email: str) -> dict:
    data = load_history()
    return data.get("users", {}).get(user_key(email), {}).get("base_resume", {})


def add_history_item(email: str, item: dict) -> None:
    key = user_key(email)
    data = load_history()
    record = data.setdefault("users", {}).setdefault(key, {"profile": {"email": key}, "items": []})
    record.setdefault("items", []).insert(0, item)
    save_history(data)


BAD_HISTORY_METADATA = {
    "",
    "company",
    "role",
    "target role",
    "unknown company",
    "position overview",
    "job overview",
    "job description",
    "role overview",
    "position summary",
    "job summary",
    "summary",
    "overview",
    "about the job",
    "responsibilities",
    "qualifications",
    "knowledge skills and abilities",
}


def needs_metadata_repair(item: dict) -> bool:
    company = str(item.get("company", "")).strip()
    role = str(item.get("role", "")).strip()
    return (
        company.lower() in BAD_HISTORY_METADATA
        or role.lower() in BAD_HISTORY_METADATA
        or metadata_value_is_bad(company, "company")
        or metadata_value_is_bad(role, "role")
    )


def repair_history_metadata_item(item: dict) -> bool:
    if not needs_metadata_repair(item) or not item.get("jd"):
        return False
    metadata = extract_job_metadata(item.get("jd", ""), api_key=os.environ.get("OPENAI_API_KEY"))
    changed = False
    company = metadata.get("company_display", "Unknown Company")
    role = metadata.get("role_display", "Target Role")
    if company and company != item.get("company"):
        item["company"] = company
        changed = True
    if role and role != item.get("role"):
        item["role"] = role
        changed = True
    if changed:
        item["metadata"] = metadata
    return changed


def repair_history_metadata_for_user(email: str) -> list[dict]:
    key = user_key(email)
    data = load_history()
    record = data.get("users", {}).get(key, {})
    items = record.get("items", [])
    changed = False
    for item in items:
        changed = repair_history_metadata_item(item) or changed
    if changed:
        save_history(data)
    return items


def get_history_items(email: str) -> list[dict]:
    return repair_history_metadata_for_user(email)


def find_history_item(run_id: str) -> dict | None:
    data = load_history()
    for record in data.get("users", {}).values():
        for item in record.get("items", []):
            if item.get("id") == run_id:
                if repair_history_metadata_item(item):
                    save_history(data)
                return item
    return None


def update_history_item(run_id: str, updater) -> dict | None:
    data = load_history()
    for record in data.get("users", {}).values():
        for index, item in enumerate(record.get("items", [])):
            if item.get("id") == run_id:
                updated = updater(item) or item
                record["items"][index] = updated
                save_history(data)
                return updated
    return None


def active_version(item: dict) -> dict:
    versions = item.get("versions") or []
    active_id = item.get("active_version_id")
    for version in versions:
        if version.get("id") == active_id:
            return version
    if versions:
        return versions[-1]
    return {
        "id": "v1",
        "docx_path": item.get("docx_path"),
        "pdf_path": item.get("pdf_path"),
        "structured_resume": item.get("structured_resume", {}),
        "analysis": item.get("analysis", {}),
        "keyword_gaps": item.get("keyword_gaps", {}),
    }


def normalize_resume_item(item: dict) -> dict:
    versions = item.get("versions")
    if not isinstance(versions, list) or not versions:
        version = {
            "id": "v1",
            "created_at": item.get("created_at") or datetime.now().isoformat(timespec="seconds"),
            "label": "Imported original",
            "instruction": "",
            "docx_path": item.get("docx_path"),
            "pdf_path": item.get("pdf_path"),
            "structured_resume": item.get("structured_resume") or {},
            "analysis": item.get("analysis") or {},
            "keyword_gaps": item.get("keyword_gaps") or {},
        }
        item["versions"] = [version]
        item["active_version_id"] = "v1"
    else:
        item.setdefault("active_version_id", active_version(item).get("id", "v1"))
    item.setdefault("user_proof", [])
    item.setdefault("playground_notes", [])
    return item


def profile_has_content(profile: dict | None) -> bool:
    if not isinstance(profile, dict):
        return False
    details = profile.get("details", {}) if isinstance(profile.get("details"), dict) else {}
    detail_count = sum(1 for value in details.values() if str(value or "").strip())
    if detail_count >= 2:
        return True
    if str(profile.get("skills", "") or "").strip():
        return True
    for key in ["experiences", "experience", "projects", "education", "certifications"]:
        values = profile.get(key, [])
        if isinstance(values, list) and any(item_has_content(item) for item in values):
            return True
    return False


def playground_payload(item: dict) -> dict:
    version = active_version(item)
    run_id = item.get("id", "")
    pdf_path = Path(version.get("pdf_path", "")) if version.get("pdf_path") else None
    has_pdf = bool(pdf_path and pdf_path.exists())
    payload = dict(item)
    payload["active_version"] = version
    payload["docx_url"] = f"/api/download/{run_id}/docx"
    payload["pdf_url"] = f"/api/download/{run_id}/pdf" if has_pdf else None
    payload["preview_url"] = f"/api/preview/{run_id}/pdf" if has_pdf else None
    return payload


def profile_to_text(profile: dict, proof: list[dict] | None = None) -> str:
    text = json.dumps(profile or {}, ensure_ascii=False)
    for item in proof or []:
        if item.get("used") is True:
            text += " " + " ".join(str(item.get(key, "")) for key in ["keyword", "where", "proof"])
    return text


SECTION_WEIGHTS = {
    "summary": 1.35,
    "recent_experience": 1.25,
    "older_experience": 1.0,
    "projects": 1.15,
    "competencies": 1.2,
}


def cluster_for_signal(term: str, category: str) -> str:
    lower = term.lower()
    if any(token in lower for token in ["campaign", "segmentation", "marketing", "market research", "competitive intelligence", "business analytics", "google analytics", "paid media", "seo"]):
        return "marketing analytics"
    if any(token in lower for token in ["aws", "azure", "snowflake", "databricks", "airflow", "dbt", "docker", "kubernetes", "distributed"]):
        return "cloud data"
    if any(token in lower for token in ["rl", "model", "pytorch", "tensorflow", "llm", "vlm", "qdrant", "vector", "simulation"]):
        return "machine learning"
    if any(token in lower for token in ["roadmap", "backlog", "agile", "scrum", "requirements", "b2b saas", "payments"]):
        return "product delivery"
    if any(token in lower for token in ["hipaa", "irb", "clinical", "patient", "healthcare", "redcap", "hospital", "service line"]):
        return "healthcare strategy"
    if any(token in lower for token in ["due diligence", "acquisition", "divestiture", "valuation"]):
        return "corporate development"
    if any(token in lower for token in ["gaap", "sox", "financial", "budget", "variance", "forecast", "oracle", "netsuite", "quickbooks"]):
        return "financial analysis"
    if category == "stakeholder_scope":
        return "stakeholder leadership"
    return category.replace("_", " ")


def keyword_defaults(category: str, importance: str) -> tuple[int, int, list[str]]:
    if importance == "critical":
        target_min, target_max = 2, 4
    elif importance == "important":
        target_min, target_max = 1, 2
    else:
        target_min, target_max = 1, 1
    preferred = ["projects", "competencies"]
    if category in {"tools_platforms", "methods_frameworks", "seniority_signals"}:
        preferred = ["summary", "recent_experience", "projects", "competencies"]
    elif category in {"functional_work", "domain_context"}:
        preferred = ["recent_experience", "projects", "summary", "competencies"]
    elif category == "stakeholder_scope":
        preferred = ["recent_experience", "summary", "competencies"]
    return target_min, target_max, preferred


JD_SIGNAL_CATALOG = {
    "tools_platforms": [
        ("Python", [r"\bpython\b"]),
        ("SQL", [r"\bsql\b"]),
        ("Excel", [r"\bexcel\b"]),
        ("Tableau", [r"\btableau\b"]),
        ("Power BI", [r"\bpower bi\b"]),
        ("Salesforce", [r"\bsalesforce\b"]),
        ("HubSpot", [r"\bhubspot\b"]),
        ("Google Analytics", [r"\bgoogle analytics\b", r"\bga4\b"]),
        ("REDCap", [r"\bredcap\b"]),
        ("Qualtrics", [r"\bqualtrics\b"]),
        ("SPSS", [r"\bspss\b"]),
        ("SAS", [r"\bsas\b"]),
        ("R", [r"\br programming\b", r"\bprogramming in r\b", r"\br\b"]),
        ("MATLAB", [r"\bmatlab\b"]),
        ("Workday", [r"\bworkday\b"]),
        ("SAP", [r"\bsap\b"]),
        ("Oracle", [r"\boracle\b"]),
        ("NetSuite", [r"\bnetsuite\b"]),
        ("QuickBooks", [r"\bquickbooks\b"]),
        ("Jira", [r"\bjira\b"]),
        ("Figma", [r"\bfigma\b"]),
        ("AWS", [r"\baws\b", r"\bamazon web services\b"]),
        ("Azure", [r"\bazure\b"]),
        ("Snowflake", [r"\bsnowflake\b"]),
        ("Databricks", [r"\bdatabricks\b"]),
        ("Airflow", [r"\bairflow\b", r"\bapache airflow\b"]),
        ("dbt", [r"\bdbt\b"]),
        ("Docker", [r"\bdocker\b"]),
        ("Kubernetes", [r"\bkubernetes\b", r"\bk8s\b"]),
        ("Git", [r"\bgit\b", r"\bgithub\b", r"\bgitlab\b"]),
        ("PyTorch", [r"\bpytorch\b"]),
        ("TensorFlow", [r"\btensorflow\b"]),
        ("scikit-learn", [r"\bscikit[- ]learn\b", r"\bsklearn\b"]),
        ("Google Cloud Platform", [r"\bgoogle cloud platform\b", r"\bgcp\b"]),
        ("Qdrant", [r"\bqdrant\b"]),
        ("vector databases", [r"\bvector databases?\b"]),
        ("LLM", [r"\bllm\b", r"\blarge language model"]),
        ("VLM", [r"\bvlm\b", r"\bvision language model"]),
        ("dLLM", [r"\bdllm\b"]),
        ("VLA", [r"\bvla\b"]),
        ("video generation", [r"\bvideo generations?\b"]),
        ("distributed training", [r"\bdistributed training\b"]),
        ("large-scale data processing", [r"\blarge[- ]scale data processing\b"]),
        ("simulation platforms", [r"\bsimulation platforms?\b"]),
        ("business intelligence", [r"\bbusiness intelligence\b", r"\bbi\b"]),
        ("analytics tools", [r"\banalytics tools?\b"]),
        ("healthcare industry databases", [r"\bhealthcare industry databases?\b"]),
        ("Minitab", [r"\bminitab\b"]),
    ],
    "functional_work": [
        ("model training", [r"\bmodel training\b", r"\btraining\b"]),
        ("fine-tuning", [r"\bfine[- ]tuning\b"]),
        ("model optimization", [r"\boptimization\b", r"\boptimizing\b"]),
        ("model monitoring", [r"\bmonitoring\b"]),
        ("channel ranking", [r"\bchannel ranking\b"]),
        ("guide personalization", [r"\bguide personalization\b"]),
        ("content recommendations", [r"\bcontent recommendations?\b"]),
        ("feature engineering", [r"\brelevant features?\b", r"\bfeature engineering\b"]),
        ("production deployment", [r"\bproduction deployment\b", r"\bdeploy\b.*\bproduction\b"]),
        ("closed-loop evaluation", [r"\bclosed[- ]loop evaluation\b"]),
        ("scenario coverage", [r"\bscenario coverage\b"]),
        ("human-led triaging", [r"\bhuman[- ]led triaging\b", r"\btriaging\b"]),
        ("high-volume workflows", [r"\bhigh[- ]volume workflows?\b"]),
        ("critical anomalies", [r"\bcritical anomalies\b", r"\banomal(?:y|ies)\b"]),
        ("fleet-scale assessment", [r"\bfleet[- ]scale assessment\b"]),
        ("evaluation systems", [r"\bevaluation systems?\b"]),
        ("training and evaluation loops", [r"\btraining and evaluation loops?\b"]),
        ("end-to-end ML systems", [r"\bend[- ]to[- ]end\b.*\bml systems?\b", r"\bshipping impactful ml systems\b"]),
        ("dashboarding", [r"\bdashboarding\b", r"\bdashboards?\b"]),
        ("reporting", [r"\breporting\b", r"\breports?\b"]),
        ("data collection", [r"\bdata collection\b", r"\bcollecting data\b"]),
        ("data analysis", [r"\bdata analysis\b", r"\banalyz(?:e|ing) data\b"]),
        ("stakeholder reporting", [r"\bstakeholder reporting\b"]),
        ("customer segmentation", [r"\bcustomer segmentation\b", r"\bsegmentation\b"]),
        ("campaign optimization", [r"\bcampaign optimization\b", r"\boptimi[sz]e campaigns?\b"]),
        ("product roadmap", [r"\bproduct roadmap\b", r"\broadmap\b"]),
        ("backlog prioritization", [r"\bbacklog prioritization\b", r"\bprioriti[sz]e backlog\b"]),
        ("user research", [r"\buser research\b", r"\bcustomer discovery\b"]),
        ("requirements gathering", [r"\brequirements gathering\b", r"\bgather requirements\b"]),
        ("patient recruitment", [r"\bpatient recruitment\b", r"\brecruit patients\b"]),
        ("budgeting", [r"\bbudgeting\b", r"\bbudget management\b"]),
        ("variance analysis", [r"\bvariance analysis\b"]),
        ("financial reporting", [r"\bfinancial reporting\b"]),
        ("actionable insights", [r"\bactionable insights?\b"]),
        ("market analysis", [r"\bmarket analysis\b"]),
        ("competitive intelligence", [r"\bcompetitive intelligence\b"]),
        ("business analytics", [r"\bbusiness analytics\b"]),
        ("due diligence", [r"\bdue diligence\b"]),
        ("valuation", [r"\bvaluation\b"]),
        ("acquisitions", [r"\bacquisitions?\b", r"\bmergers?\b"]),
        ("divestitures", [r"\bdivestitures?\b"]),
        ("end-user reports", [r"\bend[- ]user reports?\b"]),
        ("planning research", [r"\bplanning research\b"]),
        ("narrative and statistical reports", [r"\bnarrative and statistical reports?\b", r"\bstatistical reports?\b"]),
        ("finance data reconciliation", [r"\bfinance data\b.*\breconciliation", r"\breconciliations?\b.*\bfinance data\b"]),
        ("database maintenance", [r"\bmaintains? internal and external databases?\b", r"\bmaintain.*databases?\b"]),
        ("quality information", [r"\bquality information\b"]),
    ],
    "methods_frameworks": [
        ("reinforcement learning", [r"\breinforcement learning\b", r"\bstrong rl\b"]),
        ("RL-style methods", [r"\brl[- ]style methods?\b"]),
        ("linear programming", [r"\blinear programming\b"]),
        ("scheduling algorithms", [r"\bscheduling algorithms?\b"]),
        ("reward objectives", [r"\breward objectives?\b", r"\breward\s*/\s*preference objectives?\b"]),
        ("preference objectives", [r"\bpreference objectives?\b"]),
        ("preference optimization", [r"\bpreference/feedback optimization\b", r"\bpreference optimization\b"]),
        ("RLHF", [r"\brlhf\b", r"\brl from human preferences\b"]),
        ("policy learning", [r"\bpolicy learning\b"]),
        ("offline RL", [r"\boffline rl\b", r"\boffline/online rl\b"]),
        ("online RL", [r"\bonline rl\b", r"\boffline/online rl\b"]),
        ("sequence modeling", [r"\bsequence modeling\b"]),
        ("generative models", [r"\bgenerative models?\b"]),
        ("post-training techniques", [r"\bpost[- ]training techniques?\b"]),
        ("Agile", [r"\bagile\b"]),
        ("Scrum", [r"\bscrum\b"]),
        ("A/B testing", [r"\ba/b testing\b", r"\bab testing\b"]),
        ("forecasting", [r"\bforecasting\b"]),
        ("quality assurance", [r"\bquality assurance\b", r"\bqa\b"]),
        ("data integrity", [r"\bdata integrity\b"]),
        ("statistical modeling", [r"\bstatistical modeling\b", r"\badvanced statistical modeling\b"]),
        ("statistical programming", [r"\bstatistical programming\b"]),
        ("statistical analysis", [r"\bstatistical analysis\b"]),
        ("statistical visualization", [r"\bstatistical visualization\b"]),
        ("machine learning", [r"\bmachine learning\b"]),
        ("data mining", [r"\bdata mining\b"]),
        ("econometrics", [r"\beconometrics\b"]),
        ("data forecasting", [r"\bdata forecasting\b"]),
        ("quantitative data methodologies", [r"\bquantitative data methodologies\b"]),
        ("qualitative research", [r"\bqualitative research\b"]),
        ("contextual inquiry", [r"\bcontextual inquiry\b"]),
        ("individual interviews", [r"\bindividual interviews?\b"]),
        ("group sessions", [r"\bgroup sessions?\b"]),
        ("qualitative survey", [r"\bqualitative survey\b"]),
        ("secondary research", [r"\bsecondary research\b"]),
        ("ethnography", [r"\bethnograph(?:y|ic)\b"]),
        ("market research frameworks", [r"\bmarket research frameworks?\b"]),
        ("survey techniques", [r"\bsurvey techniques?\b"]),
        ("research methodology", [r"\bresearch methodology\b"]),
        ("regulatory compliance", [r"\bregulatory compliance\b", r"\bcompliance\b"]),
        ("IRB protocols", [r"\birb protocols?\b", r"\binstitutional review board\b"]),
        ("HIPAA", [r"\bhipaa\b"]),
        ("GAAP", [r"\bgaap\b"]),
        ("SOX controls", [r"\bsox controls?\b", r"\bsarbanes[- ]oxley\b"]),
        ("financial modeling", [r"\bfinancial modeling\b"]),
        ("market research", [r"\bmarket research\b"]),
        ("content strategy", [r"\bcontent strategy\b"]),
        ("SEO", [r"\bseo\b", r"\bsearch engine optimization\b"]),
        ("paid media", [r"\bpaid media\b", r"\bppc\b"]),
    ],
    "domain_context": [
        ("autonomous vehicles", [r"\bautonomous vehicles?\b"]),
        ("autonomous driving", [r"\bautonomous driving\b"]),
        ("robotics", [r"\brobotics\b"]),
        ("complex simulation environments", [r"\bcomplex simulation environments?\b"]),
        ("simulation-aligned workflows", [r"\bsimulation[- ]aligned workflows?\b"]),
        ("self-driving behavior", [r"\bself[- ]driving behavior\b"]),
        ("driving behaviors", [r"\bdriving behaviors?\b"]),
        ("safety-critical AI systems", [r"\bsafety[- ]critical ai systems?\b"]),
        ("real-world exposure", [r"\breal[- ]world exposure\b"]),
        ("FAST ecosystem", [r"\bfast ecosystem\b", r"\bfree ad[- ]supported streaming television\b"]),
        ("broadcast TV data structures", [r"\bbroadcast tv data structures?\b"]),
        ("Electronic Programming Guide", [r"\belectronic programming guide\b", r"\bepg\b"]),
        ("viewer engagement", [r"\bviewer engagement\b"]),
        ("session duration", [r"\bsession duration\b"]),
        ("healthcare compliance", [r"\bhealthcare compliance\b", r"\bhipaa\b"]),
        ("healthcare facilities", [r"\bhealthcare facilities\b"]),
        ("healthcare facility planning", [r"\bhealthcare facilit(?:y|ies)\b.*\bplanning\b"]),
        ("service line institutes", [r"\bservice line institutes?\b"]),
        ("business development", [r"\bbusiness development\b"]),
        ("healthcare strategy", [r"\bhealthcare\b.*\b(strategy|planning|decision making)\b"]),
        ("clinical research", [r"\bclinical research\b"]),
        ("patient data", [r"\bpatient data\b"]),
        ("supply chain", [r"\bsupply chain\b"]),
        ("inventory management", [r"\binventory management\b"]),
        ("demand planning", [r"\bdemand planning\b"]),
        ("fintech lending", [r"\bfintech\b", r"\blending\b"]),
        ("payments", [r"\bpayments?\b", r"\bpayment processing\b"]),
        ("B2B SaaS", [r"\bb2b saas\b", r"\bsaas\b"]),
    ],
    "stakeholder_scope": [
        ("Prediction teams", [r"\bprediction\b"]),
        ("Planning teams", [r"\bplanning\b"]),
        ("Research teams", [r"\bresearch\b"]),
        ("platform/engineering leads", [r"\bplatform/engineering leads?\b", r"\bplatform teams?\b"]),
        ("cross-cutting improvements", [r"\bcross[- ]cutting improvements?\b"]),
        ("technical leadership", [r"\btechnical leadership\b"]),
        ("stakeholder alignment", [r"\binfluencing stakeholders\b", r"\baligning teams\b"]),
        ("communication of trade-offs", [r"\bcomplex trade[- ]offs\b"]),
        ("executive reporting", [r"\bexecutive reporting\b"]),
        ("senior administration", [r"\bsenior administration\b"]),
        ("senior leadership", [r"\bsenior leadership\b", r"\bleadership\b"]),
        ("leadership presentations", [r"\bpresents? analysis and recommendations?\b.*\bleadership\b", r"\bpresent information\b", r"\bcommunicate results\b"]),
        ("Business Development stakeholders", [r"\bbusiness development\b"]),
        ("Marketing stakeholders", [r"\bmarketing\b"]),
        ("senior executives", [r"\bsenior executives?\b"]),
        ("vendor management", [r"\bvendor management\b", r"\bvendor relationships?\b"]),
        ("client-facing communication", [r"\bclient[- ]facing\b"]),
    ],
    "seniority_signals": [
        ("production-grade ML", [r"\bproduction[- ]grade\b", r"\bproduction[- ]oriented ml\b"]),
        ("ambiguous technical work", [r"\bambiguous technical work\b"]),
        ("problem framing", [r"\bproblem framing\b"]),
        ("reliable delivery", [r"\breliable delivery\b"]),
        ("evaluation rigor", [r"\bevaluation rigor\b"]),
        ("3+ years ML production experience", [r"\b3\+ years\b.*\bml\b"]),
        ("M.S. or Ph.D.", [r"\bm\.s\.\b", r"\bph\.d\.\b"]),
        ("5+ years quantitative experience", [r"\b5\+ experience\b", r"\b5\+\s+years\b.*\bquantitative\b"]),
        ("supervisor experience", [r"\bsupervisor experience\b", r"\bmanage a team\b"]),
        ("mentoring analysts", [r"\bmentor\b.*\banalysts?\b", r"\bcoach\b.*\banalysts?\b", r"\btrains? and provides direction\b"]),
        ("workload prioritization", [r"\bworkload prioritization\b", r"\bprioritize workloads\b"]),
        ("project management", [r"\bmanage numerous processes\b", r"\bprojects simultaneously\b", r"\bdefined project goals\b"]),
        ("strategic thinking", [r"\bthink and act strategically\b", r"\bstrategically\b"]),
    ],
}


SECTION_MAP = {
    "about_role": {"about the role", "about this role", "role overview", "the role", "about the job", "job summary", "position summary"},
    "about_company": {"description", "company", "overview", "who we are", "about the company", "about us", "our company", "our promise to you", "our promise"},
    "responsibilities": {"responsibility", "responsibilities", "what you'll do", "what you will do", "role responsibilities", "duties", "essential functions", "job description", "position description"},
    "requirements": {"requirements", "required", "required skills", "qualifications", "minimum qualifications", "what you bring", "basic qualifications", "knowledge skills and abilities", "knowledge skills abilities", "knowledge skill and abilities", "knowledge skill abilities", "education", "field of study", "work experience"},
    "preferred": {"preferred", "preferred skills", "nice to have", "preferred qualifications", "desired qualifications", "licenses and certifications", "license and certification", "certifications"},
    "benefits_compensation": {"compensation", "benefits", "base salary", "salary", "pay range", "privacy", "equal opportunity", "eeo", "perks", "additional information", "time type", "employee type", "travel", "relocation eligible", "physical requirements", "schedule", "shift", "address", "city", "state", "postal code", "all the benefits and perks you need for you and your family"},
}


def normalize_heading(line: str) -> str:
    return re.sub(r"[^a-z0-9 +'/-]+", "", line.strip().lower()).strip()


def parse_jd_sections(jd_text: str) -> dict:
    sections = {
        "about_company": [],
        "about_role": [],
        "responsibilities": [],
        "requirements": [],
        "preferred": [],
        "benefits_compensation": [],
        "other": [],
    }
    current = "other"
    for raw in (jd_text or "").splitlines():
        line = raw.strip(" \t•-*")
        if not line:
            continue
        heading = normalize_heading(line)
        matched = None
        for section, aliases in SECTION_MAP.items():
            if heading in aliases or any(heading.startswith(alias + " ") for alias in aliases):
                matched = section
                break
        if matched:
            current = matched
            continue
        sections[current].append(line)
    return {key: "\n".join(value) for key, value in sections.items()}


def high_signal_jd_text(sections: dict) -> str:
    return "\n".join(
        sections.get(key, "")
        for key in ["about_role", "responsibilities", "requirements", "preferred"]
        if sections.get(key)
    )


SIGNAL_CATEGORIES = [
    "tools_platforms",
    "functional_work",
    "methods_frameworks",
    "domain_context",
    "stakeholder_scope",
    "seniority_signals",
]

SIGNAL_LABELS = {
    "tools_platforms": "Tool / Platform",
    "functional_work": "Functional Work",
    "methods_frameworks": "Method / Framework",
    "domain_context": "Domain Context",
    "stakeholder_scope": "Stakeholder Scope",
    "seniority_signals": "Seniority Signal",
}

GENERIC_SIGNAL_STOPWORDS = {
    "knowledge", "responsibilities", "responsibilities design", "benefits", "benefits competitive",
    "current", "next", "train", "own", "ml", "collaborate", "design", "develop", "deploy",
    "utilize", "requirements", "qualifications", "about", "role", "company", "equal opportunity",
    "preferred", "required", "job", "work", "team", "teams", "business", "competitive", "applicant",
    "candidate", "employee", "employees", "excellent", "strong", "responsible", "ability", "skills",
}

BOILERPLATE_SIGNAL_PATTERN = re.compile(
    r"\b(?:salary|benefits?|401|medical|dental|vision|insurance|holiday|pto|tuition|"
    r"equal opportunity|disability|veteran|protected characteristic|privacy|reasonable accommodation|"
    r"founded|nasdaq|cnbc|xprize|bessemer|silicon valley|company matching|apply|application status|"
    r"over \d+ applicants?|promoted|viewed|submitted|health care plan|life insurance)\b",
    re.IGNORECASE,
)

GENERIC_LEADING_VERBS = re.compile(
    r"^(?:design|develop|deploy|own|train|evaluate|collaborate|utilize|use|manage|lead|support|"
    r"assist|create|build|drive|execute|perform|conduct|maintain|monitor|partner)\s+",
    re.IGNORECASE,
)

PROOF_WORTHY_CATEGORIES = {"tools_platforms", "methods_frameworks", "domain_context", "seniority_signals"}


def normalize_signal_text(value: str) -> str:
    value = re.sub(r"^(?:[•*\-]\s*|\d+[.)]\s*)+", "", str(value or "")).strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"^(knowledge of|experience with|hands[- ]on experience with|proficiency in|understanding of)\s+", "", value, flags=re.IGNORECASE)
    return value.strip(" .,:;()[]")


def is_valid_signal(term: str, category: str = "") -> bool:
    normalized = normalize_signal_text(term)
    lowered = normalized.lower()
    if not normalized or lowered in GENERIC_SIGNAL_STOPWORDS:
        return False
    if BOILERPLATE_SIGNAL_PATTERN.search(lowered):
        return False
    if GENERIC_LEADING_VERBS.match(normalized) and len(normalized.split()) <= 2:
        return False
    if len(normalized) < 3 or len(normalized.split()) > 7:
        return False
    if len(normalized.split()) == 1 and normalized.lower() not in {
        "python", "sql", "excel", "tableau", "salesforce", "hubspot", "workday", "sap", "oracle",
        "jira", "figma", "pytorch", "tensorflow", "qdrant", "gcp", "rlhf", "llm", "vlm", "dllm", "vla",
        "hipaa", "scrum", "agile", "aws", "azure", "snowflake", "databricks", "redcap", "ga4",
        "qualtrics", "spss", "sas", "r", "matlab", "minitab", "netsuite", "quickbooks", "airflow", "dbt",
        "docker", "kubernetes", "git", "gaap", "seo",
    }:
        return False
    if category == "stakeholder_scope" and len(normalized.split()) == 1:
        return False
    return True


def is_ignored_context_signal(term: str, category: str, sections: dict) -> bool:
    normalized = normalize_signal_text(term).lower()
    if not normalized:
        return True
    if re.search(r"\b(?:inc|llc|corp|corporation|global|company)\b|\.ai\b", normalized, re.IGNORECASE):
        return True
    ignored_text = " ".join(sections.get(key, "") for key in ["about_company", "benefits_compensation"]).lower()
    high_signal_text = high_signal_jd_text(sections).lower()
    if ignored_text and normalized in ignored_text and normalized not in high_signal_text:
        return True
    return False


def is_proof_worthy_signal(term: str, category: str, importance: str = "important", proof_question=True, evidence_type: str = "") -> bool:
    if proof_question is False:
        return False
    if not is_valid_signal(term, category):
        return False
    normalized = normalize_signal_text(term)
    if category in {"tools_platforms", "methods_frameworks"}:
        return True
    if category == "domain_context":
        return len(normalized.split()) >= 2 or normalized.lower() in {"hipaa", "fast"}
    if category == "seniority_signals":
        return importance in {"critical", "important"} and len(normalized.split()) >= 2
    if category == "functional_work":
        return evidence_type in {"responsibility", "workflow", "method", "regulated_workflow"} and len(normalized.split()) >= 2
    return False


def make_signal(term: str, category: str, source: str = "parser", importance: str = "important", proof_question=True, evidence_type: str = "") -> dict:
    normalized = normalize_signal_text(term)
    canonical = {
        "gcp": "Google Cloud Platform",
        "epg": "Electronic Programming Guide",
        "fast": "FAST ecosystem",
        "rl": "reinforcement learning",
    }.get(normalized.lower(), normalized)
    target_min, target_max, preferred_sections = keyword_defaults(category, importance)
    return {
        "term": canonical,
        "exact_phrase": canonical,
        "category": category,
        "label": SIGNAL_LABELS.get(category, category.replace("_", " ").title()),
        "source": source,
        "importance": importance if importance in {"critical", "important", "context"} else "important",
        "proof_question": is_proof_worthy_signal(canonical, category, importance, proof_question, evidence_type),
        "evidence_type": evidence_type or category,
        "target_frequency": {"min": target_min, "max": target_max},
        "preferred_sections": preferred_sections,
        "semantic_cluster": cluster_for_signal(canonical, category),
    }


def build_keyword_plan(signals: dict) -> list[dict]:
    plan = []
    for items in signals.values():
        for signal in items:
            plan.append({
                "term": signal.get("term", ""),
                "exact_phrase": signal.get("exact_phrase") or signal.get("term", ""),
                "category": signal.get("category", ""),
                "label": signal.get("label", ""),
                "importance": signal.get("importance", "important"),
                "target_frequency": signal.get("target_frequency", {"min": 1, "max": 2}),
                "preferred_sections": signal.get("preferred_sections", ["projects", "competencies"]),
                "semantic_cluster": signal.get("semantic_cluster") or cluster_for_signal(signal.get("term", ""), signal.get("category", "")),
            })
    return plan


def normalize_llm_signal_payload(payload: dict, sections: dict, source: str) -> dict:
    signals = {category: [] for category in SIGNAL_CATEGORIES}
    seen = set()
    exact_signal_text = high_signal_jd_text(sections).lower()
    for category in SIGNAL_CATEGORIES:
        values = payload.get(category, [])
        if not isinstance(values, list):
            continue
        for value in values[:18]:
            term = value.get("term", "") if isinstance(value, dict) else str(value)
            importance = value.get("importance", "important") if isinstance(value, dict) else "important"
            proof_question = value.get("proof_question", True) if isinstance(value, dict) else True
            evidence_type = value.get("evidence_type", "") if isinstance(value, dict) else ""
            if not is_valid_signal(term, category):
                continue
            if is_ignored_context_signal(term, category, sections):
                continue
            if normalize_signal_text(term).lower() not in exact_signal_text:
                continue
            signal = make_signal(term, category, source, importance, proof_question, evidence_type)
            key = signal["term"].lower()
            if key in seen:
                continue
            seen.add(key)
            signals[category].append(signal)
    important_terms = [item for values in signals.values() for item in values]
    return {
        "sections": sections,
        "signals": signals,
        "important_terms": important_terms,
        "keyword_plan": build_keyword_plan(signals),
        "ignored_sections": ["about_company", "benefits_compensation"],
        "source": source,
    }


def deterministic_jd_intelligence(jd_text: str) -> dict:
    sections = parse_jd_sections(jd_text)
    signal_text = high_signal_jd_text(sections)
    if not signal_text.strip():
        signal_text = "\n".join(sections.values())
    signals = {category: [] for category in SIGNAL_CATEGORIES}
    seen = set()

    for category, items in JD_SIGNAL_CATALOG.items():
        for term, patterns in items:
            if any(re.search(pattern, signal_text, re.IGNORECASE | re.DOTALL) for pattern in patterns):
                requirement_text = "\n".join([sections.get("requirements", ""), sections.get("preferred", "")])
                responsibility_text = sections.get("responsibilities", "")
                importance = "critical" if any(re.search(pattern, requirement_text, re.IGNORECASE | re.DOTALL) for pattern in patterns) else "important"
                if category == "functional_work" and any(re.search(pattern, responsibility_text, re.IGNORECASE | re.DOTALL) for pattern in patterns):
                    importance = "critical"
                signal = make_signal(term, category, "deterministic", importance, category in PROOF_WORTHY_CATEGORIES, category)
                key = signal["term"].lower()
                if key in seen:
                    continue
                seen.add(key)
                signals[category].append(signal)

    important_terms = [item for values in signals.values() for item in values]
    return {
        "sections": sections,
        "signals": signals,
        "important_terms": important_terms,
        "keyword_plan": build_keyword_plan(signals),
        "ignored_sections": ["about_company", "benefits_compensation"],
        "source": "deterministic",
    }


def llm_jd_intelligence(jd_text: str, api_key: str | None = None) -> dict | None:
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    sections = parse_jd_sections(jd_text)
    signal_text = high_signal_jd_text(sections)
    if not signal_text.strip():
        signal_text = jd_text
    prompt = f"""
You are the JD Intelligence Engine for a resume generation product.

Extract only hiring-relevant resume signals from the HIGH-SIGNAL JD text.
Ignore company description, awards, dates, compensation, benefits, equal opportunity, privacy text, and generic verbs.

Return strict JSON with exactly these array keys:
tools_platforms, functional_work, methods_frameworks, domain_context, stakeholder_scope, seniority_signals

Rules:
- Each array item must be an object: {{"term":"Salesforce","category":"tools_platforms","importance":"critical","proof_question":true,"evidence_type":"tool"}}.
- Include tools, platforms, software, systems, frameworks, methods, regulated workflows, responsibilities, domain concepts, stakeholder scope, and seniority signals.
- Do not output company names, product marketing, awards, cities, dates, salaries, benefits, or one-word generic verbs.
- Do not output weak generic terms like "Knowledge", "Current", "Next", "Own", "Train", "Collaborate", or "ML".
- Prefer exact JD terminology when it is meaningful, for example "Qdrant", "FAST metadata", "channel ranking", "guide personalization".
- Set proof_question true only for concrete tools, platforms, methods, regulated workflows, domain systems, or responsibilities a recruiter may ask the candidate to prove.
- Set importance to critical, important, or context.
- evidence_type must be one of: tool, platform, method, workflow, regulated_workflow, responsibility, domain, stakeholder, seniority.

HIGH-SIGNAL JD TEXT:
{signal_text[:9000]}
"""
    try:
        client = OpenAI(api_key=key)
        response = client.chat.completions.create(
            model=os.environ.get("JD_INTELLIGENCE_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        return normalize_llm_signal_payload(payload, sections, "llm")
    except Exception as exc:
        print(f"[jd-intelligence] falling back to deterministic parser: {exc}")
        return None


def extract_jd_intelligence(jd_text: str, api_key: str | None = None, force_refresh: bool = False) -> dict:
    key = jd_cache_key(jd_text)
    cache = load_jd_cache()
    if not force_refresh and key in cache and cache[key].get("parser_version") == JD_INTELLIGENCE_VERSION:
        return cache[key]

    intelligence = llm_jd_intelligence(jd_text, api_key=api_key) or deterministic_jd_intelligence(jd_text)
    intelligence["parser_version"] = JD_INTELLIGENCE_VERSION
    cache[key] = intelligence
    save_jd_cache(cache)
    return intelligence


def ensure_jd_intelligence(item_or_jd, api_key: str | None = None) -> dict:
    if isinstance(item_or_jd, dict):
        existing = item_or_jd.get("jd_intelligence")
        if existing and existing.get("parser_version") == JD_INTELLIGENCE_VERSION:
            return existing
        return extract_jd_intelligence(item_or_jd.get("jd", ""), api_key=api_key, force_refresh=True)
    return extract_jd_intelligence(str(item_or_jd or ""), api_key=api_key)


def important_jd_terms(jd_text: str) -> list[dict]:
    return extract_jd_intelligence(jd_text).get("important_terms", [])


def signal_term(signal) -> str:
    return signal.get("term", "") if isinstance(signal, dict) else str(signal)


def term_aliases(term: str) -> list[str]:
    aliases = {
        "RL-style methods": ["rl", "reinforcement learning"],
        "reinforcement learning": ["rl"],
        "LLM": ["large language model", "llms"],
        "VLM": ["vision language model", "vlms"],
        "fine-tuning": ["finetuning", "fine tuning"],
        "model monitoring": ["monitoring"],
        "distributed training": ["distributed model training"],
        "business intelligence": ["bi", "business intelligence tools"],
        "structured query language": ["sql"],
        "SQL": ["structured query language"],
        "data forecasting": ["forecasting"],
        "forecasting": ["data forecasting", "forecast models", "forecast modeling"],
        "quality assurance": ["qa", "quality review", "quality control"],
        "healthcare facilities": ["healthcare facility planning", "healthcare facility", "healthcare planning"],
        "senior administration": ["senior leadership", "senior executives", "executive leadership"],
        "leadership presentations": ["presentations to leadership", "presenting to leadership", "senior leadership presentations"],
        "finance data reconciliation": ["finance data reconciliations", "financial data reconciliation", "reconciliations"],
        "healthcare industry databases": ["healthcare databases", "industry databases"],
        "statistical visualization": ["data visualization", "statistical charts", "charts, graphs, and tables"],
        "qualitative research": ["qualitative survey", "interviews", "contextual inquiry", "ethnography"],
        "market research": ["market analysis", "research methodology", "survey techniques"],
        "competitive intelligence": ["competitive analysis"],
        "actionable insights": ["actionable market insights", "insights"],
    }
    return aliases.get(term, [])


def contains_term(text: str, signal) -> bool:
    term = signal_term(signal)
    if not term:
        return False
    normalized_text = (text or "").lower()
    normalized_term = term.lower()
    if re.search(rf"\b{re.escape(normalized_term)}\b", normalized_text):
        return True
    return any(re.search(rf"\b{re.escape(alias.lower())}\b", normalized_text) for alias in term_aliases(term))


def term_occurrences(text: str, signal) -> int:
    term = signal_term(signal)
    if not term:
        return 0
    normalized_text = (text or "").lower()
    terms = [term]
    terms.extend(term_aliases(term))
    return sum(len(re.findall(rf"\b{re.escape(candidate.lower())}\b", normalized_text)) for candidate in terms)


def generated_section_texts(data: dict) -> dict:
    projects = []
    for project in data.get("projects", []) or []:
        if isinstance(project, dict):
            projects.append(str(project.get("title", "")))
            projects.extend(str(item) for item in project.get("bullets", []))
        else:
            projects.append(str(project))
    return {
        "summary": str(data.get("summary", "")),
        "recent_experience": "\n".join(str(item) for item in data.get("destination_cleveland_bullets", []) or []),
        "older_experience": "\n".join(str(item) for item in data.get("genpact_bullets", []) or []),
        "projects": "\n".join(projects),
        "competencies": "\n".join(str(item) for item in data.get("core_competencies", []) or []),
    }


def build_keyword_strategy(jd_text: str, generated_data: dict, jd_intelligence: dict | None = None) -> dict:
    intelligence = jd_intelligence or extract_jd_intelligence(jd_text)
    plan = intelligence.get("keyword_plan") or build_keyword_plan(intelligence.get("signals", {}))
    sections = generated_section_texts(generated_data or {})
    covered = []
    weak_terms = []
    frequency = {}
    proof_map = {}
    cluster_totals = {}
    cluster_covered = {}
    weighted_total = 0
    weighted_earned = 0

    for signal in plan:
        term = signal.get("term", "")
        counts = {section: term_occurrences(text, signal) for section, text in sections.items()}
        total_count = sum(counts.values())
        target = signal.get("target_frequency") or {"min": 1, "max": 2}
        target_min = max(1, int(target.get("min", 1)))
        target_max = max(target_min, int(target.get("max", target_min)))
        preferred = signal.get("preferred_sections") or []
        matched_sections = [section for section, count in counts.items() if count]
        section_score = sum(SECTION_WEIGHTS.get(section, 1.0) for section in matched_sections if section in preferred)
        preferred_score_cap = max(1.0, min(2.6, sum(SECTION_WEIGHTS.get(section, 1.0) for section in preferred[:2])))
        frequency_score = min(1.0, total_count / target_min)
        placement_score = min(1.0, section_score / preferred_score_cap)
        exact_score = 1.0 if total_count else 0.0
        importance_weight = {"critical": 1.45, "important": 1.0, "context": 0.65}.get(signal.get("importance"), 1.0)
        signal_score = (exact_score * 0.45) + (frequency_score * 0.35) + (placement_score * 0.20)
        weighted_total += importance_weight
        weighted_earned += importance_weight * signal_score
        entry = {
            **signal,
            "count": total_count,
            "counts_by_section": counts,
            "matched_sections": matched_sections,
            "target_met": total_count >= target_min,
            "placement_met": any(section in preferred for section in matched_sections),
        }
        frequency[term] = {
            "count": total_count,
            "target_min": target_min,
            "target_max": target_max,
            "target_met": total_count >= target_min,
        }
        proof_map[term] = matched_sections
        cluster = signal.get("semantic_cluster") or "general"
        cluster_totals[cluster] = cluster_totals.get(cluster, 0) + 1
        if total_count:
            cluster_covered[cluster] = cluster_covered.get(cluster, 0) + 1
            covered.append(entry)
        else:
            weak_terms.append(entry)
        if total_count and (total_count < target_min or not entry["placement_met"]):
            weak_terms.append(entry)

    coverage_percent = round((len(covered) / max(1, len(plan))) * 100)
    ats_strategy_score = round((weighted_earned / max(1, weighted_total)) * 100)
    semantic_clusters = [
        {
            "name": cluster,
            "covered": cluster_covered.get(cluster, 0),
            "total": total,
            "coverage_percent": round((cluster_covered.get(cluster, 0) / max(1, total)) * 100),
        }
        for cluster, total in cluster_totals.items()
    ]
    section_distribution = {
        section: sum(term_occurrences(text, signal) for signal in plan)
        for section, text in sections.items()
    }
    strategy = {
        "important_terms": plan,
        "keyword_plan": plan,
        "covered": covered,
        "bridge_keywords": [item for item in covered if item.get("matched_sections") == ["projects"] or ("projects" in item.get("matched_sections", []) and "recent_experience" not in item.get("matched_sections", []))][:18],
        "weak_terms": weak_terms[:18],
        "keyword_frequency": frequency,
        "section_distribution": section_distribution,
        "semantic_clusters": semantic_clusters,
        "proof_map": proof_map,
        "coverage_percent": coverage_percent,
        "ats_strategy_score": ats_strategy_score,
    }
    strategy["ats_strategy_score"] = max(strategy["ats_strategy_score"], semantic_score_floor(strategy, "\n".join(sections.values())))
    return strategy


def build_keyword_gaps(jd_text: str, generated_data: dict, profile: dict, proof: list[dict] | None = None, jd_intelligence: dict | None = None) -> dict:
    # Backward-compatible alias for history records and frontend callers.
    return build_keyword_strategy(jd_text, generated_data, jd_intelligence=jd_intelligence)


def semantic_score_floor(strategy: dict, resume_text: str) -> int:
    if not strategy.get("important_terms"):
        return 0
    lower = (resume_text or "").lower()
    cluster_terms = {
        "marketing analytics": ["market", "marketing", "forecast", "competitive", "research", "analytics", "insight"],
        "healthcare strategy": ["healthcare", "hospital", "clinical", "patient", "service line", "facility"],
        "corporate development": ["due diligence", "valuation", "acquisition", "merger", "divestiture"],
        "financial analysis": ["finance", "financial", "reconciliation", "forecast", "econometric", "variance"],
        "stakeholder leadership": ["leadership", "executive", "stakeholder", "presentation", "mentor", "manager"],
        "machine learning": ["machine learning", "model", "statistical", "data mining"],
    }
    plan_clusters = {item.get("semantic_cluster") for item in strategy.get("important_terms", []) if item.get("semantic_cluster")}
    hits = 0
    for cluster in plan_clusters:
        tokens = cluster_terms.get(cluster, [])
        if tokens and any(token in lower for token in tokens):
            hits += 1
    if not hits:
        return 0
    return min(45, 18 + hits * 7)


def score_resume(jd_text: str, generated_data: dict, profile: dict, pdf_path: str | None, proof: list[dict] | None = None, jd_intelligence: dict | None = None) -> dict:
    strategy = build_keyword_strategy(jd_text, generated_data, jd_intelligence=jd_intelligence)
    resume_text = flatten_generated_text(generated_data or {})
    words = len(re.findall(r"\b[\w+#./-]+\b", resume_text))
    readability = max(55, min(96, 100 - abs(words - 620) // 10))
    ats = max(strategy["ats_strategy_score"], semantic_score_floor(strategy, resume_text))
    proof_strength = max(60, min(100, round((strategy["coverage_percent"] * 0.65) + (ats * 0.35))))
    role_fit = max(35, min(98, round((ats * 0.75) + (proof_strength * 0.25))))
    format_quality = 95 if pdf_path else 78
    interview_defensibility = max(60, min(100, 100 - len(strategy["weak_terms"]) * 2))
    overall = round((ats * 0.3) + (proof_strength * 0.15) + (readability * 0.15) + (role_fit * 0.2) + (format_quality * 0.1) + (interview_defensibility * 0.1))
    scores = {
        "ats_keyword_alignment": ats,
        "proof_strength": proof_strength,
        "recruiter_readability": readability,
        "role_fit": role_fit,
        "format_quality": format_quality,
        "interview_defensibility": interview_defensibility,
        "overall_score": overall,
    }
    explanations = {
        "ats_keyword_alignment": f"{len(strategy['covered'])} of {len(strategy['important_terms'])} exact JD signals are visible with weighted placement and repetition scoring.",
        "proof_strength": "Strength reflects exact phrase coverage, section distribution, and how fully the keyword plan is realized.",
        "recruiter_readability": f"The generated resume has about {words} words across summary, experience, projects, and competencies.",
        "role_fit": "Role fit blends keyword coverage with evidence strength.",
        "format_quality": "PDF preview is available." if pdf_path else "DOCX is available; PDF was skipped.",
        "interview_defensibility": "Claims remain stronger when keyword density is balanced across experience, projects, and competencies.",
    }
    return {
        "scores": scores,
        "explanations": explanations,
        "strengths": [
            "Resume was generated from the user's structured base profile.",
            "JD terms are evaluated for exact phrase use, frequency, and section placement.",
        ],
        "risks": [
            "Some important JD terms are still missing, underused, or weakly placed."
        ] if strategy["weak_terms"] else [],
        "missing_keywords": strategy["weak_terms"],
        "unsupported_keywords": [],
        "suggested_fixes": [
            "Regenerate to strengthen exact JD phrasing, bridge projects, and underused critical terms.",
            "Use playground chat for targeted tone, focus, or section-level rewrites.",
        ],
        "ats_strategy_score": ats,
        "keyword_frequency": strategy["keyword_frequency"],
        "section_distribution": strategy["section_distribution"],
        "semantic_clusters": strategy["semantic_clusters"],
        "proof_map": strategy["proof_map"],
        "weak_terms": strategy["weak_terms"],
    }


def copy_version_files(result: dict, run_dir: Path, version_id: str) -> dict:
    version_dir = run_dir / "versions"
    version_dir.mkdir(parents=True, exist_ok=True)
    docx_src = Path(result["docx_path"])
    docx_target = version_dir / f"{version_id}_{docx_src.name}"
    shutil.copy2(docx_src, docx_target)
    result["docx_path"] = str(docx_target)

    if result.get("pdf_path"):
        pdf_src = Path(result["pdf_path"])
        pdf_target = version_dir / f"{version_id}_{pdf_src.name}"
        shutil.copy2(pdf_src, pdf_target)
        result["pdf_path"] = str(pdf_target)
    return result


def merge_profile_with_proof(profile: dict, proof: list[dict]) -> dict:
    merged = json.loads(json.dumps(profile or {}))
    if not proof:
        return merged
    projects = merged.setdefault("projects", [])
    proof_lines = []
    for item in proof:
        if item.get("used") is not True:
            continue
        keyword = str(item.get("keyword", "")).strip()
        detail = str(item.get("proof", "")).strip()
        where = str(item.get("where", "")).strip()
        if keyword and detail:
            proof_lines.append(f"{keyword} ({where}): {detail}" if where else f"{keyword}: {detail}")
    if proof_lines:
        projects.append({
            "title": "User-Verified JD Evidence",
            "description": " ".join(proof_lines),
        })
    return merged


def intelligence_summary(jd_intelligence: dict, strategy: dict | None = None) -> str:
    signals = jd_intelligence.get("signals", {}) if jd_intelligence else {}
    keyword_plan = jd_intelligence.get("keyword_plan", []) if jd_intelligence else []
    lines = ["JD KEYWORD PLAN TO PRIORITIZE:"]
    for category, items in signals.items():
        values = [signal_term(item) for item in items]
        if values:
            lines.append(f"- {category.replace('_', ' ').title()}: {', '.join(values)}")
    if keyword_plan:
        lines.append("EXACT PHRASES, TARGET FREQUENCY, AND PREFERRED SECTIONS:")
        for item in keyword_plan:
            target = item.get("target_frequency", {})
            sections = ", ".join(item.get("preferred_sections", []))
            lines.append(f"- {item.get('term')}: {target.get('min', 1)}-{target.get('max', 1)} mentions; prefer {sections}; cluster {item.get('semantic_cluster')}")
    if strategy and strategy.get("weak_terms"):
        lines.append("WEAK TERMS TO STRENGTHEN IN THIS VERSION:")
        for item in strategy.get("weak_terms", []):
            lines.append(f"- {item.get('term')}: current {item.get('count', 0)} mentions; target {item.get('target_frequency', {}).get('min', 1)}+")
    lines.append("Use projects as the main bridge zone for missing keywords before overloading experience.")
    lines.append("Mirror the exact JD phrase whenever possible; do not replace it with a synonym.")
    return "\n".join(lines)


def ensure_item_intelligence(item: dict, api_key: str | None = None) -> dict:
    existing = item.get("jd_intelligence")
    if existing and existing.get("parser_version") == JD_INTELLIGENCE_VERSION:
        return existing
    item["jd_intelligence"] = extract_jd_intelligence(item.get("jd", ""), api_key=api_key, force_refresh=True)
    return item["jd_intelligence"]


def save_uploaded_file(field, destination: Path) -> Path | None:
    if field is None or not getattr(field, "filename", ""):
        return None

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        shutil.copyfileobj(field.file, handle)
    return destination


class ResumeForgeHandler(BaseHTTPRequestHandler):
    server_version = "ResumeForge/1.0"

    def __init__(self, *args, **kwargs):
        self.request_id = uuid.uuid4().hex[:12]
        self.request_started_at = time.perf_counter()
        self.response_status = None
        super().__init__(*args, **kwargs)

    def handle_one_request(self):
        with monitor_transaction("http request", "http.server", request_id=self.request_id):
            try:
                return super().handle_one_request()
            except Exception as exc:
                capture_monitoring_exception(exc, request_id=self.request_id, stage="http.request")
                raise

    def send_response(self, code, message=None):
        self.response_status = code
        super().send_response(code, message)

    def log_message(self, format, *args):
        duration_ms = round((time.perf_counter() - getattr(self, "request_started_at", time.perf_counter())) * 1000)
        print(f"[resume-forge] request_id={getattr(self, 'request_id', '-')} client={self.address_string()} method={self.command} path={self.path} duration_ms={duration_ms} - {format % args}")

    def send_api_error(self, status: int, error: str, error_type: str) -> None:
        json_response(self, status, {"error": error, "type": error_type})

    def send_error(self, code, message=None, explain=None):
        parsed = urlparse(getattr(self, "path", ""))
        if parsed.path.startswith("/api/"):
            description = message or HTTPStatus(code).phrase
            self.send_api_error(code, description, "HttpError")
            return
        super().send_error(code, message, explain)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        set_monitoring_context(request_id=self.request_id, http_method="GET", route=parsed.path)
        add_monitoring_breadcrumb("GET request", "http", path=parsed.path, request_id=self.request_id)

        if parsed.path.startswith("/api/download/"):
            self.serve_download(parsed.path)
            return

        if parsed.path.startswith("/api/preview/"):
            self.serve_preview(parsed.path)
            return

        if parsed.path.startswith("/api/resume/"):
            self.serve_resume(parsed.path)
            return

        if parsed.path == "/api/history":
            query = parse_qs(parsed.query)
            email = query.get("email", [""])[0]
            json_response(self, HTTPStatus.OK, {"items": get_history_items(email)})
            return

        if parsed.path == "/api/config":
            json_response(self, HTTPStatus.OK, {
                "google_client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
                "openai_configured": bool(os.environ.get("OPENAI_API_KEY")),
                "sentry_configured": monitoring_enabled(),
                "sentry_frontend_dsn": os.environ.get("SENTRY_FRONTEND_DSN", ""),
                "sentry_environment": os.environ.get("SENTRY_ENVIRONMENT", "development"),
                "sentry_release": os.environ.get("SENTRY_RELEASE") or BUILD_COMMIT,
                "sentry_traces_sample_rate": os.environ.get("SENTRY_FRONTEND_TRACES_SAMPLE_RATE", "0.2"),
                "build_commit": BUILD_COMMIT,
                "build_timestamp": BUILD_TIMESTAMP,
                "storage": {
                    "data_dir": str(DATA_DIR),
                    "history_exists": HISTORY_FILE.exists(),
                    "output_root": str(OUTPUT_ROOT),
                    "output_root_exists": OUTPUT_ROOT.exists(),
                },
            })
            return

        if parsed.path == "/api/health":
            json_response(self, HTTPStatus.OK, {
                "ok": True,
                "openai_configured": bool(os.environ.get("OPENAI_API_KEY")),
                "sentry_configured": monitoring_enabled(),
                "build_commit": BUILD_COMMIT,
                "build_timestamp": BUILD_TIMESTAMP,
                "storage": {
                    "data_dir": str(DATA_DIR),
                    "history_exists": HISTORY_FILE.exists(),
                    "output_root": str(OUTPUT_ROOT),
                    "output_root_exists": OUTPUT_ROOT.exists(),
                },
            })
            return

        if parsed.path == "/api/version":
            json_response(self, HTTPStatus.OK, {
                "build_commit": BUILD_COMMIT,
                "build_timestamp": BUILD_TIMESTAMP,
                "jd_intelligence_version": JD_INTELLIGENCE_VERSION,
                "sentry_configured": monitoring_enabled(),
                "storage": {
                    "data_dir": str(DATA_DIR),
                    "history_exists": HISTORY_FILE.exists(),
                    "output_root": str(OUTPUT_ROOT),
                    "output_root_exists": OUTPUT_ROOT.exists(),
                },
            })
            return

        if parsed.path == "/api/profile":
            query = parse_qs(parsed.query)
            email = query.get("email", [""])[0]
            json_response(self, HTTPStatus.OK, {"profile": get_profile(email)})
            return

        path = parsed.path if parsed.path != "/" else "/index.html"
        file_path = (PUBLIC_DIR / path.lstrip("/")).resolve()

        if not str(file_path).startswith(str(PUBLIC_DIR.resolve())) or not file_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", MIME_TYPES.get(file_path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        set_monitoring_context(request_id=self.request_id, http_method="POST", route=parsed.path)
        add_monitoring_breadcrumb("POST request", "http", path=parsed.path, request_id=self.request_id)
        try:
            if parsed.path == "/api/generate":
                result = self.handle_generate()
                json_response(self, HTTPStatus.OK, result)
                return
            if parsed.path == "/api/signin":
                with monitor_span("auth.signin", "Sign in or create Hone user", request_id=self.request_id):
                    profile = upsert_user(read_json_body(self))
                json_response(self, HTTPStatus.OK, {"profile": profile, "items": get_history_items(profile["email"])})
                return
            if parsed.path == "/api/profile":
                with monitor_span("profile.save", "Save base resume profile", request_id=self.request_id):
                    body = read_json_body(self)
                    email = body.get("email", "")
                    result = save_profile(email, body.get("profile", {}))
                json_response(self, HTTPStatus.OK, result)
                return
            if parsed.path.startswith("/api/resume/"):
                self.handle_resume_action(parsed.path)
                return
            self.send_api_error(HTTPStatus.NOT_FOUND, "API route not found.", "NotFoundError")
        except AppError as exc:
            self.send_api_error(exc.status, str(exc), exc.__class__.__name__)
        except Exception as exc:
            capture_monitoring_exception(exc, request_id=self.request_id, route=parsed.path, method="POST")
            self.send_api_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc), exc.__class__.__name__)

    def handle_generate(self) -> dict:
        content_type = self.headers.get("Content-Type", "")
        with monitor_span("generate.form", "Parse generate form", request_id=self.request_id):
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": content_type,
                    "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
                },
            )

        run_id = uuid.uuid4().hex
        run_dir = RUN_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        set_monitoring_context(run_id=run_id)

        jd_text = (form.getfirst("jd") or "").strip()
        if not jd_text:
            raise ValueError("Paste a job description before generating.")

        details = {
            "name": form.getfirst("name") or "",
            "email": form.getfirst("email") or "",
            "phone": form.getfirst("phone") or "",
            "location": form.getfirst("location") or "",
            "linkedin": form.getfirst("linkedin") or "",
        }
        user_email = form.getfirst("user_email") or details["email"]
        api_key = (form.getfirst("api_key") or "").strip() or None

        base_resume_path = BASE_RESUME
        profile_json = form.getfirst("profile_json") or ""
        profile_data = {}
        if profile_json.strip():
            with monitor_span("generate.template", "Create profile template", run_id=run_id):
                profile_data = json.loads(profile_json)
                base_resume_path = create_template_from_profile(profile_data, run_dir / "profile_template.docx")

        resume_field = form["resume"] if "resume" in form else None
        if not profile_json.strip() and resume_field is not None and getattr(resume_field, "filename", ""):
            with monitor_span("generate.upload_template", "Create uploaded resume template", run_id=run_id):
                uploaded_path = save_uploaded_file(
                    resume_field,
                    UPLOAD_DIR / f"{run_id}_{Path(resume_field.filename).name}",
                )
                if uploaded_path and uploaded_path.suffix.lower() == ".docx":
                    base_resume_path = make_template_from_resume(uploaded_path, run_dir / "resume_template.docx")

        skip_pdf = form.getfirst("skip_pdf") == "true"
        with monitor_span("generate.jd_intelligence", "Extract JD intelligence", run_id=run_id):
            jd_intelligence = extract_jd_intelligence(jd_text, api_key=api_key)
        generation_jd = jd_text + "\n\n" + intelligence_summary(jd_intelligence)
        with monitor_span("generate.resume", "Generate resume document", run_id=run_id, skip_pdf=skip_pdf):
            result = generate_resume_from_jd(
                generation_jd,
                base_resume_path=base_resume_path,
                output_root=OUTPUT_ROOT,
                details=details,
                skip_pdf=skip_pdf,
                api_key=api_key,
            )
        with monitor_span("generate.version_files", "Copy version files", run_id=run_id):
            result = copy_version_files(result, run_dir, "v1")
        profile_for_analysis = profile_data if profile_json.strip() else {}
        with monitor_span("generate.scoring", "Score resume and keyword strategy", run_id=run_id):
            keyword_gaps = build_keyword_gaps(jd_text, result["structured_resume"], profile_for_analysis, jd_intelligence=jd_intelligence)
            analysis = score_resume(
                jd_text,
                result["structured_resume"],
                profile_for_analysis,
                result["pdf_path"],
                jd_intelligence=jd_intelligence,
            )
        version = {
            "id": "v1",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "label": "Original generation",
            "instruction": "",
            "docx_path": result["docx_path"],
            "pdf_path": result["pdf_path"],
            "structured_resume": result["structured_resume"],
            "jd_intelligence": jd_intelligence,
            "analysis": analysis,
            "keyword_gaps": keyword_gaps,
        }

        RESULTS[run_id] = result
        history_item = {
            "id": run_id,
            "company": result["company"],
            "role": result["role"],
            "jd": jd_text,
            "created_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "docx_url": f"/api/download/{run_id}/docx",
            "pdf_url": f"/api/download/{run_id}/pdf" if result["pdf_path"] else None,
            "preview_url": f"/api/preview/{run_id}/pdf" if result["pdf_path"] else None,
            "docx_path": result["docx_path"],
            "pdf_path": result["pdf_path"],
            "structured_resume": result["structured_resume"],
            "profile": profile_for_analysis,
            "jd_intelligence": jd_intelligence,
            "metadata": result.get("metadata", {}),
            "api_key_available": bool(api_key or os.environ.get("OPENAI_API_KEY")),
            "skip_pdf": skip_pdf,
            "versions": [version],
            "active_version_id": "v1",
            "analysis": analysis,
            "keyword_gaps": keyword_gaps,
            "user_proof": [],
            "playground_notes": [],
        }
        with monitor_span("generate.history_save", "Save generated resume history", run_id=run_id):
            add_history_item(user_email, history_item)
        response = {
            "run_id": run_id,
            "company": result["company"],
            "role": result["role"],
            "docx_url": f"/api/download/{run_id}/docx",
            "pdf_url": f"/api/download/{run_id}/pdf" if result["pdf_path"] else None,
            "preview_url": f"/api/preview/{run_id}/pdf" if result["pdf_path"] else None,
            "history_item": history_item,
            "structured_resume": result["structured_resume"],
            "analysis": analysis,
            "keyword_gaps": keyword_gaps,
            "metadata": result.get("metadata", {}),
        }
        return response

    def serve_resume(self, path: str) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 3:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        _, _, run_id = parts
        item = find_history_item(run_id)
        if not item:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not item.get("versions") or not item.get("active_version_id"):
            item = update_history_item(run_id, normalize_resume_item) or item
        jd_intelligence = item.get("jd_intelligence") or {}
        if jd_intelligence.get("parser_version") != JD_INTELLIGENCE_VERSION:
            item = update_history_item(run_id, lambda current: self.rescore_resume_item(current)) or item
        json_response(self, HTTPStatus.OK, playground_payload(item))

    def handle_resume_action(self, path: str) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        _, _, run_id, action = parts
        body = read_json_body(self)
        if action == "proof":
            item = update_history_item(run_id, lambda current: self.save_resume_proof(current, body))
            if not item:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            json_response(self, HTTPStatus.OK, playground_payload(item))
            return
        if action == "score":
            item = update_history_item(run_id, self.rescore_resume_item)
            if not item:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            json_response(self, HTTPStatus.OK, playground_payload(item))
            return
        if action == "activate":
            item = update_history_item(run_id, lambda current: self.activate_resume_version(current, body))
            if not item:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            json_response(self, HTTPStatus.OK, playground_payload(item))
            return
        if action == "regenerate":
            item = self.regenerate_resume_item(run_id, body)
            if not item:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            json_response(self, HTTPStatus.OK, playground_payload(item))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def save_resume_proof(self, item: dict, body: dict) -> dict:
        item = normalize_resume_item(item)
        proof = body.get("proof", [])
        if not isinstance(proof, list):
            proof = []
        item["user_proof"] = proof
        jd_intelligence = ensure_item_intelligence(item)
        version = active_version(item)
        gaps = build_keyword_gaps(item.get("jd", ""), version.get("structured_resume", {}), item.get("profile", {}), proof, jd_intelligence=jd_intelligence)
        analysis = score_resume(item.get("jd", ""), version.get("structured_resume", {}), item.get("profile", {}), version.get("pdf_path"), proof, jd_intelligence=jd_intelligence)
        item["keyword_gaps"] = gaps
        item["analysis"] = analysis
        version["keyword_gaps"] = gaps
        version["analysis"] = analysis
        return item

    def activate_resume_version(self, item: dict, body: dict) -> dict:
        item = normalize_resume_item(item)
        version_id = str(body.get("version_id", "")).strip()
        versions = item.get("versions", [])
        version = next((candidate for candidate in versions if candidate.get("id") == version_id), None)
        if not version:
            return item
        item["active_version_id"] = version_id
        item["docx_path"] = version.get("docx_path")
        item["pdf_path"] = version.get("pdf_path")
        item["structured_resume"] = version.get("structured_resume", {})
        item["analysis"] = version.get("analysis", {})
        item["keyword_gaps"] = version.get("keyword_gaps", {})
        return item

    def rescore_resume_item(self, item: dict) -> dict:
        item = normalize_resume_item(item)
        jd_intelligence = ensure_item_intelligence(item)
        version = active_version(item)
        proof = item.get("user_proof", [])
        gaps = build_keyword_gaps(item.get("jd", ""), version.get("structured_resume", {}), item.get("profile", {}), proof, jd_intelligence=jd_intelligence)
        analysis = score_resume(item.get("jd", ""), version.get("structured_resume", {}), item.get("profile", {}), version.get("pdf_path"), proof, jd_intelligence=jd_intelligence)
        item["keyword_gaps"] = gaps
        item["analysis"] = analysis
        version["keyword_gaps"] = gaps
        version["analysis"] = analysis
        return item

    def regenerate_resume_item(self, run_id: str, body: dict) -> dict | None:
        set_monitoring_context(run_id=run_id)
        item = find_history_item(run_id)
        if not item:
            return None
        item = normalize_resume_item(item)
        api_key = str(body.get("api_key", "")).strip() or None
        active_api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not active_api_key:
            raise RegenerationError("Regeneration needs an OpenAI key. Configure OPENAI_API_KEY on the server or add it in the OpenAI API Key field.")
        with monitor_span("regenerate.jd_intelligence", "Ensure JD intelligence", run_id=run_id):
            jd_intelligence = ensure_item_intelligence(item, api_key=active_api_key)
        proof = body.get("proof")
        if isinstance(proof, list):
            item["user_proof"] = proof
        instruction = str(body.get("instruction", "")).strip()
        current_versions = item.setdefault("versions", [])
        version_id = f"v{len(current_versions) + 1}"
        run_dir = RUN_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        augmented_jd = item.get("jd", "")
        previous = active_version(item)
        with monitor_span("regenerate.keyword_plan", "Build regeneration keyword plan", run_id=run_id, version_id=version_id):
            current_gaps = build_keyword_gaps(
                item.get("jd", ""),
                previous.get("structured_resume", {}),
                item.get("profile", {}),
                item.get("user_proof", []),
                jd_intelligence=jd_intelligence,
            )
        augmented_jd += "\n\n" + intelligence_summary(jd_intelligence, current_gaps)
        augmented_jd += "\n\nPREVIOUS STRUCTURED RESUME VERSION:\n" + json.dumps(previous.get("structured_resume", {}), indent=2)
        if instruction:
            augmented_jd += "\n\nPLAYGROUND REGENERATION REQUEST:\n" + instruction

        source_profile = item.get("profile", {}) if isinstance(item.get("profile"), dict) else {}
        profile = source_profile
        details = profile.get("details", {}) if isinstance(profile, dict) else {}
        if profile_has_content(profile):
            with monitor_span("regenerate.template", "Create regeneration profile template", run_id=run_id, version_id=version_id):
                template_path = create_template_from_profile(profile, run_dir / f"{version_id}_template.docx")
        else:
            source_docx = previous.get("docx_path") or item.get("docx_path")
            if not source_docx or not Path(source_docx).exists():
                raise RegenerationError("Old resume source missing. Generate a fresh resume first.")
            try:
                with monitor_span("regenerate.legacy_template", "Create regeneration template from existing DOCX", run_id=run_id, version_id=version_id):
                    template_path = make_template_from_resume(Path(source_docx), run_dir / f"{version_id}_template.docx")
            except Exception as exc:
                raise RegenerationError(f"Could not prepare the old resume for regeneration: {exc}") from exc
        try:
            with monitor_span("regenerate.resume", "Generate regenerated resume document", run_id=run_id, version_id=version_id):
                result = generate_resume_from_jd(
                    augmented_jd,
                    base_resume_path=template_path,
                    output_root=OUTPUT_ROOT,
                    details=details,
                    skip_pdf=item.get("skip_pdf", False),
                    api_key=active_api_key,
                )
            with monitor_span("regenerate.version_files", "Copy regenerated version files", run_id=run_id, version_id=version_id):
                result = copy_version_files(result, run_dir, version_id)
        except Exception as exc:
            capture_monitoring_exception(exc, run_id=run_id, version_id=version_id, stage="regenerate.resume")
            raise RegenerationError(f"Regeneration failed: {exc}") from exc
        with monitor_span("regenerate.scoring", "Score regenerated resume", run_id=run_id, version_id=version_id):
            gaps = build_keyword_gaps(item.get("jd", ""), result["structured_resume"], profile, item.get("user_proof", []), jd_intelligence=jd_intelligence)
            analysis = score_resume(item.get("jd", ""), result["structured_resume"], profile, result.get("pdf_path"), item.get("user_proof", []), jd_intelligence=jd_intelligence)
        version = {
            "id": version_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "label": f"Regeneration {len(current_versions) + 1}",
            "instruction": instruction,
            "docx_path": result["docx_path"],
            "pdf_path": result["pdf_path"],
            "structured_resume": result["structured_resume"],
            "jd_intelligence": jd_intelligence,
            "analysis": analysis,
            "keyword_gaps": gaps,
        }

        def apply_update(current: dict) -> dict:
            current = normalize_resume_item(current)
            current.setdefault("versions", []).append(version)
            current["active_version_id"] = version_id
            current["docx_path"] = result["docx_path"]
            current["pdf_path"] = result["pdf_path"]
            current["structured_resume"] = result["structured_resume"]
            current["jd_intelligence"] = jd_intelligence
            current["analysis"] = analysis
            current["keyword_gaps"] = gaps
            current["user_proof"] = item.get("user_proof", [])
            current.setdefault("playground_notes", []).append({
                "created_at": version["created_at"],
                "message": instruction or "Regenerated against the keyword strategy plan.",
            })
            return current

        RESULTS[run_id] = result
        with monitor_span("regenerate.history_save", "Save regenerated resume version", run_id=run_id, version_id=version_id):
            return update_history_item(run_id, apply_update)

    def serve_download(self, path: str) -> None:
        with monitor_span("file.download", "Serve generated file download", path=path):
            parts = path.strip("/").split("/")
            if len(parts) != 4:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            _, _, run_id, kind = parts
            set_monitoring_context(run_id=run_id)
            result = RESULTS.get(run_id)
            history_item = find_history_item(run_id)
            version = active_version(history_item or {}) if history_item else {}
            target = (
                result.get("docx_path") if kind == "docx" else result.get("pdf_path")
            ) if result and not history_item else (
                version.get("docx_path") if kind == "docx" else version.get("pdf_path")
            )
            if not target:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            file_path = Path(target)
            if not file_path.exists():
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            body = file_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", MIME_TYPES.get(file_path.suffix, "application/octet-stream"))
            self.send_header("Content-Disposition", f'attachment; filename="{file_path.name}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def serve_preview(self, path: str) -> None:
        with monitor_span("file.preview", "Serve generated PDF preview", path=path):
            parts = path.strip("/").split("/")
            if len(parts) != 4 or parts[-1] != "pdf":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            _, _, run_id, _ = parts
            set_monitoring_context(run_id=run_id)
            item = find_history_item(run_id)
            version = active_version(item or {}) if item else {}
            target = version.get("pdf_path")
            if not target:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            file_path = Path(target)
            if not file_path.exists():
                self.send_error(HTTPStatus.NOT_FOUND)
                return

        file_size = file_path.stat().st_size
        range_header = self.headers.get("Range", "")
        start = 0
        end = file_size - 1
        status = HTTPStatus.OK

        if range_header.startswith("bytes="):
            match = re.match(r"bytes=(\d*)-(\d*)", range_header)
            if match:
                raw_start, raw_end = match.groups()
                if raw_start:
                    start = int(raw_start)
                if raw_end:
                    end = int(raw_end)
                if not raw_start and raw_end:
                    suffix = int(raw_end)
                    start = max(file_size - suffix, 0)
                    end = file_size - 1
                if start >= file_size or end < start:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    return
                end = min(end, file_size - 1)
                status = HTTPStatus.PARTIAL_CONTENT

        length = end - start + 1
        with file_path.open("rb") as handle:
            handle.seek(start)
            body = handle.read(length)

        self.send_response(status)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'inline; filename="{file_path.name}"')
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(os.environ.get("PORT", "8787"))
    host = os.environ.get("HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), ResumeForgeHandler)
    print(f"Resume Forge running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
