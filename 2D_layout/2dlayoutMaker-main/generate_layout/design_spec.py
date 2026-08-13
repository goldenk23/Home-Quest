"""Canonical DesignSpec: the internal structured-intent contract for AI floor plans.

This is deliberately NOT native VastuCraft v1. It must never be passed to
``LayoutSerializer`` or the web importer. It captures *what the user asked for* (rooms,
zones, relationships, priorities) with **stable semantic IDs** so later planning and
refinement phases reason about intent instead of re-parsing prose or rewriting
coordinates.

Producers
    ``from_program(program)`` maps a stage-1 room program (the compact JSON the model
    already returns today) into a spec deterministically — no NLP, no second parser.

Consumers
    The Tk tab stores the accepted spec beside the accepted native layout, and refinement
    applies bounded semantic operations (``apply_operations``) so a superseded requirement
    ("four bedrooms" then "remove one bedroom") drops out of current truth instead of
    accumulating.

Everything here is pure and offline-testable; run ``python design_spec.py`` for the
self-check that proves supersession, stable IDs, and rejection of oversized/invalid input.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field, replace
from typing import Any

SPEC_VERSION = "1.0"

# DesignSpec zones are the four Vastu quadrants the engine already reasons about. Kept
# separate from the native compass set on purpose: this is intent, not geometry.
ZONES = {"NW", "NE", "SW", "SE"}
#Python set containing every room-to-room relationship the design specification accepts:
RELATIONSHIP_KINDS = {
    "direct_door", "adjacent", "near", "separate",
    "open_plan", "access_through_public", "attached_to",
}
#priority tells the layout engine how strictly it must follow a room requirement or relationship.
PRIORITIES = {"hard", "preferred"}

# Bounds at the trust boundary: untrusted model/user input can never explode the spec.
MAX_ROOMS = 40
MAX_RELATIONSHIPS = 80
MAX_LIST = 200
MAX_NAME_LEN = 120
MAX_TEXT = 500
MAX_PLOT_FT = 1_000

# Name -> semantic type. First matching keyword wins, so "master bathroom" is a bathroom,
# not a bedroom. Extend here (one place) rather than per-caller.
_TYPE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("bathroom", "bathroom"), ("bath", "bathroom"), ("powder", "bathroom"),
    ("toilet", "bathroom"), ("wc", "bathroom"),
    ("bedroom", "bedroom"),
    ("kitchen", "kitchen"),
    ("dining", "dining"),
    ("living", "living"), ("lounge", "living"), ("family", "living"),
    ("foyer", "foyer"), ("entrance", "foyer"), ("lobby", "foyer"),
    ("hall", "corridor"), ("corridor", "corridor"), ("passage", "corridor"),
    ("puja", "puja"), ("pooja", "puja"), ("prayer", "puja"),
    ("office", "office"), ("study", "office"),
    ("utility", "utility"), ("laundry", "utility"),
    ("store", "storage"), ("storage", "storage"), ("pantry", "storage"),
    ("garage", "garage"), ("parking", "garage"),
    ("balcony", "balcony"), ("veranda", "balcony"),
)


def classify_room(name: str) -> str:
    """Return a standard room type based on words in the room name."""
    lowered = str(name or "").lower()
    for keyword, room_type in _TYPE_KEYWORDS:
        if keyword in lowered:
            return room_type
    return "room"


def _slug(value: str) -> str:
    """Turn text into a simple lowercase ID using letters, numbers, and underscores."""
    slug = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    return slug or "room"


def _clamp_int(value: Any, default: int, lo: int, hi: int) -> int:
    """Return a whole number kept between ``lo`` and ``hi``, or the default if invalid."""
    try:
        return max(lo, min(hi, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _clamp_str(value: Any, max_len: int, default: str = "") -> str:
    """Trim text and limit its length, or return the default when it is not text."""
    if not isinstance(value, str):
        return default
    return value.strip()[:max_len]


def _optional_float(value: Any) -> float | None:
    """Return a valid positive decimal number, or ``None`` when the value is unusable."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 2) if 0 < number <= MAX_PLOT_FT * MAX_PLOT_FT else None


def _as_list(value: Any) -> list:
    """Return the value when it is a list; otherwise return an empty list."""
    return value if isinstance(value, list) else []


def _as_str_list(value: Any) -> list[str]:
    """Return the non-empty text items as a list, including a single text value."""
    if isinstance(value, str):
        value = [value]
    return [item for item in _as_list(value) if isinstance(item, str) and item.strip()]


def _coerce_furniture_requirements(value: Any) -> list[dict[str, Any]]:
    """Convert furniture hints into a safe list and ignore unusable entries."""
    if isinstance(value, dict):
        value = [{"room_id": key, "items": items} for key, items in value.items()]
    return [item for item in _as_list(value) if isinstance(item, dict)][:MAX_LIST]


@dataclass
class Room:
    """A requested space. ``id`` is stable; display ``name`` may duplicate freely."""
    id: str
    type: str
    name: str
    role: str | None = None
    zone: str | None = None
    exterior_window: bool = False
    public: bool = False
    entrance: bool = False
    min_width_ft: float | None = None
    min_depth_ft: float | None = None
    target_width_ft: float | None = None
    target_depth_ft: float | None = None
    max_width_ft: float | None = None
    max_depth_ft: float | None = None
    min_area_ft2: float | None = None
    target_area_ft2: float | None = None
    max_area_ft2: float | None = None
    flooring: str | None = None
    accessibility: list[str] = field(default_factory=list)
    priority: str = "preferred"


@dataclass
class Relationship:
    """A required or preferred link between two rooms, addressed by stable ID."""
    id: str
    a: str
    b: str
    kind: str
    priority: str = "preferred"
    source_text: str = ""


