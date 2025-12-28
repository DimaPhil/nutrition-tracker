"""Session state machine for photo-based logging and edits."""

import logging
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from nutrition_tracker.domain.library import LibraryFood
from nutrition_tracker.domain.meals import MealLogDetail, MealLogSummary
from nutrition_tracker.domain.nutrition import FoodSummary
from nutrition_tracker.domain.sessions import SessionRecord
from nutrition_tracker.services.audit import AuditService
from nutrition_tracker.services.library import LibraryService
from nutrition_tracker.services.meals import MealLogService
from nutrition_tracker.services.nutrition import NutritionService

STATUS_AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
STATUS_AWAITING_ITEM_LIST = "AWAITING_ITEM_LIST"
STATUS_AWAITING_ITEM_CONFIRMATION = "AWAITING_ITEM_CONFIRMATION"
STATUS_AWAITING_ITEM_SELECTION = "AWAITING_ITEM_SELECTION"
STATUS_AWAITING_MANUAL_NAME = "AWAITING_MANUAL_NAME"
STATUS_AWAITING_MANUAL_STORE = "AWAITING_MANUAL_STORE"
STATUS_AWAITING_MANUAL_BASIS = "AWAITING_MANUAL_BASIS"
STATUS_AWAITING_MANUAL_SERVING = "AWAITING_MANUAL_SERVING"
STATUS_AWAITING_MANUAL_MACROS = "AWAITING_MANUAL_MACROS"
STATUS_AWAITING_PORTION_CHOICE = "AWAITING_PORTION_CHOICE"
STATUS_AWAITING_MANUAL_GRAMS = "AWAITING_MANUAL_GRAMS"
STATUS_AWAITING_SAVE = "AWAITING_SAVE"
STATUS_AWAITING_EDIT_CHOICE = "AWAITING_EDIT_CHOICE"
STATUS_AWAITING_EDIT_GRAMS = "AWAITING_EDIT_GRAMS"
STATUS_EDIT_SELECT_ITEM = "EDIT_SELECT_ITEM"
STATUS_EDIT_ENTER_GRAMS = "EDIT_ENTER_GRAMS"
STATUS_CANCELLED = "CANCELLED"
STATUS_COMPLETED = "COMPLETED"
MACRO_PARTS = 4

