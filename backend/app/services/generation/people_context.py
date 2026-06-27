from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.immich.models import ImmichAssetSummary

try:
    from global_gender_predictor import GlobalGenderPredictor

    _predictor = GlobalGenderPredictor()
except ImportError:
    _predictor = None


@dataclass(frozen=True)
class PeopleFaceContext:
    id: str | None = None
    person_id: str | None = None
    person_name: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    bounding_box_x1: float | None = None
    bounding_box_y1: float | None = None
    bounding_box_x2: float | None = None
    bounding_box_y2: float | None = None
    source_type: str | None = None

    def position_label(self) -> str | None:
        if (
            self.image_width is None
            or self.image_height is None
            or self.bounding_box_x1 is None
            or self.bounding_box_y1 is None
            or self.bounding_box_x2 is None
            or self.bounding_box_y2 is None
        ):
            return None
        if self.image_width <= 0 or self.image_height <= 0:
            return None

        center_x = ((self.bounding_box_x1 + self.bounding_box_x2) / 2.0) / float(self.image_width)
        center_y = ((self.bounding_box_y1 + self.bounding_box_y2) / 2.0) / float(self.image_height)

        if center_x < 0.33:
            horizontal = "left"
        elif center_x > 0.66:
            horizontal = "right"
        else:
            horizontal = "center"

        if center_y < 0.33:
            vertical = "upper"
        elif center_y > 0.66:
            vertical = "lower"
        else:
            vertical = "middle"

        if horizontal == "center" and vertical == "middle":
            return "center"
        if horizontal == "center":
            return vertical
        if vertical == "middle":
            return horizontal
        return f"{vertical} {horizontal}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "person_id": self.person_id,
            "person_name": self.person_name,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "bounding_box_x1": self.bounding_box_x1,
            "bounding_box_y1": self.bounding_box_y1,
            "bounding_box_x2": self.bounding_box_x2,
            "bounding_box_y2": self.bounding_box_y2,
            "source_type": self.source_type,
            "position_label": self.position_label(),
        }


@dataclass(frozen=True)
class PeopleContext:
    names: list[str] = field(default_factory=list)
    faces: list[PeopleFaceContext] = field(default_factory=list)
    prompt_hint: str = ""

    @property
    def has_faces(self) -> bool:
        return bool(self.faces)

    def to_dict(self) -> dict[str, Any]:
        return {
            "names": self.names,
            "name_count": len(self.names),
            "faces": [face.to_dict() for face in self.faces],
            "face_count": len(self.faces),
            "prompt_hint": self.prompt_hint,
            "has_faces": self.has_faces,
        }

    def anonymized_prompt_hint(self) -> str:
        if not self.names and not self.faces:
            return ""

        name_map = {}
        for i, name in enumerate(self.names):
            gender = infer_gender(name)
            name_map[name] = f"person {i + 1} ({gender})"
        for face in self.faces:
            if face.person_name and face.person_name not in name_map:
                gender = infer_gender(face.person_name)
                name_map[face.person_name] = f"person {len(name_map) + 1} ({gender})"

        name_hint = ""
        if self.names:
            head = [name_map[name] for name in self.names[:5]]
            suffix = f", and {len(self.names) - len(head)} more" if len(self.names) > len(head) else ""
            name_hint = f"Immich identified these people in the source photo: {', '.join(head)}{suffix}."

        face_bits: list[str] = []
        for face in self.faces[:5]:
            label = face.position_label()
            mapped_name = name_map.get(face.person_name) if face.person_name else None
            if mapped_name and label:
                face_bits.append(f"{mapped_name} is in the {label}")
            elif mapped_name:
                face_bits.append(mapped_name)
        face_hint = f" Face positions: {'; '.join(face_bits)}." if face_bits else ""

        return f"{name_hint}{face_hint}".strip()


