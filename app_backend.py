import json
import os
import re
import shutil
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import cgi

from generate_resume import (
    BASE_RESUME,
    create_template_from_profile,
    flatten_generated_text,
    generate_resume_from_jd,
    make_template_from_resume,
)


ROOT = Path(__file__).parent.resolve()
PUBLIC_DIR = ROOT / "web"
UPLOAD_DIR = ROOT / "uploads"
RUN_DIR = ROOT / "runs"
DATA_DIR = ROOT / "data"
HISTORY_FILE = DATA_DIR / "history.json"
OUTPUT_ROOT = Path(os.environ.get("OUTPUT_ROOT", DATA_DIR / "generated")).resolve()

UPLOAD_DIR.mkdir(exist_ok=True)
RUN_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

RESULTS: dict[str, dict] = {}


MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


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
    record["base_resume"] = profile
    save_history(data)
    return profile


def get_profile(email: str) -> dict:
    data = load_history()
    return data.get("users", {}).get(user_key(email), {}).get("base_resume", {})


def add_history_item(email: str, item: dict) -> None:
    key = user_key(email)
    data = load_history()
    record = data.setdefault("users", {}).setdefault(key, {"profile": {"email": key}, "items": []})
    record.setdefault("items", []).insert(0, item)
    save_history(data)


def get_history_items(email: str) -> list[dict]:
    data = load_history()
    return data.get("users", {}).get(user_key(email), {}).get("items", [])


def find_history_item(run_id: str) -> dict | None:
    data = load_history()
    for record in data.get("users", {}).values():
        for item in record.get("items", []):
            if item.get("id") == run_id:
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


def profile_to_text(profile: dict, proof: list[dict] | None = None) -> str:
    text = json.dumps(profile or {}, ensure_ascii=False)
    for item in proof or []:
        text += " " + " ".join(str(item.get(key, "")) for key in ["keyword", "where", "proof"])
    return text


def important_jd_terms(jd_text: str) -> list[str]:
    text = jd_text or ""
    lowered = text.lower()
    curated = [
        "Python", "SQL", "Pandas", "NumPy", "scikit-learn", "TensorFlow", "PyTorch",
        "machine learning", "deep learning", "statistics", "data analysis", "data cleaning",
        "data visualization", "dashboard", "Tableau", "Power BI", "Matplotlib", "Seaborn",
        "AWS", "Azure", "GCP", "S3", "EC2", "Lambda", "Glue", "Redshift", "SageMaker",
        "Databricks", "Snowflake", "ETL", "data pipeline", "model testing", "training",
        "overfitting", "SQL databases", "communication", "collaboration", "reports",
        "real datasets", "Kaggle", "GitHub", "cloud platforms", "problem-solving",
    ]
    terms = [term for term in curated if re.search(rf"\b{re.escape(term.lower())}\b", lowered)]

    for match in re.finditer(r"\b[A-Z][A-Za-z0-9+#./-]*(?:\s+[A-Z][A-Za-z0-9+#./-]*){0,2}\b", text):
        value = match.group(0).strip(" .,:;()[]")
        if 2 <= len(value) <= 36 and value.lower() not in {"we", "the", "job", "about"}:
            terms.append(value)

    for pattern in [
        r"\b(?:build|building|testing|training|cleaning|preparing|visualization|dashboards?|reports?|databases?|models?)\b(?:\s+\w+){0,3}",
        r"\b(?:data|machine learning|cloud|statistical|academic|internship)\s+\w+(?:\s+\w+)?\b",
    ]:
        for match in re.finditer(pattern, lowered):
            phrase = re.sub(r"\s+", " ", match.group(0)).strip()
            if len(phrase.split()) >= 2:
                terms.append(phrase)

    seen = set()
    cleaned = []
    stop = {"full time", "onsite hybrid", "required skills", "preferred nice", "key responsibilities"}
    for term in terms:
        term = re.sub(r"\s+", " ", term).strip(" .,:;()[]")
        key = term.lower()
        if key in seen or key in stop or " with" in key or len(key) < 2:
            continue
        seen.add(key)
        cleaned.append(term)
    return cleaned[:45]