_logger = logging.getLogger(__name__)


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
        self,
        user_id: UUID,
        photo_id: UUID | None,
        status: str,
        context: dict[str, object],
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
    library_service: LibraryService
    nutrition_service: NutritionService
    meal_log_service: MealLogService
    audit_service: AuditService
    debug: bool = False

    async def start_session(  # noqa: PLR0913
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
        context: dict[str, object] = {
            "flow": "photo",
            "user_id": str(user_id),
            "items": vision_items or [],
            "current_index": 0,
            "resolved_items": [],
        }
        session = self.session_repository.create_session(
            user_id=user_id,
            photo_id=photo_id,
            status=STATUS_AWAITING_CONFIRMATION,
            context=context,
        )
        if self.debug:
            _logger.info(
                "Session started: user=%s items=%s",
                user_id,
                len(vision_items or []),
            )
        prompt = SessionPrompt(
            text=_build_initial_prompt(vision_items),
            reply_markup=_inline_keyboard(
                [
                    ("Looks right", _callback_data(session.id, "confirm")),
                    ("Fix items", _callback_data(session.id, "fix")),
                    ("Cancel", _callback_data(session.id, "cancel")),
                ]
            ),
        )
        return session.id, prompt

    def start_library_add_session(self, user_id: UUID) -> SessionPrompt:
        """Start a manual library-add session."""
        context: dict[str, object] = {
            "flow": "library",
            "user_id": str(user_id),
            "manual": {"target": "library"},
        }
        self.session_repository.create_session(
            user_id=user_id,
            photo_id=None,
            status=STATUS_AWAITING_MANUAL_NAME,
            context=context,
        )
        return SessionPrompt(text="Enter the food name to add to your library.")

    def start_edit_session(
        self, user_id: UUID, meal_log_id: UUID
    ) -> SessionPrompt | None:
        """Start editing a saved meal log."""
        detail = self.meal_log_service.get_meal_detail(meal_log_id)
        if detail is None:
            return None
        context: dict[str, object] = {
            "flow": "edit",
            "user_id": str(user_id),
            "meal_id": str(meal_log_id),
            "edit_items": [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "grams": item.grams,
                    "calories": item.calories,
                    "protein_g": item.protein_g,
                    "fat_g": item.fat_g,
                    "carbs_g": item.carbs_g,
                }
                for item in detail.items
            ],
        }
        session = self.session_repository.create_session(
            user_id=user_id,
            photo_id=None,
            status=STATUS_EDIT_SELECT_ITEM,
            context=context,
        )
        return _edit_item_prompt(session.id, context)

    def cancel_active_session(self, user_id: UUID) -> SessionPrompt | None:
        """Cancel the active session for a user, if any."""
        session = self.session_repository.get_active_session(user_id)
        if session is None:
            return None
        return self._cancel_session(session)

    async def handle_callback(
        self, session_id: UUID, action: str, payload: str | None = None
    ) -> SessionPrompt | None:
        """Handle a callback action and return the next prompt."""
        session = self.session_repository.get_session(session_id)
        if session is None or session.status in {STATUS_COMPLETED, STATUS_CANCELLED}:
            return None

        flow = str(session.context.get("flow", "photo"))
        if action == "cancel":
            return self._cancel_session(session)

        if flow == "photo":
            return await self._handle_photo_callback(session, action, payload)
        if flow == "edit":
            return self._handle_edit_callback(session, action, payload)
        if flow == "library":
            return self._handle_library_callback(session, action, payload)
        return None

    async def handle_text(self, user_id: UUID, text: str) -> SessionPrompt | None:
        """Handle free-text replies for the active session."""
        session = self.session_repository.get_active_session(user_id)
        if session is None:
            return None

        flow = str(session.context.get("flow", "photo"))
        if flow == "photo":
            return await self._handle_photo_text(session, text)
        if flow == "library":
            return await self._handle_library_text(session, text)
        if flow == "edit":
            return self._handle_edit_text(session, text)
        return None

    async def _handle_photo_callback(  # noqa: PLR0911, PLR0912
        self, session: SessionRecord, action: str, payload: str | None
    ) -> SessionPrompt | None:
        context = dict(session.context)
        if action == "confirm":
            context["current_index"] = 0
            return await self._prompt_item_confirmation(session.id, context)
        if action == "fix":
            self.session_repository.update_session(
                session.id, status=STATUS_AWAITING_ITEM_LIST, context=context
            )
            return SessionPrompt(
                text="Please list the foods in the photo (comma-separated)."
            )
        if action == "item_yes":
            return await self._apply_candidate_selection(session.id, context, 0)
        if action == "item_no":
            return self._prompt_item_selection(session.id, context)
        if action == "choose" and payload is not None:
            index = _safe_int(payload)
            if index is None:
                return None
            return await self._apply_candidate_selection(session.id, context, index)
        if action == "basis_100":
            return self._set_manual_basis(session.id, context, "per100g")
        if action == "basis_serv":
            return self._set_manual_basis(session.id, context, "perServing")
        if action.startswith("store_"):
            return self._set_manual_store(session.id, context, action)
        if action == "portion_est":
            return await self._apply_estimate(session.id, context)
        if action == "portion_manual":
            self.session_repository.update_session(
                session.id, status=STATUS_AWAITING_MANUAL_GRAMS, context=context
            )
            item = _current_item(context)
            label = _item_label(item)
            return SessionPrompt(text=f"Enter grams for {label}.")
        if action == "portion_skip":
            _mark_skipped(context)
            return await self._advance_or_summarize(session.id, context)
        if action == "edit":
            self.session_repository.update_session(
                session.id, status=STATUS_AWAITING_EDIT_CHOICE, context=context
            )
            return _edit_choice_prompt(session.id, context)
        if action == "edit_item" and payload is not None:
            index = _safe_int(payload)
            if index is None:
                return None
            context["edit_index"] = index
            self.session_repository.update_session(
                session.id, status=STATUS_AWAITING_EDIT_GRAMS, context=context
            )
            items = context.get("resolved_items", [])
            if isinstance(items, list) and 0 <= index < len(items):
                name = str(items[index].get("name", "item"))
            else:
                name = "item"
            return SessionPrompt(text=f"Enter new grams for {name}.")
        return None

    async def _handle_photo_text(  # noqa: PLR0911, PLR0912
        self, session: SessionRecord, text: str
    ) -> SessionPrompt | None:
        context = dict(session.context)
        if session.status == STATUS_AWAITING_ITEM_LIST:
            items = _parse_item_list(text)
            if not items:
                return SessionPrompt(text="Please send a comma-separated list.")
            context["items"] = [{"label": item} for item in items]
            context["current_index"] = 0
            return await self._prompt_item_confirmation(session.id, context)

        if session.status == STATUS_AWAITING_MANUAL_NAME:
            name = text.strip()
            if not name:
                return SessionPrompt(text="Please provide a name for the item.")
            manual = dict(context.get("manual", {}))
            manual["name"] = name
            context["manual"] = manual
            self.session_repository.update_session(
                session.id, status=STATUS_AWAITING_MANUAL_STORE, context=context
            )
            return _manual_store_prompt(session.id, name)

        if session.status == STATUS_AWAITING_MANUAL_STORE:
            return SessionPrompt(text="Choose a store using the buttons.")

        if session.status == STATUS_AWAITING_MANUAL_SERVING:
            grams = _parse_grams(text)
            if grams is None:
                return SessionPrompt(text="Enter the serving size in grams.")
            manual = dict(context.get("manual", {}))
            manual["serving_size_g"] = grams
            context["manual"] = manual
            self.session_repository.update_session(
                session.id, status=STATUS_AWAITING_MANUAL_MACROS, context=context
            )
            return SessionPrompt(
                text=(
                    "Enter calories, protein, fat, carbs per serving "
                    "(e.g., 200, 10, 5, 30)."
                )
            )

        if session.status == STATUS_AWAITING_MANUAL_MACROS:
            macros = _parse_macros(text)
            if macros is None:
                return SessionPrompt(
                    text="Enter calories, protein, fat, carbs (e.g., 200, 10, 5, 30)."
                )
            context = await self._finalize_manual_entry(session.id, context, macros)
            if context.get("flow") == "library":
                return SessionPrompt(text="Saved to your library.")
            return _portion_prompt(session.id, context)

        if session.status == STATUS_AWAITING_MANUAL_GRAMS:
            grams = _parse_grams(text)
            if grams is None:
                return SessionPrompt(text="Please reply with a number of grams.")
            _record_current_grams(context, grams)
            return await self._advance_or_summarize(session.id, context)

        if session.status == STATUS_AWAITING_EDIT_GRAMS:
            grams = _parse_grams(text)
            if grams is None:
                return SessionPrompt(text="Please reply with grams.")
            _apply_edit_grams(context, grams)
            return await self._show_summary(session.id, context)

        return None

    def _handle_edit_callback(
        self, session: SessionRecord, action: str, payload: str | None
    ) -> SessionPrompt | None:
        context = dict(session.context)
        if action == "edit_item" and payload is not None:
            index = _safe_int(payload)
            if index is None:
                return None
            context["edit_item_id"] = _edit_item_id(context, index)
            context["edit_item_name"] = _edit_item_name(context, index)
            self.session_repository.update_session(
                session.id, status=STATUS_EDIT_ENTER_GRAMS, context=context
            )
            name = context.get("edit_item_name", "item")
            return SessionPrompt(text=f"Enter new grams for {name}.")
        return None

    def _handle_edit_text(
        self, session: SessionRecord, text: str
    ) -> SessionPrompt | None:
        if session.status != STATUS_EDIT_ENTER_GRAMS:
            return None
        grams = _parse_grams(text)
        if grams is None:
            return SessionPrompt(text="Please reply with grams.")
        item_id_raw = session.context.get("edit_item_id")
        if not isinstance(item_id_raw, str):
            return None
        try:
            item_id = UUID(item_id_raw)
        except ValueError:
            return None
        detail = self.meal_log_service.update_meal_item_grams(item_id, grams)
        self.session_repository.update_session(
            session.id, status=STATUS_COMPLETED, context=dict(session.context)
        )
        if detail is None:
            return SessionPrompt(text="Unable to update that meal item.")
        before = _edit_item_snapshot(session.context, item_id)
        after = _detail_item_snapshot(detail, item_id)
        if before or after:
            self.audit_service.record_event(
                user_id=session.user_id,
                entity_type="meal_item",
                entity_id=item_id,
                event_type="update_grams",
                before=before,
                after=after,
            )
        return SessionPrompt(text=_format_meal_detail(detail))

    def _handle_library_callback(
        self, session: SessionRecord, action: str, _payload: str | None
    ) -> SessionPrompt | None:
        context = dict(session.context)
        if action == "basis_100":
            return self._set_manual_basis(session.id, context, "per100g")
        if action == "basis_serv":
            return self._set_manual_basis(session.id, context, "perServing")
        if action.startswith("store_"):
            return self._set_manual_store(session.id, context, action)
        return None

    async def _handle_library_text(
        self, session: SessionRecord, text: str
    ) -> SessionPrompt | None:
        if session.status in {
            STATUS_AWAITING_MANUAL_NAME,
            STATUS_AWAITING_MANUAL_BASIS,
            STATUS_AWAITING_MANUAL_SERVING,
            STATUS_AWAITING_MANUAL_MACROS,
        }:
            return await self._handle_photo_text(session, text)
        return None

    def _cancel_session(self, session: SessionRecord) -> SessionPrompt:
        if session.photo_id:
            self.photo_repository.delete_photo(session.photo_id)
        self.session_repository.update_session(
            session.id,
            status=STATUS_CANCELLED,
            context=dict(session.context),
        )
        return SessionPrompt(text="Session cancelled. Send another photo to start.")

    async def _prompt_item_confirmation(
        self, session_id: UUID, context: dict[str, object]
    ) -> SessionPrompt:
        items = context.get("items", [])
        if not isinstance(items, list) or not items:
            context["items"] = [{"label": "item"}]
        await self._ensure_candidates(context)
        options = context.get("candidate_options", [])
        if not isinstance(options, list) or not options:
            self.session_repository.update_session(
                session_id, status=STATUS_AWAITING_MANUAL_NAME, context=context
            )
            return SessionPrompt(text="What is the item? Reply with a name.")
        top = options[0]
        if isinstance(top, dict) and top.get("type") == "manual":
            return self._set_manual_target(session_id, context)
        label = _current_item_label(context)
        choice = str(top.get("label", "this item"))
        self.session_repository.update_session(
            session_id, status=STATUS_AWAITING_ITEM_CONFIRMATION, context=context
        )
        return SessionPrompt(
            text=f"For {label}, I think it's {choice}. Use this?",
            reply_markup=_inline_keyboard(
                [
                    ("Yes", _callback_data(session_id, "item_yes")),
                    ("No", _callback_data(session_id, "item_no")),
                ]
            ),
        )

    def _prompt_item_selection(
        self, session_id: UUID, context: dict[str, object]
    ) -> SessionPrompt:
        options = context.get("candidate_options", [])
        buttons: list[tuple[str, str]] = []
        if isinstance(options, list):
            for index, option in enumerate(options):
                if not isinstance(option, dict):
                    continue
                label = str(option.get("label", "Option"))
                buttons.append(
                    (label, _callback_data(session_id, "choose", str(index)))
                )
        self.session_repository.update_session(
            session_id, status=STATUS_AWAITING_ITEM_SELECTION, context=context
        )
        label = _current_item_label(context)
        return SessionPrompt(
            text=f"Select the {label} item:",
            reply_markup=_inline_keyboard(buttons),
        )

    async def _apply_candidate_selection(  # noqa: PLR0911
        self, session_id: UUID, context: dict[str, object], index: int
    ) -> SessionPrompt | None:
        options = context.get("candidate_options", [])
        if not isinstance(options, list) or not (0 <= index < len(options)):
            return None
        option = options[index]
        if not isinstance(option, dict):
            return None
        option_type = str(option.get("type", ""))
        if self.debug:
            _logger.info(
                "Candidate selected: type=%s label=%s",
                option_type,
                option.get("label"),
            )
        if option_type == "manual":
            return self._set_manual_target(session_id, context)
        if option_type == "library":
            _set_item_food(context, option)
            self.session_repository.update_session(
                session_id, status=STATUS_AWAITING_PORTION_CHOICE, context=context
            )
            return _portion_prompt(session_id, context)
        if option_type == "fdc":
            fdc_id = option.get("fdc_id")
            if isinstance(fdc_id, int):
                try:
                    details = await self.nutrition_service.get_food(fdc_id)
                except Exception:
                    _logger.exception("FDC get failed: fdc_id=%s", fdc_id)
                    prompt = self._prompt_item_selection(session_id, context)
                    return SessionPrompt(
                        text=(
                            "USDA lookup timed out. "
                            "Please choose another option or try again.\n\n"
                            f"{prompt.text}"
                        ),
                        reply_markup=prompt.reply_markup,
                    )
                option = dict(option)
                option.update(
                    {
                        "basis": "per100g",
                        "serving_size_g": details.serving_size_g,
                        "calories": details.macros.calories,
                        "protein_g": details.macros.protein_g,
                        "fat_g": details.macros.fat_g,
                        "carbs_g": details.macros.carbs_g,
                        "source_ref": str(fdc_id),
                    }
                )
                _set_item_food(context, option)
                self.session_repository.update_session(
                    session_id, status=STATUS_AWAITING_PORTION_CHOICE, context=context
                )
                return _portion_prompt(session_id, context)
        return None

    def _set_manual_target(
        self, session_id: UUID, context: dict[str, object]
    ) -> SessionPrompt:
        manual = {
            "target": context.get("flow", "photo"),
            "item_index": context.get("current_index"),
        }
        context["manual"] = manual
        self.session_repository.update_session(
            session_id, status=STATUS_AWAITING_MANUAL_NAME, context=context
        )
        label = _current_item_label(context)
        return SessionPrompt(text=f"Enter the name for {label}.")

    def _set_manual_basis(
        self, session_id: UUID, context: dict[str, object], basis: str
    ) -> SessionPrompt:
        manual = dict(context.get("manual", {}))
        manual["basis"] = basis
        context["manual"] = manual
        if basis == "perServing":
            self.session_repository.update_session(
                session_id, status=STATUS_AWAITING_MANUAL_SERVING, context=context
            )
            return SessionPrompt(text="Enter the serving size in grams.")
        self.session_repository.update_session(
            session_id, status=STATUS_AWAITING_MANUAL_MACROS, context=context
        )
        return SessionPrompt(
            text="Enter calories, protein, fat, carbs per 100g (e.g., 200, 10, 5, 30)."
        )

    def _set_manual_store(
        self, session_id: UUID, context: dict[str, object], action: str
    ) -> SessionPrompt:
        store = {
            "store_costco": "costco",
            "store_tj": "trader_joes",
            "store_target": "target",
            "store_other": None,
        }.get(action)
        manual = dict(context.get("manual", {}))
        manual["store"] = store
        context["manual"] = manual
        self.session_repository.update_session(
            session_id, status=STATUS_AWAITING_MANUAL_BASIS, context=context
        )
        name = str(manual.get("name", "item"))
        return _manual_basis_prompt(session_id, name)

    async def _finalize_manual_entry(
        self, session_id: UUID, context: dict[str, object], macros: tuple[float, ...]
    ) -> dict[str, object]:
        manual = dict(context.get("manual", {}))
        name = str(manual.get("name", "item"))
        basis = str(manual.get("basis", "per100g"))
        serving_size = manual.get("serving_size_g")
        food_payload = {
            "type": "manual",
            "name": name,
            "label": name,
            "source_type": "manual",
            "basis": basis,
            "serving_size_g": serving_size,
            "store": manual.get("store"),
            "calories": macros[0],
            "protein_g": macros[1],
            "fat_g": macros[2],
            "carbs_g": macros[3],
        }
        if self.debug:
            _logger.info(
                "Manual entry: name=%s basis=%s calories=%s",
                name,
                basis,
                macros[0],
            )
        if manual.get("target") == "library":
            self.library_service.create_manual_food(
                user_id=_require_user_id(context),
                payload={
                    "name": name,
                    "brand": None,
                    "store": manual.get("store"),
                    "source_type": "manual",
                    "source_ref": None,
                    "basis": basis,
                    "serving_size_g": serving_size,
                    "calories": macros[0],
                    "protein_g": macros[1],
                    "fat_g": macros[2],
                    "carbs_g": macros[3],
                },
            )
            self.session_repository.update_session(
                session_id, status=STATUS_COMPLETED, context=context
            )
            return context

        _set_item_food(context, food_payload)
        self.session_repository.update_session(
            session_id, status=STATUS_AWAITING_PORTION_CHOICE, context=context
        )
        return context

    async def _apply_estimate(
        self, session_id: UUID, context: dict[str, object]
    ) -> SessionPrompt | None:
        item = _current_item(context)
        estimate = _estimate_grams(item)
        if estimate is None:
            self.session_repository.update_session(
                session_id, status=STATUS_AWAITING_MANUAL_GRAMS, context=context
            )
            return SessionPrompt(text="Enter grams for the item.")
        _record_current_grams(context, estimate)
        return await self._advance_or_summarize(session_id, context)

    async def _advance_or_summarize(
        self, session_id: UUID, context: dict[str, object]
    ) -> SessionPrompt:
        context["current_index"] = int(context.get("current_index", 0)) + 1
        items = context.get("items", [])
        if isinstance(items, list) and context["current_index"] < len(items):
            return await self._prompt_item_confirmation(session_id, context)
        return await self._show_summary(session_id, context)

    async def _show_summary(
        self, session_id: UUID, context: dict[str, object]
    ) -> SessionPrompt:
        resolved_items = _build_resolved_items(context)
        context["resolved_items"] = resolved_items
        summary = await self.meal_log_service.compute_summary(resolved_items)
        if self.debug:
            _logger.info(
                "Session summary: items=%s calories=%s",
                len(summary.items),
                summary.total_calories,
            )
        self.session_repository.update_session(
            session_id, status=STATUS_AWAITING_SAVE, context=context
        )
        return SessionPrompt(
            text=_format_summary(summary),
            reply_markup=_inline_keyboard(
                [
                    ("Save", _callback_data(session_id, "save")),
                    ("Edit", _callback_data(session_id, "edit")),
                    ("Cancel", _callback_data(session_id, "cancel")),
                ]
            ),
        )

    async def _ensure_candidates(self, context: dict[str, object]) -> None:
        item = _current_item(context)
        label = _item_label(item)
        user_id = _require_user_id(context)
        library = self.library_service.search(user_id, label, limit=3)
        try:
            fdc = await self.nutrition_service.search(label, limit=3)
        except Exception:
            _logger.exception("FDC search failed: label=%s", label)
            fdc = []
        if self.debug:
            _logger.info(
                "Candidate options: label=%s library=%s fdc=%s",
                label,
                len(library),
                len(fdc),
            )
        context["candidate_options"] = _build_candidate_options(library, fdc)


