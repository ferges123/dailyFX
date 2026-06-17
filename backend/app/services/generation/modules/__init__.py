from __future__ import annotations

from app.schemas.generation import GenerationModuleResponse
from app.services.generation.modules.aerochrome import AerochromeModule
from app.services.generation.modules.apple_weather import AppleWeatherModule
from app.services.generation.modules.base import ModuleDefinition
from app.services.generation.modules.bokeh_blur import BokehBlurModule
from app.services.generation.modules.cartoon import CartoonModule
from app.services.generation.modules.collage import CollageModule
from app.services.generation.modules.cyanotype import CyanotypeModule
from app.services.generation.modules.duotone import DuotoneModule
from app.services.generation.modules.filmstrip import FilmstripModule
from app.services.generation.modules.glitch import GlitchModule
from app.services.generation.modules.halftone import HalftoneModule
from app.services.generation.modules.hdr import HDRModule
from app.services.generation.modules.huji import HujiModule
from app.services.generation.modules.instafilter import InstafilterModule
from app.services.generation.modules.instaweather import InstaWeatherModule
from app.services.generation.modules.light_leak import LightLeakModule
from app.services.generation.modules.museum_archive import MuseumArchiveModule
from app.services.generation.modules.neon_bloom import NeonBloomModule
from app.services.generation.modules.paper_cutout import PaperCutoutModule
from app.services.generation.modules.pencil_sketch import PencilSketchModule
from app.services.generation.modules.polaroid import PolaroidModule
from app.services.generation.modules.popart import PopArtModule
from app.services.generation.modules.prism_split import PrismSplitModule
from app.services.generation.modules.vintage_film import VintageFilmModule

LOCAL_MODULE_CLASSES = [
    AppleWeatherModule,
    InstaWeatherModule,
    MuseumArchiveModule,
    BokehBlurModule,
    VintageFilmModule,
    HujiModule,
    CollageModule,
    InstafilterModule,
    FilmstripModule,
    PopArtModule,
    DuotoneModule,
    HalftoneModule,
    GlitchModule,
    LightLeakModule,
    NeonBloomModule,
    CyanotypeModule,
    PolaroidModule,
    PrismSplitModule,
    PaperCutoutModule,
    PencilSketchModule,
    CartoonModule,
    HDRModule,
    AerochromeModule,
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
        modules: dict[str, object] = {module_class.name: module_class() for module_class in LOCAL_MODULE_CLASSES}
        from app.services.generation.ai_effects_builder import build_ai_module
        from app.services.generation.ai_effects_repository import list_ai_effect_rows

        rows = list_ai_effect_rows()
        ai_modules = {row.id: build_ai_module(row) for row in rows}
        modules.update(ai_modules)
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


def list_module_definitions() -> list[ModuleDefinition]:
    return [
        ModuleDefinition(
            name=module.name,
            label=module.label,
            description=module.description,
            default_weight=module.default_weight,
            default_config=module.default_config or {},
            config_schema=getattr(module, "config_schema", None) or [],
        )
        for module in MODULES.values()
    ]


def list_generation_module_responses() -> list[GenerationModuleResponse]:
    return [
        GenerationModuleResponse(
            name=module.name,
            label=module.label,
            description=module.description,
            default_weight=module.default_weight,
            default_config=module.default_config or {},
            config_schema=getattr(module, "config_schema", None) or [],
        )
        for module in MODULES.values()
    ]
