"""Session state machine for photo-based logging."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from nutrition_tracker.domain.sessions import SessionRecord


class PhotoRepository(Protocol):
    """Persistence interface for photo metadata."""

    def create_photo(
        self,
        user_id: UUID,
        telegram_chat_id: int,
        telegram_message_id: int,
        telegram_file_id: str,
        telegram_file_unique_id: str | None,
    ) -> UUID:
        """Create a photo metadata record and return its id."""

    def delete_photo(self, photo_id: UUID) -> None:
        """Delete a photo metadata record."""


class SessionRepository(Protocol):
    """Persistence interface for photo sessions."""

    def create_session(
        self, user_id: UUID, photo_id: UUID, status: str, context: dict[str, object]
    ) -> SessionRecord:
        """Create a new session and return it."""

    def get_session(self, session_id: UUID) -> SessionRecord | None:
        """Return a session by id, if present."""

    def get_active_session(self, user_id: UUID) -> SessionRecord | None:
        """Return the latest active session for a user, if present."""

    def update_session(
        self, session_id: UUID, status: str, context: dict[str, object]
    ) -> None:
        """Update a session status and context."""


@dataclass(frozen=True)
class SessionPrompt:
    """Represents the next user-facing prompt."""

    text: str
    reply_markup: dict | None = None


@dataclass
class SessionService:
    """State machine for guiding a photo session."""

    photo_repository: PhotoRepository
    session_repository: SessionRepository

    def start_session(  # noqa: PLR0913
        self,
        user_id: UUID,
        telegram_chat_id: int,
        telegram_message_id: int,
        telegram_file_id: str,
        telegram_file_unique_id: str | None,
        vision_items: list[dict[str, object]] | None = None,
    ) -> tuple[UUID, SessionPrompt]:
        """Create a session for a new photo and return the first prompt."""
        photo_id = self.photo_repository.create_photo(
            user_id=user_id,
            telegram_chat_id=telegram_chat_id,
            telegram_message_id=telegram_message_id,
            telegram_file_id=telegram_file_id,
            telegram_file_unique_id=telegram_file_unique_id,
        )
        context = {
            "items": vision_items or [],
            "resolved_items": [],
            "current_index": 0,
        }
        session = self.session_repository.create_session(
            user_id=user_id,
            photo_id=photo_id,
            status="AWAITING_CONFIRMATION",
            context=context,
        )
        prompt = SessionPrompt(
            text=_build_initial_prompt(vision_items),
            reply_markup=_inline_keyboard(
                [
                    ("Looks right", _callback_data(session.id, "confirm")),
                    ("Cancel", _callback_data(session.id, "cancel")),
                ]
            ),
        )
        return session.id, prompt

    def handle_callback(  # noqa: PLR0911
        self, session_id: UUID, action: str
    ) -> SessionPrompt | None:
        """Handle a callback action and return the next prompt."""
        session = self.session_repository.get_session(session_id)
        if session is None or session.status in {"COMPLETED", "CANCELLED"}:
            return None

        if action == "confirm":
            context = dict(session.context)
            if context.get("items"):
                context["current_index"] = 0
                context["resolved_items"] = []
                self.session_repository.update_session(
                    session_id,
                    status="AWAITING_PORTION_CHOICE",
                    context=context,
                )
                return _portion_prompt(session_id, context)
            self.session_repository.update_session(
                session_id,
                status="AWAITING_ITEM_NAME",
                context=context,
            )
            return SessionPrompt(
                text="What is the main item in the photo? Reply with a name.",
            )
        if action == "cancel":
            if session.photo_id:
                self.photo_repository.delete_photo(session.photo_id)
            self.session_repository.update_session(
                session_id,
                status="CANCELLED",
                context=dict(session.context),
            )
            return SessionPrompt(text="Session cancelled. Send another photo to start.")
        if action == "use_estimate":
            return self._apply_estimate(session_id, session)
        if action == "enter_grams":
            context = dict(session.context)
            self.session_repository.update_session(
                session_id,
                status="AWAITING_MANUAL_GRAMS",
                context=context,
            )
            item = _current_item(context)
            label = item.get("label", "item")
            return SessionPrompt(text=f"Enter grams for {label}.")
        return None

    def handle_text(self, user_id: UUID, text: str) -> SessionPrompt | None:
        """Handle free-text replies for the active session."""
        session = self.session_repository.get_active_session(user_id)
        if session is None:
            return None

        context = dict(session.context)
        if session.status == "AWAITING_ITEM_NAME":
            context["items"] = [{"label": text.strip()}]
            context["current_index"] = 0
            context["resolved_items"] = []
            self.session_repository.update_session(
                session.id, status="AWAITING_PORTION_CHOICE", context=context
            )
            return _portion_prompt(session.id, context)

        if session.status == "AWAITING_MANUAL_GRAMS":
            grams = _parse_grams(text)
            if grams is None:
                return SessionPrompt(text="Please reply with a number of grams.")
            _record_current_item(context, grams)
            return self._advance_or_summarize(session.id, context)

        return None

    def _apply_estimate(
        self, session_id: UUID, session: SessionRecord
    ) -> SessionPrompt | None:
        context = dict(session.context)
        item = _current_item(context)
        estimate = _estimate_grams(item)
        if estimate is None:
            self.session_repository.update_session(
                session_id,
                status="AWAITING_MANUAL_GRAMS",
                context=context,
            )
            return SessionPrompt(text="Enter grams for the item.")
        _record_current_item(context, estimate)
        return self._advance_or_summarize(session_id, context)

    def _advance_or_summarize(
        self, session_id: UUID, context: dict[str, object]
    ) -> SessionPrompt:
        context["current_index"] = int(context.get("current_index", 0)) + 1
        items = context.get("items", [])
        if isinstance(items, list) and context["current_index"] < len(items):
            self.session_repository.update_session(
                session_id,
                status="AWAITING_PORTION_CHOICE",
                context=context,
            )
            return _portion_prompt(session_id, context)

        self.session_repository.update_session(
            session_id,
            status="AWAITING_SAVE",
            context=context,
        )
        return _summary_prompt(session_id, context)


def _callback_data(session_id: UUID, action: str) -> str:
    """Build callback_data within Telegram's 64-byte limit."""
    return f"s:{session_id}:{action}"