def _callback_data(session_id: UUID, action: str, payload: str | None = None) -> str:
    """Build callback_data within Telegram's 64-byte limit."""
    if payload is None:
        return f"s:{session_id}:{action}"
    return f"s:{session_id}:{action}:{payload}"


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
    cleaned = text.strip().lower().replace("grams", "").replace("g", "").strip()
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return int(value) if value > 0 else None


def _parse_macros(text: str) -> tuple[float, float, float, float] | None:
    parts = [p for p in text.replace(",", " ").split() if p]
    if len(parts) != MACRO_PARTS:
        return None
    try:
        calories, protein, fat, carbs = (float(p) for p in parts)
    except ValueError:
        return None
    return calories, protein, fat, carbs


def _parse_item_list(text: str) -> list[str]:
    items = [chunk.strip() for chunk in text.split(",")]
    return [item for item in items if item]


def _current_item(context: dict[str, object]) -> dict[str, object]:
    items = context.get("items", [])
    index = int(context.get("current_index", 0))
    if isinstance(items, list) and 0 <= index < len(items):
        item = items[index]
        if isinstance(item, dict):
            return item
    return {}


def _current_item_label(context: dict[str, object]) -> str:
    return _item_label(_current_item(context))


def _item_label(item: dict[str, object]) -> str:
    return str(item.get("label") or item.get("name") or "item")


