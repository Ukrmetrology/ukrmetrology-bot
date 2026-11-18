import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from docx import Document

TEMPLATE = Path(os.getenv(
    "CONTRACT_TEMPLATE",
    "templates/dogovir_fiz_osoba_template.docx",
))
OUT = Path("data/contracts")
OUT.mkdir(parents=True, exist_ok=True)

TOKENS = {
    "{{CONTRACT_NO}}": "contract_no",
    "{{DATE}}": "contract_date",
    "{{CLIENT_NAME}}": "name",
    "{{CLIENT_PHONE}}": "phone",
    "{{OBJECT_ADDRESS}}": "address",
    "{{SERVICE}}": "service",
    "{{DEVICE_TYPE}}": "device",
    "{{QUANTITY}}": "quantity",
    "{{DEVICE_DETAILS}}": "details",
    "{{COMPANY_NAME}}": "company_name",
    "{{COMPANY_ADDRESS}}": "company_address",
    "{{COMPANY_PHONE}}": "company_phone",
    "{{COMPANY_EMAIL}}": "company_email",
}

REQUIRED_TOKENS = (
    "{{CONTRACT_NO}}",
    "{{DATE}}",
    "{{CLIENT_NAME}}",
    "{{CLIENT_PHONE}}",
    "{{OBJECT_ADDRESS}}",
    "{{SERVICE}}",
)


def _replace_in_paragraph(paragraph, mapping):
    original = paragraph.text
    updated = original
    for token, value in mapping.items():
        updated = updated.replace(token, str(value))
    if updated == original:
        return
    if paragraph.runs:
        paragraph.runs[0].text = updated
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(updated)


def _walk_container(container, mapping):
    for paragraph in container.paragraphs:
        _replace_in_paragraph(paragraph, mapping)
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                _walk_container(cell, mapping)


def _all_container_text(container):
    result = [paragraph.text for paragraph in container.paragraphs]
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                result.extend(_all_container_text(cell))
    return result


def _all_document_text(document):
    result = _all_container_text(document)
    for section in document.sections:
        for part in (
            section.header, section.footer,
            section.first_page_header, section.first_page_footer,
            section.even_page_header, section.even_page_footer,
        ):
            result.extend(_all_container_text(part))
    return "\n".join(result)


def create_contract(data):
    if not TEMPLATE.is_file():
        raise FileNotFoundError(f"Не знайдено шаблон договору: {TEMPLATE}")

    now = datetime.now(ZoneInfo("Europe/Kyiv"))
    contract_date = data.get("contract_date") or now.strftime("%d.%m.%Y")
    contract_no = data.get("contract_no") or f"{int(data['id']):04d}/{contract_date}"

    mapping = {
        "{{CONTRACT_NO}}": contract_no,
        "{{DATE}}": contract_date,
        "{{CLIENT_NAME}}": data.get("name", ""),
        "{{CLIENT_PHONE}}": data.get("phone", ""),
        "{{OBJECT_ADDRESS}}": data.get("address", ""),
        "{{SERVICE}}": data.get("service", ""),
        "{{DEVICE_TYPE}}": data.get("device", ""),
        "{{QUANTITY}}": data.get("quantity", ""),
        "{{DEVICE_DETAILS}}": data.get("details", "Немає"),
        "{{COMPANY_NAME}}": os.getenv("COMPANY_NAME", "ТОВ «УКРМЕТРОЛОГІЯ»"),
        "{{COMPANY_ADDRESS}}": os.getenv("COMPANY_ADDRESS", "м. Одеса, Південна дорога, буд. 57"),
        "{{COMPANY_PHONE}}": os.getenv("COMPANY_PHONE", "+380 67 009 13 88"),
        "{{COMPANY_EMAIL}}": os.getenv("COMPANY_EMAIL", "ukrmetrology2023@gmail.com"),
    }

    document = Document(TEMPLATE)
    missing = [token for token in REQUIRED_TOKENS if token not in _all_document_text(document)]
    if missing:
        raise ValueError(
            "У шаблоні договору відсутні обов’язкові маркери: "
            + ", ".join(missing)
            + ". Додайте їх у потрібні місця DOCX, не змінюючи юридичний текст."
        )

    _walk_container(document, mapping)
    for section in document.sections:
        for part in (
            section.header, section.footer,
            section.first_page_header, section.first_page_footer,
            section.even_page_header, section.even_page_footer,
        ):
            _walk_container(part, mapping)

    remaining = [token for token in REQUIRED_TOKENS if token in _all_document_text(document)]
    if remaining:
        raise ValueError("Не вдалося замінити маркери: " + ", ".join(remaining))

    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / f"dogovir_{int(data['id']):04d}.docx"
    document.save(output)
    return output
