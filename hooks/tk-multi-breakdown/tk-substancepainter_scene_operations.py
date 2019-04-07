# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

import sgtk
from sgtk.errors import TankError


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


HookBaseClass = sgtk.get_hook_baseclass()


"""
tk-breakdown requires item['node'] to be a str. This is what is displayed in 
the list of recognized items to update. We want to add metadata to each item
as what we want to display as name is not the actual item to update.
In our case, we want to display the nguiname of the resrouce, color in green 
the items in used in the project, and also the resource id for reference.
As a str is required we are forced to inherit from str instead of the more
python friendly object + __repr__ magic method.
"""
class SubstancePainterResource(str):
    def __new__(cls, resource, key, in_use, nice_name):
        text = "(%s) - <b><span style='color:%s'>%s</b></span><br/><nobr><sub>%s</sub></nobr>" % ("Used" if in_use else "Not Used", "green" if in_use else "gray", nice_name, key)
        obj = str.__new__(cls, text)
        obj.resource = resource
        obj.in_use = in_use
        obj.key = key
        obj.nice_name = nice_name
        return obj

class BreakdownSceneOperations(HookBaseClass):
    """
    Breakdown operations for Substance Painter.

    This implementation handles detection of Substance Painter resources, 
    that have been loaded with the tk-multi-loader2 toolkit app.
    """

    def sort_by_used_and_guiName(a, b):
        pass
    def scan_scene(self):
        """
        The scan scene method is executed once at startup and its purpose is
        to analyze the current scene and return a list of references that are
        to be potentially operated on.

        The return data structure is a list of dictionaries. Each scene 
        reference that is returned should be represented by a dictionary with 
        three keys:

        - "attr": The filename attribute of the 'node' that is to be operated
           on. Most DCCs have a concept of a node, attribute, path or some other
           way to address a particular object in the scene.
        - "type": The object type that this is. This is later passed to the
           update method so that it knows how to handle the object.
        - "path": Path on disk to the referenced object.

        Toolkit will scan the list of items, see if any of the objects matches
        any templates and try to determine if there is a more recent version
        available. Any such versions are then displayed in the UI as out of 
        date.
        """

        # We find the resources to update by checking the tk-multi-loader 
        # project settings that the tk app have been setting as it was used
        # to import resouces from published files.

        refs = []
        engine = sgtk.platform.current_engine()
        engine.log_debug("tk-multi-breakdown called")

        resources = engine.app.get_project_settings("tk-multi-loader2") or {}
        engine.log_debug("tk-multi-breakdown | resources: %s" % resources)

        in_use_resources = engine.app.document_resources()
        in_use_resources_versions = []
        for key in in_use_resources:
            resource_info = engine.app.get_resource_info(key)
            in_use_resources_versions.append(resource_info['version'])

        for key in resources.keys():
            resource_info = engine.app.get_resource_info(key)

            if resource_info:
                in_use = resource_info['version'] in in_use_resources_versions
                nice_name = resource_info['guiName']

                ref_path = resources[key]
                ref_path = ref_path.replace("/", os.path.sep)
                
                # see SubstancePainterResource for explanation why we use
                # a custom class
                refs.append(
                    {
                        "type": "file",
                        "path": ref_path,
                        "node": SubstancePainterResource(resource_info, key, in_use, nice_name) # "(%s) - <b><span style='color:%s'>%s</b></span><br/><nobr><sub>%s</sub></nobr>" % ("Used" if in_use else "Not Used", "green" if in_use else "gray", nice_name, key),
                    }
                )

        return refs

    def update(self, items):
        """
        Perform replacements given a number of scene items passed from the app.

        Once a selection has been performed in the main UI and the user clicks
        the update button, this method is called.

        The items parameter is a list of dictionaries on the same form as was
        generated by the scan_scene hook above. The path key now holds
        the that each attribute should be updated *to* rather than the current
        path.
        """

        engine = self.parent.engine
        engine.log_debug("%s" % items)

        for i in items:
            resource_info = i["node"]
            resource_key = resource_info.key
            node_type = i["type"]
            new_path = i["path"]
            
            if node_type == "file":
                engine.log_debug(
                    "Resource %s: Updating to file: %s" % (resource_key, new_path)
                )
                resource_info = engine.app.get_resource_info(resource_key)
                for usage in resource_info['usages']:
                    engine.log_debug("Importing for usage: %s" % usage)
                    new_resource = engine.app.import_project_resource(new_path, usage, "Shotgun")
                    engine.log_debug("Updating usage: %s" % usage)
                    engine.log_debug("existing url: %s" % resource_key)
                    engine.log_debug("new_resource url: %s" % new_resource)
                    engine.app.update_document_resources(resource_key, new_resource['url'])
                    engine.log_debug(
                        "Resource %s: Updated usage: %s" % (new_resource['url'], usage)
                    )