def _estimate_grams(item: dict[str, object]) -> int | None:
    low = item.get("estimated_grams_low")
    high = item.get("estimated_grams_high")
    if isinstance(low, int | float) and isinstance(high, int | float) and high > 0:
        return round((float(low) + float(high)) / 2)
    if isinstance(low, int | float) and low > 0:
        return round(float(low))
    return None


def _record_current_grams(context: dict[str, object], grams: int) -> None:
    item = _current_item(context)
    item["grams"] = grams


def _mark_skipped(context: dict[str, object]) -> None:
    item = _current_item(context)
    item["skipped"] = True


def _set_item_food(context: dict[str, object], option: dict[str, object]) -> None:
    item = _current_item(context)
    item["food"] = {
        "name": option.get("name") or option.get("label") or "item",
        "source_type": option.get("source_type") or option.get("type"),
        "food_id": option.get("food_id"),
        "source_ref": option.get("source_ref"),
        "basis": option.get("basis") or "per100g",
        "serving_size_g": option.get("serving_size_g"),
        "calories": option.get("calories"),
        "protein_g": option.get("protein_g"),
        "fat_g": option.get("fat_g"),
        "carbs_g": option.get("carbs_g"),
        "brand": option.get("brand"),
        "store": option.get("store"),
    }


def _portion_prompt(session_id: UUID, context: dict[str, object]) -> SessionPrompt:
    item = _current_item(context)
    food = item.get("food") or {}
    name = str(food.get("name") or _item_label(item))
    estimate = _estimate_grams(item)
    buttons: list[tuple[str, str]] = []
    if estimate:
        buttons.append(
            (
                f"Use {estimate}g (est.)",
                _callback_data(session_id, "portion_est"),
            )
        )
    buttons.append(("Enter grams", _callback_data(session_id, "portion_manual")))
    buttons.append(("Skip item", _callback_data(session_id, "portion_skip")))
    return SessionPrompt(
        text=f"How much {name} is there?",
        reply_markup=_inline_keyboard(buttons),
    )


