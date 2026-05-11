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
        if item.get("used") is True:
            text += " " + " ".join(str(item.get(key, "")) for key in ["keyword", "where", "proof"])
    return text


JD_SIGNAL_CATALOG = {
    "technical_tools": [
        ("Python", [r"\bpython\b"]),
        ("PyTorch", [r"\bpytorch\b"]),
        ("TensorFlow", [r"\btensorflow\b"]),
        ("scikit-learn", [r"\bscikit[- ]learn\b", r"\bsklearn\b"]),
        ("LLM", [r"\bllm\b", r"\blarge language model"]),
        ("VLM", [r"\bvlm\b", r"\bvision language model"]),
        ("dLLM", [r"\bdllm\b"]),
        ("VLA", [r"\bvla\b"]),
        ("video generation", [r"\bvideo generations?\b"]),
        ("distributed training", [r"\bdistributed training\b"]),
        ("large-scale data processing", [r"\blarge[- ]scale data processing\b"]),
        ("simulation platforms", [r"\bsimulation platforms?\b"]),
    ],
    "functional_work": [
        ("model training", [r"\bmodel training\b", r"\btraining\b"]),
        ("fine-tuning", [r"\bfine[- ]tuning\b"]),
        ("model optimization", [r"\boptimization\b", r"\boptimizing\b"]),
        ("model monitoring", [r"\bmonitoring\b"]),
        ("closed-loop evaluation", [r"\bclosed[- ]loop evaluation\b"]),
        ("scenario coverage", [r"\bscenario coverage\b"]),
        ("human-led triaging", [r"\bhuman[- ]led triaging\b", r"\btriaging\b"]),
        ("high-volume workflows", [r"\bhigh[- ]volume workflows?\b"]),
        ("critical anomalies", [r"\bcritical anomalies\b", r"\banomal(?:y|ies)\b"]),
        ("fleet-scale assessment", [r"\bfleet[- ]scale assessment\b"]),
        ("evaluation systems", [r"\bevaluation systems?\b"]),
        ("training and evaluation loops", [r"\btraining and evaluation loops?\b"]),
        ("end-to-end ML systems", [r"\bend[- ]to[- ]end\b.*\bml systems?\b", r"\bshipping impactful ml systems\b"]),
    ],
    "ml_methods": [
        ("reinforcement learning", [r"\breinforcement learning\b", r"\bstrong rl\b"]),
        ("RL-style methods", [r"\brl[- ]style methods?\b"]),
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
    ],
    "domain_signals": [
        ("autonomous vehicles", [r"\bautonomous vehicles?\b"]),
        ("autonomous driving", [r"\bautonomous driving\b"]),
        ("robotics", [r"\brobotics\b"]),
        ("complex simulation environments", [r"\bcomplex simulation environments?\b"]),
        ("simulation-aligned workflows", [r"\bsimulation[- ]aligned workflows?\b"]),
        ("self-driving behavior", [r"\bself[- ]driving behavior\b"]),
        ("driving behaviors", [r"\bdriving behaviors?\b"]),
        ("safety-critical AI systems", [r"\bsafety[- ]critical ai systems?\b"]),
        ("real-world exposure", [r"\breal[- ]world exposure\b"]),
    ],
    "collaboration_signals": [
        ("Prediction teams", [r"\bprediction\b"]),
        ("Planning teams", [r"\bplanning\b"]),
        ("Research teams", [r"\bresearch\b"]),
        ("platform/engineering leads", [r"\bplatform/engineering leads?\b", r"\bplatform teams?\b"]),
        ("cross-cutting improvements", [r"\bcross[- ]cutting improvements?\b"]),
        ("technical leadership", [r"\btechnical leadership\b"]),
        ("stakeholder alignment", [r"\binfluencing stakeholders\b", r"\baligning teams\b"]),
        ("communication of trade-offs", [r"\bcomplex trade[- ]offs\b"]),
    ],
    "seniority_signals": [
        ("production-grade ML", [r"\bproduction[- ]grade\b", r"\bproduction[- ]oriented ml\b"]),
        ("ambiguous technical work", [r"\bambiguous technical work\b"]),
        ("problem framing", [r"\bproblem framing\b"]),
        ("reliable delivery", [r"\breliable delivery\b"]),
        ("evaluation rigor", [r"\bevaluation rigor\b"]),
        ("3+ years ML production experience", [r"\b3\+ years\b.*\bml\b"]),
        ("M.S. or Ph.D.", [r"\bm\.s\.\b", r"\bph\.d\.\b"]),
    ],
}


