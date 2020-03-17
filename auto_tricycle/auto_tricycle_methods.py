import pymel.core as pm
import os
import mutils

def extractAssets(selection = []):
    d = 'P:/MBA_SE02/assets/characters'
    characters_options = os.listdir(d)

    char_name = []
    tricycle_name = []

    if len(selection) == 2:
        for item in selection:
            asset_name = item.namespace().split(':')[0]
            if 'tricycles' in asset_name:
                tricycle_name = asset_name
            elif asset_name.split('_')[0] in characters_options:
                char_name = asset_name
    if bool(char_name and tricycle_name):
        return [char_name,tricycle_name]
    else:
        pm.displayWarning("choose exactly 2 objects - one character and one tricycle")
        return []

def getPose(char_name):
    path = "P:/MBA_SE02/assets/characters/%s/anim_lib/RIG/Tricycles_Pose.pose/pose.json" % char_name
    if os.path.exists(path):
        return path
    else:
        return None

def applyPose(ns, pose_path):
    char_name = ns.split('_')[0]
    cache_pose = 'P:/MBA_SE02/assets/characters/%s/anim_lib/RIG/Tricycles_Pose.pose/pose.json' % char_name
    pose = mutils.Pose.fromPath(cache_pose)
    pose.select(namespaces=[ns])
    pose.load()

def constraintToTricycle(assets):
    char_name = assets[0]
    tricycle_name = assets[1]
    pm.parentConstraint(tricycle_name+':cog_C0_ctl', char_name+':global_C0_ctl_cns_ctl',mo=1)
    pm.parentConstraint(tricycle_name + ':pedal_L0_ctl', char_name + ':leg_L0_ik_ctl', mo=1)
    pm.parentConstraint(tricycle_name + ':pedal_R0_ctl', char_name + ':leg_R0_ik_ctl', mo=1)
    pm.parentConstraint(tricycle_name + ':frontWheel_L1_fk2_ctl', char_name + ':arm_L0_ik_ctl', mo=1)
    pm.parentConstraint(tricycle_name + ':frontWheel_R1_fk2_ctl', char_name + ':arm_R0_ik_ctl', mo=1)