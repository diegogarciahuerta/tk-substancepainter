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


RESOURCE_IN_USE_COLOR = "#e7a81d"
RESOURCE_NOT_IN_USE_COLOR = "gray"


class SubstancePainterResource(str):
    """
    Helper Class to store metadata per update item.

    tk-multi-breakdown requires item['node'] to be a str. This is what is displayed in 
    the list of recognized items to update. We want to add metadata to each item
    as what we want to display as name is not the actual item to update.
    In our case, we want to display the nguiname of the resrouce, color in green 
    the items in used in the project, and also the resource id for reference.
    As a str is required we are forced to inherit from str instead of the more
    python friendly object + __repr__ magic method.
    """

    def __new__(cls, resource, in_use, nice_name):
        text = (
            "<span style='color:%s'><b>(%s) - %s</b></span>"
            "<br/><nobr><sub>%s</sub></nobr>"
            % (
                RESOURCE_IN_USE_COLOR if in_use else RESOURCE_NOT_IN_USE_COLOR,
                "Used" if in_use else "Not Used",
                nice_name,
                resource["url"],
            )
        )
        obj = str.__new__(cls, text)
        obj.resource = resource
        obj.in_use = in_use
        obj.nice_name = nice_name
        return obj


class BreakdownSceneOperations(HookBaseClass):
    """
    Breakdown operations for Substance Painter.

    This implementation handles detection of Substance Painter resources, 
    that have been loaded with the tk-multi-loader2 toolkit app.
    """

    def _sort_by_used_and_nice_name(self, a, b):
        # sort by use
        if a["node"].in_use and not b["node"].in_use:
            return -1

        if not a["node"].in_use and b["node"].in_use:
            return 1

        # sort by version
        return cmp(a["node"].resource["version"], b["node"].resource["version"])

    def _document_resources_by_version(self, engine):
        resources_in_project = {}

        in_use_resources = engine.app.document_resources()
        for in_use_resource in in_use_resources:
            res_info = engine.app.get_resource_info(in_use_resource)
            if res_info:
                resources_in_project[res_info["version"]] = res_info

        return resources_in_project

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

        # We identify resrouces to update by their unique id that is the
        # resource version. At this stage it is not clear if this is a decent
        # assumption or not, but found that the resource url would include
        # something like project0 or project2, and the actual resource was
        # the same, so needed to find an alternative as a unique id for the
        # resource.

        refs = []
        engine = sgtk.platform.current_engine()

        resources_in_project = self._document_resources_by_version(engine)
        resources = engine.app.get_project_settings("tk-multi-loader2") or {}

        for url in resources.keys():
            res_info = engine.app.get_resource_info(url)

            if res_info:
                in_use = res_info["version"] in resources_in_project
                nice_name = res_info["guiName"]

                ref_path = resources[url]
                ref_path = ref_path.replace("/", os.path.sep)

                # see SubstancePainterResource for explanation why we use
                # a custom class
                refs.append(
                    {
                        "type": "file",
                        "path": ref_path,
                        "node": SubstancePainterResource(res_info, in_use, nice_name),
                    }
                )

        if refs:
            refs.sort(self._sort_by_used_and_nice_name)

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

        engine = sgtk.platform.current_engine()

        resources_in_project = self._document_resources_by_version(engine)

        for i in items:
            node = i["node"]
            node_type = i["type"]
            new_path = i["path"]

            if node_type == "file":
                # here we identify from the existing resources in the scene
                # which one is the one to update. We identify it by the version
                # which acts as a unique id per resource.
                res_info = node.resource
                if res_info["version"] in resources_in_project:
                    res_info = resources_in_project[res_info["version"]]

                url = res_info["url"]

                for usage in res_info["usages"]:
                    new_url = engine.app.import_project_resource(
                        new_path, usage, "Shotgun"
                    )

                    engine.log_debug("Updating usage: %s" % usage)
                    engine.log_debug("Existing resource url: %s" % url)
                    engine.log_debug("New resource url: %s" % new_url)

                    engine.app.update_document_resources(url, new_url)

                    engine.log_debug("Updated usage: %s" % usage)
