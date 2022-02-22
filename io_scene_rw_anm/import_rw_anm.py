import bpy
from mathutils import Matrix
from os import path
from . anm import Anm

POSEDATA_PREFIX = 'pose.bones["%s"].'


def invalid_active_object(self, context):
    self.layout.label(text='You need to select the armature to import animation')


def set_keyframe(curves, frame, values):
    for i, c in enumerate(curves):
        c.keyframe_points.add(1)
        c.keyframe_points[-1].co = frame, values[i]
        c.keyframe_points[-1].interpolation = 'LINEAR'


def create_action(arm_obj, anm_act, fps):
    act = bpy.data.actions.new('action')
    curves_loc, curves_rot = [], []

    for bone in arm_obj.pose.bones:
        g = act.groups.new(name=bone.name)
        cl = [act.fcurves.new(data_path=(POSEDATA_PREFIX % bone.name) + 'location', index=i) for i in range(3)]
        cr = [act.fcurves.new(data_path=(POSEDATA_PREFIX % bone.name) + 'rotation_quaternion', index=i) for i in range(4)]

        for c in cl:
            c.group = g

        for c in cr:
            c.group = g

        curves_loc.append(cl)
        curves_rot.append(cr)
        bone.rotation_mode = 'QUATERNION'

    for kf in anm_act.keyframes:
        bone = arm_obj.pose.bones[kf.bone_id]
        mat = Matrix.Translation(kf.pos) @ kf.rot.to_matrix().to_4x4()
        if bone.parent:
            mat = bone.parent.matrix @ mat
        bone.matrix = mat
        set_keyframe(curves_loc[kf.bone_id], kf.time * fps, bone.location)
        set_keyframe(curves_rot[kf.bone_id], kf.time * fps, bone.rotation_quaternion)

    return act


def load(context, filepath, *, fps):
    arm_obj = context.view_layer.objects.active
    if not arm_obj or type(arm_obj.data) != bpy.types.Armature:
        context.window_manager.popup_menu(invalid_active_object, title='Error', icon='ERROR')
        return {'CANCELLED'}

    anm = Anm.load(filepath)
    if not anm.chunks:
        return {'CANCELLED'}

    animation_data = arm_obj.animation_data
    if not animation_data:
        animation_data = arm_obj.animation_data_create()

    bpy.ops.object.mode_set(mode='POSE')

    context.scene.frame_start = 0
    for chunk in anm.chunks:
        act = create_action(arm_obj, chunk.action, fps)
        act.name = path.basename(filepath)
        act['dragonff_rw_version'] = chunk.version
        animation_data.action = act
        context.scene.frame_end = chunk.action.duration * fps

    bpy.ops.object.mode_set(mode='OBJECT')

    return {'FINISHED'}