@dataclass
class DesignSpec:
    """Store all validated information needed to create one floor plan."""

    version: str = SPEC_VERSION
    project_name: str = "AI Layout"
    plot: dict[str, Any] = field(default_factory=dict)
    building: dict[str, Any] = field(default_factory=dict)
    rooms: list[Room] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    furniture_requirements: list[dict[str, Any]] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    locked_constraints: list[str] = field(default_factory=list)
    traceability: list[dict[str, str]] = field(default_factory=list)

    def room_by_id(self, room_id: str) -> Room | None:
        """Find a room by its ID, or return ``None`` when it does not exist."""
        return next((r for r in self.rooms if r.id == room_id), None)

    def rooms_of_type(self, room_type: str) -> list[Room]:
        """Return every room with the requested type, such as ``bedroom``."""
        return [r for r in self.rooms if r.type == room_type]

    def summary(self) -> str:
        """Return a short sentence describing the plot size and its rooms."""
        parts = []
        for room in self.rooms:
            zone = f"@{room.zone}" if room.zone else ""
            parts.append(f"{room.name}{zone}")
        plot = self.plot
        head = ""
        if plot.get("width_ft") and plot.get("depth_ft"):
            head = f"{plot['width_ft']}x{plot['depth_ft']} ft "
        return f"{head}{len(self.rooms)} spaces: " + ", ".join(parts)


def _unique_id(base: str, taken: set[str]) -> str:
    """Create a room ID that is not already in ``taken`` and record it as used."""
    candidate = f"room_{base}"
    if candidate not in taken:
        taken.add(candidate)
        return candidate
    n = 2
    while f"{candidate}_{n}" in taken:
        n += 1
    result = f"{candidate}_{n}"
    taken.add(result)
    return result


def make_room(name: str, taken: set[str], **overrides: Any) -> Room:
    """Create a clean ``Room`` from its name and any supplied room settings."""
    name = _clamp_str(name, MAX_NAME_LEN, "Room") or "Room"
    requested_id = _slug(overrides.get("id") or name)
    room = Room(
        id=_unique_id(requested_id.removeprefix("room_"), taken),
        type=(_clamp_str(overrides.get("type"), 40) or classify_room(name)).lower(),
        name=name,
    )
    room.role = _clamp_str(overrides.get("role"), 60) or None
    if overrides.get("zone") in ZONES:
        room.zone = overrides["zone"]
    room.exterior_window = bool(overrides.get("exterior_window", overrides.get("window", False)))
    room.public = bool(overrides.get("public", False))
    room.entrance = bool(overrides.get("entrance", False))
    room.min_width_ft = _optional_float(overrides.get("min_width_ft"))
    room.min_depth_ft = _optional_float(overrides.get("min_depth_ft"))
    room.target_width_ft = _optional_float(overrides.get("target_width_ft", overrides.get("min_ft")))
    room.target_depth_ft = _optional_float(overrides.get("target_depth_ft"))
    room.max_width_ft = _optional_float(overrides.get("max_width_ft"))
    room.max_depth_ft = _optional_float(overrides.get("max_depth_ft"))
    room.min_area_ft2 = _optional_float(overrides.get("min_area_ft2"))
    room.target_area_ft2 = _optional_float(overrides.get("target_area_ft2"))
    room.max_area_ft2 = _optional_float(overrides.get("max_area_ft2"))
    room.flooring = _clamp_str(overrides.get("flooring"), 40) or None
    room.accessibility = [
        _clamp_str(item, MAX_TEXT) for item in (overrides.get("accessibility") or [])
        if isinstance(item, str) and item.strip()
    ][:20]
    room.priority = overrides["priority"] if overrides.get("priority") in PRIORITIES else "preferred"
    return room


