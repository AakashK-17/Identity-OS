# Hone

Hone is an AI resume workspace for job seekers. Users sign in, build a structured base profile once, paste job descriptions, generate tailored resumes, preview the final PDF, score the result, and keep every company, role, JD, DOCX, PDF, and version in searchable history.

The product is designed as a job-search memory system, not a one-off resume generator.

## What It Does

- **Google sign-in** keeps each user's profile, resumes, and history separated by account.
- **Structured base profile** collects contact details, experience, projects, skills, education, certifications, and other resume foundation data.
- **JD intelligence** parses job descriptions into hiring-relevant signals instead of noisy keyword fragments.
- **Resume generation** creates tailored DOCX and PDF files from the user's profile and target JD.
- **PDF preview** shows the generated resume directly inside the app.
- **Resume scoring** evaluates ATS alignment, proof strength, readability, role fit, format quality, and interview defensibility.
- **Keyword strategy analysis** tracks exact matches, bridge keywords, repetition targets, section distribution, and semantic clusters.
- **Resume Playground** lets users regenerate a resume version with proof, safe JD additions, or chat-style refinement.
- **Version history** preserves older resume versions instead of overwriting them.
- **Searchable job history** stores company, role, JD, timestamp, DOCX, PDF, analysis, and playground notes.

## Current Product Flow

1. User lands on the public homepage.
2. User signs in with Google.
3. User enters their base resume details in the workspace.
4. User pastes a job description.
5. Hone extracts company, role, JD signals, risks, and proof-worthy requirements.
6. The backend generates a tailored resume as DOCX and PDF.
7. The app opens the Resume Playground for that run.
8. User previews the PDF, reviews scores and keyword strategy, then regenerates new versions when needed.
9. Every run is saved automatically into history.

## Tech Stack

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python HTTP server
- **AI:** OpenAI API
- **Documents:** `python-docx`
- **PDF export:** LibreOffice headless mode
- **Auth:** Google Identity Services
- **Storage:** JSON files and generated assets on local disk or Render persistent disk
- **Deployment:** Docker + Render Blueprint

## Repository Structure

```text
web/
  index.html              Landing page and workspace shell
  styles.css              Full UI styling and responsive layout
  app.js                  Frontend state, auth, history, playground, generation
  identity-engine.js      Landing page interaction layer

app_backend.py            Main web server and API
generate_resume.py        Legacy/local CLI resume generator
prepare_resume_template.py Legacy DOCX placeholder helper
requirements.txt          Python dependencies
Dockerfile                Production image with LibreOffice
render.yaml               Render Blueprint configuration
.env.example              Local environment template
```

## Backend API

Key routes:

```text
GET  /api/config
POST /api/signin
GET  /api/profile
POST /api/profile
GET  /api/history
POST /api/generate
GET  /api/resume/{run_id}
GET  /api/preview/{run_id}/pdf
GET  /api/download/{run_id}/docx
GET  /api/download/{run_id}/pdf
POST /api/resume/{run_id}/proof
POST /api/resume/{run_id}/regenerate
POST /api/resume/{run_id}/score
POST /api/resume/{run_id}/activate
```

## Environment Variables

Create a local `.env` file from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Set:

```text
OPENAI_API_KEY=your_openai_api_key_here
GOOGLE_CLIENT_ID=your_google_oauth_web_client_id_here
HOST=127.0.0.1
PORT=8787
OUTPUT_ROOT=./data/generated
```

Do not commit `.env`. It contains secrets.

## Local Setup

Install Python dependencies:

```powershell
pip install -r requirements.txt
```

Install LibreOffice for PDF export:

```text
https://www.libreoffice.org/download/download-libreoffice/
```

Run the app:

```powershell
python app_backend.py
```

Open:

```text
http://127.0.0.1:8787
```

## Google Login Setup

In Google Cloud Console:

1. Go to **Google Auth Platform**.
2. Configure the OAuth consent screen.
3. Create an **OAuth Client ID**.
4. Choose **Web application**.
5. Add local and production origins:

```text
http://127.0.0.1:8787
https://identity-os-resume.onrender.com
```

6. Copy the Web Client ID into:

```text
GOOGLE_CLIENT_ID=...
```

For Render, add it as a service environment variable.

## Deploy To Render

This project is ready for Render Blueprint deployment.

1. Push the repo to GitHub.
2. In Render, create a new **Blueprint** from the repo.
3. Render reads `render.yaml`.
4. Add these environment variables:

```text
OPENAI_API_KEY=your OpenAI API key
GOOGLE_CLIENT_ID=your Google OAuth Web Client ID
HOST=0.0.0.0
PORT=8787
OUTPUT_ROOT=/app/data/generated
```

5. Confirm the persistent disk is mounted at:

```text
/app/data
```

6. Redeploy.

Production URL currently used:

```text
https://identity-os-resume.onrender.com
```

## Local Docker Test

```powershell
docker build -t identity-os-resume .
docker run --rm -p 8787:8787 --env-file .env identity-os-resume
```

## JD Intelligence And Keyword Strategy

Hone extracts hiring signals from high-signal JD sections only:

- Role overview
- Responsibilities
- Qualifications
- Requirements
- Preferred skills

It ignores:

- Company history
- Awards
- Benefits
- Compensation
- Legal and equal opportunity text
- Dates
- Locations
- Generic verbs

Signals are grouped into:

- `tools_platforms`
- `functional_work`
- `methods_frameworks`
- `domain_context`
- `stakeholder_scope`
- `seniority_signals`

The app turns important signals into a keyword plan with exact phrases, repetition targets, preferred sections, and semantic clusters. It should track terms like `PyTorch`, `Qdrant`, `Salesforce`, `IRB protocols`, `GAAP`, or `Google Analytics`, not noisy fragments like `Knowledge`, `Current`, `Benefits`, `NASDAQ`, or company names.

## Resume Playground

Each generated resume gets a unique playground with:

- Overall score and category scores
- Exact matched JD signals
- Bridge keywords added through projects
- Weak or underused terms
- Keyword frequency and section distribution
- Semantic cluster coverage
- Keyword placement proof map
- PDF preview
- DOCX and PDF downloads
- Version selector
- Regeneration status
- Chat-style refinement box
- Version history notes

Regeneration creates a new version and keeps the previous one available.

## Storage Notes

Current v1 storage is file-based:

```text
data/
  history.json
  profiles.json
  jd_cache.json
runs/
uploads/
OUTPUT_ROOT/
```

On Render, generated files and JSON history should live on the persistent disk. For a larger multi-user product, move this layer to Postgres or Supabase and move documents to object storage.

## Legacy CLI Scripts

The old local script flow still exists for quick experiments:

```powershell
python generate_resume.py
```

That script reads `job_description.txt` and uses a DOCX template workflow. The main product experience is now the web app in `app_backend.py` and `web/`.

## Security Notes

- Never commit raw OpenAI keys.
- Never store user-provided API keys in history.
- Google profile data is used only to scope profile and history records by account.
- The current JSON storage is suitable for a single-instance MVP, not a fully scaled production system.