def contains_term(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term.lower())}\b", (text or "").lower()) is not None


def build_keyword_gaps(jd_text: str, generated_data: dict, profile: dict, proof: list[dict] | None = None) -> dict:
    terms = important_jd_terms(jd_text)
    generated_text = flatten_generated_text(generated_data or {})
    evidence_text = profile_to_text(profile, proof)
    covered = []
    supported_missing = []
    needs_user_proof = []
    not_recommended = []
    high_risk = {"sagemaker", "redshift", "glue", "lambda", "ec2", "s3", "databricks", "snowflake", "azure", "gcp"}

    for term in terms:
        if contains_term(generated_text, term):
            covered.append(term)
        elif contains_term(evidence_text, term):
            supported_missing.append(term)
        elif term.lower() in high_risk:
            needs_user_proof.append(term)
        elif len(term.split()) > 3:
            not_recommended.append(term)
        else:
            needs_user_proof.append(term)

    total = max(1, len(terms))
    return {
        "important_terms": terms,
        "covered": covered,
        "supported_missing": supported_missing[:18],
        "needs_user_proof": needs_user_proof[:18],
        "not_recommended": not_recommended[:12],
        "coverage_percent": round((len(covered) / total) * 100),
    }


def score_resume(jd_text: str, generated_data: dict, profile: dict, pdf_path: str | None, proof: list[dict] | None = None) -> dict:
    gaps = build_keyword_gaps(jd_text, generated_data, profile, proof)
    resume_text = flatten_generated_text(generated_data or {})
    words = len(re.findall(r"\b[\w+#./-]+\b", resume_text))
    proof_penalty = min(45, len(gaps["needs_user_proof"]) * 5)
    supported_penalty = min(20, len(gaps["supported_missing"]) * 3)
    readability = max(55, min(96, 100 - abs(words - 620) // 10))
    ats = max(0, min(100, gaps["coverage_percent"] - supported_penalty // 2))
    proof_strength = max(0, 100 - proof_penalty - supported_penalty)
    role_fit = max(35, min(98, round((ats * 0.65) + (proof_strength * 0.35))))
    format_quality = 95 if pdf_path else 78
    interview_defensibility = max(0, 100 - proof_penalty)
    overall = round((ats + proof_strength + readability + role_fit + format_quality + interview_defensibility) / 6)
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
        "ats_keyword_alignment": f"{len(gaps['covered'])} of {len(gaps['important_terms'])} important JD signals are visible in the resume.",
        "proof_strength": "Unsupported terms are separated for user proof before regeneration.",
        "recruiter_readability": f"The generated resume has about {words} words across summary, experience, projects, and competencies.",
        "role_fit": "Role fit blends keyword coverage with evidence strength.",
        "format_quality": "PDF preview is available." if pdf_path else "DOCX is available; PDF was skipped.",
        "interview_defensibility": "Claims stay stronger when tools and responsibilities have profile evidence or user proof.",
    }
    return {
        "scores": scores,
        "explanations": explanations,
        "strengths": [
            "Resume was generated from the user's structured base profile.",
            "JD terms are evaluated against actual resume text and profile evidence.",
        ],
        "risks": [
            "Some JD terms require user proof before safe inclusion."
        ] if gaps["needs_user_proof"] else [],
        "missing_keywords": gaps["supported_missing"] + gaps["needs_user_proof"],
        "unsupported_keywords": gaps["needs_user_proof"],
        "suggested_fixes": [
            "Provide proof for unsupported keywords, then regenerate for stronger ATS alignment.",
            "Use playground chat for targeted tone, focus, or section-level rewrites.",
        ],
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
        if item.get("used") is False:
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


def save_uploaded_file(field, destination: Path) -> Path | None:
    if field is None or not getattr(field, "filename", ""):
        return None

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        shutil.copyfileobj(field.file, handle)
    return destination


class ResumeForgeHandler(BaseHTTPRequestHandler):
    server_version = "ResumeForge/1.0"

    def log_message(self, format, *args):
        print(f"[resume-forge] {self.address_string()} - {format % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

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
            json_response(self, HTTPStatus.OK, {"google_client_id": os.environ.get("GOOGLE_CLIENT_ID", "")})
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
        try:
            if parsed.path == "/api/generate":
                result = self.handle_generate()
                json_response(self, HTTPStatus.OK, result)
                return
            if parsed.path == "/api/signin":
                profile = upsert_user(read_json_body(self))
                json_response(self, HTTPStatus.OK, {"profile": profile, "items": get_history_items(profile["email"])})
                return
            if parsed.path == "/api/profile":
                body = read_json_body(self)
                email = body.get("email", "")
                profile = save_profile(email, body.get("profile", {}))
                json_response(self, HTTPStatus.OK, {"profile": profile})
                return
            if parsed.path.startswith("/api/resume/"):
                self.handle_resume_action(parsed.path)
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def handle_generate(self) -> dict:
        content_type = self.headers.get("Content-Type", "")
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
            profile_data = json.loads(profile_json)
            base_resume_path = create_template_from_profile(profile_data, run_dir / "profile_template.docx")

        resume_field = form["resume"] if "resume" in form else None
        if not profile_json.strip() and resume_field is not None and getattr(resume_field, "filename", ""):
            uploaded_path = save_uploaded_file(
                resume_field,
                UPLOAD_DIR / f"{run_id}_{Path(resume_field.filename).name}",
            )
            if uploaded_path and uploaded_path.suffix.lower() == ".docx":
                base_resume_path = make_template_from_resume(uploaded_path, run_dir / "resume_template.docx")

        skip_pdf = form.getfirst("skip_pdf") == "true"
        result = generate_resume_from_jd(
            jd_text,
            base_resume_path=base_resume_path,
            output_root=OUTPUT_ROOT,
            details=details,
            skip_pdf=skip_pdf,
            api_key=api_key,
        )
        result = copy_version_files(result, run_dir, "v1")
        profile_for_analysis = profile_data if profile_json.strip() else {}
        keyword_gaps = build_keyword_gaps(jd_text, result["structured_resume"], profile_for_analysis)
        analysis = score_resume(
            jd_text,
            result["structured_resume"],
            profile_for_analysis,
            result["pdf_path"],
        )
        version = {
            "id": "v1",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "label": "Original generation",
            "instruction": "",
            "docx_path": result["docx_path"],
            "pdf_path": result["pdf_path"],
            "structured_resume": result["structured_resume"],
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
            "skip_pdf": skip_pdf,
            "versions": [version],
            "active_version_id": "v1",
            "analysis": analysis,
            "keyword_gaps": keyword_gaps,
            "user_proof": [],
            "playground_notes": [],
        }
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
        version = active_version(item)
        payload = dict(item)
        payload["active_version"] = version
        payload["docx_url"] = f"/api/download/{run_id}/docx"
        payload["pdf_url"] = f"/api/download/{run_id}/pdf" if version.get("pdf_path") else None
        payload["preview_url"] = f"/api/preview/{run_id}/pdf" if version.get("pdf_path") else None
        json_response(self, HTTPStatus.OK, payload)

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
            json_response(self, HTTPStatus.OK, item)
            return
        if action == "score":
            item = update_history_item(run_id, self.rescore_resume_item)
            if not item:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            json_response(self, HTTPStatus.OK, item)
            return
        if action == "activate":
            item = update_history_item(run_id, lambda current: self.activate_resume_version(current, body))
            if not item:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            json_response(self, HTTPStatus.OK, item)
            return
        if action == "regenerate":
            item = self.regenerate_resume_item(run_id, body)
            if not item:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            json_response(self, HTTPStatus.OK, item)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def save_resume_proof(self, item: dict, body: dict) -> dict:
        proof = body.get("proof", [])
        if not isinstance(proof, list):
            proof = []
        item["user_proof"] = proof
        version = active_version(item)
        gaps = build_keyword_gaps(item.get("jd", ""), version.get("structured_resume", {}), item.get("profile", {}), proof)
        analysis = score_resume(item.get("jd", ""), version.get("structured_resume", {}), item.get("profile", {}), version.get("pdf_path"), proof)
        item["keyword_gaps"] = gaps
        item["analysis"] = analysis
        version["keyword_gaps"] = gaps
        version["analysis"] = analysis
        return item

    def activate_resume_version(self, item: dict, body: dict) -> dict:
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
        version = active_version(item)
        proof = item.get("user_proof", [])
        gaps = build_keyword_gaps(item.get("jd", ""), version.get("structured_resume", {}), item.get("profile", {}), proof)
        analysis = score_resume(item.get("jd", ""), version.get("structured_resume", {}), item.get("profile", {}), version.get("pdf_path"), proof)
        item["keyword_gaps"] = gaps
        item["analysis"] = analysis
        version["keyword_gaps"] = gaps
        version["analysis"] = analysis
        return item

    def regenerate_resume_item(self, run_id: str, body: dict) -> dict | None:
        item = find_history_item(run_id)
        if not item:
            return None
        proof = body.get("proof")
        if isinstance(proof, list):
            item["user_proof"] = proof
        instruction = str(body.get("instruction", "")).strip()
        current_versions = item.setdefault("versions", [])
        version_id = f"v{len(current_versions) + 1}"
        run_dir = RUN_DIR / run_id
        proof_text = "\n".join(
            f"- {entry.get('keyword', '')}: {entry.get('proof', '')}"
            for entry in item.get("user_proof", [])
            if entry.get("used") is not False and entry.get("proof")
        )
        augmented_jd = item.get("jd", "")
        if proof_text:
            augmented_jd += "\n\nUSER-VERIFIED PROOF TO USE ONLY WHERE CREDIBLE:\n" + proof_text
        if instruction:
            augmented_jd += "\n\nPLAYGROUND REGENERATION REQUEST:\n" + instruction

        profile = merge_profile_with_proof(item.get("profile", {}), item.get("user_proof", []))
        template_path = create_template_from_profile(profile, run_dir / f"{version_id}_template.docx")
        details = profile.get("details", {})
        result = generate_resume_from_jd(
            augmented_jd,
            base_resume_path=template_path,
            output_root=OUTPUT_ROOT,
            details=details,
            skip_pdf=item.get("skip_pdf", False),
        )
        result = copy_version_files(result, run_dir, version_id)
        gaps = build_keyword_gaps(item.get("jd", ""), result["structured_resume"], profile, item.get("user_proof", []))
        analysis = score_resume(item.get("jd", ""), result["structured_resume"], profile, result.get("pdf_path"), item.get("user_proof", []))
        version = {
            "id": version_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "label": f"Regeneration {len(current_versions) + 1}",
            "instruction": instruction,
            "docx_path": result["docx_path"],
            "pdf_path": result["pdf_path"],
            "structured_resume": result["structured_resume"],
            "analysis": analysis,
            "keyword_gaps": gaps,
        }

        def apply_update(current: dict) -> dict:
            current.setdefault("versions", []).append(version)
            current["active_version_id"] = version_id
            current["docx_path"] = result["docx_path"]
            current["pdf_path"] = result["pdf_path"]
            current["structured_resume"] = result["structured_resume"]
            current["analysis"] = analysis
            current["keyword_gaps"] = gaps
            current["user_proof"] = item.get("user_proof", [])
            current.setdefault("playground_notes", []).append({
                "created_at": version["created_at"],
                "message": instruction or "Regenerated with saved proof.",
            })
            return current

        RESULTS[run_id] = result
        return update_history_item(run_id, apply_update)

    def serve_download(self, path: str) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        _, _, run_id, kind = parts
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
        parts = path.strip("/").split("/")
        if len(parts) != 4 or parts[-1] != "pdf":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        _, _, run_id, _ = parts
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
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'inline; filename="{file_path.name}"')
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