def _manual_basis_prompt(session_id: UUID, name: str) -> SessionPrompt:
    return SessionPrompt(
        text=f"Are the nutrition values for {name} per 100g or per serving?",
        reply_markup=_inline_keyboard(
            [
                ("Per 100g", _callback_data(session_id, "basis_100")),
                ("Per serving", _callback_data(session_id, "basis_serv")),
            ]
        ),
    )


def _manual_store_prompt(session_id: UUID, name: str) -> SessionPrompt:
    return SessionPrompt(
        text=f"Which store is {name} from?",
        reply_markup=_inline_keyboard(
            [
                ("Costco", _callback_data(session_id, "store_costco")),
                ("Trader Joe's", _callback_data(session_id, "store_tj")),
                ("Target", _callback_data(session_id, "store_target")),
                ("Other/Skip", _callback_data(session_id, "store_other")),
            ]
        ),
    )


def _build_candidate_options(
    library: list[LibraryFood], fdc: list[FoodSummary]
) -> list[dict[str, object]]:
    options: list[dict[str, object]] = []
    for food in library:
        options.append(
            {
                "type": "library",
                "label": _format_library_food(food),
                "name": food.name,
                "brand": food.brand,
                "store": food.store,
                "food_id": str(food.id),
                "source_type": "library",
                "source_ref": food.source_ref,
                "basis": food.basis,
                "serving_size_g": food.serving_size_g,
                "calories": food.calories,
                "protein_g": food.protein_g,
                "fat_g": food.fat_g,
                "carbs_g": food.carbs_g,
            }
        )
    for summary in fdc:
        options.append(
            {
                "type": "fdc",
                "label": _format_fdc_food(summary),
                "name": summary.description,
                "fdc_id": summary.fdc_id,
                "source_type": "fdc",
            }
        )
    options.append({"type": "manual", "label": "Enter manually"})
    return options


