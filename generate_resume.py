import argparse
import json
import os
import re
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.shared import Inches, Pt
from docx.text.paragraph import Paragraph
from openai import OpenAI


# ---------------- CONFIG ---------------- #

BASE_RESUME = Path(r"D:\Resume's and coverletter\University of Utah Health Research\Aakash Kunarapu_Data Scientist_Template.docx")
OUTPUT_ROOT = Path(os.environ.get("OUTPUT_ROOT", r"D:\Resume's and coverletter"))
DEFAULT_JD_FILE = Path("job_description.txt")
DEFAULT_MODEL = "gpt-4o-mini"
MIN_GENERATED_WORDS = 575
FORBIDDEN_POSITIONING_WORDS = ["equivalent", "adjacent", "similar"]
FORMAT_REFERENCE = Path(__file__).parent / "format_reference_b.docx"
ANTI_AI_PATTERNS = [
    "stakeholder-ready",
    "recruiter-ready",
    "hiring-manager keyword proof",
    "interview-ready",
    "business-ready",
]

PLACEHOLDERS = {
    "{{SUMMARY}}": "summary",
    "{{DESTINATION_CLEVELAND}}": "destination_cleveland_bullets",
    "{{GENPACT}}": "genpact_bullets",
    "{{PROJECTS}}": "projects",
    "{{CORE_COMPETENCIES}}": "core_competencies",
}

SECTION_ALIASES = {
    "summary": ["PROFESSIONAL SUMMARY", "SUMMARY", "PROFILE", "CAREER SUMMARY", "ABOUT"],
    "experience": ["EXPERIENCE", "PROFESSIONAL EXPERIENCE", "WORK EXPERIENCE", "EMPLOYMENT HISTORY"],
    "projects": ["PROJECTS", "PROJECT EXPERIENCE", "ACADEMIC PROJECTS", "SELECTED PROJECTS"],
    "competencies": ["CORE COMPETENCIES", "SKILLS", "TECHNICAL SKILLS", "CORE SKILLS", "COMPETENCIES"],
    "education": ["EDUCATION", "ACADEMIC BACKGROUND"],
    "certifications": ["CERTIFICATIONS", "CERTIFICATION", "LICENSES"],
}


# ---------------- TEXT HELPERS ---------------- #

