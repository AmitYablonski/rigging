from pipeline.utils import lprint
lprint("i'm in publisher test!!!")

import os
import sys
import functools
import shutil
import uuid
import tempfile
import traceback
import getpass
import datetime
import json
import copy
import time
from enum import Enum
# from sb_libs.latest.Qt import QtWidgets, QtCore, QtGui
from pipeline.utils import lprint, nJoin, assure_folder_exists
# from pipeline.widgets import Combo, PromptUser, UserMassage, GroupInput
# from pipeline.thread_helper import Thread
import pipeline
from pipeline import data_helper
from libSB.sb_sync import SyncContext, DependencyType

from libSB import sb_projects
from libSB.sb_standard_lib import Dictlike


# from libSB.sb_filesystem.types import SB_File
# from libSB.sb_site import SBSiteLib
# from libSB.sb_path import StorageMapping

# import sb_ui

# site_lib = SBSiteLib()

os.chdir(os.path.dirname(pipeline.__file__)) #<-- set cwd

################################################################################
VERSION_MAJOR = 'alpha'
VERSION_MINOR = 0
VERSION_PATCH = 0

__version__ = "{}.{}.{}".format(VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH)

def assure_path_exists(path):
    dir = os.path.dirname(path)
    if not os.path.exists(dir):
        os.makedirs(dir)

class PublishException(Exception):
    def __init__(self, message, traceback = None):
        super(PublishException, self).__init__(message)
        self._message = message
        if traceback:
            lprint(traceback)


