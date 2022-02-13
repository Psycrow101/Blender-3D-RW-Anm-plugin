import bpy
from bpy.props import (
        StringProperty,
        BoolProperty,
        FloatProperty,
        )
from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper,
        )
from . anm import unpack_rw_lib_id, pack_rw_lib_id

bl_info = {
    "name": "Sonic Heroes Animation",
    "author": "Psycrow",
    "version": (0, 0, 3),
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

    export_version: bpy.props.StringProperty(
        maxlen=7,
        default="3.5.0.1",
        name="Version Export"
    )

    fps: FloatProperty(
        name="FPS",
        description="Value by which the keyframe time is divided",
        default=30.0,
    )

    create_intermediate: BoolProperty(
        name="Create intermediate",
        description="Create intermediate keyframes to fill the entire timeline",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.alignment = 'CENTER'

        col.alert = not self.verify_rw_version()
        icon = "ERROR" if col.alert else "NONE"
        col.prop(self, "export_version", icon=icon)

        col = layout.column()
        col.alignment = 'CENTER'
        col.prop(self, "fps")
        col.prop(self, "create_intermediate")

    def execute(self, context):
        from . import export_sh_anm

        if not self.verify_rw_version():
            self.report({"ERROR_INVALID_INPUT"}, "Invalid RW Version")
            return {'CANCELLED'}

        return export_sh_anm.save(context, self.filepath, self.fps, self.get_selected_rw_version(), self.create_intermediate)

    def invoke(self, context, event):
        arm_obj = context.view_layer.objects.active
        if arm_obj and type(arm_obj.data) == bpy.types.Armature:
            animation_data = arm_obj.animation_data
            if animation_data and animation_data.action and 'dragonff_rw_version' in animation_data.action:
                rw_version = animation_data.action['dragonff_rw_version']
                self.export_version = '%x.%x.%x.%x' % unpack_rw_lib_id(rw_version)

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def verify_rw_version(self):
        if len(self.export_version) != 7:
            return False

        for i, c in enumerate(self.export_version):
            if i % 2 == 0 and not c.isdigit():
                return False
            if i % 2 == 1 and not c == '.':
                return False

        return True

    def get_selected_rw_version(self):
        ver = self.export_version
        return pack_rw_lib_id(*map(lambda c: int('0x%c' % c, 0), (ver[0], ver[2], ver[4], ver[6])))


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
