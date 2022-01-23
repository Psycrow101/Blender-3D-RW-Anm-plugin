import bpy
from bpy.props import (
        StringProperty,
        FloatProperty,
        )
from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper,
        )

bl_info = {
    "name": "Sonic Heroes Animation",
    "author": "Psycrow",
    "version": (0, 0, 1),
    "blender": (2, 81, 0),
    "location": "File > Import-Export",
    "description": "Import / Export Sonic Heroes Animation (.anm)",
    "warning": "",
    "wiki_url": "",
    "support": 'COMMUNITY',
    "category": "Import-Export"
}

if "bpy" in locals():
    import importlib
    if "import_sh_anm" in locals():
        importlib.reload(import_sh_anm)
    if "export_sh_anm" in locals():
        importlib.reload(export_sh_anm)


class ImportSonicHeroesAnm(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.sonic_heroes_anm"
    bl_label = "Import Sonic Heroes Animation"
    bl_options = {'PRESET', 'UNDO'}

    filter_glob: StringProperty(default="*.anm", options={'HIDDEN'})
    filename_ext = ".anm"

    fps: FloatProperty(
        name="FPS",
        description="Value by which the keyframe time is multiplied",
        default=30.0,
    )

    def execute(self, context):
        from . import import_sh_anm

        keywords = self.as_keywords(ignore=("filter_glob",
                                            ))

        return import_sh_anm.load(context, **keywords)


class ExportSonicHeroesAnm(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.sonic_heroes_anm"
    bl_label = "Export Sonic Heroes Animation"
    bl_options = {'PRESET'}

    filter_glob: StringProperty(default="*.anm", options={'HIDDEN'})
    filename_ext = ".anm"

    fps: FloatProperty(
        name="FPS",
        description="Value by which the keyframe time is divided",
        default=30.0,
    )

    def execute(self, context):
        from . import export_sh_anm

        keywords = self.as_keywords(ignore=("filter_glob",
                                            ))

        return export_sh_anm.save(context, keywords['filepath'], keywords['fps'])


def menu_func_import(self, context):
    self.layout.operator(ImportSonicHeroesAnm.bl_idname,
                         text="Sonic Heroes Animation (.anm)")


def menu_func_export(self, context):
    self.layout.operator(ExportSonicHeroesAnm.bl_idname,
                         text="Sonic Heroes Animation [unstable] (.anm)")


classes = (
    ImportSonicHeroesAnm,
    ExportSonicHeroesAnm,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
