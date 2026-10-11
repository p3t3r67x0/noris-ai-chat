"""Fixed public chat error messages; never leak internals."""


class ChatError(Exception):
    def __init__(self, code: str, status: int = 400) -> None:
        self.code = code
        self.status = status
        self.message = MESSAGES[code]
        super().__init__(self.message)


MESSAGES = {
    "ATTACHMENT_NOT_FOUND": "Diese Datei ist nicht verfügbar oder gehört zu einem anderen Chat.",
    "ATTACHMENT_TYPE": (
        "Erlaubt sind UTF-8-Text, Markdown, PDF, PNG und JPEG mit passendem Dateiformat."
    ),
    "ATTACHMENT_INVALID": "Die Datei ist beschädigt oder entspricht nicht dem angegebenen Format.",
    "ATTACHMENT_PDF_ENCRYPTED": "Verschlüsselte PDFs werden nicht unterstützt.",
    "ATTACHMENT_PDF_PAGE_LIMIT": "Die PDF überschreitet die erlaubte Seitenzahl.",
    "ATTACHMENT_TEXT_LIMIT": "Der extrahierte Text überschreitet die erlaubte Textmenge.",
    "ATTACHMENT_PROCESSING_LIMIT": "Die Datei überschreitet die sicheren Verarbeitungslimits.",
    "ATTACHMENT_PROCESSING_TIMEOUT": "Die Dateiverarbeitung hat zu lange gedauert.",
    "ATTACHMENT_UPLOAD_TIMEOUT": "Die Übertragung der Datei hat zu lange gedauert.",
    "ATTACHMENT_SIZE": "Die Datei ist leer oder überschreitet die erlaubte Dateigröße.",
    "ATTACHMENT_QUOTA": (
        "Die Datei- oder Speichergrenze ist erreicht. Entferne nicht mehr benötigte Dateien."
    ),
    "ATTACHMENT_IN_USE": (
        "Eine gesendete Datei kann nur zusammen mit der Unterhaltung gelöscht werden."
    ),
    "ATTACHMENT_INCOMPATIBLE": (
        "Diese Datei kann vom gewählten Modell nicht verwendet werden. "
        "Bilder benötigen ein Modell mit bestätigter Bildeingabe. "
        "PDFs ohne extrahierbaren Text können nur gespeichert werden."
    ),
    "NOT_FOUND": "Diese Unterhaltung existiert nicht.",
    "ACCESS_DENIED": "Bitte melde dich für den Chatzugriff an.",
    "ORIGIN_DENIED": "Diese Herkunft ist für Chatanfragen nicht zugelassen.",
    "VERSION_CONFLICT": "Die Unterhaltung wurde zwischenzeitlich geändert.",
    "INVALID_PARENT": "Die übergeordnete Nachricht ist ungültig.",
    "INVALID_MESSAGE": "Die Nachricht entspricht nicht dem erwarteten Format.",
    "MESSAGE_EXISTS": "Diese Nachricht wurde bereits mit anderem Inhalt gespeichert.",
    "INVALID_LEAF": "Der ausgewählte Gesprächspfad ist ungültig.",
    "CONVERSATION_EXISTS": "Diese Unterhaltung wurde bereits mit anderen Daten importiert.",
    "IMPORT_CONFLICT": "Der Import enthält Konflikte mit vorhandenen Unterhaltungen.",
    "IMPORT_INVALID": "Der Import enthält ungültige Daten.",
    "GENERATION_NOT_FOUND": "Diese Generierung existiert nicht.",
    "GENERATION_ACTIVE": "Diese Generierung läuft bereits.",
    "INVALID_INPUT": "Die Anfrage ist ungültig.",
    "INVALID_CURSOR": "Die Seitenmarkierung ist ungültig. Lade die Liste erneut.",
    "INTERNAL_ERROR": "Die Chatanfrage konnte nicht verarbeitet werden.",
}