def _format_library_food(food: LibraryFood) -> str:
    parts = [food.name]
    if food.brand:
        parts.append(str(food.brand))
    if food.store:
        parts.append(str(food.store))
    return " · ".join(parts)


def _format_fdc_food(summary: FoodSummary) -> str:
    brand = summary.brand_owner or summary.brand_name
    if brand:
        return f"{summary.description} · {brand}"
    return summary.description


def _build_resolved_items(context: dict[str, object]) -> list[dict[str, object]]:
    items = context.get("items", [])
    resolved: list[dict[str, object]] = []
    if not isinstance(items, list):
        return resolved
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        if item.get("skipped"):
            continue
        grams = item.get("grams")
        food = item.get("food")
        if not isinstance(food, dict):
            continue
        if grams is None:
            continue
        resolved.append(
            {
                "item_index": idx,
                "name": food.get("name") or item.get("label") or "item",
                "grams": grams,
                "source_type": food.get("source_type"),
                "source_ref": food.get("source_ref"),
                "food_id": food.get("food_id"),
                "basis": food.get("basis"),
                "serving_size_g": food.get("serving_size_g"),
                "calories": food.get("calories"),
                "protein_g": food.get("protein_g"),
                "fat_g": food.get("fat_g"),
                "carbs_g": food.get("carbs_g"),
                "brand": food.get("brand"),
                "store": food.get("store"),
            }
        )
    return resolved


