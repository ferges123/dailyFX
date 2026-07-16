from __future__ import annotations

from importlib import import_module

_LOCAL_MODULE_SPECS = (
    ("apple_weather", "AppleWeatherModule"),
    ("instaweather", "InstaWeatherModule"),
    ("museum_archive", "MuseumArchiveModule"),
    ("bokeh_blur", "BokehBlurModule"),
    ("vintage_film", "VintageFilmModule"),
    ("huji", "HujiModule"),
    ("collage", "CollageModule"),
    ("instafilter", "InstafilterModule"),
    ("filmstrip", "FilmstripModule"),
    ("popart", "PopArtModule"),
    ("duotone", "DuotoneModule"),
    ("halftone", "HalftoneModule"),
    ("glitch", "GlitchModule"),
    ("light_leak", "LightLeakModule"),
    ("neon_bloom", "NeonBloomModule"),
    ("cyanotype", "CyanotypeModule"),
    ("polaroid", "PolaroidModule"),
    ("prism_split", "PrismSplitModule"),
    ("paper_cutout", "PaperCutoutModule"),
    ("pencil_sketch", "PencilSketchModule"),
    ("cartoon", "CartoonModule"),
    ("hdr", "HDRModule"),
    ("aerochrome", "AerochromeModule"),
)


def _load_local_module_classes() -> list[type]:
    """Load effect implementations only when the registry is first used."""
    return [
        getattr(import_module(f"{__name__}.{module_name}"), class_name)
        for module_name, class_name in _LOCAL_MODULE_SPECS
    ]


LOCAL_MODULE_GROUPS = {
    "apple_weather": "Portrait",
    "instaweather": "Portrait",
    "museum_archive": "Poster",
    "bokeh_blur": "Portrait",
    "vintage_film": "Photography",
    "huji": "Photography",
    "collage": "Poster",
    "instafilter": "Photography",
    "filmstrip": "Photography",
    "popart": "Artistic",
    "duotone": "Artistic",
    "halftone": "Artistic",
    "glitch": "Artistic",
    "light_leak": "Photography",
    "neon_bloom": "Artistic",
    "cyanotype": "Photography",
    "polaroid": "Photography",
    "prism_split": "Photography",
    "paper_cutout": "Artistic",
    "pencil_sketch": "Artistic",
    "cartoon": "Illustration",
    "hdr": "Photography",
    "aerochrome": "Photography",
}


class GenerationModuleRegistry:
    def __init__(self) -> None:
        self._modules: dict[str, object] | None = None

    def _build(self) -> dict[str, object]:
        modules: dict[str, object] = {
            module_class.name: module_class() for module_class in _load_local_module_classes()
        }
        from sqlalchemy.exc import OperationalError, ProgrammingError

        from app.services.generation.ai_effects_builder import build_ai_module
        from app.services.generation.ai_effects_repository import list_ai_effect_rows

        try:
            rows = list_ai_effect_rows()
            ai_modules = {row.id: build_ai_module(row) for row in rows}
            modules.update(ai_modules)
        except (OperationalError, ProgrammingError):
            pass
        return modules

    def _ensure(self) -> dict[str, object]:
        if self._modules is None:
            self._modules = self._build()
        return self._modules

    def refresh(self) -> dict[str, object]:
        self._modules = self._build()
        return self._modules

    def invalidate(self) -> None:
        self._modules = None

    def get(self, key: str, default: object | None = None) -> object | None:
        return self._ensure().get(key, default)

    def items(self):
        return self._ensure().items()

    def values(self):
        return self._ensure().values()

    def keys(self):
        return self._ensure().keys()

    def __contains__(self, key: object) -> bool:
        return key in self._ensure()

    def __getitem__(self, key: str):
        return self._ensure()[key]

    def __iter__(self):
        return iter(self._ensure())

    def __len__(self) -> int:
        return len(self._ensure())


MODULES = GenerationModuleRegistry()
