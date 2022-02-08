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


def get_pose_mats(context, arm_obj, act, create_intermediate):
    frame_start = context.scene.frame_start
    frame_end = context.scene.frame_end + 1

    bone_ids = [b for b, bone in enumerate(arm_obj.data.bones) if is_bone_taged(bone)]
    times_map = {}
    for curve in act.fcurves:
        if 'pose.bones' not in curve.data_path:
            continue

        bone_name = curve.data_path.split('"')[1]
        bone_id = arm_obj.data.bones.find(bone_name)
        if bone_id not in bone_ids:
            continue
        
        for kp in curve.keyframe_points:
            time = kp.co[0]
            if not frame_start <= time <= frame_end:
                continue
            if time not in times_map:
                times_map[time] = []
            times_map[time].append(bone_id)

    if create_intermediate:
        times_map = {time: bone_ids for time in times_map}
    else:
        times_map[min(times_map)] = bone_ids
        times_map[max(times_map)] = bone_ids

    old_frame = context.scene.frame_current

    bone_mats_map = {}
    for frame in range(frame_start, frame_end + 1):
        bone_mats_map[frame] = {}
        context.scene.frame_set(frame)
        for b in bone_ids:
            pose_bone, arm_bone = arm_obj.pose.bones[b], arm_obj.data.bones[b]
            mat = pose_bone.matrix
            if pose_bone.parent:
                mat = pose_bone.parent.matrix.inverted_safe() @ mat
            bone_mats_map[frame][b] = mat

    context.scene.frame_set(old_frame)

    pose_mats = {}
    for time, bids in times_map.items():
        pose_mats[time] = {}
        for bone_id in sorted(bids):
            prev_time, next_time = int(time), int(time + 1)
            prev_mat, next_mat = bone_mats_map[prev_time][bone_id], bone_mats_map[next_time][bone_id]
            pose_mats[time][bone_id] = prev_mat.lerp(next_mat, time - prev_time)

    return pose_mats


def sort_pose_mats(pose_mats):
    def find_next_time(c_bone_id, c_bone_time):
        for t, m in ordered_pose_mats.items():
            if t >= c_bone_time and c_bone_id in m.keys():
                return t
        return None

    ordered_pose_mats = OrderedDict(sorted(pose_mats.items()))
    sorted_pose_mats = []

    times_set, bone_ids_set = set(), set()
    for time, mats in ordered_pose_mats.items():
        times_set.add(time)
        for bone_id in mats.keys():
            bone_ids_set.add(bone_id)

    for time in times_set:
        for bone_id in bone_ids_set:
            next_time = find_next_time(bone_id, time)
            if next_time is None:
                continue
            sorted_pose_mats.append((next_time, bone_id, ordered_pose_mats[next_time][bone_id]))
            del ordered_pose_mats[next_time][bone_id]

    return sorted_pose_mats


def create_anm_action(context, arm_obj, act, fps, create_intermediate):
    keyframes = []
    sorted_pose_mats = sort_pose_mats(get_pose_mats(context, arm_obj, act, create_intermediate))
    duration = 0.0

    for time, bone_id, pose_mat in sorted_pose_mats:
        bone = arm_obj.pose.bones[bone_id]
        pos = pose_mat.to_translation()
        rot = pose_mat.to_quaternion()
        keyframes.append(AnmKeyframe(time / fps, bone_id, pos, rot))
        if time > duration:
            duration = time

    return AnmAction(ANM_ACTION_VERSION, 0, duration / fps, keyframes)


def save(context, filepath, fps, create_intermediate):
    arm_obj = context.view_layer.objects.active
    if not arm_obj or type(arm_obj.data) != bpy.types.Armature:
        context.window_manager.popup_menu(invalid_active_object, title='Error', icon='ERROR')
        return {'CANCELLED'}

    act = arm_obj.animation_data.action
    if not act:
        context.window_manager.popup_menu(missing_action, title='Error', icon='ERROR')
        return {'CANCELLED'}

    anm_act = create_anm_action(context, arm_obj, act, fps, create_intermediate)
    anm = Anm([AnmChunk(ANM_CHUNK_ID, ANM_CHUNK_VERSION, anm_act)])
    anm.save(filepath)

    return {'FINISHED'}