def _format_summary(summary: MealLogSummary) -> str:
    lines = [
        "Summary:",
        f"Total: {summary.total_calories:.0f} kcal, "
        f"{summary.total_protein_g:.1f}P / "
        f"{summary.total_fat_g:.1f}F / "
        f"{summary.total_carbs_g:.1f}C",
        "Items:",
    ]
    for item in summary.items:
        lines.append(
            f"- {item.name}: {item.grams:.0f}g — "
            f"{item.calories:.0f} kcal "
            f"({item.protein_g:.1f}P/{item.fat_g:.1f}F/{item.carbs_g:.1f}C)"
        )
    return "\n".join(lines)


def _edit_choice_prompt(session_id: UUID, context: dict[str, object]) -> SessionPrompt:
    items = context.get("resolved_items", [])
    buttons: list[tuple[str, str]] = []
    if isinstance(items, list):
        for index, item in enumerate(items):
            if isinstance(item, dict):
                name = str(item.get("name", "item"))
                buttons.append(
                    (name, _callback_data(session_id, "edit_item", str(index)))
                )
    return SessionPrompt(
        text="Which item do you want to edit?",
        reply_markup=_inline_keyboard(buttons),
    )


def _apply_edit_grams(context: dict[str, object], grams: int) -> None:
    items = context.get("resolved_items", [])
    index = int(context.get("edit_index", -1))
    if isinstance(items, list) and 0 <= index < len(items):
        item = items[index]
        if isinstance(item, dict):
            item["grams"] = grams
            source_index = item.get("item_index")
            original_items = context.get("items", [])
            if (
                isinstance(source_index, int)
                and isinstance(original_items, list)
                and 0 <= source_index < len(original_items)
            ):
                source_item = original_items[source_index]
                if isinstance(source_item, dict):
                    source_item["grams"] = grams


