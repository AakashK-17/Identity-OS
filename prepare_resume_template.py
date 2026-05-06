import shutil
from datetime import datetime
from pathlib import Path

from docx import Document

from generate_resume import (
    paragraph_index,
    replace_range_after_anchor,
)


SOURCE_RESUME = Path(r"D:\Resume's and coverletter\University of Utah Health Research\Aakash Kunarapu_Data Scientist.docx")
TEMPLATE_RESUME = Path(r"D:\Resume's and coverletter\University of Utah Health Research\Aakash Kunarapu_Data Scientist_Template.docx")


def main() -> None:
    backup_path = SOURCE_RESUME.with_name(
        f"{SOURCE_RESUME.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{SOURCE_RESUME.suffix}"
    )
    shutil.copy2(SOURCE_RESUME, backup_path)

    doc = Document(str(SOURCE_RESUME))

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

    doc.save(str(TEMPLATE_RESUME))
    print(f"Template created: {TEMPLATE_RESUME}")
    print(f"Backup created: {backup_path}")


if __name__ == "__main__":
    main()
