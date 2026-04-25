import asyncio
import time
from enum import Enum
from typing import Any, Dict, Optional

class State(str, Enum):
    NEW = "NEW"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class StateEntry:
    def __init__(self, key: str, request_hash: str):
        self.key = key
        self.state = State.NEW
        self.request_hash = request_hash
        self.response: Optional[Dict[str, Any]] = None
        self.future: Optional[asyncio.Future] = None
        self.created_at = time.time()

class TransitionResult:
    def __init__(self, entry: StateEntry, is_new: bool):
        self.entry = entry
        self.is_new = is_new

class StateManager:
    def __init__(self) -> None:
        self._store: Dict[str, StateEntry] = {}

    def get_entry(self, key: str) -> Optional[StateEntry]:
        return self._store.get(key)

    def transition_to_processing(self, key: str, request_hash: str) -> TransitionResult:
        entry = self._store.get(key)
        if entry:
            if entry.state == State.FAILED:
                entry.state = State.PROCESSING
                entry.request_hash = request_hash
                entry.future = asyncio.Future()
                return TransitionResult(entry, True)
            return TransitionResult(entry, False)
        
        entry = StateEntry(key, request_hash)
        entry.state = State.PROCESSING
        entry.future = asyncio.Future()
        self._store[key] = entry
        return TransitionResult(entry, True)

    def transition_to_completed(self, key: str, response: Dict[str, Any]) -> None:
        entry = self._store.get(key)
        if entry and entry.state == State.PROCESSING:
            entry.state = State.COMPLETED
            entry.response = response
            if entry.future and not entry.future.done():
                entry.future.set_result(response)

    def transition_to_failed(self, key: str, error: Exception) -> None:
        entry = self._store.get(key)
        if entry and entry.state == State.PROCESSING:
            entry.state = State.FAILED
            if entry.future and not entry.future.done():
                entry.future.set_exception(error)

    def sweep_expired(self, ttl_seconds: float) -> int:
        now = time.time()
        to_remove = [k for k, v in self._store.items() if now - v.created_at > ttl_seconds]
        for k in to_remove:
            del self._store[k]
        return len(to_remove)

state_manager = StateManager()