import os
from pathlib import Path
from datetime import datetime
from docx import Document

TEMPLATE=Path(os.getenv('CONTRACT_TEMPLATE','templates/dogovir_fiz_osoba_template.docx'))
OUT=Path('data/contracts'); OUT.mkdir(parents=True,exist_ok=True)
TOKENS={
 '{{CONTRACT_NO}}':'contract_no','{{DATE}}':'date','{{CLIENT_NAME}}':'name','{{CLIENT_PHONE}}':'phone',
 '{{OBJECT_ADDRESS}}':'address','{{SERVICE}}':'service','{{DEVICE_TYPE}}':'device','{{QUANTITY}}':'quantity','{{DEVICE_DETAILS}}':'details'
}
def _replace_in_paragraph(p,mapping):
    # Preserve formatting when a token occupies a whole run; otherwise replace in paragraph text.
    full=p.text
    for token,value in mapping.items(): full=full.replace(token,str(value))
    if full!=p.text:
        if p.runs:
            p.runs[0].text=full
            for r in p.runs[1:]: r.text=''
        else: p.add_run(full)
def _walk(container,mapping):
    for p in container.paragraphs:_replace_in_paragraph(p,mapping)
    for t in container.tables:
        for row in t.rows:
            for cell in row.cells:_walk(cell,mapping)
def create_contract(d):
    if not TEMPLATE.exists():
        raise FileNotFoundError(f'Не знайдено шаблон договору: {TEMPLATE}')
    n=int(d['id']); date=datetime.now().strftime('%d.%m.%Y'); no=f'{n:04d}/{date}'
    mapping={k:(no if k=='{{CONTRACT_NO}}' else date if k=='{{DATE}}' else d.get(v,'')) for k,v in TOKENS.items()}
    doc=Document(TEMPLATE); _walk(doc,mapping)
    # Contract must be reviewed by manager. This file is a draft, not a signed agreement.
    out=OUT/f'dogovir_{n:04d}.docx'; doc.save(out); return out