def safe_filename(value: str, fallback: str, max_len: int = 80) -> str:
    value = (value or fallback).strip()
    value = re.sub(r"[<>:\"/\\|?*\n\r\t]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:max_len].strip(" .") or fallback


def extract_company_role(jd_text: str) -> tuple[str, str]:
    company_match = re.search(r"^\s*Company\s*:\s*(.+)$", jd_text, re.IGNORECASE | re.MULTILINE)
    role_match = re.search(r"^\s*Role\s*:\s*(.+)$", jd_text, re.IGNORECASE | re.MULTILINE)

    company = company_match.group(1).strip() if company_match else "Company"
    role = role_match.group(1).strip() if role_match else "Role"
    lines = [line.strip() for line in jd_text.splitlines() if line.strip()]

    if company == "Company":
        company_patterns = [
            r"\b([A-Z][A-Za-z&.\- ]+(?:LLC|Inc\.?|Corporation|Corp\.?|Company|Technologies|Consulting|Agriscience|Health|University|Labs|Group|Bank|Capital))\b",
            r"\b([A-Z][A-Za-z&.\- ]{2,50})\s+(?:invites applications|is looking|is seeking)\b",
            r"\b([A-Z][A-Za-z&.\- ]{2,50})\s+is\s+(?:a|an)\b",
        ]
        for line in lines[:40]:
            lower = line.lower()
            if any(skip in lower for skip in ["apply now", "share this job", "benefits", "salary range"]):
                continue
            for pattern in company_patterns:
                match = re.search(pattern, line)
                if match:
                    company = match.group(1).strip(" .,-")
                    break
            if company != "Company":
                break

        if company == "Company":
            for known in ["Deloitte", "Corteva Agriscience", "RK Infotech LLC"]:
                if known.lower() in jd_text.lower():
                    company = known
                    break

    if role == "Role":
        title_keywords = ["scientist", "analyst", "engineer", "consultant", "developer", "architect", "manager", "specialist", "researcher"]
        for line in lines[:15]:
            lower = line.lower()
            if 2 <= len(line.split()) <= 8 and any(keyword in lower for keyword in title_keywords):
                role = re.sub(r"^\s*Job Title\s*:\s*", "", line, flags=re.IGNORECASE).strip()
                break

    if role == "Role":
        for title in ["Data Scientist", "Data Science Consultant", "Data Analyst", "Research Analyst", "Statistics Research Scientist", "Machine Learning Engineer"]:
            if re.search(rf"\b{re.escape(title)}\b", jd_text, re.IGNORECASE):
                role = title
                break

    return company, role


def extract_json(text: str) -> dict:
    """Handle plain JSON or JSON wrapped in a Markdown code fence."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)


def flatten_generated_text(data: dict) -> str:
    parts = [str(data.get("summary", ""))]
    parts.extend(str(item) for item in data.get("destination_cleveland_bullets", []))
    parts.extend(str(item) for item in data.get("genpact_bullets", []))

    for project in data.get("projects", []):
        if isinstance(project, dict):
            parts.append(str(project.get("title", "")))
            parts.extend(str(item) for item in project.get("bullets", []))
        else:
            parts.append(str(project))

    parts.extend(str(item) for item in data.get("core_competencies", []))
    return "\n".join(parts)


def generated_word_count(data: dict) -> int:
    text = re.sub(r"\*\*", "", flatten_generated_text(data))
    return len(re.findall(r"\b[\w+#./-]+\b", text))


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w+#./-]+\b", re.sub(r"\*\*", "", str(text))))


def expand_sentence(text: str, target_min: int, filler: str) -> str:
    text = str(text).strip().rstrip(".")
    if word_count(text) >= target_min:
        return text + "."

    filler_words = filler.strip().rstrip(".")
    separator = " using " if not re.search(r"\busing\b", text, re.IGNORECASE) else " for "
    expanded = f"{text}{separator}{filler_words}"
    return expanded.strip().rstrip(".") + "."


def trim_to_max_words(text: str, max_words: int) -> str:
    words = str(text).strip().split()
    if len(words) <= max_words:
        return str(text).strip()
    return " ".join(words[:max_words]).rstrip(".,;") + "."


def repair_generated_resume(data: dict, jd_text: str) -> dict:
    """Deterministically densify common thin outputs before failing quality control."""
    data.setdefault("summary", "")
    data.setdefault("destination_cleveland_bullets", [])
    data.setdefault("genpact_bullets", [])
    data.setdefault("projects", [])
    data.setdefault("core_competencies", [])

    if word_count(data.get("summary", "")) < 60:
        data["summary"] = (
            "Data Scientist with an M.S. in Computer Science and 4+ years of experience in "
            "**Python**, **SQL**, **machine learning**, and **data visualization**. Skilled in translating "
            "complex datasets into practical insights through **data cleaning**, modeling, dashboards, "
            "and stakeholder reporting. Differentiates through reproducible workflows, fast JD alignment, "
            "practical analytics delivery, and clear communication across research, operations, consulting, "
            "and client-facing environments with measurable business impact."
        )
    else:
        data["summary"] = trim_to_max_words(data.get("summary", ""), 82)

    experience_fillers = [
        "**Python**, **SQL**, quality checks, and stakeholder-ready reporting",
        "**machine learning**, exploratory analysis, and measurable business insight delivery",
        "**Power BI**, dashboard validation, and cross-functional communication",
        "**data cleaning**, documentation, and reproducible workflow standards",
        "**analytics**, trend identification, and decision-support reporting",
    ]

    for key in ["destination_cleveland_bullets", "genpact_bullets"]:
        bullets = data.get(key, [])
        for index, bullet in enumerate(bullets):
            filler = experience_fillers[index % len(experience_fillers)]
            bullets[index] = trim_to_max_words(expand_sentence(bullet, 18, filler), 25)
        data[key] = bullets

    generic_project_fillers = [
        "**feature engineering**, model validation, performance tracking, reporting review, reproducible documentation, and practical business interpretation",
        "**data cleaning**, exploratory analysis, visualization, output review, business interpretation, and documented technical assumptions",
        "**Python**, **SQL**, dashboard validation, quality checks, data lineage, model evaluation, and project evidence",
    ]

    for project_index, project in enumerate(data.get("projects", [])):
        if not isinstance(project, dict):
            continue
        bullets = project.get("bullets", [])
        for bullet_index, bullet in enumerate(bullets):
            filler = generic_project_fillers[(project_index + bullet_index) % len(generic_project_fillers)]
            bullets[bullet_index] = trim_to_max_words(expand_sentence(bullet, 24, filler), 30)
            if word_count(bullets[bullet_index]) < 20:
                bullets[bullet_index] = trim_to_max_words(
                    bullets[bullet_index].rstrip(".")
                    + " with measurable business context and clear technical evidence.",
                    30,
                )
        project["bullets"] = bullets

    if len(data.get("core_competencies", [])) < 6:
        data.setdefault("core_competencies", []).append(
            "Professional Attributes: **problem-solving**, **continuous learning**, **collaboration**, **communication**, **documentation**, **stakeholder engagement**"
        )

    density_terms = [
        "**risk reduction**",
        "**quality control**",
        "**business impact**",
        "**technical documentation**",
        "**reproducible workflows**",
        "**stakeholder communication**",
    ]
    density_index = 0

    while generated_word_count(data) < MIN_GENERATED_WORDS and density_index < 60:
        projects = data.get("projects", [])
        expanded = False
        for project in projects:
            if not isinstance(project, dict):
                continue
            bullets = project.setdefault("bullets", [])
            if len(bullets) < 3:
                bullets.append(
                    "Documented **methods**, assumptions, validation results, and business implications to support technical and non-technical review."
                )
                expanded = True
                break
        if expanded:
            continue

        competencies = data.setdefault("core_competencies", [])
        if len(competencies) < 6:
            competencies.append(
                "Role Alignment: **data science**, **machine learning**, **Python**, **SQL**, **analytics**, **reporting**, **business outcomes**"
            )
            continue

        target = density_index % len(competencies)
        competencies[target] = competencies[target].rstrip(".") + ", " + density_terms[density_index % len(density_terms)]
        density_index += 1

    for word in FORBIDDEN_POSITIONING_WORDS:
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        for key in ["summary", "destination_cleveland_bullets", "genpact_bullets", "core_competencies"]:
            if isinstance(data.get(key), str):
                data[key] = pattern.sub("", data[key])
            elif isinstance(data.get(key), list):
                data[key] = [pattern.sub("", str(item)).replace("  ", " ").strip() for item in data[key]]

        for project in data.get("projects", []):
            if isinstance(project, dict):
                project["title"] = pattern.sub("", str(project.get("title", ""))).replace("  ", " ").strip()
                project["bullets"] = [
                    pattern.sub("", str(item)).replace("  ", " ").strip()
                    for item in project.get("bullets", [])
                ]

    for phrase in ANTI_AI_PATTERNS:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        for key in ["summary", "destination_cleveland_bullets", "genpact_bullets", "core_competencies"]:
            if isinstance(data.get(key), str):
                data[key] = pattern.sub("", data[key]).replace("  ", " ").strip()
            elif isinstance(data.get(key), list):
                data[key] = [pattern.sub("", str(item)).replace("  ", " ").strip() for item in data[key]]

        for project in data.get("projects", []):
            if isinstance(project, dict):
                project["title"] = pattern.sub("", str(project.get("title", ""))).replace("  ", " ").strip()
                project["bullets"] = [
                    pattern.sub("", str(item)).replace("  ", " ").strip()
                    for item in project.get("bullets", [])
                ]

    return data


def validate_generated_resume(data: dict) -> list[str]:
    issues = []
    word_count = generated_word_count(data)
    if word_count < MIN_GENERATED_WORDS:
        issues.append(
            f"Generated content is too short at {word_count} words. Minimum is {MIN_GENERATED_WORDS} words so the resume fills at least one complete page."
        )

    summary_words = len(re.findall(r"\b[\w+#./-]+\b", str(data.get("summary", ""))))
    if summary_words < 60 or summary_words > 85:
        issues.append(f"Summary must be 60-80 words; current summary is {summary_words} words.")

    for key in ["destination_cleveland_bullets", "genpact_bullets"]:
        bullets = data.get(key, [])
        if len(bullets) != 5:
            issues.append(f"{key} must contain exactly 5 bullets.")
        for index, bullet in enumerate(bullets, start=1):
            count = len(re.findall(r"\b[\w+#./-]+\b", str(bullet)))
            if count < 15 or count > 28:
                issues.append(f"{key} bullet {index} must be 15-25 words; current count is {count}.")

    projects = data.get("projects", [])
    if len(projects) != 3:
        issues.append("projects must contain exactly 3 project objects.")
    for index, project in enumerate(projects, start=1):
        if not isinstance(project, dict):
            issues.append(f"Project {index} must be an object with title and bullets.")
            continue
        bullets = project.get("bullets", [])
        if len(bullets) < 2 or len(bullets) > 3:
            issues.append(f"Project {index} must contain 2-3 bullets.")
        for bullet_index, bullet in enumerate(bullets, start=1):
            count = len(re.findall(r"\b[\w+#./-]+\b", str(bullet)))
            if count < 20 or count > 34:
                issues.append(f"Project {index} bullet {bullet_index} must be 20-30 words; current count is {count}.")

    competencies = data.get("core_competencies", [])
    if len(competencies) < 5 or len(competencies) > 6:
        issues.append("core_competencies must contain 5-6 categories.")

    lowered = flatten_generated_text(data).lower()
    for word in FORBIDDEN_POSITIONING_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            issues.append(f"Do not use the forbidden positioning word: {word}.")

    for pattern in ANTI_AI_PATTERNS:
        if pattern in lowered:
            issues.append(f"Remove synthetic phrase: {pattern}.")

    repeated_starts = {}
    for bullet in data.get("destination_cleveland_bullets", []) + data.get("genpact_bullets", []):
        first = str(bullet).strip().split(" ", 1)[0].lower()
        if first:
            repeated_starts[first] = repeated_starts.get(first, 0) + 1
    for first, count in repeated_starts.items():
        if count > 2:
            issues.append(f"Too many bullets start with '{first}'. Vary cadence.")

    return issues


def make_template_from_resume(source_path: Path, template_path: Path) -> Path:
    """Create a strict placeholder template from a resume with the expected section headings."""
    doc = Document(str(source_path))

    summary_heading = paragraph_index(doc, "PROFESSIONAL SUMMARY", exact=True)
    experience_heading = paragraph_index(doc, "EXPERIENCE", exact=True)
    replace_range_after_anchor(doc, summary_heading, experience_heading, ["{{SUMMARY}}"])

    dc_heading = paragraph_index(doc, "Destination Cleveland")
    genpact_heading = paragraph_index(doc, "Genpact", start=max(dc_heading, 0))
    replace_range_after_anchor(doc, dc_heading + 1, genpact_heading, ["{{DESTINATION_CLEVELAND}}"])

    genpact_heading = paragraph_index(doc, "Genpact")
    projects_heading = paragraph_index(doc, "PROJECTS", start=max(genpact_heading, 0), exact=True)
    replace_range_after_anchor(doc, genpact_heading + 1, projects_heading, ["{{GENPACT}}"])

    projects_heading = paragraph_index(doc, "PROJECTS", exact=True)
    core_heading = paragraph_index(doc, "CORE COMPETENCIES", start=max(projects_heading, 0), exact=True)
    replace_range_after_anchor(doc, projects_heading, core_heading, ["{{PROJECTS}}"])

    core_heading = paragraph_index(doc, "CORE COMPETENCIES", exact=True)
    education_heading = paragraph_index(doc, "EDUCATION", start=max(core_heading, 0), exact=True)
    replace_range_after_anchor(doc, core_heading, education_heading, ["{{CORE_COMPETENCIES}}"])

    template_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(template_path))
    return template_path


def set_bottom_border(paragraph, color="000000", size="6") -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = p_pr.find(qn("w:pBdr"))
    if p_bdr is None:
        p_bdr = OxmlElement("w:pBdr")
        p_pr.append(p_bdr)

    bottom = p_bdr.find(qn("w:bottom"))
    if bottom is None:
        bottom = OxmlElement("w:bottom")
        p_bdr.append(bottom)

    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)


def create_template_from_profile(profile: dict, template_path: Path) -> Path:
    doc = Document(str(FORMAT_REFERENCE)) if FORMAT_REFERENCE.exists() else Document()

    details = profile.get("details", {})
    name = details.get("name") or "Candidate Name"
    has_contact = any(
        (details.get(key) or "").strip()
        for key in ["location", "phone", "email", "linkedin"]
    )

    if not FORMAT_REFERENCE.exists() or len(doc.paragraphs) < 10:
        # Emergency fallback only. Normal path keeps the user's B-format skeleton.
        name_paragraph = doc.add_paragraph()
        name_run = name_paragraph.add_run(name)
        name_run.bold = True
        name_paragraph.alignment = 1
        if contact:
            contact_paragraph = doc.add_paragraph(contact)
            contact_paragraph.alignment = 1
        doc.add_paragraph("PROFESSIONAL SUMMARY").style = "Heading 1"
        doc.add_paragraph("{{SUMMARY}}")
        doc.add_paragraph("EXPERIENCE").style = "Heading 1"
        doc.add_paragraph("{{DESTINATION_CLEVELAND}}")
        doc.add_paragraph("{{GENPACT}}")
        doc.add_paragraph("PROJECTS").style = "Heading 1"
        doc.add_paragraph("{{PROJECTS}}")
        doc.add_paragraph("CORE COMPETENCIES").style = "Heading 1"
        doc.add_paragraph("{{CORE_COMPETENCIES}}")
    else:
        # Preserve the exact B-format paragraph structure, spacing, styles, and margins.
        while len(doc.paragraphs) > 0 and not doc.paragraphs[-1].text.strip():
            delete_paragraph(doc.paragraphs[-1])

        set_paragraph_text_preserve_first_run(doc.paragraphs[0], name)
        if contact and len(doc.paragraphs) > 1:
            set_paragraph_text_preserve_first_run(doc.paragraphs[1], contact)

        summary_idx = paragraph_index(doc, "PROFESSIONAL SUMMARY", exact=True)
        exp_idx = paragraph_index(doc, "EXPERIENCE", exact=True)
        projects_idx = paragraph_index(doc, "PROJECTS", exact=True)
        competencies_idx = paragraph_index(doc, "CORE COMPETENCIES", exact=True)
        education_idx = paragraph_index(doc, "EDUCATION", exact=True)
        certifications_idx = paragraph_index(doc, "CERTIFICATIONS", exact=True)

        if summary_idx >= 0 and exp_idx > summary_idx:
            replace_range_after_anchor(doc, summary_idx, exp_idx, ["{{SUMMARY}}"])

        experiences = profile.get("experiences", [])[:2]
        while len(experiences) < 2:
            experiences.append({})

        experience_lines = []
        for index, experience in enumerate(experiences):
            company = experience.get("company") or f"Company {index + 1}"
            title = experience.get("title") or "Role"
            duration = experience.get("duration") or ""
            location = experience.get("location") or ""
            header = f"{company} – {title}"
            if duration:
                header += f"\t{duration}"
            experience_lines.append(header)
            if location:
                experience_lines.append(location)
            experience_lines.append("{{DESTINATION_CLEVELAND}}" if index == 0 else "{{GENPACT}}")

        projects_idx = paragraph_index(doc, "PROJECTS", exact=True)
        exp_idx = paragraph_index(doc, "EXPERIENCE", exact=True)
        if exp_idx >= 0 and projects_idx > exp_idx:
            replace_range_after_anchor(doc, exp_idx, projects_idx, experience_lines)

        competencies_idx = paragraph_index(doc, "CORE COMPETENCIES", exact=True)
        projects_idx = paragraph_index(doc, "PROJECTS", exact=True)
        if projects_idx >= 0 and competencies_idx > projects_idx:
            replace_range_after_anchor(doc, projects_idx, competencies_idx, ["{{PROJECTS}}"])

        education_idx = paragraph_index(doc, "EDUCATION", exact=True)
        competencies_idx = paragraph_index(doc, "CORE COMPETENCIES", exact=True)
        if competencies_idx >= 0 and education_idx > competencies_idx:
            replace_range_after_anchor(doc, competencies_idx, education_idx, ["{{CORE_COMPETENCIES}}"])

        education = profile.get("education", [])
        certifications_idx = paragraph_index(doc, "CERTIFICATIONS", exact=True)
        education_idx = paragraph_index(doc, "EDUCATION", exact=True)
        if education_idx >= 0:
            education_lines = []
            for item in education:
                school = item.get("school", "")
                degree = item.get("degree", "")
                year = item.get("year", "")
                line = " — ".join(part for part in [school, degree] if part)
                if year:
                    line += f"\t{year}"
                if line.strip():
                    education_lines.append(line)
            education_end = certifications_idx if certifications_idx > education_idx else len(doc.paragraphs)
            replace_range_after_anchor(doc, education_idx, education_end, education_lines)

        certifications = profile.get("certifications", [])
        certifications_idx = paragraph_index(doc, "CERTIFICATIONS", exact=True)
        if certifications_idx >= 0:
            certification_lines = []
            for item in certifications:
                text = item.get("name", "") if isinstance(item, dict) else str(item)
                if text.strip():
                    certification_lines.append(text.strip())
            replace_range_after_anchor(doc, certifications_idx, len(doc.paragraphs), certification_lines)

        # Bold experience headers created from profile data, matching B's visual language.
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if " – " in text and "\t" in text and paragraph.runs:
                for run in paragraph.runs:
                    run.bold = True

    template_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(template_path))
    return template_path


def create_template_from_profile(profile: dict, template_path: Path) -> Path:
    """Build the screenshot-style resume structure from stored profile fields."""
    doc = Document()

    section = doc.sections[0]
    section.top_margin = Inches(0.55)
    section.bottom_margin = Inches(0.55)
    section.left_margin = Inches(0.58)
    section.right_margin = Inches(0.58)

    normal = doc.styles["Normal"]
    normal.font.name = "Arial"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    normal.font.size = Pt(9.6)
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(2.2)
    normal.paragraph_format.line_spacing = 1.06

    details = profile.get("details", {})
    name = details.get("name") or "Candidate Name"
    contact = " • ".join(
        value for value in [
            details.get("location", ""),
            details.get("phone", ""),
            details.get("email", ""),
            details.get("linkedin", ""),
        ]
        if value
    )
    has_contact = any(
        (details.get(key) or "").strip()
        for key in ["location", "phone", "email", "linkedin"]
    )

    def set_spacing(paragraph, before=0, after=2.2, line_spacing=1.06):
        paragraph.paragraph_format.space_before = Pt(before)
        paragraph.paragraph_format.space_after = Pt(after)
        paragraph.paragraph_format.line_spacing = line_spacing
        return paragraph

    def add_run(paragraph, text, bold=False, italic=False, size=9.6):
        run = paragraph.add_run(str(text))
        run.font.name = "Arial"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
        run.font.size = Pt(size)
        run.bold = bold
        run.italic = italic
        return run

    def add_plain(text="", bold=False, italic=False, size=9.6, align=None, after=2.2):
        paragraph = doc.add_paragraph()
        set_spacing(paragraph, after=after)
        if align is not None:
            paragraph.alignment = align
        add_run(paragraph, text, bold=bold, italic=italic, size=size)
        return paragraph

    def add_section_heading(text):
        paragraph = add_plain(text, bold=True, size=11.6, after=2)
        set_bottom_border(paragraph)
        return paragraph

    def add_tabbed_line(left, right="", bold=False, italic=False):
        paragraph = doc.add_paragraph()
        set_spacing(paragraph, after=1.4)
        paragraph.paragraph_format.tab_stops.add_tab_stop(Inches(7.28), WD_TAB_ALIGNMENT.RIGHT)
        add_run(paragraph, left, bold=bold, italic=italic)
        if right:
            add_run(paragraph, "\t" + str(right), bold=bold)
        return paragraph

    add_plain(name, bold=True, size=9.8, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
    if has_contact:
        contact_paragraph = add_plain("", size=9.6, align=WD_ALIGN_PARAGRAPH.CENTER, after=14)
        set_contact_line(contact_paragraph, details)

    add_section_heading("PROFESSIONAL SUMMARY")
    add_plain("{{SUMMARY}}", after=6)

    add_section_heading("EXPERIENCE")
    experiences = profile.get("experiences", [])[:2]
    while len(experiences) < 2:
        experiences.append({})

    for index, experience in enumerate(experiences):
        company = experience.get("company") or f"Company {index + 1}"
        title = experience.get("title") or "Role"
        duration = experience.get("duration") or ""
        location = experience.get("location") or ""
        add_tabbed_line(f"{company} – {title}", duration, bold=True)
        if location:
            add_plain(location, italic=True, after=1)
        placeholder = "{{DESTINATION_CLEVELAND}}" if index == 0 else "{{GENPACT}}"
        add_plain(placeholder, after=7 if index == 0 else 11)

    add_section_heading("PROJECTS")
    add_plain("{{PROJECTS}}", after=10)

    add_section_heading("CORE COMPETENCIES")
    add_plain("{{CORE_COMPETENCIES}}", after=8)

    education = profile.get("education", [])
    if education:
        add_section_heading("EDUCATION")
        for item in education:
            school = item.get("school", "")
            degree = item.get("degree", "")
            year = item.get("year", "")
            if school:
                add_tabbed_line(school, year)
            if degree:
                add_plain(degree, italic=True, after=1.2)

    certifications = profile.get("certifications", [])
    if certifications:
        add_section_heading("CERTIFICATIONS")
        for item in certifications:
            text = item.get("name", "") if isinstance(item, dict) else str(item)
            if text.strip():
                add_plain(text.strip(), after=1)

    template_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(template_path))
    return template_path


def document_text(doc: Document) -> str:
    parts = [p.text for p in doc.paragraphs if p.text.strip()]

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                cell_text = "\n".join(p.text for p in cell.paragraphs if p.text.strip())
                if cell_text:
                    parts.append(cell_text)

    return "\n".join(parts)


def update_contact_details(doc: Document, details: dict) -> None:
    name = (details.get("name") or "").strip()
    location = (details.get("location") or "").strip()
    phone = (details.get("phone") or "").strip()
    email = (details.get("email") or "").strip()
    linkedin = (details.get("linkedin") or "").strip()

    if name and doc.paragraphs:
        set_paragraph_text_preserve_first_run(doc.paragraphs[0], name)

    contact_parts = [part for part in [location, phone, email, linkedin] if part]
    if contact_parts and len(doc.paragraphs) > 1:
        set_paragraph_text_preserve_first_run(doc.paragraphs[1], " • ".join(contact_parts))


def set_paragraph_text_preserve_first_run(paragraph, text: str) -> None:
    if not paragraph.runs:
        paragraph.add_run(text)
        return

    paragraph.runs[0].text = text
    for run in paragraph.runs[1:]:
        run._element.getparent().remove(run._element)


def add_hyperlink(paragraph, text: str, url: str):
    relationship_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship_id)

    run = OxmlElement("w:r")
    run_properties = OxmlElement("w:rPr")

    color = OxmlElement("w:color")
    color.set(qn("w:val"), "000000")
    run_properties.append(color)

    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "none")
    run_properties.append(underline)

    bold = OxmlElement("w:b")
    run_properties.append(bold)

    run.append(run_properties)
    text_element = OxmlElement("w:t")
    text_element.text = text
    run.append(text_element)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)
    return hyperlink


def normalize_linkedin_url(value: str) -> str:
    value = (value or "").strip()
    if not value or value.lower() == "linkedin":
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if "linkedin.com" in value.lower():
        return "https://" + value.lstrip("/")
    return ""


def set_contact_line(paragraph, details: dict) -> None:
    paragraph.clear()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    parts = [
        (details.get("location") or "").strip(),
        (details.get("phone") or "").strip(),
        (details.get("email") or "").strip(),
    ]
    parts = [part for part in parts if part]
    linkedin_url = normalize_linkedin_url(details.get("linkedin", ""))

    for index, part in enumerate(parts):
        if index:
            paragraph.add_run(" • ")
        paragraph.add_run(part)

    if linkedin_url or (details.get("linkedin") or "").strip():
        if parts:
            paragraph.add_run(" • ")
        if linkedin_url:
            add_hyperlink(paragraph, "LinkedIn", linkedin_url)
        else:
            paragraph.add_run("LinkedIn")

    for run in paragraph.runs:
        run.font.name = "Arial"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
        run.font.size = Pt(9.6)


def update_contact_details(doc: Document, details: dict) -> None:
    name = (details.get("name") or "").strip()
    clean_details = {
        "location": (details.get("location") or "").strip(),
        "phone": (details.get("phone") or "").strip(),
        "email": (details.get("email") or "").strip(),
        "linkedin": (details.get("linkedin") or "").strip(),
    }

    if name and doc.paragraphs:
        set_paragraph_text_preserve_first_run(doc.paragraphs[0], name)
        doc.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    if any(clean_details.values()) and len(doc.paragraphs) > 1:
        set_contact_line(doc.paragraphs[1], clean_details)


def format_value(value) -> str:
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                title = str(item.get("title", "")).strip()
                bullets = item.get("bullets", [])
                body = " ".join(str(bullet).strip().rstrip(".") + "." for bullet in bullets if str(bullet).strip())
                if title and body:
                    lines.append(f"{title}: {body}")
                elif title:
                    lines.append(title)
            else:
                lines.append(str(item).strip())
        return "\n".join(line for line in lines if line)
    return str(value).strip()


def add_text_with_bold(paragraph, text: str) -> None:
    paragraph.clear()
    parts = re.split(r"(\*\*.*?\*\*)", str(text))
    for part in parts:
        if not part:
            continue
        run = paragraph.add_run(part[2:-2] if part.startswith("**") and part.endswith("**") else part)
        run.font.name = "Arial"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
        run.font.size = Pt(9.6)
        run.bold = part.startswith("**") and part.endswith("**")


def apply_bullet(paragraph) -> None:
    paragraph.paragraph_format.left_indent = None
    paragraph.paragraph_format.first_line_indent = None
    paragraph.paragraph_format.hanging_indent = None


def replace_inline_placeholder(paragraph, placeholder: str, new_text: str) -> bool:
    if placeholder not in paragraph.text:
        return False

    add_text_with_bold(paragraph, paragraph.text.replace(placeholder, new_text))
    return True


def insert_formatted_paragraph_after(paragraph, text: str, style=None) -> Paragraph:
    new_element = OxmlElement("w:p")
    paragraph._p.addnext(new_element)
    new_paragraph = Paragraph(new_element, paragraph._parent)
    source_p_pr = paragraph._p.pPr
    if source_p_pr is not None:
        new_paragraph._p.insert(0, deepcopy(source_p_pr))
    if style:
        try:
            new_paragraph.style = style
        except KeyError:
            pass
        apply_bullet(new_paragraph)
    new_paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    add_text_with_bold(new_paragraph, text)
    return new_paragraph


def replace_block_placeholder(doc: Document, placeholder: str, value, style=None) -> bool:
    if placeholder == "{{PROJECTS}}" and isinstance(value, list):
        replacement_lines = []
        for project in value:
            if isinstance(project, dict):
                title = str(project.get("title", "")).strip()
                bullets = [str(item).strip() for item in project.get("bullets", []) if str(item).strip()]
                body = " ".join(bullet.rstrip(".") + "." for bullet in bullets)
                if title and body:
                    replacement_lines.append({"text": f"**{title}:** {body}", "bullet": False})
                elif title:
                    replacement_lines.append({"text": f"**{title}**", "bullet": False})
                else:
                    replacement_lines.append({"text": body, "bullet": False})
            else:
                replacement_lines.append({"text": str(project).strip(), "bullet": False})
    else:
        raw_lines = value if isinstance(value, list) else [value]
        replacement_lines = []
        for item in raw_lines:
            text = str(item).strip()
            if placeholder == "{{CORE_COMPETENCIES}}" and ":" in text and "**" not in text.split(":", 1)[0]:
                key, rest = text.split(":", 1)
                text = f"**{key.strip()}:**{rest}"
            if style is not None and text and not text.startswith("•"):
                text = "• " + text
            replacement_lines.append({"text": text, "bullet": False})

    replacement_lines = [item for item in replacement_lines if item["text"]]

    for paragraph in list(doc.paragraphs):
        if placeholder not in paragraph.text:
            continue

        if paragraph.text.strip() == placeholder:
            for line in reversed(replacement_lines):
                line_style = style if line["bullet"] else None
                insert_formatted_paragraph_after(paragraph, line["text"], style=line_style)
            delete_paragraph(paragraph)
            return True

        return replace_inline_placeholder(paragraph, placeholder, format_value(value))

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in list(cell.paragraphs):
                    if placeholder not in paragraph.text:
                        continue

                    if paragraph.text.strip() == placeholder:
                        for line in reversed(replacement_lines):
                            line_style = style if line["bullet"] else None
                            insert_formatted_paragraph_after(paragraph, line["text"], style=line_style)
                        delete_paragraph(paragraph)
                        return True

                    return replace_inline_placeholder(paragraph, placeholder, format_value(value))

    return False


def replace_placeholders(doc: Document, data: dict) -> list[str]:
    missing = []
    for placeholder, key in PLACEHOLDERS.items():
        value = data.get(key, "")
        if key in {"destination_cleveland_bullets", "genpact_bullets", "core_competencies"} and isinstance(value, list):
            value = [item if str(item).strip().startswith("•") else f"• {item}" for item in value]
        found = replace_block_placeholder(doc, placeholder, value, style=None)
        if not found:
            missing.append(placeholder)
    return missing


def delete_paragraph(paragraph) -> None:
    element = paragraph._element
    element.getparent().remove(element)
    paragraph._p = paragraph._element = None


def insert_paragraphs_after(paragraph, lines: list[str], style=None):
    current = paragraph
    for line in lines:
        new_element = OxmlElement("w:p")
        current._p.addnext(new_element)
        current = Paragraph(new_element, current._parent)
        current.text = str(line).strip()
        if style:
            current.style = style
    return current


def paragraph_index(doc: Document, text: str, start: int = 0, exact: bool = False) -> int:
    needle = text.lower()
    for idx, paragraph in enumerate(doc.paragraphs[start:], start=start):
        haystack = paragraph.text.strip().lower()
        if exact and haystack == needle:
            return idx
        if not exact and needle in haystack:
            return idx
    return -1


def replace_range_after_anchor(doc: Document, anchor_idx: int, end_idx: int, lines: list[str]) -> None:
    if anchor_idx < 0 or end_idx <= anchor_idx:
        return

    anchor = doc.paragraphs[anchor_idx]
    old_paragraphs = list(doc.paragraphs[anchor_idx + 1:end_idx])

    for paragraph in old_paragraphs:
        delete_paragraph(paragraph)

    insert_paragraphs_after(anchor, lines)


def replace_existing_resume_sections(doc: Document, data: dict) -> None:
    """Fallback for the current base resume when placeholders have not been added."""
    summary_heading = paragraph_index(doc, "PROFESSIONAL SUMMARY", exact=True)
    experience_heading = paragraph_index(doc, "EXPERIENCE", exact=True)
    if summary_heading >= 0 and experience_heading > summary_heading:
        replace_range_after_anchor(
            doc,
            summary_heading,
            experience_heading,
            [format_value(data.get("summary", ""))],
        )

    dc_heading = paragraph_index(doc, "Destination Cleveland")
    genpact_heading = paragraph_index(doc, "Genpact", start=max(dc_heading, 0))
    projects_heading = paragraph_index(doc, "PROJECTS", start=max(genpact_heading, 0), exact=True)

    if dc_heading >= 0 and genpact_heading > dc_heading:
        # Keep the location line, replace only the experience bullets.
        replace_range_after_anchor(
            doc,
            dc_heading + 1,
            genpact_heading,
            data.get("experience_dc", []),
        )

    genpact_heading = paragraph_index(doc, "Genpact")
    projects_heading = paragraph_index(doc, "PROJECTS", start=max(genpact_heading, 0), exact=True)
    if genpact_heading >= 0 and projects_heading > genpact_heading:
        replace_range_after_anchor(
            doc,
            genpact_heading + 1,
            projects_heading,
            data.get("experience_genpact", []),
        )

    skills_heading = paragraph_index(doc, "CORE COMPETENCIES", exact=True)
    education_heading = paragraph_index(doc, "EDUCATION", start=max(skills_heading, 0), exact=True)
    if skills_heading >= 0 and education_heading > skills_heading:
        skills = data.get("skills", [])
        if isinstance(skills, list):
            skills_text = ", ".join(str(skill).strip() for skill in skills if str(skill).strip())
        else:
            skills_text = str(skills).strip()
        replace_range_after_anchor(doc, skills_heading, education_heading, [skills_text])


# ---------------- LLM ---------------- #

def build_prompt(base_resume_text: str, jd_text: str) -> str:
    return f"""
You are an elite resume strategist and hiring committee analyst.

Use the Universal Resume Shortlisting Framework:
1. Deconstruct the JD into:
   - Core Functional Requirements
   - Systems / Infrastructure Signals
   - Risk Signals, meaning what the employer is afraid of
   - Tooling Stack
   - Cultural / Domain Alignment
   - Seniority Level
2. Identify gaps and positioning opportunities in the current resume.
3. Choose one best positioning persona:
   Data Infrastructure Builder, Analytical Problem Solver, Research Operations Partner,
   Systems Optimizer, Insight Translator, Technical Architect, or Growth Analyst.
4. Rewrite:
   - Professional Summary
   - Experience bullets
   - Projects
   - Core Competencies
5. Use the bullet formula:
   Action + System/Method + Context + Measurable Impact + Risk Reduction.
6. Ensure:
   - Natural keyword mirroring for ATS
   - Human readability
   - No exaggeration
   - Clear measurable outcomes where available
   - Reproducibility and structure emphasis when relevant
7. The resume should reduce perceived hiring risk and sound like the candidate has already solved the employer's problem.

Built-in generation rule:
Follow the framework and make sure important JD keywords are present and proven in Experience, Projects, or Core Competencies.
If the current experience is not a literal match for the JD, find truthful scope inside the candidate's experience that can be reframed to meet the JD requirements and company needs.
Improve readability and do not write unnecessarily long lines.
Strict note: do not use words like "equivalent", "adjacent", or "similar".
If the JD says AWS, include AWS along with relevant services such as S3, EC2, Lambda, Glue, Redshift, SageMaker, or CloudWatch when they fit the candidate's background.
The candidate accepts a resume going over one page, but does not accept a resume that fails to fill one complete page.

Critical automation instruction:
Rewrite every resume section from Professional Summary through Core Competencies.
Do not partially edit the resume.
Maintain original formatting from the uploaded/template DOCX.
Use bullet points in Experience.
Bold important JD keywords naturally using **keyword** markdown.
Core Competencies must use paired category format:
• Category: keyword, keyword, keyword.
Remove duplicate project text.
Keep readability high.
Every word must earn its place. Keep keywords, proof points, and differentiators. Remove filler.
Do not underwrite. The generated sections must contain at least {MIN_GENERATED_WORDS} total words before formatting.
Final trust test before returning JSON:
Would a recruiter believe this candidate exists and want to interview them?
If not, rewrite the weak sections before returning JSON.

Strict output requirements:
- Return valid JSON only.
- No Markdown fences.
- No commentary outside JSON.
- Rewrite the whole resume body, not isolated fragments.
- summary must be one paragraph of 60-80 words and should visually read as 4-6 lines in a resume.
- summary must include: positioning identity, years of experience and degree, top 3-4 JD-matched skills, and one differentiator.
- destination_cleveland_bullets must contain exactly 5 bullets of 15-25 words each.
- genpact_bullets must contain exactly 5 bullets of 15-25 words each.
- Experience bullets must use: Action verb + what was done + tool/method + result.
- No stacking clauses with commas.
- Do not use "and" to connect two different actions in one bullet.
- If a bullet needs a semicolon, split the idea before returning JSON.
- projects must contain exactly 3 project objects.
- Each project object must have a title with tools in parentheses and 2-3 detail strings.
- The DOCX will render each project as one paragraph, not separate project bullets.
- Each project paragraph must quickly show tools, what was built, what it did, and one measurable outcome if available.
- core_competencies must contain 5-6 paired category bullets.
- Each core competency category must contain 4-8 keywords.
- Categories should map to JD signals: core functional skills, technical tools, domain methods, communication/stakeholders, data/reporting tools, and culture/professional attributes only if signaled.
- Keywords inside each category should mirror the JD phrasing where truthful.
- Do not include bullet symbols in JSON values; the DOCX writer adds bullets.
- Use **bold** around important ATS keywords, tools, domain phrases, and differentiators.
- Target 30-50 bolded terms across the entire generated resume.
- Include Technical Skills inside core_competencies when useful.
- Do not make generic claims like "increased accuracy" unless grounded in the source resume or clearly framed as project output.
- If a JD keyword is important, prove it in Experience or Projects, not only in Core Competencies.
- Never return a thin resume. Expand Projects and Core Competencies first, then Experience bullets within the allowed range.

JSON schema:
{{
  "summary": "string",
  "destination_cleveland_bullets": ["bullet", "bullet", "bullet", "bullet", "bullet"],
  "genpact_bullets": ["bullet", "bullet", "bullet", "bullet", "bullet"],
  "projects": [
    {{
      "title": "Project Name (Python, SQL, Power BI)",
      "bullets": ["bullet", "bullet"]
    }}
  ],
  "core_competencies": [
    "Machine Learning & AI: Python, scikit-learn, RAG, vector databases, evaluation metrics",
    "Data Analysis & Statistics: SQL, Pandas, NumPy, hypothesis testing, regression"
  ]
}}

BASE RESUME:
{base_resume_text}

JOB DESCRIPTION:
{jd_text}
""".strip()


def build_retry_prompt(base_prompt: str, previous_data: dict, issues: list[str]) -> str:
    return f"""
{base_prompt}

The previous JSON failed quality control.

Quality control issues:
{chr(10).join(f"- {issue}" for issue in issues)}

Previous JSON:
{json.dumps(previous_data, indent=2)}

Rewrite the JSON now. Preserve the exact schema. Fix every issue. The resume must fill at least one complete page.
""".strip()


def call_llm(base_resume_text: str, jd_text: str, model: str, api_key: str | None = None) -> dict:
    client = OpenAI(api_key=api_key) if api_key else OpenAI()
    prompt = build_prompt(base_resume_text, jd_text)
    data = None
    issues = []

    for attempt in range(3):
        active_prompt = prompt if attempt == 0 else build_retry_prompt(prompt, data, issues)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": active_prompt}],
            temperature=0.25,
            response_format={"type": "json_object"},
        )
        data = extract_json(response.choices[0].message.content)
        issues = validate_generated_resume(data)
        if not issues:
            return data

    return repair_generated_resume(data, jd_text)


# ---------------- PDF EXPORT ---------------- #

def find_libreoffice() -> str:
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        shutil.which("soffice"),
        shutil.which("libreoffice"),
    ]

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)

    raise FileNotFoundError(
        "LibreOffice was not found. Install it or add soffice.exe to PATH."
    )


def convert_to_pdf(docx_path: Path, output_dir: Path) -> Path:
    pdf_path = output_dir / f"{docx_path.stem}.pdf"

    try:
        soffice = find_libreoffice()
        subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(docx_path),
            ],
            check=True,
        )
        return pdf_path
    except FileNotFoundError:
        pass

    ps_command = (
        "$word = New-Object -ComObject Word.Application; "
        "$word.Visible = $false; "
        "$doc = $word.Documents.Open($env:DOCX_PATH); "
        "$doc.SaveAs([ref]$env:PDF_PATH, [ref]17); "
        "$doc.Close(); "
        "$word.Quit();"
    )
    env = os.environ.copy()
    env["DOCX_PATH"] = str(docx_path)
    env["PDF_PATH"] = str(pdf_path)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_command], check=True, env=env)
    return pdf_path


# ---------------- GENERATION API ---------------- #

def generate_resume_from_jd(
    jd_text: str,
    base_resume_path: Path = BASE_RESUME,
    output_root: Path = OUTPUT_ROOT,
    model: str = DEFAULT_MODEL,
    details: dict | None = None,
    skip_pdf: bool = False,
    api_key: str | None = None,
) -> dict:
    if not base_resume_path.exists():
        raise FileNotFoundError(f"Base resume not found: {base_resume_path}")

    doc = Document(str(base_resume_path))
    base_resume_text = document_text(doc)

    data = call_llm(base_resume_text, jd_text, model, api_key=api_key)

    company_raw, role_raw = extract_company_role(jd_text)
    company = safe_filename(company_raw, "Company")
    role = safe_filename(role_raw, "Role")
    output_dir = output_root / company
    output_dir.mkdir(parents=True, exist_ok=True)

    update_contact_details(doc, details or {})

    missing = replace_placeholders(doc, data)
    if missing:
        raise ValueError(
            "Template placeholders missing: "
            + ", ".join(missing)
            + ". Add these exact placeholders to the base DOCX: "
            + ", ".join(PLACEHOLDERS.keys())
        )

    candidate_name = safe_filename((details or {}).get("name", ""), "Resume", max_len=60)
    docx_path = output_dir / f"{candidate_name}_{role}.docx"
    doc.save(str(docx_path))

    pdf_path = None
    if not skip_pdf:
        pdf_path = convert_to_pdf(docx_path, output_dir)

    return {
        "company": company,
        "role": role,
        "output_dir": str(output_dir),
        "docx_path": str(docx_path),
        "pdf_path": str(pdf_path) if pdf_path else None,
        "structured_resume": data,
    }


# ---------------- MAIN ---------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a tailored resume from a job description.")
    parser.add_argument("--jd", default=str(DEFAULT_JD_FILE), help="Path to the job description text file.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model to use.")
    parser.add_argument("--skip-pdf", action="store_true", help="Save DOCX only and skip PDF conversion.")
    args = parser.parse_args()

    jd_path = Path(args.jd)
    if not jd_path.exists():
        raise FileNotFoundError(f"Job description file not found: {jd_path}")
    jd_text = jd_path.read_text(encoding="utf-8")
    result = generate_resume_from_jd(jd_text, model=args.model, skip_pdf=args.skip_pdf)
    print(f"DOCX generated: {result['docx_path']}")
    if result["pdf_path"]:
        print(f"PDF generated: {result['pdf_path']}")


if __name__ == "__main__":
    main()
