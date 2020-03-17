###################### imports ####################
import pymel.core as pm
import os, sys

path = "P:/MBA_SE02/scripts/rigging/amit/auto_tricycle"

if os.path.exists(path):
    if not path in sys.path:
        sys.path.append(path)

import auto_tricycle_methods as atm
reload(atm)

###################################################


# fetch assets from selection
assets = atm.extractAssets(selection = pm.ls(sl=True))
print assets


# get pose path for character
# todo: consider character name with _ in it
pose_path = atm.getPose(assets[0].split('_')[0])

# apply pose
atm.applyPose(assets[0], pose_path)


# constraint character to tricycle
atm.constraintToTricycle(assets)