def _safe_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _edit_item_id(context: dict[str, object], index: int) -> str | None:
    items = context.get("edit_items", [])
    if isinstance(items, list) and 0 <= index < len(items):
        item = items[index]
        if isinstance(item, dict):
            return item.get("id")
    return None


def _edit_item_name(context: dict[str, object], index: int) -> str:
    items = context.get("edit_items", [])
    if isinstance(items, list) and 0 <= index < len(items):
        item = items[index]
        if isinstance(item, dict):
            return str(item.get("name", "item"))
    return "item"


def _edit_item_prompt(session_id: UUID, context: dict[str, object]) -> SessionPrompt:
    buttons: list[tuple[str, str]] = []
    items = context.get("edit_items", [])
    if isinstance(items, list):
        for index, item in enumerate(items):
            if isinstance(item, dict):
                label = str(item.get("name", "item"))
                buttons.append(
                    (label, _callback_data(session_id, "edit_item", str(index)))
                )
    return SessionPrompt(
        text="Which item do you want to edit?",
        reply_markup=_inline_keyboard(buttons),
    )


def _edit_item_snapshot(
    context: dict[str, object], item_id: UUID
) -> dict[str, object] | None:
    items = context.get("edit_items", [])
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("id") == str(item_id):
                return {
                    "name": item.get("name"),
                    "grams": item.get("grams"),
                    "calories": item.get("calories"),
                    "protein_g": item.get("protein_g"),
                    "fat_g": item.get("fat_g"),
                    "carbs_g": item.get("carbs_g"),
                }
    return None


def _detail_item_snapshot(
    detail: MealLogDetail, item_id: UUID
) -> dict[str, object] | None:
    for item in detail.items:
        if item.id == item_id:
            return {
                "name": item.name,
                "grams": item.grams,
                "calories": item.calories,
                "protein_g": item.protein_g,
                "fat_g": item.fat_g,
                "carbs_g": item.carbs_g,
            }
    return None


def _format_meal_detail(detail: MealLogDetail) -> str:
    lines = [
        f"Meal updated: {detail.total_calories:.0f} kcal",
        "Items:",
    ]
    for item in detail.items:
        lines.append(f"- {item.name}: {item.grams:.0f}g — {item.calories:.0f} kcal")
    return "\n".join(lines)


def _require_user_id(context: dict[str, object]) -> UUID:
    user_id = context.get("user_id")
    if isinstance(user_id, UUID):
        return user_id
    if isinstance(user_id, str):
        return UUID(user_id)
    raise ValueError("Missing user_id in session context")
