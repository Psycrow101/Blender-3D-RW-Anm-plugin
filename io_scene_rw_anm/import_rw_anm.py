import bpy

from mathutils import Matrix
from os import path

from .types.anm import Anm, AnmAnimation
from .types.ska import Ska
from .types.tmo import Tmo

POSEDATA_PREFIX = 'pose.bones["%s"].'


def invalid_active_object(self, context):
    self.layout.label(text='You need to select the armature to import animation')


def set_keyframe(curves, frame, values):
    for i, c in enumerate(curves):
        c.keyframe_points.add(1)
        c.keyframe_points[-1].co = frame, values[i]
        c.keyframe_points[-1].interpolation = 'LINEAR'


def translation_matrix(v):
    return Matrix.Translation(v)


def local_to_basis_matrix(local_matrix, global_matrix, parent_matrix):
    return global_matrix.inverted() @ (parent_matrix @ local_matrix)


def create_action(arm_obj, rw_animation: AnmAnimation, options):
    fps = options["fps"]
    location_scale = options["location_scale"]

    act = bpy.data.actions.new('action')
    curves_loc, curves_rot = [], []
    prev_rots = {}
    bones_map = {}

    for bone_id, bone in enumerate(arm_obj.data.bones):
        g = act.groups.new(name=bone.name)
        cl = [act.fcurves.new(data_path=(POSEDATA_PREFIX % bone.name) + 'location', index=i) for i in range(3)]
        cr = [act.fcurves.new(data_path=(POSEDATA_PREFIX % bone.name) + 'rotation_quaternion', index=i) for i in range(4)]

        for c in cl + cr:
            c.group = g

        curves_loc.append(cl)
        curves_rot.append(cr)

        pose_bone = arm_obj.pose.bones[bone.name]
        pose_bone.rotation_mode = 'QUATERNION'
        pose_bone.location = (0, 0, 0)
        pose_bone.rotation_quaternion = (1, 0, 0, 0)

        prev_rots[bone] = None

        bone_tag = bone.get("bone_id")
        if bone_tag is not None:
            bones_map[bone_tag] = bone_id

    for kf in rw_animation.keyframes:

        if kf.is_indexed_bones():
            bone_id = kf.bone_id
            if bone_id >= len(arm_obj.data.bones):
                continue

        else:
            bone_id = bones_map[kf.bone_id]

        bone = arm_obj.data.bones[bone_id]
        frame = kf.time * fps
        pos, rot = None, None

        if not kf.is_pose_space():
            rest_mat = bone.matrix_local
            if bone.parent:
                parent_mat = bone.parent.matrix_local
                local_rot = (parent_mat.inverted_safe() @ rest_mat).to_quaternion()
            else:
                parent_mat = Matrix.Identity(4)
                local_rot = rest_mat.to_quaternion()

            if kf.pos is not None:
                mat = translation_matrix(kf.pos)
                mat_basis = local_to_basis_matrix(mat, rest_mat, parent_mat)
                pos = mat_basis.to_translation()

            rot = local_rot.rotation_difference(kf.rot)

        else:
            pos = kf.pos * location_scale
            rot = kf.rot

        # Correction opposite direction of rotation
        prev_rot = prev_rots[bone]
        if prev_rot:
            alt_rot = rot.copy()
            alt_rot.negate()
            if rot.rotation_difference(prev_rot).angle > alt_rot.rotation_difference(prev_rot).angle:
                rot = alt_rot
        prev_rots[bone] = rot

        if pos is not None:
            set_keyframe(curves_loc[bone_id], frame, pos)

        set_keyframe(curves_rot[bone_id], frame, rot)

    return act


def load(context, filepath, options):
    arm_obj = context.view_layer.objects.active
    if not arm_obj or type(arm_obj.data) != bpy.types.Armature:
        context.window_manager.popup_menu(invalid_active_object, title='Error', icon='ERROR')
        return {'CANCELLED'}

    rw_animations = []
    rw_version = None

    ext = path.splitext(filepath)[-1].lower()
    if ext == ".ska":
        ska = Ska.load(filepath)
        rw_animations = [ska.animation]
        rw_version = None

    elif ext == ".tmo":
        tmo = Tmo.load(filepath)
        if tmo.chunks:
            rw_animations = [chunk.animation for chunk in tmo.chunks]
            rw_version = tmo.chunks[0].version

    else:
        anm = Anm.load(filepath)
        if anm.chunks:
            rw_animations = [chunk.animation for chunk in anm.chunks]
            rw_version = anm.chunks[0].version

    if not rw_animations:
        return {'CANCELLED'}

    animation_data = arm_obj.animation_data
    if not animation_data:
        animation_data = arm_obj.animation_data_create()

    bpy.ops.object.mode_set(mode='POSE')

    context.scene.frame_start = 0
    for anim in rw_animations:
        act = create_action(arm_obj, anim, options)
        act.name = path.basename(filepath)
        animation_data.action = act
        context.scene.frame_end = int(anim.duration * options["fps"])

        if rw_version is not None:
            act['dragonff_rw_version'] = rw_version

    bpy.ops.object.mode_set(mode='OBJECT')

    return {'FINISHED'}