def from_dict(raw: dict[str, Any]) -> DesignSpec:
    """Convert user or AI dictionary data into a validated DesignSpec.

    Invalid or oversized room and relationship data raises an error instead of being
    ignored. If a room has no ID, one is created from its name. Relationships must refer
    to room IDs.
    """
    if not isinstance(raw, dict):
        raise ValueError("design spec must be an object")
    raw_rooms = raw.get("rooms")
    raw_relationships = raw.get("relationships", [])
    if not isinstance(raw_rooms, list) or not raw_rooms:
        raise ValueError("design spec rooms must be a non-empty array")
    if len(raw_rooms) > MAX_ROOMS:
        raise ValueError(f"design spec has more than {MAX_ROOMS} rooms")
    if not isinstance(raw_relationships, list) or len(raw_relationships) > MAX_RELATIONSHIPS:
        raise ValueError(f"design spec relationships must be an array of at most {MAX_RELATIONSHIPS}")
    if len(str(raw.get("project_name", ""))) > MAX_NAME_LEN:
        raise ValueError(f"project_name exceeds {MAX_NAME_LEN} characters")
    # Auxiliary metadata (assumptions/locked_constraints/traceability/furniture_requirements)
    # is advisory and, for furniture, consumed by a separate stage. It is normalized and
    # clamped rather than validated strictly, so the model's formatting choices for these
    # hints can never sink an otherwise valid structural spec. Rooms, plot, and relationships
    # below remain strict.
    plot = raw.get("plot") if isinstance(raw.get("plot"), dict) else {}
    for key in ("width_ft", "depth_ft"):
        try:
            value = float(plot.get(key))
        except (TypeError, ValueError):
            raise ValueError(f"plot.{key} must be a number") from None
        if not 1 <= value <= MAX_PLOT_FT:
            raise ValueError(f"plot.{key} must be from 1 to {MAX_PLOT_FT}")
    building = raw.get("building") if isinstance(raw.get("building"), dict) else {}
    setbacks = plot.get("setbacks_ft") if isinstance(plot.get("setbacks_ft"), dict) else {}
    spec = DesignSpec(
        version=_clamp_str(raw.get("version"), 10, SPEC_VERSION) or SPEC_VERSION,
        project_name=_clamp_str(raw.get("project_name"), MAX_NAME_LEN, "AI Layout") or "AI Layout",
        plot={
            "width_ft": _clamp_int(plot.get("width_ft"), 40, 1, MAX_PLOT_FT),
            "depth_ft": _clamp_int(plot.get("depth_ft", plot.get("height_ft")), 40, 1, MAX_PLOT_FT),
            "facing": (_clamp_str(plot.get("facing"), 1, "N") or "N").upper(),
            "setbacks_ft": {key: max(0.0, _optional_float(setbacks.get(key)) or 0.0)
                              for key in ("front", "rear", "left", "right")},
        },
        building={
            "floors": _clamp_int(building.get("floors"), 1, 1, 10),
            "footprint": _clamp_str(building.get("footprint"), 40, "rectangular") or "rectangular",
            "strategy_preferences": [_clamp_str(x, 60)
                                     for x in _as_str_list(building.get("strategy_preferences"))][:20],
            "circulation_preference": _clamp_str(building.get("circulation_preference"), 60),
            "privacy_priority": _clamp_str(building.get("privacy_priority"), 20),
        },
        assumptions=[_clamp_str(x, MAX_TEXT) for x in _as_list(raw.get("assumptions"))
                     if isinstance(x, str) and x.strip()][:MAX_LIST],
        locked_constraints=[_clamp_str(x, MAX_NAME_LEN) for x in _as_list(raw.get("locked_constraints"))
                            if isinstance(x, str) and x.strip()][:MAX_LIST],
        traceability=[{
            "source_text": _clamp_str(x.get("source_text"), MAX_TEXT),
            "constraint": _clamp_str(x.get("constraint"), MAX_TEXT),
        } for x in _as_list(raw.get("traceability")) if isinstance(x, dict)][:MAX_LIST],
    )

    taken: set[str] = set()
    source_ids: set[str] = set()
    aliases: dict[str, set[str]] = {}

    def add_alias(alias: Any, room_id: str) -> None:
        """Connect another usable room name or ID to the room's final ID."""
        key = _slug(alias)
        if not key:
            return
        aliases.setdefault(key, set()).add(room_id)
        if key.startswith("room_"):
            aliases.setdefault(key.removeprefix("room_"), set()).add(room_id)
        else:
            aliases.setdefault(f"room_{key}", set()).add(room_id)

    for item in raw_rooms:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            raise ValueError("every room must be an object with a non-empty name")
        if len(item["name"]) > MAX_NAME_LEN:
            raise ValueError(f"room name exceeds {MAX_NAME_LEN} characters")
        for key in (
            "min_width_ft", "min_depth_ft", "target_width_ft", "target_depth_ft",
            "max_width_ft", "max_depth_ft", "min_area_ft2", "target_area_ft2", "max_area_ft2",
        ):
            if key in item and item[key] is not None and _optional_float(item[key]) is None:
                raise ValueError(f"room {item['name']!r} has invalid {key}")
        source_id = _slug(item.get("id")) if item.get("id") else f"room_{_slug(item['name'])}"
        if source_id in source_ids:
            raise ValueError(f"duplicate room id {source_id!r}")
        source_ids.add(source_id)
        room = make_room(item["name"], taken, **{k: v for k, v in item.items() if k != "name"})
        for alias in (source_id, room.id, item["name"]):
            add_alias(alias, room.id)
        spec.rooms.append(room)

    def resolve_endpoint(value: Any, relationship_index: int, side: str) -> str:
        """Find the final room ID used by one end of a relationship."""
        key = _slug(value)
        matches = aliases.get(key, set())
        if not matches:
            raise ValueError(
                f"relationship {relationship_index} endpoint {side}={value!r} does not match any room ID"
            )
        if len(matches) > 1:
            raise ValueError(
                f"relationship {relationship_index} endpoint {side}={value!r} is ambiguous; use an exact room ID"
            )
        return next(iter(matches))

    rel_taken: set[str] = set()
    for index, item in enumerate(raw_relationships, 1):
        if not isinstance(item, dict):
            raise ValueError("every relationship must be an object")
        a = resolve_endpoint(item.get("a"), index, "a")
        b = resolve_endpoint(item.get("b"), index, "b")
        if a == b:
            raise ValueError(
                f"relationship {index} references the same room {a!r} on both endpoints"
            )
        kind = item.get("kind")
        if kind not in RELATIONSHIP_KINDS:
            raise ValueError(f"unsupported relationship kind {kind!r}")
        spec.relationships.append(Relationship(
            id=_unique_id_rel(a, b, rel_taken), a=a, b=b, kind=kind,
            priority=item.get("priority") if item.get("priority") in PRIORITIES else "preferred",
            source_text=_clamp_str(item.get("source_text"), MAX_TEXT),
        ))

    spec.furniture_requirements = _coerce_furniture_requirements(raw.get("furniture_requirements"))
    errors = validate_spec(spec)
    if errors:
        raise ValueError("; ".join(errors[:12]))
    return spec


_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_BRIEF_ROOM_TERMS: dict[str, tuple[str, ...]] = {
    "bedroom": ("bedroom", "bed room"),
    "bathroom": ("bathroom", "bath room", "toilet", "powder room", "wc"),
    "kitchen": ("kitchen",),
    "dining": ("dining",),
    "living": ("living", "lounge", "family room"),
    "foyer": ("foyer", "entrance lobby"),
    "puja": ("puja", "pooja", "prayer room"),
    "office": ("office", "study room"),
    "utility": ("utility", "laundry"),
    "storage": ("storage", "store room", "pantry"),
    "garage": ("garage", "parking"),
    "balcony": ("balcony", "veranda"),
}


def _brief_count(brief: str, room_type: str) -> int | None:
    """Read a room count from text, such as three bedrooms or 3 BHK."""
    terms = _BRIEF_ROOM_TERMS.get(room_type, (room_type,))
    number = rf"(\d+|{'|'.join(_NUMBER_WORDS)})"
    for term in terms:
        match = re.search(rf"\b{number}[\s-]+{re.escape(term)}s?\b", brief)
        if match:
            token = match.group(1)
            return int(token) if token.isdigit() else _NUMBER_WORDS[token]
    if room_type == "bedroom":
        bhk = re.search(r"\b(\d+)\s*bhk\b", brief)
        if bhk:
            return int(bhk.group(1))
    return None


# Negation cues that flip a room mention from a request into an exclusion. A brief that
# says "do not add a garage" or lists excluded rooms must not be read as requesting them.
_NEGATION_CUES = (
    "do not", "don't", "dont", "do n't", "without", "avoid", "exclude", "excluding",
    "never", "not add", "no need", "should not", "shouldn't", "must not",
)


def _positive_clauses(text: str) -> str:
    """Remove sentences that say something should not be included."""
    return " ".join(
        clause for clause in re.split(r"[.\n;:]", text)
        if not any(cue in clause for cue in _NEGATION_CUES)
    )