def _inline_keyboard(buttons: list[tuple[str, str]]) -> dict:
    """Build a Telegram inline keyboard payload."""
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": callback}] for label, callback in buttons
        ]
    }


def _build_initial_prompt(vision_items: list[dict[str, object]] | None) -> str:
    """Build the first prompt with detected items if available."""
    if not vision_items:
        return "I received your photo. Ready to identify foods?"

    lines = []
    for item in vision_items:
        label = str(item.get("label", "item"))
        confidence = item.get("confidence")
        if isinstance(confidence, int | float):
            confidence_pct = f"{confidence:.0%}"
            lines.append(f"- {label} ({confidence_pct})")
        else:
            lines.append(f"- {label}")
    formatted = "\n".join(lines)
    return f"I think I see:\n{formatted}\nDoes this look right?"


def _parse_grams(text: str) -> int | None:
    """Parse a grams value from user input."""
    cleaned = text.strip().lower().replace("grams", "").replace("g", "")
    try:
        value = int(float(cleaned))
    except ValueError:
        return None
    return value if value > 0 else None


def _current_item(context: dict[str, object]) -> dict[str, object]:
    items = context.get("items", [])
    index = int(context.get("current_index", 0))
    if isinstance(items, list) and 0 <= index < len(items):
        item = items[index]
        if isinstance(item, dict):
            return item
    return {}


def _estimate_grams(item: dict[str, object]) -> int | None:
    low = item.get("estimated_grams_low")
    high = item.get("estimated_grams_high")
    if isinstance(low, int | float) and isinstance(high, int | float) and high > 0:
        return round((float(low) + float(high)) / 2)
    if isinstance(low, int | float) and low > 0:
        return round(float(low))
    return None


def _record_current_item(context: dict[str, object], grams: int) -> None:
    item = _current_item(context)
    resolved = list(context.get("resolved_items", []))
    resolved.append(
        {
            "label": item.get("label", "item"),
            "grams": grams,
        }
    )
    context["resolved_items"] = resolved


def _portion_prompt(session_id: UUID, context: dict[str, object]) -> SessionPrompt:
    item = _current_item(context)
    label = item.get("label", "item")
    estimate = _estimate_grams(item)
    buttons: list[tuple[str, str]] = []
    if estimate:
        buttons.append(
            (
                f"Use {estimate}g (est.)",
                _callback_data(session_id, "use_estimate"),
            )
        )
    buttons.append(("Enter grams", _callback_data(session_id, "enter_grams")))
    return SessionPrompt(
        text=f"How much {label} is there?",
        reply_markup=_inline_keyboard(buttons),
    )


def _summary_prompt(session_id: UUID, context: dict[str, object]) -> SessionPrompt:
    items = context.get("resolved_items", [])
    lines = []
    for item in items:
        if isinstance(item, dict):
            label = item.get("label", "item")
            grams = item.get("grams", "?")
            lines.append(f"- {label}: {grams}g")
    summary = "\n".join(lines) if lines else "No items recorded."
    return SessionPrompt(
        text=f"Summary:\\n{summary}\\nSave this meal?",
        reply_markup=_inline_keyboard(
            [
                ("Save", _callback_data(session_id, "save")),
                ("Cancel", _callback_data(session_id, "cancel")),
            ]
        ),
    )
