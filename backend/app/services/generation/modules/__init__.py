from app.services.generation.modules.base import ModuleDefinition
from app.services.generation.modules.ai_anime import AIAnimeModule
from app.services.generation.modules.ai_caricature import AICaricatureModule
from app.services.generation.modules.ai_brick_built_figure import AIBrickBuiltFigureModule
from app.services.generation.modules.ai_cinematic_3d_toy import AICinematic3DToyModule
from app.services.generation.modules.ai_collectible_figure import AICollectibleFigureModule
from app.services.generation.modules.ai_comic_book import AIComicBookModule
from app.services.generation.modules.ai_fantasy_hero import AIFantasyHeroModule
from app.services.generation.modules.ai_cyberpunk import AICyberpunkModule
from app.services.generation.modules.ai_claymation import AIClaymationModule
from app.services.generation.modules.ai_high_fashion_editorial import AIHighFashionEditorialModule
from app.services.generation.modules.bokeh_blur import BokehBlurModule
from app.services.generation.modules.cartoon import CartoonModule
from app.services.generation.modules.collage import CollageModule
from app.services.generation.modules.duotone import DuotoneModule
from app.services.generation.modules.filmstrip import FilmstripModule
from app.services.generation.modules.glitch import GlitchModule
from app.services.generation.modules.halftone import HalftoneModule
from app.services.generation.modules.hdr import HDRModule
from app.services.generation.modules.instafilter import InstafilterModule
from app.services.generation.modules.cyanotype import CyanotypeModule
from app.services.generation.modules.paper_cutout import PaperCutoutModule
from app.services.generation.modules.pencil_sketch import PencilSketchModule
from app.services.generation.modules.polaroid import PolaroidModule
from app.services.generation.modules.light_leak import LightLeakModule
from app.services.generation.modules.prism_split import PrismSplitModule
from app.services.generation.modules.neon_bloom import NeonBloomModule
from app.services.generation.modules.popart import PopArtModule
from app.services.generation.modules.huji import HujiModule
from app.services.generation.modules.museum_archive import MuseumArchiveModule
from app.services.generation.modules.ai_yellow_cartoon_sitcom import AIYellowCartoonSitcomModule
from app.services.generation.modules.vintage_film import VintageFilmModule

MODULE_CLASSES = [
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
    AICaricatureModule,
    AIAnimeModule,
    AIComicBookModule,
    AICyberpunkModule,
    AIClaymationModule,
    AICinematic3DToyModule,
    AICollectibleFigureModule,
    AIFantasyHeroModule,
    AIHighFashionEditorialModule,
    AIBrickBuiltFigureModule,
    AIYellowCartoonSitcomModule,
]

MODULES = {module_class.name: module_class() for module_class in MODULE_CLASSES}


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
