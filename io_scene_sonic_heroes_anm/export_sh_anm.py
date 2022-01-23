import bpy
from mathutils import Matrix, Quaternion, Vector
from collections import OrderedDict
from . anm import Anm, AnmChunk, AnmAction, AnmKeyframe, ANM_CHUNK_ID, ANM_CHUNK_VERSION, ANM_ACTION_VERSION


def invalid_active_object(self, context):
    self.layout.label(text='You need to select the armature to export animation')


def missing_action(self, context):
    self.layout.label(text='No action for active armature. Nothing to export')


def is_bone_taged(bone):
    return bone.get('bone_id') is not None


def get_local_mats(arm_obj):
    local_mats = {}
    for bone in arm_obj.data.bones:
        mat = bone.matrix_local
        if bone.parent:
            mat = bone.parent.matrix_local.inverted_safe() @ mat
        local_mats[bone.name] = mat
    return local_mats


def get_pose_mats(arm_obj, act):
    motion_types = ('location', 'rotation_quaternion')

    pose_trans = {}
    for curve in act.fcurves:
        if 'pose.bones' not in curve.data_path:
            continue

        bone_name = curve.data_path.split('"')[1]
        if not is_bone_taged(arm_obj.data.bones[bone_name]):
            continue
        bone_id = arm_obj.pose.bones.find(bone_name)

        mt = curve.data_path[15+len(bone_name):]
        if mt not in motion_types:
            continue
        motion_id = motion_types.index(mt)

        for kp in curve.keyframe_points:
            time, val = kp.co

            if time not in pose_trans:
                pose_trans[time] = {}
            if bone_id not in pose_trans[time]:
                pose_trans[time][bone_id] = [Vector(), Quaternion()]

            pose_trans[time][bone_id][motion_id][curve.array_index] = val

    pose_mats = {}  
    for time, motions in pose_trans.items():
        if time not in pose_mats:
            pose_mats[time] = {}
        for bone_id, motion in motions.items():
            pose_mats[time][bone_id] = Matrix.Translation(motion[0]) @ motion[1].to_matrix().to_4x4()
        pose_mats[time] = OrderedDict(sorted(pose_mats[time].items()))

    pose_mats = OrderedDict(sorted(pose_mats.items()))
    return pose_mats


def sort_pose_mats(pose_mats):
    def find_next_time(c_bone_id, c_bone_time):
        for t, m in pose_mats.items():
            if t >= c_bone_time and c_bone_id in m.keys():
                return t
        return None

    pose_mats_sorted = []

    times_uniq, bone_ids_uniq = set(), set()
    for time, mats in pose_mats.items():
        times_uniq.add(time)
        for bone_id in mats.keys():
            bone_ids_uniq.add(bone_id)

    for time in times_uniq:
        for bone_id in bone_ids_uniq:
            next_time = find_next_time(bone_id, time)
            if next_time is None:
                continue
            pose_mats_sorted.append((next_time, bone_id, pose_mats[next_time][bone_id]))
            del pose_mats[next_time][bone_id]

    return pose_mats_sorted


def create_anm_action(arm_obj, act, fps):
    keyframes = []
    local_mats = get_local_mats(arm_obj)
    pose_mats = sort_pose_mats(get_pose_mats(arm_obj, act))

    duration = 0.0

    for time, bone_id, pose_mat in pose_mats:
        bone = arm_obj.pose.bones[bone_id]
        mat = local_mats[bone.name] @ pose_mat
        pos = mat.to_translation()
        rot = mat.to_quaternion()
        keyframes.append(AnmKeyframe(time / fps, bone_id, pos, rot))
        if time > duration:
            duration = time

    return AnmAction(ANM_ACTION_VERSION, 0, duration / fps, keyframes)


def save(context, filepath, fps):
    arm_obj = context.view_layer.objects.active
    if not arm_obj or type(arm_obj.data) != bpy.types.Armature:
        context.window_manager.popup_menu(invalid_active_object, title='Error', icon='ERROR')
        return {'CANCELLED'}

    act = arm_obj.animation_data.action
    if not act:
        context.window_manager.popup_menu(missing_action, title='Error', icon='ERROR')
        return {'CANCELLED'}

    anm_act = create_anm_action(arm_obj, act, fps)
    anm = Anm([AnmChunk(ANM_CHUNK_ID, ANM_CHUNK_VERSION, anm_act)])
    anm.save(filepath)

    return {'FINISHED'}
