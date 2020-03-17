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

from maya import cmds
import maya.mel

class Publish_QA(object):
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
            cmds.file(new=True, f=True)
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

        root = r'p:\MBA_SE02\tmp\publisher'

        job_key = next(iter(self.job_data['jobs']))
        asset_key = next(iter(self.job_data['jobs'][job_key]))
        asset_path = os.path.split(os.path.normpath(self.job_data['jobs'][job_key][asset_key][u"path"]))
        asset_name = asset_path[-1]
        asset_type = asset_path[-2]

        from MBA_SE02.internal.publish.apps import publisher_core
        data = {
            "root": root,
            "project": "MBA_SE02",
            "assetType": asset_type,
            "asset": asset_name,
            "note": "batch publish",
            "mode": publisher_core.Publish_mode.WET,
            "require_animation": False,
            "render_preview": False,
            "render_test": False,
        }

        result = publisher_core.cli_execute(data)
        lprint(result)

        if not result["result"]:
            lprint("Failed maya_script_job")
            cmds.file(new=True, f=True)
            maya.standalone.uninitialize()
            os._exit(1)



    def on_failed(self):
        lprint("Failed maya_script_job")
        # Uninitialize is required to exit, otherwise mayapy freezes indefinitely.
        cmds.file(new=True, f=True)
        maya.standalone.uninitialize()
        os._exit(1)


if __name__ == "__main__":
    Publish_QA().run()


###################################################################################################
###################################################################################################
### END SCRIPT TASK ###############################################################################
###################################################################################################
###################################################################################################


