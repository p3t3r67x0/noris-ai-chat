import re

from noris_ai.llm.errors import LLMError


class SSEDecoder:
    """Bounded SSE data frames across UTF-8 and LF/CRLF/CR network boundaries."""

    def __init__(self, limit: int = 65_536) -> None:
        self._buffer = b""
        self._data: list[str] = []
        self._size = 0
        self._limit = limit
        self._skip_lf = False
        self._first_line = True

    def feed(self, chunk: bytes) -> list[str]:
        if chunk and self._skip_lf:
            if chunk.startswith(b"\n"):
                chunk = chunk[1:]
            self._skip_lf = False
        self._buffer += chunk
        frames: list[str] = []
        while match := re.search(rb"\r\n|\r|\n", self._buffer):
            self._skip_lf = match.group() == b"\r" and match.end() == len(self._buffer)
            line, self._buffer = self._buffer[: match.start()], self._buffer[match.end() :]
            if len(line) > self._limit:
                raise LLMError("INVALID_RESPONSE")
            try:
                text = line.decode("utf-8-sig" if self._first_line else "utf-8")
            except UnicodeDecodeError:
                raise LLMError("INVALID_RESPONSE") from None
            self._first_line = False
            if not text:
                if self._data:
                    frames.append("\n".join(self._data))
                self._data = []
                self._size = 0
            elif text.startswith("data:"):
                value = text[5:]
                if value.startswith(" "):
                    value = value[1:]
                self._size += len(line) + 1
                if self._size > self._limit:
                    raise LLMError("INVALID_RESPONSE")
                self._data.append(value)
        if len(self._buffer) > self._limit:
            raise LLMError("INVALID_RESPONSE")
        return frames

    @property
    def incomplete(self) -> bool:
        return bool(self._buffer or self._data)