class Publisher(Dictlike):
    waiting_to_start = "Waiting to start"
    ready = "Ready"
    locked = "Locked"
    failed = "Failed"
    passed = "Passed automation"

    def __init__(self, root=None):
        Dictlike.__init__(self, None)
        self.require_shading = True
        self.root = root

    def init_asset(self, asset=None):
        if not hasattr(self, "asset"):
            self.asset = asset

        if not self.asset:
            raise RuntimeError

        asset = self.asset

        self.public_task = asset.getTask("public")
        self.public_version = self.public_task['version_repository']["dir"]["next"]

        self.rigging_task = asset.getTask("rigging")
        self.rigging_versions = self.rigging_task["versions"]

        self.shading_task = asset.getTask("shading")
        self.shading_versions = self.shading_task["versions"]

        self.anim_tests_task = asset.getTask("anim_tests")
        self.anim_tests_versions = self.anim_tests_task["versions"]

        if (not self.anim_tests_versions) and (asset["variant"]):
            # maybe this is a variant?
            # let's get it's base asset
            base_asset = asset.dir['metadata_file']['json_data']['base_asset'][-1]
            project = asset['project']
            characters = project.get_asset_type("characters")
            base_asset = characters.get_asset(base_asset)

            self.anim_tests_task = base_asset.getTask("anim_tests")
            self.anim_tests_versions = self.anim_tests_task["versions"]


        ###################################################
        # the following data will be without any python objects - should be serializable
        self["publish"] = {}
        self["publish"]["asset"] = asset["lineage"]
        lprint("initiated with asset: {}".format(asset["lineage"]))
        self.set_sandbox()


    def set_sandbox(self):
        # define the 'sandbox' for the publishing process

        id = uuid.uuid4()
        data = {}
        data["id"] = "{}".format(id)
        if self.root:
            asset_name = "_".join(self["publish"]["asset"][-2:])
            data["asset_name"] = asset_name
            root = os.path.join(self.root, asset_name)
        else:
            root = tempfile.gettempdir()

        assure_folder_exists(root)


        data["base"] = nJoin(root, "{}".format(id))

        data["rigging"] =             {"path": nJoin(data["base"], '{}_rigging.ma'.format(id)),
                                       "path_mb": nJoin(data["base"], '{}_rigging.mb'.format(id)),
                                       "state": Publisher.waiting_to_start}

        data["shading"] =             {"path": nJoin(data["base"], '{}_shading.ma'.format(id)),
                                       "state": Publisher.waiting_to_start}

        data["animation"] =           {"path": nJoin(data["base"], '{}_animation.ma'.format(id)),
                                       "state": Publisher.waiting_to_start}

        data["test"] =                {"path": nJoin(data["base"], '{}_test.ma'.format(id)),
                                       "state": Publisher.waiting_to_start}

        self["publish"]["sandbox"] = data

    def set_public_stamp(self, rigging_version, shading_version):
        if not self.public_task:
            raise RuntimeError

        rigging_origin_version = filter(lambda x: x["number"] == rigging_version, self.rigging_versions)[-1]
        rigging_origin_version = str(rigging_origin_version["number"])

        if self.require_shading:
            shading_origin_version = filter(lambda x: x["number"] == shading_version, self.shading_versions)[-1]
            shading_origin_version = str(shading_origin_version["number"])
        else:
            shading_origin_version = "0"

        if not "public_stamp" in self["publish"]:

            self["publish"]["public_stamp"] = {
                "ID": self["publish"]["sandbox"]["id"],
                "Version": self.public_version["suffix"],
                "Asset": self.asset["name"],
                "Root": self.asset["project"]["dir"]["path"],
                "Show": self.asset["project"]["name"],
                "Author": getpass.getuser(),
                "Date": str(datetime.datetime.now()),
                "Origin_rigging": rigging_origin_version,
                "Origin_shading": shading_origin_version,
            }

        else:
            lprint("public stamp already initiated")


    def get_selected_versions(self, rigging_version = 1, shading_version = 1, anim_test_version = 1):
        return {
            "rigging": filter(lambda x: x["number"] == rigging_version, self.rigging_versions)[-1],
            "shading": filter(lambda x: x["number"] == shading_version, self.shading_versions)[-1],
            "anim_test": self.anim_tests_versions[0] if self.anim_tests_versions else None#for some reasone this list is reveresed -\\_(' ')_//-
        }


    def process_rigging(self, rigging_version, shading_version):
        ##############################################################################################################################
        # the rigging should be processed in maya
        ##############################################################################################################################
        try:
            sl = self.get_selected_versions(rigging_version, shading_version)
            self.set_public_stamp(sl["rigging"]["number"], sl["shading"]["number"])

            import pymel.core as pm
            from MBA_SE02.internal.rigging import publish as rigging_publish
            from pipeline.variants.pipeline_maya.utils import maya_helper
            reload(rigging_publish)
            reload(maya_helper)

            lprint(sl["rigging"].dir["path"])
            maya_helper.open_scene(sl["rigging"].dir["path"])

            def process():
                publisher = rigging_publish.Rigging_publish(public_stamp=self["publish"]["public_stamp"])
                # publisher.published_successfully.connect(self.on_rigging_processed_successfully)
                # publisher.published_failed.connect(self.on_rigging_processed_failed)
                result = publisher.start()
                if result:
                    self.on_rigging_processed_successfully()
                else:
                    self.on_rigging_processed_failed()

                return result
            # pm.evalDeferred(lambda: process())
            return process()

        except:
            lprint(traceback.format_exc())
            self.on_rigging_processed_failed()

    def process_shading(self, rigging_version, shading_version):
        ##############################################################################################################################
        # the shading should be processed in maya
        ##############################################################################################################################
        try:
            sl = self.get_selected_versions(rigging_version, shading_version)
            self.set_public_stamp(sl["rigging"]["number"], sl["shading"]["number"])
            import pymel.core as pm
            from MBA_SE02.internal.shading.publish import publish as shading_publish
            from pipeline.variants.pipeline_maya.utils import maya_helper
            reload(shading_publish)
            reload(maya_helper)

            maya_helper.open_scene(sl["shading"].dir["path"])

            def process():
                publisher = shading_publish.Shading_publish(public_stamp=self["publish"]["public_stamp"])
                # publisher.published_successfully.connect(self.on_shading_processed_successfully)
                # publisher.published_failed.connect(self.on_shading_processed_failed)
                # publisher.start()
                result = publisher.start()
                if result:
                    self.on_shading_processed_successfully()
                else:
                    self.on_shading_processed_failed()
                return result
            # pm.evalDeferred(lambda: process())
            return process()

        except:
            self.on_shading_processed_failed()

    def process_animation(self, load=True):
        ##############################################################################################################################
        # the animation should be processed in maya
        ##############################################################################################################################
        try:
            sl = self.get_selected_versions()
            saved_animation = ''
            saved_camera = None
            if load:
                dir = sl["anim_test"]["parent"]['dir']["path"]
                anim = os.path.basename(sl["anim_test"]["path"])
                saved_animation = nJoin(dir, "studiolibrary", "{}.anim".format(anim))
                saved_camera = nJoin(dir, "camera", "{}.anim.ma".format(anim))
                if not os.path.exists(saved_camera):
                    saved_camera = None

                self['publish']['animation_camera'] = saved_camera

            if not os.path.isdir(saved_animation) and load:
                lprint("no animation was found in {}".format(saved_animation))
                raise Exception("no animation was found in {}".format(saved_animation))

            from maya import cmds
            from pipeline.variants.pipeline_maya.utils import maya_helper
            reload(maya_helper)

            import studiolibrary
            from mutils import animation

            maya_helper.new_scene()
            ns = '{}_0001'.format(self.asset["name"])
            cmds.file(self["publish"]["sandbox"]["rigging"]["path"], r=True, f=True, ns=ns, esn=False)

            if load:
                apply_animation = animation.Animation.fromPath(saved_animation)
                apply_animation.load(namespaces=[ns])

                sFrame = apply_animation.startFrame()
                eFrame = apply_animation.endFrame()
                cmds.playbackOptions(ast=sFrame)
                cmds.playbackOptions(aet=eFrame)

                if saved_camera:
                    cmds.file(saved_camera, i=True, pr=True)

            else:
                cmds.playbackOptions(ast=0)
                cmds.playbackOptions(aet=1)

            assure_folder_exists(self["publish"]["sandbox"]["base"])
            maya_helper.save_scene_as(path=self["publish"]["sandbox"]["base"],
                                      file_name=os.path.basename(self["publish"]["sandbox"]["animation"]["path"]))

            self.update_process_state(Publisher.ready, "animation")
            return True
            #TODO: close file...
        except:
            lprint(traceback.format_exc())
            return False
            # raise Exception()

    def process_test(self):
        ##############################################################################################################################
        # the animation should be processed in maya
        ##############################################################################################################################
        try:
            import pymel.core as pm
            from MBA_SE02.internal.publish import publish
            from pipeline.variants.pipeline_maya.utils import maya_helper
            reload(publish)
            reload(maya_helper)

            def process():
                test = publish.Asset_Publish(test_paths={"rigging":self["publish"]["sandbox"]["rigging"]["path_mb"],
                                                       "shading":self["publish"]["sandbox"]["shading"]["path"],
                                                       "base": self["publish"]["sandbox"]["base"],
                                                                 }
                                                     )
                result = test.start()
                if result:
                    self.on_test_processed_successfully()
                else:
                    self.on_test_processed_failed()
                return result
            # pm.evalDeferred(lambda: process())
            return process()

        except:
            self.on_test_processed_failed()

    def update_process_state(self, status, process):
        self["publish"]["sandbox"][process]["state"] = status
        lprint("{} Process: {}".format(process, status))


    def on_rigging_processed_successfully(self, *args):
        from pipeline.variants.pipeline_maya.utils import maya_helper
        reload(maya_helper)
        try:
            assure_folder_exists(self["publish"]["sandbox"]["base"])
            maya_helper.save_scene_as(path=self["publish"]["sandbox"]["base"],
                                      file_name=os.path.basename(self["publish"]["sandbox"]["rigging"]["path"]))
            maya_helper.save_scene_as(path=self["publish"]["sandbox"]["base"],
                                      file_name=os.path.basename(self["publish"]["sandbox"]["rigging"]["path_mb"]), typ='mayaBinary')
            lprint("Temp rigging master saved to: {}".format(self["publish"]["sandbox"]["rigging"]))
            maya_helper.new_scene()
            self.update_process_state(Publisher.ready, "rigging")
        except:
            lprint(traceback.format_exc())
            self.on_rigging_processed_failed()

    def on_rigging_processed_failed(self):
        self.update_process_state(Publisher.failed, "rigging")

    def on_shading_processed_successfully(self, *args):
        from pipeline.variants.pipeline_maya.utils import maya_helper
        reload(maya_helper)

        try:
            assure_folder_exists(self["publish"]["sandbox"]["base"])
            maya_helper.save_scene_as(path=self["publish"]["sandbox"]["base"],
                                      file_name=os.path.basename(self["publish"]["sandbox"]["shading"]["path"]))
            lprint("Temp shading master saved to: {}".format(self["publish"]["sandbox"]["shading"]))
            maya_helper.new_scene()
            self.update_process_state(Publisher.ready, "shading")

        except:
            lprint(traceback.format_exc())
            self.on_shading_processed_failed()

    def on_shading_processed_failed(self):
        self.update_process_state(Publisher.failed, "shading")

    def on_test_processed_successfully(self):
        self.update_process_state(Publisher.passed, "test")

    def on_test_processed_failed(self):
        self.update_process_state(Publisher.failed, "test")







    def process_publish(self, note = None):

        if note == "" or (not note):
            lprint('warning: must provide a note')
            raise PublishException("warning: must provide a note")

        # setup the copy paths
        public_path = self.public_task['version_repository']["dir"]["path"]
        next = self.public_task['version_repository']["dir"]["next"]
        dir = nJoin(public_path, next["suffix"])

        # this will not support xgen!!
        rigging_name = "{asset}_rigging_{version}.ma".format(asset = self.asset["name"], version = next["suffix"])
        rigging_name_mb = "{asset}_rigging_{version}.mb".format(asset=self.asset["name"], version=next["suffix"])
        shading_name = "{asset}_shading_{version}.ma".format(asset = self.asset["name"], version = next["suffix"])
        rigging = nJoin(dir, rigging_name)
        rigging_mb = nJoin(dir, rigging_name_mb)
        shading = nJoin(dir, shading_name)

        try:
            assure_folder_exists(dir)

            lprint("=== copying temp files: ===")
            lprint(self["publish"]["sandbox"]["shading"])
            lprint(self["publish"]["sandbox"]["rigging"])

            lprint("=== into public folders: ===")
            lprint(rigging)
            lprint(shading)

            lprint(self.public_task["master_rigging"]["dir"]["path"])
            lprint(self.public_task["master_shading"]["dir"]["path"])

            shutil.copy2(self["publish"]["sandbox"]["rigging"]["path"], rigging)
            shutil.copy2(self["publish"]["sandbox"]["rigging"]["path_mb"], rigging_mb)
            shutil.copy2(self["publish"]["sandbox"]["rigging"]["path"], self.public_task["master_rigging"]["dir"]["path"])
            shutil.copy2(self["publish"]["sandbox"]["rigging"]["path_mb"], self.public_task["master_rigging_mb"]["dir"]["path"])

            if self.require_shading:
                shutil.copy2(self["publish"]["sandbox"]["shading"]["path"], shading)
                shutil.copy2(self["publish"]["sandbox"]["shading"]["path"], self.public_task["master_shading"]["dir"]["path"])

            lprint("=== done copy ===")
        except:
            raise PublishException("warning: errors during files copying", traceback=traceback.format_exc())

        try:
            data_helper.insert_metadata_version_entry(path=self.public_task["dir"]["metadata_file"]["path"],
                                                      version_number=[next["number"], str(0)],
                                                      author=self["publish"]["public_stamp"]["Author"],
                                                      note=note,
                                                      key='versions',
                                                      add_include=False,
                                                      origin={"rigging": self["publish"]["public_stamp"]["Origin_rigging"],
                                                              "shading": self["publish"]["public_stamp"]["Origin_shading"]
                                                              }
                                                      )
        except:
            raise PublishException("warning: errors during metadata setup", traceback=traceback.format_exc())

        ##############################################################
        # Sync with Signiant
        ##############################################################
        with SyncContext(dependencies=DependencyType.RECURSIVE_PARTIAL, description='Publishing of: {}'.format(self.asset['name']), priority=98) as sync:
            sync.append(self.public_task["master_rigging"]["dir"]["path"])
            sync.append(self.public_task["master_rigging_mb"]["dir"]["path"])
            sync.append(self.public_task["master_shading"]["dir"]["path"])
            sync.append(self.public_task["dir"]["metadata_file"]["path"])

        with SyncContext(dependencies=DependencyType.NONE,description='Publishing of (aux data): {}'.format(self.asset['name']), priority=70) as sync:
            git_repo_path = os.path.join(self.rigging_task['dir']['path'], self.asset['name'])
            sync.append(git_repo_path)
            sync.append(rigging)
            sync.append(rigging_mb)
            sync.append(shading)
        ##############################################################



        try:
            self.public_task["parent"].add_note("Maya: {}".format(note))
        except:
            lprint("warning: failed to save note to ftrack - {}".format(traceback=traceback.format_exc()))
            # raise PublishException("warning: failed to save note to ftrack", traceback=traceback.format_exc())


        return {"public_path": public_path, "next": next}



    def open_scene(self, path):
        from pipeline.variants.pipeline_maya.utils import maya_helper
        reload(maya_helper)
        maya_helper.open_scene(path)


    def _export(self, exportPath):

        id = self["publish"]["sandbox"]["id"]
        target_dir = nJoin(exportPath, id)
        assure_folder_exists(target_dir)

        target_rigging = nJoin(target_dir, '{}_rigging.ma'.format(id))
        target_shading = nJoin(target_dir, '{}_shading.ma'.format(id))
        target_animation = nJoin(target_dir, '{}_animation.ma'.format(id))
        target_test = nJoin(target_dir, '{}_test.ma'.format(id))
        target_data = nJoin(target_dir, '{}_data.json'.format(id))

        errors = []
        try:
            shutil.copy2(self["publish"]["sandbox"]["rigging"]["path"], target_rigging)
        except:
            errors.append("failed to copy rigging file")

        try:
            shutil.copy2(self["publish"]["sandbox"]["shading"]["path"], target_shading)
        except:
            errors.append("failed to copy shading file")

        try:
            shutil.copy2(self["publish"]["sandbox"]["animation"]["path"], target_animation)
        except:
            errors.append("failed to copy animation file")
        # shutil.copy2(self["publish"]["sandbox"]["test"]["path"], target_test)

        exported_data = copy.deepcopy(self["publish"])
        exported_data["sandbox"]["base"] = target_dir
        exported_data["sandbox"]["rigging"]["path"] = target_rigging
        exported_data["sandbox"]["shading"]["path"] = target_shading
        exported_data["sandbox"]["animation"]["path"] = target_animation
        exported_data["sandbox"]["test"]["path"] = target_test

        self["publish"]["sandbox"]["base"] = target_dir
        self["publish"]["sandbox"]["rigging"]["path"] = target_rigging
        self["publish"]["sandbox"]["shading"]["path"] = target_shading
        self["publish"]["sandbox"]["animation"]["path"] = target_animation
        self["publish"]["sandbox"]["test"]["path"] = target_test


        with open(target_data, 'w') as DataFile:
            json.dump(exported_data, DataFile, indent=4)

        lprint("finished exporting data:")
        lprint(json.dumps(exported_data, indent=4))
        return errors

    def _import(self, importPath):
        id = os.path.basename(importPath)
        data_file = nJoin(importPath, "{}_data.json".format(id))
        if not os.path.isfile(data_file):
            raise RuntimeError

        with open(data_file, "r") as DataFile:
            data = json.load(DataFile)

        projects = sb_projects.SB_LibProjects(None)
        time.sleep(0.1)

        project = projects.get_project(data["asset"][0])
        props = project.getAssetType(data["asset"][2])
        asset = props.getAsset(data["asset"][3])
        self.init_asset(asset)
        self["publish"] = copy.deepcopy(data)

        lprint("finished importing data")
        # lprint(json.dumps(self["publish"], indent=4))