SECTION_MAP = {
    "about_company": {"about", "description", "company", "overview", "who we are"},
    "responsibilities": {"responsibility", "responsibilities", "what you'll do", "what you will do", "role responsibilities"},
    "requirements": {"requirements", "required", "qualifications", "minimum qualifications"},
    "preferred": {"preferred", "nice to have", "preferred qualifications"},
    "benefits_compensation": {"compensation", "benefits", "base salary", "salary", "privacy"},
}


def normalize_heading(line: str) -> str:
    return re.sub(r"[^a-z0-9 +'/-]+", "", line.strip().lower()).strip()


def parse_jd_sections(jd_text: str) -> dict:
    sections = {
        "about_company": [],
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
        for key in ["responsibilities", "requirements", "preferred"]
        if sections.get(key)
    )


def extract_jd_intelligence(jd_text: str) -> dict:
    sections = parse_jd_sections(jd_text)
    signal_text = high_signal_jd_text(sections)
    if not signal_text.strip():
        signal_text = "\n".join(sections.values())
    signals = {category: [] for category in JD_SIGNAL_CATALOG}
    seen = set()

    for category, items in JD_SIGNAL_CATALOG.items():
        for term, patterns in items:
            if any(re.search(pattern, signal_text, re.IGNORECASE | re.DOTALL) for pattern in patterns):
                key = term.lower()
                if key in seen:
                    continue
                seen.add(key)
                signals[category].append({
                    "term": term,
                    "category": category,
                    "label": category.replace("_", " ").title(),
                })

    important_terms = [item for values in signals.values() for item in values]
    return {
        "sections": sections,
        "signals": signals,
        "important_terms": important_terms,
        "ignored_sections": ["about_company", "benefits_compensation"],
    }


def ensure_jd_intelligence(item_or_jd) -> dict:
    if isinstance(item_or_jd, dict):
        return item_or_jd.get("jd_intelligence") or extract_jd_intelligence(item_or_jd.get("jd", ""))
    return extract_jd_intelligence(str(item_or_jd or ""))


def important_jd_terms(jd_text: str) -> list[dict]:
    return extract_jd_intelligence(jd_text).get("important_terms", [])


def signal_term(signal) -> str:
    return signal.get("term", "") if isinstance(signal, dict) else str(signal)


def contains_term(text: str, signal) -> bool:
    term = signal_term(signal)
    if not term:
        return False
    normalized_text = (text or "").lower()
    normalized_term = term.lower()
    if re.search(rf"\b{re.escape(normalized_term)}\b", normalized_text):
        return True
    aliases = {
        "RL-style methods": ["rl", "reinforcement learning"],
        "reinforcement learning": ["rl"],
        "LLM": ["large language model", "llms"],
        "VLM": ["vision language model", "vlms"],
        "fine-tuning": ["finetuning", "fine tuning"],
        "model monitoring": ["monitoring"],
        "distributed training": ["distributed model training"],
    }
    return any(re.search(rf"\b{re.escape(alias.lower())}\b", normalized_text) for alias in aliases.get(term, []))


