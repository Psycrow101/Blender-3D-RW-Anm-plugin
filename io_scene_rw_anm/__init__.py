import bpy
from bpy.props import (
        StringProperty,
        FloatProperty,
        CollectionProperty,
        )
from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper,
        )
from pathlib import Path
from . anm import unpack_rw_lib_id, pack_rw_lib_id

bl_info = {
    "name": "RenderWare Animation",
    "author": "Psycrow",
    "version": (0, 1, 3),
    "blender": (2, 81, 0),
    "location": "File > Import-Export",
    "description": "Import / Export RenderWare Animation (.anm)",
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

    filter_glob: StringProperty(default="*.anm", options={'HIDDEN'})
    filename_ext = ".anm"

    fps: FloatProperty(
        name="FPS",
        description="Value by which the keyframe time is multiplied",
        default=30.0,
    )

    files: CollectionProperty(type=bpy.types.PropertyGroup)

    def execute(self, context):
        from . import import_rw_anm

        files_dir = Path(self.filepath)
        for selection in self.files:
            file_path = Path(files_dir.parent, selection.name)
            if file_path.suffix.lower() == self.filename_ext:
                import_rw_anm.load(context, file_path, self.fps)
        return {'FINISHED'}


class ExportRenderWareAnm(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.renderware_anm"
    bl_label = "Export RenderWare Animation"
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

    def execute(self, context):
        from . import export_rw_anm

        if not self.verify_rw_version():
            self.report({"ERROR_INVALID_INPUT"}, "Invalid RW Version")
            return {'CANCELLED'}

        return export_rw_anm.save(context, self.filepath, self.fps, self.get_selected_rw_version())

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
    self.layout.operator(ImportRenderWareAnm.bl_idname,
                         text="RenderWare Animation (.anm)")


def menu_func_export(self, context):
    self.layout.operator(ExportRenderWareAnm.bl_idname,
                         text="RenderWare Animation (.anm)")


classes = (
    ImportRenderWareAnm,
    ExportRenderWareAnm,
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