_DIMENSION_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:ft|feet|foot)?\s*[x\u00d7]\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|foot)?"
)
_PLOT_CUES = ("plot", "lot", "site", "parcel", "land")


def _extract_plot_dimensions(text: str) -> tuple[int, int] | None:
    """Find the plot width and depth in text, or return ``None`` if they are missing."""
    matches = list(_DIMENSION_RE.finditer(text))
    if not matches:
        return None

    def dims(match: re.Match) -> tuple[int, int]:
        """Convert one matched width-and-depth pair into whole numbers."""
        return int(round(float(match.group(1)))), int(round(float(match.group(2))))

    labelled = [
        match for match in matches
        if any(cue in text[max(0, match.start() - 25): match.end() + 25] for cue in _PLOT_CUES)
    ]
    if labelled:
        return dims(labelled[0])
    return dims(max(matches, key=lambda m: float(m.group(1)) * float(m.group(2))))


def align_with_brief(spec: DesignSpec, brief: str, *, initial: bool) -> tuple[list[str], list[str]]:
    """Update a design spec to match clear instructions in the user's written request.

    Returns notes about automatic changes and errors that still need to be fixed.
    """
    text = str(brief or "").lower()
    # Room requests are detected only in non-negated clauses so an exclusion list cannot be
    # misread as requesting the rooms it forbids. Dimensions/facing/zones stay on full text.
    positive = _positive_clauses(text)
    notes: list[str] = []
    errors: list[str] = []

    plot_dims = _extract_plot_dimensions(text)
    if plot_dims:
        width, depth = plot_dims
        if (spec.plot.get("width_ft"), spec.plot.get("depth_ft")) != (width, depth):
            notes.append(f"used explicit plot size {width}x{depth} ft")
        spec.plot["width_ft"], spec.plot["depth_ft"] = width, depth

    facing_match = re.search(r"\b(north|south|east|west)[\s-]*facing\b", text)
    if facing_match:
        spec.plot["facing"] = facing_match.group(1)[0].upper()

    if initial and "setback" not in text:
        setbacks = spec.plot.setdefault("setbacks_ft", {})
        if any(float(setbacks.get(key, 0) or 0) for key in ("front", "rear", "left", "right")):
            notes.append("ignored AI-invented setbacks because the brief did not request them")
        spec.plot["setbacks_ft"] = {key: 0.0 for key in ("front", "rear", "left", "right")}
    if initial and not re.search(r"\b(?:two|2|multi)[\s-]*(?:floor|storey|story)", text):
        spec.building["floors"] = 1

    requested_bedrooms = _brief_count(text, "bedroom")
    if initial:
        explicit_types = {
            room_type for room_type, terms in _BRIEF_ROOM_TERMS.items()
            if any(term in positive for term in terms)
        }
        if re.search(r"\b\d+\s*bhk\b", text):
            explicit_types.update({"bedroom", "living", "kitchen"})
        allowed_types = explicit_types | {"living", "bathroom"}
        removed: list[Room] = []

        for room in spec.rooms:
            if room.type == "room":
                room.type = classify_room(room.name)
        kept: list[Room] = []
        for room in spec.rooms:
            if room.type == "corridor" or room.type not in allowed_types:
                removed.append(room)
            else:
                kept.append(room)
        spec.rooms = kept

        def trim(room_type: str, maximum: int | None) -> None:
            """Keep no more than ``maximum`` rooms of this type."""
            if maximum is None:
                return
            matches = [room for room in spec.rooms if room.type == room_type]
            for room in matches[maximum:]:
                spec.rooms.remove(room)
                removed.append(room)

        # Trimming rules, in order of authority:
        #  1. An explicit number in the brief ("2 bathrooms", "3-bedroom") is enforced exactly.
        #  2. Living/bathroom that the user never mentioned are "assumed" spaces capped at 1,
        #     so an over-eager model can't invent extras (e.g. a 3-bedroom brief with no
        #     bathroom mentioned keeps one assumed bathroom, not three).
        #  3. A type the user DID mention but without a number keeps the model's count — this
        #     is what preserves an explicitly-listed master + common bathroom that a prior
        #     default-to-1 rule silently deleted.
        if requested_bedrooms is not None:
            trim("bedroom", requested_bedrooms)
        for room_type in ("bathroom", "living", "kitchen", "puja", "dining", "foyer",
                          "office", "utility", "storage", "garage", "balcony"):
            count = _brief_count(text, room_type)
            if count is not None:
                trim(room_type, count)
            elif room_type in {"living", "bathroom"} and room_type not in explicit_types:
                trim(room_type, 1)

        removed_ids = {room.id for room in removed}
        if removed_ids:
            spec.relationships = [
                rel for rel in spec.relationships if rel.a not in removed_ids and rel.b not in removed_ids
            ]
            spec.furniture_requirements = [
                item for item in spec.furniture_requirements
                if item.get("room_id") not in removed_ids
            ]
            labels = ", ".join(room.name for room in removed)
            note = f"ignored AI-invented unrequested spaces: {labels}"
            notes.append(note)
            if note not in spec.assumptions:
                spec.assumptions.append(note)

    # Bedroom count is the one room quantity we can extract reliably (word-boundary "N
    # bedrooms" / "NBHK"); enforce it so the model cannot silently over- or under-produce
    # the primary rooms. We deliberately do NOT re-derive other requested rooms from the
    # brief text: the model already interpreted the prose, and substring matching here only
    # manufactures false "brief requests X but the spec has none" failures (e.g. an exclusion
    # list "do not add an office" contains the word "office"). Over-generation is instead
    # bounded by the spec instruction, best-effort pruning below, and feasibility.
    if requested_bedrooms is not None:
        actual = len(spec.rooms_of_type("bedroom"))
        if actual != requested_bedrooms:
            errors.append(f"brief requests exactly {requested_bedrooms} bedrooms; spec has {actual}")

    kitchens = spec.rooms_of_type("kitchen")
    if kitchens and any(term in text for term in ("southeast", "south-east", "south east")):
        kitchens[0].zone, kitchens[0].priority = "SE", "hard"
    pujas = spec.rooms_of_type("puja")
    if pujas and ("vastu" in text or any(term in text for term in ("northeast", "north-east", "north east"))):
        pujas[0].zone, pujas[0].priority = "NE", "hard"

    if kitchens and ("open kitchen" in text or "open-plan kitchen" in text or "open plan kitchen" in text):
        living = next(iter(spec.rooms_of_type("living")), None)
        if living and not any({rel.a, rel.b} == {kitchens[0].id, living.id} for rel in spec.relationships):
            taken = {rel.id for rel in spec.relationships}
            spec.relationships.append(Relationship(
                id=_unique_id_rel(kitchens[0].id, living.id, taken),
                a=kitchens[0].id, b=living.id, kind="open_plan", priority="hard",
                source_text="open kitchen",
            ))

    entrances = [room for room in spec.rooms if room.entrance]
    if len(entrances) != 1:
        for room in spec.rooms:
            room.entrance = False
        entrance = next(iter(spec.rooms_of_type("living")), None) or next(
            (room for room in spec.rooms if room.public), None
        ) or (spec.rooms[0] if spec.rooms else None)
        if entrance:
            entrance.entrance = True
            entrance.public = True
            notes.append(f"used {entrance.name} as the {spec.plot.get('facing', 'N')}-facing entrance")

    for note in notes:
        if note not in spec.assumptions:
            spec.assumptions.append(note)
    errors.extend(validate_spec(spec))
    return notes, errors


