import json
import os
import shutil
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import cgi

from generate_resume import (
    BASE_RESUME,
    create_template_from_profile,
    generate_resume_from_jd,
    make_template_from_resume,
)


ROOT = Path(__file__).parent.resolve()
PUBLIC_DIR = ROOT / "web"
UPLOAD_DIR = ROOT / "uploads"
RUN_DIR = ROOT / "runs"
DATA_DIR = ROOT / "data"
HISTORY_FILE = DATA_DIR / "history.json"
OUTPUT_ROOT = Path(os.environ.get("OUTPUT_ROOT", RUN_DIR / "generated")).resolve()

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

        RESULTS[run_id] = result
        history_item = {
            "id": run_id,
            "company": result["company"],
            "role": result["role"],
            "jd": jd_text,
            "created_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "docx_url": f"/api/download/{run_id}/docx",
            "pdf_url": f"/api/download/{run_id}/pdf" if result["pdf_path"] else None,
            "docx_path": result["docx_path"],
            "pdf_path": result["pdf_path"],
        }
        add_history_item(user_email, history_item)
        response = {
            "run_id": run_id,
            "company": result["company"],
            "role": result["role"],
            "docx_url": f"/api/download/{run_id}/docx",
            "pdf_url": f"/api/download/{run_id}/pdf" if result["pdf_path"] else None,
            "history_item": history_item,
            "structured_resume": result["structured_resume"],
        }
        return response

    def serve_download(self, path: str) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        _, _, run_id, kind = parts
        result = RESULTS.get(run_id)
        if not result:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        target = result.get("docx_path") if kind == "docx" else result.get("pdf_path")
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


def main() -> None:
    port = int(os.environ.get("PORT", "8787"))
    host = os.environ.get("HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), ResumeForgeHandler)
    print(f"Resume Forge running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
