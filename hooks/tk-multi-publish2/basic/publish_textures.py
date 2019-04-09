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
import pprint

import sgtk
from sgtk.util.filesystem import ensure_folder_exists


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


HookBaseClass = sgtk.get_hook_baseclass()


class SubstancePainterTexturesPublishPlugin(HookBaseClass):
    """
    Plugin for publishing an open Substance Painter session.

    This hook relies on functionality found in the base file publisher hook in
    the publish2 app and should inherit from it in the configuration. The hook
    setting for this plugin should look something like this::

        hook: "{self}/publish_file.py:{engine}/tk-multi-publish2/basic/publish_session.py"

    """

    # NOTE: The plugin icon and name are defined by the base file plugin.

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """

        loader_url = (
            "https://support.shotgunsoftware.com/hc/en-us/articles/219033078"
        )

        return """
        Publishes the file to Shotgun. A <b>Publish</b> entry will be
        created in Shotgun which will include a reference to the file's current
        path on disk. If a publish template is configured, a copy of the
        current session will be copied to the publish template path which
        will be the file that is published. Other users will be able to access
        the published file via the <b><a href='%s'>Loader</a></b> so long as
        they have access to the file's location on disk.

        If the session has not been saved, validation will fail and a button
        will be provided in the logging output to save the file.

        <h3>File versioning</h3>
        If the filename contains a version number, the process will bump the
        file to the next version after publishing.

        The <code>version</code> field of the resulting <b>Publish</b> in
        Shotgun will also reflect the version number identified in the filename
        The basic worklfow recognizes the following version formats by default:

        <ul>
        <li><code>filename.v###.ext</code></li>
        <li><code>filename_v###.ext</code></li>
        <li><code>filename-v###.ext</code></li>
        </ul>

        After publishing, if a version number is detected in the work file, the
        work file will automatically be saved to the next incremental version
        number. For example, <code>filename.v001.ext</code> will be published
        and copied to <code>filename.v002.ext</code>

        If the next incremental version of the file already exists on disk, the
        validation step will produce a warning, and a button will be provided
        in the logging output which will allow saving the session to the next
        available version number prior to publishing.

        <br><br><i>NOTE: any amount of version number padding is supported. for
        non-template based workflows.</i>

        <h3>Overwriting an existing publish</h3>
        In non-template workflows, a file can be published multiple times,
        however only the most recent publish will be available to other users.
        Warnings will be provided during validation if there are previous
        publishes.
        """ % (
            loader_url,
        )

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to receive
        through the settings parameter in the accept, validate, publish and
        finalize methods.

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

        # inherit the settings from the base publish plugin
        base_settings = super(SubstancePainterTexturesPublishPlugin, self).settings or {}

        # settings specific to this class
        substancepainter_publish_settings = {
            "Publish Template": {
                "type": "template",
                "default": None,
                "description": "Template path for published texture folder. "
                "Should correspond to a template defined in "
                "templates.yml.",
            }
        }

        # update the base settings
        base_settings.update(substancepainter_publish_settings)

        return base_settings

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for 
        example ["substancepainter.*", "file.substancepainter"]
        """
        return ["substancepainter.textures"]

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin. Only items matching the filters defined via 
        the item_filters property will be presented to this method.

        A publish task will be generated for each item accepted here. Returns a
        dictionary with the following booleans:

            - accepted: Indicates if the plugin is interested in this value at
                all. Required.
            - enabled: If True, the plugin will be enabled in the UI, otherwise
                it will be disabled. Optional, True by default.
            - visible: If True, the plugin will be visible in the UI, otherwise
                it will be hidden. Optional, True by default.
            - checked: If True, the plugin will be checked in the UI, otherwise
                it will be unchecked. Optional, True by default.

        :param settings: Dictionary of Settings. The keys are strings, matching
                         the keys returned in the settings property. The values
                         are `Setting` instances.
        :param item: Item to process

        :returns: dictionary with boolean keys accepted, required and enabled
        """

        # if a publish template is configured, disable context change. This
        # is a temporary measure until the publisher handles context switching
        # natively.
        if settings.get("Publish Template").value:
            item.context_change_allowed = False

        self.logger.info(
            "Substance Painter '%s' plugin accepted the publish textures."
            % (self.name,)
        )
        return {"accepted": True, "checked": True}

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish. Returns a
        boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
                         the keys returned in the settings property. The values 
                         are `Setting` instances.
        :param item: Item to process
        :returns: True if item is valid, False otherwise.
        """

        publisher = self.parent

        # populate the publish template on the item if found
        publish_template_setting = settings.get("Publish Template")
        publish_template = publisher.engine.get_template_by_name(publish_template_setting.value)
        if publish_template:
            item.properties["publish_template"] = publish_template
        else:
            error_msg = "Validation failed. Publish template not found"
            self.logger.error(error_msg)
            raise Exception(error_msg)

        export_path = _export_path()
        if not os.path.isdir(export_path):
            error_msg = "Validation failed. Export path does not exist on disk."
            self.logger.error(error_msg)
            raise Exception(error_msg)

        item.properties["export_path"] = export_path

        textures = os.listdir(export_path)
        textures = [os.path.join(export_path, texture) for texture in textures]
        textures = [texture for texture in textures if os.path.isfile(texture)]
        self.logger.debug("Files in export path: %s" % textures)

        if not textures:
            error_msg = "Validation failed. Export path does not contain any texture."
            self.logger.error(error_msg)
            raise Exception(error_msg)

        item.properties["textures"] = textures

        return True


    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
                         the keys returned in the settings property.
                         The values are `Setting` instances.
        :param item: Item to process
        """

        publisher = self.parent

        publish_template = item.properties["publish_template"]
        publish_type =  item.properties["publish_type"]

        # Get fields from the current context
        fields = {}
        ctx_fields = self.parent.context.as_template_fields(publish_template)
        fields.update(ctx_fields)

        context_entity_type = self.parent.context.entity['type']
        publish_name = context_entity_type + "_textures"

        existing_publishes = self._find_publishes(self.parent.context, publish_name, publish_type)
        version = max([p["version_number"] for p in existing_publishes] or [0]) + 1
        fields["version"] = version

        publish_path = publish_template.apply_fields(fields)
        publish_path = sgtk.util.ShotgunPath.normalize(publish_path)

        # make sure destination folder exists
        ensure_folder_exists(publish_path)

        textures = item.properties["textures"]

        for src in textures:
            _, filenamefile = os.path.split(src)
            dst = os.path.join(publish_path, filenamefile)
            sgtk.util.filesystem.copy_file(src, dst) 

        self.logger.info("A Publish will be created in Shotgun and linked to:")
        self.logger.info("  %s" % (publish_path,))

        # arguments for publish registration

        # add dependencies
        dependency_paths = []
        if "sg_publish_path" in item.parent.properties:
            self.logger.debug("Added dependency: %s" % item.parent.properties.sg_publish_path)
            dependency_paths.append(item.parent.properties.sg_publish_path)

        self.logger.info("Registering publish...")

        publish_data = {
            "tk": publisher.sgtk,
            "context": item.context,
            "comment": item.description,
            "path": publish_path,
            "name": publish_name,
            "version_number": version,
            "thumbnail_path": item.get_thumbnail_as_path(),
            "published_file_type": publish_type,
            "dependency_paths": dependency_paths,
        }

        # log the publish data for debugging
        self.logger.debug(
            "Populated Publish data...",
            extra={
                "action_show_more_info": {
                    "label": "Publish Data",
                    "tooltip": "Show the complete Publish data dictionary",
                    "text": "<pre>%s</pre>" % (pprint.pformat(publish_data),)
                }
            }
        )

        # create the publish and stash it in the item properties for other
        # plugins to use.
        item.properties["sg_publish_data"] = sgtk.util.register_publish(
            **publish_data)

        # inject the publish path such that children can refer to it when
        # updating dependency information
        item.properties["sg_publish_path"] = publish_path

        self.logger.info("Publish registered!")

        # now that we've published. keep a handle on the path that was published
        item.properties["path"] = publish_path


    def finalize(self, settings, item):
        """
        Execute the finalization pass. This pass executes once all the publish
        tasks have completed, and can for example be used to version up files.

        :param settings: Dictionary of Settings. The keys are strings, matching
                         the keys returned in the settings property.
                         The values are `Setting` instances.
        :param item: Item to process
        """

        # do the base class finalization
        super(SubstancePainterTexturesPublishPlugin, self).finalize(settings, item)

    def _find_publishes(self, ctx, publish_name, publish_type):
        """
        Given a context, publish name and type, find all publishes from Shotgun
        that match.
        
        :param ctx:             Context to use when looking for publishes
        :param publish_name:    The name of the publishes to look for
        :param publish_type:    The type of publishes to look for
        
        :returns:               A list of Shotgun publish records that match the search
                                criteria        
        """
        publish_entity_type = sgtk.util.get_published_file_entity_type(self.parent.sgtk)
        if publish_entity_type == "PublishedFile":
            publish_type_field = "published_file_type.PublishedFileType.code"
        else:
            publish_type_field = "tank_type.TankType.code"
        
        # construct filters from the context:
        filters = [["project", "is", ctx.project]]
        if ctx.entity:
            filters.append(["entity", "is", ctx.entity])
        if ctx.task:
            filters.append(["task", "is", ctx.task])
            
        # add in name & type:
        if publish_name:
            filters.append(["name", "is", publish_name])
        if publish_type:
            filters.append([publish_type_field, "is", publish_type])
            
        # retrieve a list of all matching publishes from Shotgun:
        sg_publishes = []
        try:
            query_fields = ["version_number"]
            sg_publishes = self.parent.shotgun.find(publish_entity_type, filters, query_fields)
        except Exception, e:
            self.logger.error("Failed to find publishes of type '%s', called '%s', for context %s: %s" 
                              % (publish_name, publish_type, ctx, e))
        return sg_publishes


def _export_path():
    """
    Return the path to the current session
    :return:
    """
    engine = sgtk.platform.current_engine()

    # get the path to the current file
    path = engine.app.get_project_export_path()

    if isinstance(path, unicode):
        path = path.encode("utf-8")

    return path