def to_dict(spec: DesignSpec) -> dict[str, Any]:
    """Convert a ``DesignSpec`` into a dictionary that can be saved as JSON."""
    from dataclasses import asdict
    return asdict(spec)


def from_program(program: dict[str, Any]) -> DesignSpec:
    """Convert the older room-program format into the standard ``DesignSpec`` format."""
    if not isinstance(program, dict):
        program = {}
    taken: set[str] = set()
    spec = DesignSpec(
        project_name=_clamp_str(program.get("project_name"), MAX_NAME_LEN, "AI Layout") or "AI Layout",
    )
    plot = program.get("plot") if isinstance(program.get("plot"), dict) else {}
    spec.plot = {
        "width_ft": _clamp_int(plot.get("width_ft"), 40, 1, MAX_PLOT_FT),
        "depth_ft": _clamp_int(plot.get("height_ft", plot.get("depth_ft")), 40, 1, MAX_PLOT_FT),
        "facing": _clamp_str(program.get("facing"), 2) or "N",
    }

    by_name: dict[str, Room] = {}
    rows = program.get("rows") if isinstance(program.get("rows"), dict) else {}
    for band in ("top", "bottom"):
        for raw in list(rows.get(band, []))[:MAX_ROOMS]:
            if not isinstance(raw, dict) or not raw.get("name"):
                continue
            room = make_room(raw["name"], taken, **{k: v for k, v in raw.items() if k != "name"})
            spec.rooms.append(room)
            by_name.setdefault(str(raw["name"]), room)
            if len(spec.rooms) >= MAX_ROOMS:
                break

    corridor_name = _clamp_str(program.get("corridor_name"), MAX_NAME_LEN)
    if corridor_name and len(spec.rooms) < MAX_ROOMS:
        corridor = make_room(corridor_name, taken, type="corridor", public=True)
        spec.rooms.append(corridor)
        by_name.setdefault(corridor_name, corridor)

    rel_taken: set[str] = set()
    for pair in list(program.get("doors", []))[:MAX_RELATIONSHIPS]:
        if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
            continue
        a, b = by_name.get(str(pair[0])), by_name.get(str(pair[1]))
        if a is None or b is None or a.id == b.id:
            continue
        rid = _unique_id_rel(a.id, b.id, rel_taken)
        spec.relationships.append(Relationship(id=rid, a=a.id, b=b.id, kind="direct_door", priority="hard"))
    return spec


def _unique_id_rel(a: str, b: str, taken: set[str]) -> str:
    """Create an unused ID for a relationship between two rooms."""
    base = f"rel_{a}__{b}"
    if base not in taken:
        taken.add(base)
        return base
    n = 2
    while f"{base}_{n}" in taken:
        n += 1
    result = f"{base}_{n}"
    taken.add(result)
    return result


def validate_spec(spec: DesignSpec) -> list[str]:
    """Check a design spec and return a list of problems; an empty list means it is valid."""
    errors: list[str] = []
    if spec.version != SPEC_VERSION:
        errors.append(f'version must be "{SPEC_VERSION}"')
    if not spec.project_name:
        errors.append("project_name is required")
    if len(spec.rooms) == 0:
        errors.append("spec must contain at least one room")
    if len(spec.rooms) > MAX_ROOMS:
        errors.append(f"spec has more than {MAX_ROOMS} rooms")
    if len(spec.relationships) > MAX_RELATIONSHIPS:
        errors.append(f"spec has more than {MAX_RELATIONSHIPS} relationships")

    for key in ("width_ft", "depth_ft"):
        value = spec.plot.get(key)
        if not isinstance(value, int) or value < 1 or value > MAX_PLOT_FT:
            errors.append(f"plot.{key} must be an integer from 1 to {MAX_PLOT_FT}")
    if spec.plot.get("facing") not in {"N", "S", "E", "W"}:
        errors.append("plot.facing must be N, S, E, or W")
    known_strategies = {"recursive_subdivision", "open_living_core", "side_corridor",
                        "zoned_wings", "constraint_solver"}
    unknown_strategies = set(spec.building.get("strategy_preferences") or []) - known_strategies
    if unknown_strategies:
        errors.append(f"unknown strategy preferences: {sorted(unknown_strategies)}")

    ids: set[str] = set()
    for room in spec.rooms:
        if not room.id or room.id in ids:
            errors.append(f"room id {room.id!r} must be unique and non-empty")
        ids.add(room.id)
        if len(room.name) > MAX_NAME_LEN:
            errors.append(f"room {room.id} name exceeds {MAX_NAME_LEN} characters")
        if room.zone is not None and room.zone not in ZONES:
            errors.append(f"room {room.id} zone {room.zone!r} is not one of {sorted(ZONES)}")
        if room.priority not in PRIORITIES:
            errors.append(f"room {room.id} priority must be hard or preferred")
        for low, target, high, label in (
            (room.min_width_ft, room.target_width_ft, room.max_width_ft, "width"),
            (room.min_depth_ft, room.target_depth_ft, room.max_depth_ft, "depth"),
            (room.min_area_ft2, room.target_area_ft2, room.max_area_ft2, "area"),
        ):
            values = [value for value in (low, target, high) if value is not None]
            if any(value <= 0 for value in values):
                errors.append(f"room {room.id} {label} values must be positive")
            if low is not None and target is not None and low > target:
                errors.append(f"room {room.id} minimum {label} exceeds target")
            if target is not None and high is not None and target > high:
                errors.append(f"room {room.id} target {label} exceeds maximum")
            if low is not None and high is not None and low > high:
                errors.append(f"room {room.id} minimum {label} exceeds maximum")

    entrances = [r for r in spec.rooms if r.entrance]
    if len(entrances) > 1:
        errors.append("at most one room may be the entrance")

    rel_ids: set[str] = set()
    for rel in spec.relationships:
        if not rel.id or rel.id in rel_ids:
            errors.append(f"relationship id {rel.id!r} must be unique and non-empty")
        rel_ids.add(rel.id)
        if rel.kind not in RELATIONSHIP_KINDS:
            errors.append(f"relationship {rel.id} kind {rel.kind!r} is unsupported")
        if rel.priority not in PRIORITIES:
            errors.append(f"relationship {rel.id} priority must be hard or preferred")
        if rel.a not in ids or rel.b not in ids:
            errors.append(f"relationship {rel.id} references a room that does not exist")
    return errors


