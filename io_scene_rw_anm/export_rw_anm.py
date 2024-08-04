import bpy
from dataclasses import dataclass
from mathutils import Quaternion, Vector
from . anm import Anm, AnmChunk, AnmAction, AnmKeyframe, ANM_CHUNK_ID, ANM_ACTION_VERSION


def invalid_active_object(self, context):
    self.layout.label(text='You need to select the armature to export animation')


def missing_action(self, context):
    self.layout.label(text='No action for active armature. Nothing to export')


def no_tagged_bones(self, context):
    self.layout.label(text='No tagged bones in armature. To export animation, you must first import the dff model')


def is_bone_taged(bone):
    return bone.get('bone_id') is not None


@dataclass
class PoseBoneTransform:
    pos: Vector
    rot: Quaternion

    def lerp(self, trans, factor):
        return PoseBoneTransform(self.pos.lerp(trans.pos, factor), self.rot.slerp(trans.rot, factor))


def get_pose_transforms(context, arm_obj, act):
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
            if not frame_start <= time < frame_end:
                continue
            if time not in times_map:
                times_map[time] = set()
            times_map[time].add(bone_id)

    times_map[min(times_map)] = bone_ids
    times_map[max(times_map)] = bone_ids

    old_frame = context.scene.frame_current

    bone_transforms_map = {}
    for frame in range(frame_start, frame_end + 1):
        bone_transforms_map[frame] = {}
        context.scene.frame_set(frame)
        context.view_layer.update()
        for b in bone_ids:
            pose_bone = arm_obj.pose.bones[b]
            pos = pose_bone.location.copy()
            if pose_bone.rotation_mode == 'QUATERNION':
                rot = pose_bone.rotation_quaternion.copy()
            else:
                rot = pose_bone.rotation_euler.to_quaternion()
            transform = PoseBoneTransform(pos, rot)
            bone_transforms_map[frame][b] = transform

    context.scene.frame_set(old_frame)

    pose_transforms = []
    for time, bids in times_map.items():
        for bone_id in bids:
            prev_time, next_time = int(time), int(time + 1)
            prev_transform = bone_transforms_map[prev_time][bone_id]
            next_transform = bone_transforms_map[next_time][bone_id]
            pose_transforms.append((bone_id, time, prev_transform.lerp(next_transform, time - prev_time)))

    return pose_transforms


def sort_pose_transforms(pose_transforms):
    sorted_pose_transforms_s1 = sorted(pose_transforms)
    curr_bone_id = sorted_pose_transforms_s1[0][0]
    prev_time = sorted_pose_transforms_s1[0][1] - 1.0

    sorted_pose_transforms_s2 = []
    for bone_id, time, pose_transform in sorted_pose_transforms_s1:
        if bone_id != curr_bone_id:
            curr_bone_id = bone_id
            prev_time = time - 1.0

        sorted_pose_transforms_s2.append((prev_time, bone_id, time, pose_transform))
        prev_time = time

    sorted_pose_transforms = [(bone_id, time, pose_transform) for _, bone_id, time, pose_transform in sorted(sorted_pose_transforms_s2)]
    return sorted_pose_transforms


def create_anm_action(context, arm_obj, act, fps):
    keyframes = []
    sorted_pose_transforms = sort_pose_transforms(get_pose_transforms(context, arm_obj, act))
    duration = 0.0
    frame_start = context.scene.frame_start

    for bone_id, time, pose_transform in sorted_pose_transforms:
        bone = arm_obj.data.bones[bone_id]
        time = time - frame_start

        loc_mat = bone.matrix_local.copy()
        if bone.parent:
            loc_mat = bone.parent.matrix_local.inverted_safe() @ loc_mat

        kf_pos, kf_rot = pose_transform.pos, pose_transform.rot
        kf_pos += loc_mat.to_translation()
        kf_rot = loc_mat.inverted_safe().to_quaternion().rotation_difference(kf_rot)

        keyframes.append(AnmKeyframe(time / fps, bone_id, kf_pos, kf_rot))
        if time > duration:
            duration = time

    return AnmAction(ANM_ACTION_VERSION, 0, duration / fps, keyframes)


def save(context, filepath, fps, export_version):
    arm_obj = context.view_layer.objects.active
    if not arm_obj or type(arm_obj.data) != bpy.types.Armature:
        context.window_manager.popup_menu(invalid_active_object, title='Error', icon='ERROR')
        return {'CANCELLED'}

    act = None
    animation_data = arm_obj.animation_data
    if animation_data:
        act = animation_data.action

    if not act:
        context.window_manager.popup_menu(missing_action, title='Error', icon='ERROR')
        return {'CANCELLED'}

    if not any(is_bone_taged(bone) for bone in arm_obj.data.bones):
        context.window_manager.popup_menu(no_tagged_bones, title='Error', icon='ERROR')
        return {'CANCELLED'}

    anm_act = create_anm_action(context, arm_obj, act, fps)
    anm = Anm([AnmChunk(ANM_CHUNK_ID, export_version, anm_act)])
    anm.save(filepath)

    return {'FINISHED'}
