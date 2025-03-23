import bpy
from bpy.props import (
        CollectionProperty,
        EnumProperty,
        FloatProperty,
        StringProperty,
        )
from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper,
        )
from pathlib import Path
from .types.common import unpack_rw_lib_id, pack_rw_lib_id

bl_info = {
    "name": "RenderWare Animation",
    "author": "Psycrow",
    "version": (0, 4, 1),
    "blender": (2, 81, 0),
    "location": "File > Import-Export",
    "description": "Import / Export RenderWare Animation (.anm, .ska)",
    "warning": "",
    "wiki_url": "",
    "support": 'COMMUNITY',
    "category": "Import-Export"
}

if "bpy" in locals():
    import importlib
    if "import_rw_anm" in locals():
        importlib.reload(import_rw_anm)
    if "export_rw_anm" in locals():
        importlib.reload(export_rw_anm)


class ImportRenderWareAnm(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.renderware_anm"
    bl_label = "Import RenderWare Animation"
    bl_options = {'PRESET', 'UNDO'}

    filter_glob: StringProperty(default="*.*anm;*.ska;*.tmo", options={'HIDDEN'})
    filename_ext = ".anm"

    fps: FloatProperty(
        name="FPS",
        description="Value by which the keyframe time is multiplied",
        default=30.0,
    )

    location_scale: FloatProperty(
        name="Location Scale",
        description="Bone location vector multiplier",
        default=8.0,
        step=100.0,
        min=0.0,
    )

    files: CollectionProperty(type=bpy.types.PropertyGroup)

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "fps")
        layout.separator()

        box = layout.box()
        box.label(text="8ing")
        box.prop(self, "location_scale")

    def execute(self, context):
        from . import import_rw_anm

        options = {
            "fps": self.fps,
            "location_scale": self.location_scale,
        }

        files_dir = Path(self.filepath)
        for selection in self.files:
            file_path = Path(files_dir.parent, selection.name)
            file_ext = file_path.suffix.lower()
            if file_ext in (".ska", ".tmo") or file_ext[-3:] == "anm":
                import_rw_anm.load(context, file_path, options)
        return {'FINISHED'}


class ExportRenderWareAnm(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.renderware_anm"
    bl_label = "Export RenderWare Animation (.anm)"
    bl_options = {'PRESET'}

    filter_glob: StringProperty(default="*.anm", options={'HIDDEN'})
    filename_ext = ".anm"

    export_version: StringProperty(
        maxlen=7,
        default="3.5.0.1",
        name="Version Export"
    )

    keyframe_type: EnumProperty(
        name="Keyframe Type",
        items=(
            ("0x0001", "Uncompressed", "Uncompressed"),
            ("0x0002", "Compressed", "Compressed"),
            ("0x0100", "Compressed Rotations (rotanm)", "Compressed Rotations"),
            ("0x1103", "Climax", "Climax (0x1103)"),
        )
    )

    fps: FloatProperty(
        name="FPS",
        description="Value by which the keyframe time is divided",
        default=30.0,
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
        col.prop(self, "keyframe_type")
        col.prop(self, "fps")

    def execute(self, context):
        from . import export_rw_anm

        if not self.verify_rw_version():
            self.report({"ERROR_INVALID_INPUT"}, "Invalid RW Version")
            return {'CANCELLED'}

        return export_rw_anm.save(context, self.filepath, self.fps, self.get_selected_rw_version(), int(self.keyframe_type, 16))

    def invoke(self, context, event):
        arm_obj = context.view_layer.objects.active
        if arm_obj and type(arm_obj.data) == bpy.types.Armature:
            animation_data = arm_obj.animation_data
            if animation_data and animation_data.action and 'dragonff_rw_version' in animation_data.action:
                rw_version = animation_data.action['dragonff_rw_version']
                self.export_version = '%x.%x.%x.%x' % unpack_rw_lib_id(rw_version)

        if not self.filepath:
            if context.blend_data.filepath:
                self.filepath = context.blend_data.filepath
            else:
                self.filepath = "untitled"

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


class ExportRenderWareSka(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.renderware_ska"
    bl_label = "Export RenderWare Animation (.ska)"
    bl_options = {'PRESET'}

    filter_glob: StringProperty(default="*.ska", options={'HIDDEN'})
    filename_ext = ".ska"

    fps: FloatProperty(
        name="FPS",
        description="Value by which the keyframe time is divided",
        default=30.0,
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.alignment = 'CENTER'
        col.prop(self, "keyframe_type")
        col.prop(self, "fps")

    def execute(self, context):
        from . import export_rw_anm

        return export_rw_anm.save(context, self.filepath, self.fps, 0, 0)


class OBJECT_MT_RWAnimExportChoice(bpy.types.Menu):
    bl_label = "RenderWare Animation (.anm, .ska)"

    def draw(self, context):
            self.layout.operator(ExportRenderWareAnm.bl_idname,
                                text="RenderWare Animation (.anm)")
            self.layout.operator(ExportRenderWareSka.bl_idname,
                                text="RenderWare Animation (.ska)")


def menu_func_import(self, context):
    self.layout.operator(ImportRenderWareAnm.bl_idname,
                         text="RenderWare Animation (.anm, .ska, .tmo)")


def menu_func_export(self, context):
    self.layout.menu("OBJECT_MT_RWAnimExportChoice", text=OBJECT_MT_RWAnimExportChoice.bl_label)


classes = (
    ImportRenderWareAnm,
    ExportRenderWareAnm,
    ExportRenderWareSka,
    OBJECT_MT_RWAnimExportChoice,
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