def _get_attr(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _get_first(source: Any, *keys: str) -> Any:
    for key in keys:
        value = _get_attr(source, key, None)
        if value is not None:
            return value
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _coerce_person_name(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _coerce_face_context(
    item: Any, person_id: str | None = None, person_name: str | None = None
) -> PeopleFaceContext | None:
    face_id = _coerce_person_name(_get_first(item, "id", "faceId"))
    image_width = _coerce_int(_get_first(item, "imageWidth", "image_width"))
    image_height = _coerce_int(_get_first(item, "imageHeight", "image_height"))
    source_type = _coerce_person_name(_get_first(item, "sourceType", "source_type"))

    x1 = _coerce_float(_get_first(item, "boundingBoxX1", "bounding_box_x1"))
    y1 = _coerce_float(_get_first(item, "boundingBoxY1", "bounding_box_y1"))
    x2 = _coerce_float(_get_first(item, "boundingBoxX2", "bounding_box_x2"))
    y2 = _coerce_float(_get_first(item, "boundingBoxY2", "bounding_box_y2"))

    if x1 is None or y1 is None or x2 is None or y2 is None:
        x = _coerce_float(_get_first(item, "x"))
        y = _coerce_float(_get_first(item, "y"))
        width = _coerce_float(_get_first(item, "width"))
        height = _coerce_float(_get_first(item, "height"))
        if None not in (x, y, width, height):
            x1 = x
            y1 = y
            x2 = x + width
            y2 = y + height

    if x1 is None or y1 is None or x2 is None or y2 is None:
        return None

    return PeopleFaceContext(
        id=face_id,
        person_id=person_id,
        person_name=person_name,
        image_width=image_width,
        image_height=image_height,
        bounding_box_x1=x1,
        bounding_box_y1=y1,
        bounding_box_x2=x2,
        bounding_box_y2=y2,
        source_type=source_type,
    )


def _coerce_people_item(item: Any) -> tuple[str | None, list[PeopleFaceContext]]:
    person_id = _coerce_person_name(_get_first(item, "id", "personId", "person_id"))
    name = _coerce_person_name(_get_first(item, "name"))

    faces: list[PeopleFaceContext] = []
    raw_faces = _get_first(item, "faces", "faceList", "face")
    if isinstance(raw_faces, list):
        for face_item in raw_faces:
            if face_item is None:
                continue
            if isinstance(face_item, dict) or hasattr(face_item, "__dict__"):
                face = _coerce_face_context(face_item, person_id=person_id, person_name=name)
                if face is not None:
                    faces.append(face)
    elif isinstance(raw_faces, dict) or hasattr(raw_faces, "__dict__"):
        face = _coerce_face_context(raw_faces, person_id=person_id, person_name=name)
        if face is not None:
            faces.append(face)

    return name, faces


def build_people_context(source: ImmichAssetSummary | Any) -> PeopleContext | None:
    raw_people = _get_first(source, "people", "people_list")
    if not isinstance(raw_people, list):
        return None

    names: list[str] = []
    faces: list[PeopleFaceContext] = []

    for item in raw_people:
        if item is None:
            continue
        if not (isinstance(item, dict) or hasattr(item, "__dict__")):
            continue
        name, person_faces = _coerce_people_item(item)
        if name and name not in names:
            names.append(name)
        for face in person_faces:
            faces.append(face)

    if not names and not faces:
        return None

    name_hint = ""
    if names:
        names_with_gender = [f"{name} ({infer_gender(name)})" for name in names]
        head = names_with_gender[:5]
        suffix = f", and {len(names) - len(head)} more" if len(names) > len(head) else ""
        name_hint = f"Immich identified these people in the source photo: {', '.join(head)}{suffix}."

    face_bits: list[str] = []
    for face in faces[:5]:
        label = face.position_label()
        if face.person_name and label:
            gendered_name = f"{face.person_name} ({infer_gender(face.person_name)})"
            face_bits.append(f"{gendered_name} is in the {label}")
        elif face.person_name:
            gendered_name = f"{face.person_name} ({infer_gender(face.person_name)})"
            face_bits.append(gendered_name)
    face_hint = f" Face positions: {'; '.join(face_bits)}." if face_bits else ""

    prompt_hint = f"{name_hint}{face_hint}".strip()
    return PeopleContext(names=names, faces=faces, prompt_hint=prompt_hint)


async def load_people_context(client: Any, asset: ImmichAssetSummary | Any) -> PeopleContext | None:
    context = build_people_context(asset)
    needs_faces = bool(context and context.names and not context.faces)

    if not needs_faces:
        return context

    get_asset_info = getattr(client, "get_asset_info", None)
    if not callable(get_asset_info):
        return context

    asset_id = _coerce_person_name(_get_first(asset, "id"))
    if not asset_id:
        return context

    try:
        detailed = await get_asset_info(asset_id)
    except Exception:
        return context

    if not isinstance(detailed, dict):
        return context

    detailed_context = build_people_context(detailed)
    if detailed_context and (detailed_context.faces or detailed_context.names):
        return detailed_context

    return context


def infer_gender(name: str) -> str:
    """Infer gender ('male' or 'female') from a person's name/label using global-gender-predictor with a fallback."""
    if not name:
        return "male"

    tokens = name.strip().split()
    if not tokens:
        return "male"
    first_name = tokens[0]
    first_name_lower = first_name.lower()

    # Pre-heuristics: check highly specific familial/explicit terms first,
    # because external predictor may incorrectly classify them based on other languages.
    male_exceptions = {
        "kuba",
        "tata",
        "dziadek",
        "wujek",
        "luca",
        "andrea",
        "barnaba",
        "kosma",
        "bonawentura",
        "mustafa",
    }
    female_terms = {"mama", "babcia", "ciocia", "córka", "zona", "żona", "siostra"}

    if first_name_lower in female_terms:
        return "female"
    if first_name_lower in male_exceptions:
        return "male"

    # Try using global-gender-predictor
    if _predictor is not None:
        try:
            res = _predictor.predict_gender(first_name)
            if res and res.lower() in ("male", "female"):
                return res.lower()
        except Exception:
            pass

    # Post-heuristics fallback (Polish general name rules)
    if first_name_lower.endswith("a"):
        return "female"

    return "male"
