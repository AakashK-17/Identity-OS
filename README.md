# Local AI Resume Generator

This folder contains a runnable resume tailoring script for your current paths.

## One-Time Setup

Install Python dependencies:

```powershell
pip install python-docx openai
```

Install LibreOffice for PDF export:

https://www.libreoffice.org/download/download-libreoffice/

Set your OpenAI API key in PowerShell:

```powershell
$env:OPENAI_API_KEY="your_api_key_here"
```

For a permanent Windows user environment variable:

```powershell
setx OPENAI_API_KEY "your_api_key_here"
```

Restart PowerShell after using `setx`.

## Base Resume Template

The generator uses this strict template file:

```text
D:\Resume's and coverletter\University of Utah Health Research\Aakash Kunarapu_Data Scientist_Template.docx
```

Create/update it from your current base resume by running:

```powershell
python prepare_resume_template.py
```

It copies from:

```text
D:\Resume's and coverletter\University of Utah Health Research\Aakash Kunarapu_Data Scientist.docx
```

The template must contain these placeholders exactly where the generated content should go:

```text
{{SUMMARY}}
{{DESTINATION_CLEVELAND}}
{{GENPACT}}
{{PROJECTS}}
{{CORE_COMPETENCIES}}
```

The generator now requires every placeholder above. It rewrites the full resume body from
Professional Summary through Core Competencies instead of partially editing the original text.

Recommended template layout:

```text
PROFESSIONAL SUMMARY
{{SUMMARY}}

EXPERIENCE
Destination Cleveland – Research Analyst. Aug 2025 – Dec 2025
Cleveland, OH
{{DESTINATION_CLEVELAND}}

Genpact – Data Scientist. Feb 2021 – Jul 2023
Hyderabad, India
{{GENPACT}}

PROJECTS
{{PROJECTS}}

CORE COMPETENCIES
{{CORE_COMPETENCIES}}
```

## Generate A Resume

Paste a full job description into:

```text
job_description.txt
```

Run:

```powershell
python generate_resume.py
```

The output goes to:

```text
D:\Resume's and coverletter\<Company_Name>\
```

The script saves both:

```text
Aakash Kunarapu_<Role>.docx
Aakash Kunarapu_<Role>.pdf
```

## Useful Options

Generate DOCX only:

```powershell
python generate_resume.py --skip-pdf
```

Use a different JD file:

```powershell
python generate_resume.py --jd "D:\path\to\jd.txt"
```

## Deploy The Website

This app is deployment-ready with Docker because production PDF export needs LibreOffice.

Recommended host: Render Web Service.

1. Push this folder to a GitHub repository.
2. In Render, create a new Blueprint from the repository.
3. Render will read `render.yaml` and build the Docker image.
4. Add these environment variables in Render:

```text
OPENAI_API_KEY=your OpenAI API key
GOOGLE_CLIENT_ID=your Google OAuth Web Client ID
HOST=0.0.0.0
PORT=8787
OUTPUT_ROOT=/app/data/generated
```

5. In Google Cloud Console, create an OAuth Web Client ID.
6. Add your deployed Render URL to Authorized JavaScript origins:

```text
https://your-render-app.onrender.com
```

7. Paste that client ID into `GOOGLE_CLIENT_ID` on Render and redeploy.

Local Docker test:

```powershell
docker build -t identity-os-resume .
docker run --rm -p 8787:8787 --env-file .env.example identity-os-resume
```

Production note: Render uses the configured persistent disk at `/app/data` for saved profiles,
history, and generated resume files. For a larger product, move this data to Postgres/Supabase
so it scales safely across multiple app instances.