def main():
    pass


class Publish_mode(Enum):
    DRY = -1                #do not publish anything
    WET = 1            #publish new asset into the pipeline


def cli_execute(data):
    '''
    data {
        root: string
        project: string
        assetType: string
        asset: string
        note: string
        mode: Publish_mode
        require_animation: bool
    }

    '''

    exec_ = {
        "result" : False,
        "data" : {}
    }

    from libSB import sb_projects
    from libSB.sb_authentication.credentials import SBCredentialManager

    import maya.cmds as cmds

    lprint("Prior to init of SB_LibProjects")

    projects = sb_projects.SB_LibProjects(credentials=SBCredentialManager.batch_credentials)
    # projects.wait_for_online()
    import time
    time.sleep(3)

    lprint("Initiated SB_LibProjects")

    project = projects.get_project(data["project"])
    chars = project.getAssetType(data["assetType"])
    asset = chars.getAsset(data["asset"])

    pub = Publisher(root=data["root"])
    pub.init_asset(asset)
    rig = pub.rigging_versions[0]["number"]
    shd = pub.shading_versions[0]["number"]

    # import pprint
    # pprint.pprint(pub["publish"]['sandbox'])
    #
    #
    # print rig
    # print shd

    # # print os.path.basename(pub.anim_tests_versions[0]["path"])
    # sl = pub.get_selected_versions()
    #
    # dir = sl["anim_test"]["parent"]['dir']["path"]
    # print sl["anim_test"]
    # anim = os.path.basename(sl["anim_test"]["path"])
    # print dir
    # print anim
    #
    # return
    #

    if (data["require_animation"]) and (not pub.anim_tests_versions):
        lprint("No animation to load")
        exec_["data"] = pub["publish"]
        return exec_

    from pipeline.variants.pipeline_maya.utils import maya_helper
    reload(maya_helper)

    maya_helper.new_scene()
    try:
        res = pub.process_rigging(rig, shd)
        if not res: raise Exception()
    except:
        lprint(traceback.format_exc())
        lprint('Failed processing rig')
        exec_["data"] = pub["publish"]
        return exec_


    maya_helper.new_scene()
    try:
        res = pub.process_shading(rig, shd)
        if not res: raise Exception()
    except:
        lprint(traceback.format_exc())
        lprint('Failed processing shading')
        exec_["data"] = pub["publish"]
        return exec_

    maya_helper.new_scene()
    try:
        res = pub.process_animation(load=data["require_animation"])
        if not res: raise Exception()
    except:
        lprint(traceback.format_exc())
        lprint('Failed creating animation scene')
        exec_["data"] = pub["publish"]
        return exec_

    if data["render_preview"]:
        # let's export a take
        try:

            from MBA_SE02.internal.publish.blast import publish

            _data = {
                "id": pub["publish"]["sandbox"]["id"],
                "path": pub["publish"]["sandbox"]["base"],
                "asset_name": pub["publish"]["sandbox"]["asset_name"],
                "animation_camera": pub["publish"].get("animation_camera", False)
            }
            pub_blast = publish.Asset_QA_blast(data=_data)
            res = pub_blast.start()
            if not res: raise Exception()

        except:
            lprint(traceback.format_exc())
            return exec_


    try:
        res = pub.process_test()
        if not res: raise Exception()
    except:
        lprint(traceback.format_exc())
        lprint('Failed processing assembly test')
        exec_["data"] = pub["publish"]
        return exec_


    try:
        # save the test scene
        cmds.file(rename=pub["publish"]["sandbox"]["test"]["path"])
        cmds.file(f=True, s=True, type="mayaAscii", op="v=1")
    except:
        lprint(traceback.format_exc())
        lprint('Failed saving test scene')
        exec_["data"] = pub["publish"]
        return exec_


    if data["render_test"]:
        # let's export a take
        try:

            from MBA_SE02.internal.publish.render import publish

            _data = {
                "id": pub["publish"]["sandbox"]["id"],
                "path": pub["publish"]["sandbox"]["base"],
                "asset_name": pub["publish"]["sandbox"]["asset_name"],
                "all_animation": data.get("all_animation", False),
                "animation_camera" : pub["publish"].get("animation_camera", False)
            }
            pub_blast = publish.Asset_QA_render(data=_data)
            res = pub_blast.start()
            if not res: raise Exception()

        except:
            lprint(traceback.format_exc())
            return exec_


    # print pub['publish']['sandbox']['base']
    if data["mode"] == Publish_mode.WET:
        try:
            res = pub.process_publish(note=data["note"])
            if not res: raise Exception()

            exec_["result"] = True
            return exec_

        except:
            lprint(traceback.format_exc())
            lprint('Failed publishing asset')
            exec_["data"] = pub["publish"]
            return exec_


    # completed with zero errors!
    exec_["result"] = True
    exec_["data"] = pub["publish"]
    return exec_




if __name__ == '__main__':
    main()

