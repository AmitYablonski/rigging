# Mayapy script job template

from __future__ import print_function

from pipeline.utils import lprint

lprint("Initializing maya.standalone...")
# After running this, Maya will echo almost all logger output to stderr.
# Other threads might still write to stdout (e.g. vray), but we have no control over them from our thread.
import maya.standalone

maya.standalone.initialize(name="test")



import os
import time
import traceback
from libSB.utils.text import format_duration
from libSB.legacy import versions_helper


from maya import cmds
import maya.mel
import pymel.core as pm

class Piggy_fix(object):
    """
        A Deadline job that creates and manages a queue of Signiant jobs based on data in a json file
    """
    def __init__(self):
        from libSB.sb_sync import SigniantLib
        self.siglib = SigniantLib()

        from libSB.sb_applications.sb_deadline import libDeadline
        self.libdeadline = libDeadline(self)


    def run(self):
        script_start = time.time()

        try:
            self.import_data_deadline()
            self.execute()

            lprint("Job complete in {}".format(format_duration(time.time() - script_start)))
            # Uninitialize is required to exit, otherwise mayapy freezes indefinitely.
            maya.standalone.uninitialize()
            os._exit(0)

        except Exception as e:
            traceback.print_exc()
            lprint(e)
            self.on_failed()


    def import_data_deadline(self):
        lprint("Getting data from Deadline")
        self.current_job = self.libdeadline['current_job']
        self.job_data = self.current_job['extra_info']['task_data']
        lprint(self.job_data)


    def execute(self):

        job_key = next(iter(self.job_data['jobs']))
        asset_key = next(iter(self.job_data['jobs'][job_key]))
        asset_path = os.path.split(os.path.normpath(self.job_data['jobs'][job_key][asset_key][u"path"]))
        asset_name = asset_path[-1]
        asset_type = asset_path[-2]


        asset_path = os.path.join('P:/MBA_SE02', 'assets', asset_type, asset_name)
        asset_shading_json = os.path.join(asset_path, asset_name, 'shading', 'shading.json')
        shading_versions_path = os.path.join(asset_path, 'shading', 'versions')

        current_file, version_number = versions_helper.get_latest_version_path_for_asset(shading_versions_path, asset_name, 'shading', increment_version=False)

        cmds.file(new=True, force=True)

        try:
            cmds.file(current_file, o=True)
        except RuntimeError:
            # Maya will output other errors encountered during loading between the printed exception info and the "Warning: skipped" line.
            lprint(traceback.format_exc())
            lprint('Warning: skipped RuntimeError in scene load.')
        except:
            raise Exception('Errors while loading scene - {}'.format(current_file))

        #####################################################################################

        lprint('***************** START PROCESS ******************************')
        lprint('[piggy shading fix] finished loading:{}'.format(current_file))

        try:
            conn = pm.listConnections('piggy_baseRN', s=True, d=False, p=True)
            for con in conn:
                pm.disconnectAttr(con)
    
            shader = pm.PyNode("piggy_base:PiggyHair_Opacity_Offset")
            hairObjs = ['piggy_base:piggy_hair_offset_high', 'piggy_base:piggy_ponytail_high_offset']

            shader_sg = pm.sets(renderable=True, noSurfaceShader=True, empty=True, name="{}SG".format(shader.name()))
            shader.outColor.connect(shader_sg.surfaceShader)
            cmds.select(hairObjs)
            cmds.sets(e=True, forceElement=shader_sg.name())
        except:
            lprint(traceback.format_exc())
            raise Exception('[piggy shading fix] Failed during code execution!')


        lprint('[piggy shading fix] Done!')
        lprint('***************** FINISHED PROCESS ******************************')
        #####################################################################################

        new_file, new_version_number = versions_helper.get_latest_version_path_for_asset(shading_versions_path, asset_name, 'shading', increment_version=True)

        try:
            if not os.path.exists(os.path.dirname(new_file)):
                os.makedirs(os.path.dirname(new_file))

            cmds.file(rename=new_file)
            cmds.file(f=True, s=True, type="mayaAscii", op="v=1")
            lprint('[piggy shading fix] Saved new version {}'.format(new_file))
        except:
            lprint(traceback.format_exc())
            raise Exception('[piggy shading fix] Unable to save new version - {}'.format(new_file))


        if os.path.isfile(asset_shading_json):
            versions_helper.insert_metadata_version_entry(path=asset_shading_json,
                                                          version_number=str(new_version_number),
                                                          author="batch",
                                                          note="piggy shading fix",
                                                          key="versions",
                                                          add_include=True)
            lprint('[piggy shading fix] Saved new metadata {}'.format(asset_shading_json))



    def on_failed(self):
        lprint("Failed maya_script_job")
        # Uninitialize is required to exit, otherwise mayapy freezes indefinitely.
        maya.standalone.uninitialize()
        os._exit(1)


if __name__ == "__main__":
    Piggy_fix().run()


###################################################################################################
###################################################################################################
### END SCRIPT TASK ###############################################################################
###################################################################################################
###################################################################################################


