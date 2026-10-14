class LLMError(Exception):
    """Only fixed, public messages; never forward upstream bodies or exception text."""

    def __init__(self, code: str, status: int = 502) -> None:
        self.code = code
        self.status = status
        self.message = MESSAGES[code]
        super().__init__(self.message)


MESSAGES = {
    "RESEARCH_DISABLED": "Die Recherche ist nicht freigeschaltet.",
    "RESEARCH_UNAVAILABLE": "Die Recherche ist derzeit nicht verfügbar.",
    "RESEARCH_INVALID": "Die Anfrage ist für die Recherche nicht zulässig.",
    "RESEARCH_NO_SOURCES": "Die Recherche hat keine verwendbaren Quellen geliefert.",
    "RESEARCH_FAILED": "Die Recherche konnte nicht sicher abgeschlossen werden.",
    "RESEARCH_APPROVAL_REQUIRED": "Die Recherche benötigt eine ausdrückliche Freigabe.",
    "LLM_DISABLED": "Die Modellanbindung ist nicht freigeschaltet.",
    "ACCESS_DENIED": "Bitte melde dich für den Modellzugriff an.",
    "ORIGIN_DENIED": "Diese Herkunft ist für Modellanfragen nicht zugelassen.",
    "REQUEST_TOO_LARGE": "Die Anfrage überschreitet die zulässige Größe.",
    "INVALID_REQUEST": "Die Anfrage muss gültiges JSON enthalten.",
    "CONTEXT_LIMIT": (
        "Die Anfrage überschreitet mit Gespräch, Anhängen und reservierter Antwort "
        "das Kontextlimit dieses Modells. Kürze den Inhalt oder wähle ein Modell "
        "mit größerem Kontext."
    ),
    "MODEL_UNAVAILABLE": "Das ausgewählte Modell ist nicht verfügbar.",
    "REASONING_UNSUPPORTED": "Diese Denkstufe wird vom ausgewählten Modell nicht unterstützt.",
    "RATE_LIMIT": "Zu viele Modellanfragen. Bitte versuche es später erneut.",
    "BUDGET_LIMIT": "Das konfigurierte tägliche Tokenbudget ist ausgeschöpft.",
    "GENERATION_ACTIVE": "Diese Generierung läuft bereits.",
    "TITLE_ALREADY_ATTEMPTED": "Für diese Unterhaltung wurde bereits ein Titel angefordert.",
    "PROVIDER_UNREACHABLE": "Der Modelldienst ist derzeit nicht erreichbar.",
    "PROVIDER_AUTH_FAILED": "Die Anmeldung beim Modelldienst ist fehlgeschlagen.",
    "PROVIDER_ERROR": "Der Modelldienst konnte die Anfrage nicht verarbeiten.",
    "TIMEOUT": "Die Modellantwort hat zu lange gedauert.",
    "STREAM_INTERRUPTED": "Die Verbindung endete vor dem Abschluss der Antwort.",
    "INVALID_RESPONSE": "Der Modelldienst hat eine ungültige Antwort geliefert.",
    "OUTPUT_LIMIT": "Die Antwort überschreitet das konfigurierte Ausgabelimit.",
    "RESPONSE_SIZE_LIMIT": (
        "Die gespeicherte Antwort hat die konfigurierte Größenbegrenzung erreicht."
    ),
    "STREAM_SIZE_LIMIT": "Die Übertragung hat die konfigurierte Größenbegrenzung erreicht.",
    "CONTINUATION_LIMIT": "Die maximale Anzahl Fortsetzungen ist erreicht.",
    "AUTO_CONTINUATION_LIMIT": (
        "Das Limit für automatische Fortsetzungen ist erreicht. Der bisherige Text bleibt erhalten."
    ),
    "DUPLICATE_CONTINUATION": (
        "Das Modell hat vorhandenen Text wiederholt. Die bisherige Antwort bleibt erhalten."
    ),
    "CONTENT_FILTERED": "Der Modelldienst hat die Antwort blockiert.",
    "INTERNAL_ERROR": "Die Modellantwort konnte nicht verarbeitet werden.",
}
