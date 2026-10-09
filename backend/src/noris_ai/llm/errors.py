class LLMError(Exception):
    """Only fixed, public messages; never forward upstream bodies or exception text."""

    def __init__(self, code: str, status: int = 502) -> None:
        self.code = code
        self.status = status
        self.message = MESSAGES[code]
        super().__init__(self.message)


MESSAGES = {
    "LLM_DISABLED": "Die Modellanbindung ist nicht freigeschaltet.",
    "ACCESS_DENIED": "Bitte melde dich für den Modellzugriff an.",
    "ORIGIN_DENIED": "Diese Herkunft ist für Modellanfragen nicht zugelassen.",
    "REQUEST_TOO_LARGE": "Die Anfrage überschreitet die zulässige Größe.",
    "INVALID_REQUEST": "Die Anfrage muss gültiges JSON enthalten.",
    "CONTEXT_LIMIT": "Der Gesprächskontext ist zu groß für dieses Modell. Starte einen neuen Chat.",
    "MODEL_UNAVAILABLE": "Das ausgewählte Modell ist nicht verfügbar.",
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
    "DUPLICATE_CONTINUATION": (
        "Das Modell hat vorhandenen Text wiederholt. Die bisherige Antwort bleibt erhalten."
    ),
    "CONTENT_FILTERED": "Der Modelldienst hat die Antwort blockiert.",
    "INTERNAL_ERROR": "Die Modellantwort konnte nicht verarbeitet werden.",
}