# --------------------------------------------------------------------------- operations
# Bounded semantic edits used by spec-based refinement. Each returns a RequirementResult so
# the UI can show what actually changed instead of silently mutating intent.

def apply_operations(spec: DesignSpec, operations: list[dict[str, Any]]) -> tuple[DesignSpec, list[dict[str, Any]]]:
    """Apply requested changes to a copy of the spec and report what happened.

    The original spec is not changed, and locked rooms or rules stay protected.
    """
    working = copy.deepcopy(spec)
    taken = {r.id for r in working.rooms}
    rel_taken = {r.id for r in working.relationships}
    results: list[dict[str, Any]] = []

    for op in operations[:MAX_LIST]:
        if not isinstance(op, dict):
            results.append({"op": op, "status": "rejected", "evidence": "operation must be an object"})
            continue
        kind = op.get("op")
        try:
            status, evidence = _apply_one(working, op, taken, rel_taken)
        except Exception as exc:  # noqa: BLE001 - one bad op must not abort the batch
            status, evidence = "rejected", f"{type(exc).__name__}: {exc}"
        results.append({"op": kind, "status": status, "evidence": evidence})
    return working, results


def _locked(working: DesignSpec, room_id: str) -> bool:
    """Return whether a room is protected from removal."""
    return room_id in working.locked_constraints


def _apply_one(working: DesignSpec, op: dict[str, Any], taken: set[str], rel_taken: set[str]) -> tuple[str, str]:
    """Apply one requested change and return its status with a short explanation."""
    kind = op.get("op")

    if kind == "add_room":
        if len(working.rooms) >= MAX_ROOMS:
            return "rejected", f"room limit {MAX_ROOMS} reached"
        room = make_room(op.get("name", "Room"), taken, **{k: v for k, v in op.items() if k != "name"})
        working.rooms.append(room)
        return "applied", f"added {room.name} ({room.id})"

    if kind == "remove_room":
        room = _resolve_room(working, op)
        if room is None:
            return "no_op", "no matching room to remove"
        if _locked(working, room.id):
            return "rejected", f"{room.id} is locked"
        working.rooms = [r for r in working.rooms if r.id != room.id]
        working.relationships = [x for x in working.relationships if room.id not in (x.a, x.b)]
        return "applied", f"removed {room.name} ({room.id})"

    if kind == "set_count":
        room_type = str(op.get("type", "")).lower()
        want = _clamp_int(op.get("count"), 0, 0, MAX_ROOMS)
        current = working.rooms_of_type(room_type)
        if len(current) == want:
            return "no_op", f"already {want} {room_type}(s)"
        if len(current) > want:
            # Remove extras, newest first, but never a locked room.
            removable = [r for r in reversed(current) if not _locked(working, r.id)]
            drop = removable[: len(current) - want]
            drop_ids = {r.id for r in drop}
            working.rooms = [r for r in working.rooms if r.id not in drop_ids]
            working.relationships = [x for x in working.relationships if not (drop_ids & {x.a, x.b})]
            return "applied", f"reduced {room_type} from {len(current)} to {len(working.rooms_of_type(room_type))}"
        for i in range(want - len(current)):
            if len(working.rooms) >= MAX_ROOMS:
                break
            label = room_type.capitalize() if room_type else "Room"
            working.rooms.append(make_room(f"{label} {len(current) + i + 1}", taken, type=room_type))
        return "applied", f"increased {room_type} to {len(working.rooms_of_type(room_type))}"

    if kind == "set_zone":
        room = _resolve_room(working, op)
        if room is None:
            return "no_op", "no matching room"
        zone = op.get("zone")
        if zone is not None and zone not in ZONES:
            return "rejected", f"zone {zone!r} invalid"
        room.zone = zone
        return "applied", f"{room.id} zone set to {zone}"

    if kind == "resize_target":
        room = _resolve_room(working, op)
        if room is None:
            return "no_op", "no matching room"
        room.target_width_ft = _clamp_int(op.get("width_ft"), room.target_width_ft or 8, 1, MAX_PLOT_FT)
        return "applied", f"{room.id} target width {room.target_width_ft} ft"

    if kind == "set_relationship":
        a = _resolve_room(working, {"id": op.get("a")}) or _resolve_room(working, {"name": op.get("a")})
        b = _resolve_room(working, {"id": op.get("b")}) or _resolve_room(working, {"name": op.get("b")})
        rel_kind = op.get("kind")
        if a is None or b is None or a.id == b.id:
            return "rejected", "both rooms must exist and differ"
        if rel_kind not in RELATIONSHIP_KINDS:
            return "rejected", f"kind {rel_kind!r} unsupported"
        priority = op.get("priority") if op.get("priority") in PRIORITIES else "preferred"
        rid = _unique_id_rel(a.id, b.id, rel_taken)
        working.relationships.append(Relationship(id=rid, a=a.id, b=b.id, kind=rel_kind, priority=priority))
        return "applied", f"{a.id} {rel_kind} {b.id}"

    if kind == "set_strategy_preference":
        value = _clamp_str(op.get("value"), 60)
        if not value:
            return "rejected", "value required"
        prefs = working.building.setdefault("strategy_preferences", [])
        if value not in prefs and len(prefs) < 20:
            prefs.append(value)
        return "applied", f"strategy preference {value}"

    if kind == "set_furniture_requirement":
        room = _resolve_room(working, op)
        items = [i for i in (op.get("items") or []) if isinstance(i, str)][:50]
        if room is None or not items:
            return "rejected", "room and items required"
        working.furniture_requirements.append({"room_id": room.id, "items": items})
        return "applied", f"{len(items)} items for {room.id}"

    if kind == "lock":
        target = _clamp_str(op.get("constraint"), MAX_NAME_LEN)
        if target and target not in working.locked_constraints and len(working.locked_constraints) < MAX_LIST:
            working.locked_constraints.append(target)
        return "applied", f"locked {target}"

    if kind == "unlock":
        target = _clamp_str(op.get("constraint"), MAX_NAME_LEN)
        working.locked_constraints = [c for c in working.locked_constraints if c != target]
        return "applied", f"unlocked {target}"

    return "rejected", f"unknown operation {kind!r}"


