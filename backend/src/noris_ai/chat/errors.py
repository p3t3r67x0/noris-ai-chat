"""Fixed public chat error messages; never leak internals."""


class ChatError(Exception):
    def __init__(self, code: str, status: int = 400) -> None:
        self.code = code
        self.status = status
        self.message = MESSAGES[code]
        super().__init__(self.message)


MESSAGES = {
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
    "INTERNAL_ERROR": "Die Chatanfrage konnte nicht verarbeitet werden.",
}