def build_keyword_gaps(jd_text: str, generated_data: dict, profile: dict, proof: list[dict] | None = None, jd_intelligence: dict | None = None) -> dict:
    intelligence = jd_intelligence or extract_jd_intelligence(jd_text)
    terms = intelligence.get("important_terms", [])
    generated_text = flatten_generated_text(generated_data or {})
    evidence_text = profile_to_text(profile, proof)
    covered = []
    supported_missing = []
    needs_user_proof = []
    not_recommended = []
    high_risk_categories = {"domain_signals", "ml_methods", "seniority_signals", "technical_tools"}

    for signal in terms:
        category = signal.get("category", "") if isinstance(signal, dict) else ""
        if contains_term(generated_text, signal):
            covered.append(signal)
        elif contains_term(evidence_text, signal):
            supported_missing.append(signal)
        elif category in high_risk_categories:
            needs_user_proof.append(signal)
        else:
            not_recommended.append(signal)

    total = max(1, len(terms))
    return {
        "important_terms": terms,
        "covered": covered,
        "supported_missing": supported_missing[:18],
        "needs_user_proof": needs_user_proof[:18],
        "not_recommended": not_recommended[:12],
        "coverage_percent": round((len(covered) / total) * 100),
    }


def score_resume(jd_text: str, generated_data: dict, profile: dict, pdf_path: str | None, proof: list[dict] | None = None, jd_intelligence: dict | None = None) -> dict:
    gaps = build_keyword_gaps(jd_text, generated_data, profile, proof, jd_intelligence=jd_intelligence)
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


def intelligence_summary(jd_intelligence: dict, supported_missing: list, proven_terms: list) -> str:
    signals = jd_intelligence.get("signals", {}) if jd_intelligence else {}
    lines = ["JD INTELLIGENCE SIGNALS TO PRIORITIZE:"]
    for category, items in signals.items():
        values = [signal_term(item) for item in items]
        if values:
            lines.append(f"- {category.replace('_', ' ').title()}: {', '.join(values)}")
    if supported_missing:
        lines.append("SUPPORTED MISSING TERMS TO ADD WHERE NATURAL:")
        lines.extend(f"- {signal_term(item)}" for item in supported_missing)
    if proven_terms:
        lines.append("USER-PROVEN TERMS TO ADD WHERE TRUTHFUL:")
        lines.extend(f"- {item}" for item in proven_terms)
    lines.append("Do not add unproven needs_user_proof terms.")
    return "\n".join(lines)


def ensure_item_intelligence(item: dict) -> dict:
    if not item.get("jd_intelligence"):
        item["jd_intelligence"] = extract_jd_intelligence(item.get("jd", ""))
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
        jd_intelligence = extract_jd_intelligence(jd_text)
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
            "api_key_available": bool(api_key or os.environ.get("OPENAI_API_KEY")),
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
        if not item.get("jd_intelligence"):
            item = update_history_item(run_id, lambda current: self.rescore_resume_item(current)) or item
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
        item = find_history_item(run_id)
        if not item:
            return None
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("Regeneration needs an OpenAI key configured on the server.")
        jd_intelligence = ensure_item_intelligence(item)
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
            if entry.get("used") is True and entry.get("proof")
        )
        augmented_jd = item.get("jd", "")
        previous = active_version(item)
        current_gaps = build_keyword_gaps(
            item.get("jd", ""),
            previous.get("structured_resume", {}),
            item.get("profile", {}),
            item.get("user_proof", []),
            jd_intelligence=jd_intelligence,
        )
        proven_terms = [
            entry.get("keyword", "")
            for entry in item.get("user_proof", [])
            if entry.get("used") is True and entry.get("proof")
        ]
        augmented_jd += "\n\n" + intelligence_summary(
            jd_intelligence,
            current_gaps.get("supported_missing", []),
            proven_terms,
        )
        augmented_jd += "\n\nPREVIOUS STRUCTURED RESUME VERSION:\n" + json.dumps(previous.get("structured_resume", {}), indent=2)
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