def _resolve_room(working: DesignSpec, op: dict[str, Any]) -> Room | None:
    """Find the room named in an operation by ID first, then by its display name."""
    if op.get("id"):
        room = working.room_by_id(str(op["id"]))
        if room is not None:
            return room
    name = op.get("name")
    if name:
        lowered = str(name).lower()
        return next((r for r in working.rooms if r.name.lower() == lowered), None)
    return None


if __name__ == "__main__":
    # ponytail: the one runnable guard — proves the Phase 1 acceptance criteria offline.
    canonical = {
        "project_name": "Spec Self Check",
        "plot": {"width_ft": 60, "height_ft": 80},
        "rows": {
            "top": [
                {"name": "Guest Bedroom", "zone": "NW", "window": True, "min_ft": 12},
                {"name": "Foyer", "public": True, "entrance": True, "min_ft": 8},
                {"name": "Bedroom", "window": True, "min_ft": 12},
                {"name": "Bedroom", "window": True, "min_ft": 12},
                {"name": "Puja Room", "zone": "NE", "min_ft": 8},
            ],
            "bottom": [
                {"name": "Master Bedroom", "zone": "SW", "window": True, "min_ft": 12},
                {"name": "Master Bathroom", "window": True, "min_ft": 6},
                {"name": "Kitchen", "zone": "SE", "window": True, "min_ft": 10},
            ],
        },
        "doors": [["Master Bedroom", "Master Bathroom"]],
    }

    spec = from_program(canonical)
    assert validate_spec(spec) == [], validate_spec(spec)

    # Stable IDs: two rooms literally named "Bedroom" get distinct references.
    bedrooms = [r for r in spec.rooms if r.name == "Bedroom"]
    assert len(bedrooms) == 2 and bedrooms[0].id != bedrooms[1].id, "duplicate names need distinct IDs"

    # Master Bathroom is a bathroom, not a bedroom, despite containing "master".
    assert classify_room("Master Bathroom") == "bathroom"
    assert classify_room("Master Bedroom") == "bedroom"

    # Relationship references survive duplicate display names (they use IDs).
    assert spec.relationships and spec.relationships[0].kind == "direct_door"

    # Supersession: "four bedrooms" then "remove one bedroom" -> exactly three.
    baseline_bedrooms = len(spec.rooms_of_type("bedroom"))
    assert baseline_bedrooms == 4, baseline_bedrooms
    four, _ = apply_operations(spec, [{"op": "set_count", "type": "bedroom", "count": 4}])
    assert len(four.rooms_of_type("bedroom")) == 4, four.rooms_of_type("bedroom")
    three, results = apply_operations(four, [{"op": "set_count", "type": "bedroom", "count": 3}])
    assert len(three.rooms_of_type("bedroom")) == 3, three.rooms_of_type("bedroom")
    assert results[0]["status"] == "applied"
    # The superseded requirement is gone from current truth; the input spec is untouched.
    assert len(spec.rooms_of_type("bedroom")) == baseline_bedrooms, "apply_operations must not mutate the input spec"

    # Locked rooms are never removed by a count reduction.
    locked = copy.deepcopy(four)
    locked.locked_constraints.append(four.rooms_of_type("bedroom")[-1].id)
    reduced, _ = apply_operations(locked, [{"op": "set_count", "type": "bedroom", "count": 1}])
    assert four.rooms_of_type("bedroom")[-1].id in {r.id for r in reduced.rooms}, "locked room survived"

    # Trust boundary: oversized/invalid input is rejected, not silently accepted.
    too_many = DesignSpec(rooms=[make_room(f"R{i}", set()) for i in range(MAX_ROOMS + 5)])
    assert any("more than" in e for e in validate_spec(too_many))
    bad_zone = from_program(canonical)
    bad_zone.rooms[0].zone = "XX"
    assert any("zone" in e for e in validate_spec(bad_zone))
    dangling = from_program(canonical)
    dangling.relationships.append(Relationship(id="rel_x", a="room_ghost", b="room_none", kind="adjacent"))
    assert any("does not exist" in e for e in validate_spec(dangling))

    # Verbose advisory output must not sink a valid structural spec: an over-long
    # furniture_requirements list is clamped to MAX_LIST, not rejected.
    flooded = {
        "project_name": "Flood Check", "version": SPEC_VERSION,
        "plot": {"width_ft": 40, "depth_ft": 60},
        "rooms": [{"name": "Living Room"}, {"name": "Kitchen"}],
        "furniture_requirements": [{"room_id": "room_living_room", "items": ["sofa"]}] * (MAX_LIST + 50),
    }
    flooded_spec = from_dict(flooded)
    assert len(flooded_spec.furniture_requirements) == MAX_LIST, len(flooded_spec.furniture_requirements)
    # An object-keyed furniture_requirements (a common model deviation) is coerced to a list
    # of {room_id, items} rather than aborting the structural spec.
    object_shaped = from_dict({**flooded, "furniture_requirements": {
        "room_living_room": ["sofa", "tv_unit"], "room_kitchen": ["stove"]}})
    assert len(object_shaped.furniture_requirements) == 2, object_shaped.furniture_requirements
    assert {r["room_id"] for r in object_shaped.furniture_requirements} == {"room_living_room", "room_kitchen"}
    # A scalar/garbage value is ignored (empty), never fatal.
    assert from_dict({**flooded, "furniture_requirements": "nonsense"}).furniture_requirements == []

    # Alignment must never manufacture "brief requests X but the spec has none" failures
    # from brief text — including a multi-line "do not add" exclusion list, which is exactly
    # the phrasing that broke generation. Only the reliable bedroom-count contract is enforced.
    exclusion_brief = (
        "Create a north-facing 50x70 ft home with 3 bedrooms, a living room, a kitchen in "
        "the southeast, and a puja room in the northeast.\n"
        "Do not add\nDining room\nFoyer\nUtility room\nStorage room\nOffice\nBalcony\nGarage"
    )
    aligned = from_dict({
        "project_name": "Exclusion Check", "version": SPEC_VERSION,
        "plot": {"width_ft": 50, "depth_ft": 70, "facing": "N"},
        "rooms": [
            {"name": "Master Bedroom"}, {"name": "Bedroom 2"}, {"name": "Bedroom 3"},
            {"name": "Living Room"}, {"name": "Kitchen"}, {"name": "Puja Room"},
        ],
    })
    _, exclusion_errors = align_with_brief(aligned, exclusion_brief, initial=True)
    assert exclusion_errors == [], exclusion_errors
    # The reliable bedroom-count contract still holds: extra bedrooms are pruned to the
    # requested count, and too few (which pruning cannot fix) is reported.
    over = from_dict({
        "project_name": "Bedroom Over", "version": SPEC_VERSION,
        "plot": {"width_ft": 50, "depth_ft": 70, "facing": "N"},
        "rooms": [{"name": f"Bedroom {i}"} for i in range(1, 6)] + [{"name": "Kitchen"}],
    })
    align_with_brief(over, "50x70 ft home with 3 bedrooms and a kitchen", initial=True)
    assert len(over.rooms_of_type("bedroom")) == 3, over.rooms_of_type("bedroom")
    under = from_dict({
        "project_name": "Bedroom Under", "version": SPEC_VERSION,
        "plot": {"width_ft": 50, "depth_ft": 70, "facing": "N"},
        "rooms": [{"name": "Bedroom 1"}, {"name": "Bedroom 2"}, {"name": "Kitchen"}],
    })
    _, count_errors = align_with_brief(under, "50x70 ft home with 3 bedrooms and a kitchen", initial=True)
    assert any("3 bedrooms" in e for e in count_errors), count_errors

    # Plot dimensions must never latch onto a room size. A brief that lists the plot plus many
    # smaller room sizes (including a 6x7 puja) must resolve the plot, not the last room read.
    assert _extract_plot_dimensions(
        "north-facing 52 ft x 76 ft rectangular plot. master bedroom 14x15 ft. puja 6x7 ft."
    ) == (52, 76)
    # Even without a "plot" keyword, the largest pair wins over room sizes.
    assert _extract_plot_dimensions("home with a 11x12 bedroom, a 6x7 bath, and a 40x60 area") == (40, 60)
    dim_spec = from_dict({
        "project_name": "Dim Check", "version": SPEC_VERSION,
        "plot": {"width_ft": 6, "depth_ft": 7},  # model mistakenly used the puja room size
        "rooms": [{"name": "Master Bedroom"}, {"name": "Puja Room"}, {"name": "Kitchen"}],
    })
    align_with_brief(dim_spec, "52 ft x 76 ft plot with a master bedroom, kitchen, and a 6x7 ft puja room", initial=True)
    assert (dim_spec.plot["width_ft"], dim_spec.plot["depth_ft"]) == (52, 76), dim_spec.plot

    # strategy_preferences returned as a bare string must not be split into characters.
    pref_spec = from_dict({
        "project_name": "Pref Check", "version": SPEC_VERSION,
        "plot": {"width_ft": 40, "depth_ft": 60},
        "building": {"strategy_preferences": "open_living_core"},
        "rooms": [{"name": "Living Room"}, {"name": "Kitchen"}],
    })
    assert pref_spec.building["strategy_preferences"] == ["open_living_core"], pref_spec.building
    assert validate_spec(pref_spec) == [], validate_spec(pref_spec)

    # Explicitly-listed rooms must not be trimmed away just because the brief states no count.
    # Two distinct bathrooms named in prose (but no "2 bathrooms" phrase) must both survive.
    two_bath = from_dict({
        "project_name": "Two Bath", "version": SPEC_VERSION,
        "plot": {"width_ft": 52, "depth_ft": 76, "facing": "N"},
        "rooms": [
            {"name": "Master Bedroom"}, {"name": "Living Room"}, {"name": "Kitchen"},
            {"name": "Master Bathroom"}, {"name": "Common Bathroom"},
        ],
    })
    align_with_brief(
        two_bath,
        "52x76 ft home with a master bedroom, living room, kitchen, a master bathroom, and a common bathroom",
        initial=True,
    )
    assert len(two_bath.rooms_of_type("bathroom")) == 2, two_bath.rooms_of_type("bathroom")
    # An explicit count is still honored: "2 bathrooms" trims a spec that has 3.
    three_bath = from_dict({
        "project_name": "Three Bath", "version": SPEC_VERSION,
        "plot": {"width_ft": 52, "depth_ft": 76, "facing": "N"},
        "rooms": [
            {"name": "Living Room"},
            {"name": "Bathroom 1"}, {"name": "Bathroom 2"}, {"name": "Bathroom 3"},
        ],
    })
    align_with_brief(three_bath, "52x76 ft home with a living room and 2 bathrooms", initial=True)
    assert len(three_bath.rooms_of_type("bathroom")) == 2, three_bath.rooms_of_type("bathroom")

    print("design_spec self-check passed:", spec.summary())
