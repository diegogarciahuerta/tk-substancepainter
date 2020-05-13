# Copyright (c) 2017 Shotgun Software Inc.
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


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


HookBaseClass = sgtk.get_hook_baseclass()


SESSION_PUBLISHED_TYPE = "Substance Painter Project File"


class SubstancePainterSessionCollector(HookBaseClass):
    """
    Collector that operates on the substance painter session. Should inherit 
    from the basic collector hook.
    """

    @property
    def settings(self):
        """
        Dictionary defining the settings that this collector expects to receive
        through the settings parameter in the process_current_session and
        process_file methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """

        # grab any base class settings
        collector_settings = (
            super(SubstancePainterSessionCollector, self).settings or {}
        )

        # settings specific to this collector
        substancepainter_session_settings = {
            "Work Template": {
                "type": "template",
                "default": None,
                "description": "Template path for artist work files. Should "
                "correspond to a template defined in "
                "templates.yml. If configured, is made available"
                "to publish plugins via the collected item's "
                "properties. ",
            },
            "Work Export Template": {
                "type": "template",
                "default": None,
                "description": "Template path for where the textures are "
                "exported. Should correspond to a template defined in "
                "templates.yml.",
            },
            "Publish Textures as Folder": {
                "type": "bool",
                "default": True,
                "description": "Publish Substance Painter textures as a folder."
                "If true (default) textures will be all exported"
                " together as a folder publish."
                "If false, each texture will be exported and"
                " published as each own version stream.",
            },
        }

        # update the base settings with these settings
        collector_settings.update(substancepainter_session_settings)

        return collector_settings

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the current session open in Substance Painter and parents a 
        subtree of items under the parent_item passed in.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance

        """

        # create an item representing the current substance painter session
        item = self.collect_current_substancepainter_session(settings, parent_item)

        if item:
            publish_as_folder_setting = settings.get("Publish Textures as Folder")
            if publish_as_folder_setting and publish_as_folder_setting.value:
                resource_items = self.collect_textures_as_folder(settings, item)
            else:
                resource_items = self.collect_textures(settings, item)

    def get_export_path(self, settings):
        publisher = self.parent

        work_template = None
        work_template_setting = settings.get("Work Template")
        if work_template_setting:
            work_template = publisher.engine.get_template_by_name(
                work_template_setting.value
            )

            self.logger.debug("Work template defined for Substance Painter collection.")

        work_export_template = None
        work_export_template_setting = settings.get("Work Export Template")
        if work_export_template_setting:
            self.logger.debug(
                "Work Export template settings: %s" % work_export_template_setting
            )

            work_export_template = publisher.engine.get_template_by_name(
                work_export_template_setting.value
            )

            self.logger.debug(
                "Work Export template defined for Substance Painter collection."
            )

        if work_export_template and work_template:
            path = publisher.engine.app.get_current_project_path()
            fields = work_template.get_fields(path)
            export_path = work_export_template.apply_fields(fields)

            self.logger.debug("Work Export Path is: %s " % export_path)

            return export_path

    def collect_textures_as_folder(self, settings, parent_item):
        publisher = self.parent
        engine = publisher.engine

        self.logger.debug("Exporting textures as a folder...")

        export_path = self.get_export_path(settings)
        if not export_path:
            export_path = engine.app.get_project_export_path()

        engine.show_busy(
            "Exporting textures",
            "Texture are being exported so they can " "be published.\n\nPlease wait...",
        )

        map_export_info = engine.app.export_document_maps(export_path)
        engine.clear_busy()

        self.logger.debug("Collecting exported textures...")

        if export_path:
            textures = os.listdir(export_path)
            if textures:
                textures_item = parent_item.create_item(
                    "substancepainter.textures",
                    "Textures",
                    "Substance Painter Textures",
                )

                icon_path = os.path.join(
                    self.disk_location, os.pardir, "icons", "texture.png"
                )

                textures_item.set_icon_from_path(icon_path)

                textures_item.properties["path"] = export_path
                textures_item.properties["publish_type"] = "Texture Folder"

    def collect_textures(self, settings, parent_item):
        publisher = self.parent
        engine = sgtk.platform.current_engine()

        self.logger.debug("Exporting textures...")

        export_path = self.get_export_path(settings)
        if not export_path:
            export_path = engine.app.get_project_export_path()

        engine.show_busy(
            "Exporting textures",
            "Texture are being exported so they can " "be published.\n\nPlease wait...",
        )

        map_export_info = engine.app.export_document_maps(export_path)
        engine.clear_busy()

        self.logger.debug("Collecting exported textures...")

        icon_path = os.path.join(self.disk_location, os.pardir, "icons", "texture.png")

        for texture_set_name, texture_set in map_export_info.iteritems():
            for texture_id, texture_file in texture_set.iteritems():
                if os.path.exists(texture_file):
                    _, filenamefile = os.path.split(texture_file)
                    texture_name, _ = os.path.splitext(filenamefile)

                    self.logger.debug("texture: %s" % texture_file)
                    textures_item = parent_item.create_item(
                        "substancepainter.texture", "Texture", texture_name
                    )
                    textures_item.set_icon_from_path(icon_path)

                    textures_item.properties["path"] = texture_file
                    textures_item.properties["publish_type"] = "Texture"

    def collect_current_substancepainter_session(self, settings, parent_item):
        """
        Creates an item that represents the current substance painter session.

        :param parent_item: Parent Item instance

        :returns: Item of type substancepainter.session
        """

        publisher = self.parent
        engine = sgtk.platform.current_engine()

        # get the path to the current file
        path = engine.app.get_current_project_path()

        # determine the display name for the item
        if path:
            file_info = publisher.util.get_file_path_components(path)
            display_name = file_info["filename"]
        else:
            display_name = "Current Substance Painter Session"

        # create the session item for the publish hierarchy
        session_item = parent_item.create_item(
            "substancepainter.session", "Substance Painter Session", display_name,
        )

        # get the icon path to display for this item
        icon_path = os.path.join(self.disk_location, os.pardir, "icons", "session.png")
        session_item.set_icon_from_path(icon_path)

        # if a work template is defined, add it to the item properties so
        # that it can be used by attached publish plugins
        work_template_setting = settings.get("Work Template")
        if work_template_setting:

            work_template = publisher.engine.get_template_by_name(
                work_template_setting.value
            )

            # store the template on the item for use by publish plugins. we
            # can't evaluate the fields here because there's no guarantee the
            # current session path won't change once the item has been created.
            # the attached publish plugins will need to resolve the fields at
            # execution time.
            session_item.properties["work_template"] = work_template
            session_item.properties["publish_type"] = SESSION_PUBLISHED_TYPE

            self.logger.debug("Work template defined for session.")

        self.logger.info("Collected current Substance Painter session")

        return session_item
