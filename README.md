# UKRMETROLOGIYA Telegram bot v5

A button-led Ukrainian-language intake bot for individual customers. See `README_ЗАПУСК.txt` for setup and required DOCX template markers.

The bot sends the customer only `Заявку прийнято`, while the manager receives the full application and a DOCX draft. Manager-only actions support replacing the DOCX, approving, or rejecting.

**Important:** the DOCX template must be supplied locally as `templates/dogovir_fiz_osoba_template.docx` and contain the documented `{{...}}` replacement markers. Financial details are intentionally gated until IBAN and price list are ready. SQLite is implemented; Google Sheets integration is not yet enabled in this build.
