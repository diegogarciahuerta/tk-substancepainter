# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""A Substance Painter engine for Tank.
https://www.allegorithmic.com/products/substance-painter
"""

import os
import sys
import time
import inspect
import logging
import traceback
import six
from functools import wraps
from distutils.version import LooseVersion

import tank
from tank.log import LogManager
from tank.platform import Engine
from tank.platform.constants import SHOTGUN_ENGINE_NAME
from tank.platform.constants import TANK_ENGINE_INIT_HOOK_NAME


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


# env variable that control if to show the compatibility warning dialog
# when Substance Painter software version is above the tested one.
SHOW_COMP_DLG = "SGTK_COMPATIBILITY_DIALOG_SHOWN"

MINIMUM_SUPPORTED_VERSION = "2018.3"


def to_new_version_system(version):
    """
    Converts a version string into a new style version.

    New version system was introduced in version 2020.1, that became
    version 6.1.0, so we need to do some magic to normalize versions.
    https://docs.substance3d.com/spdoc/version-2020-1-6-1-0-194216357.html

    The way we support this new version system is to use LooseVersion for
    version comparisons. We modify the major version if the version is higher
    than 2017.1.0 for the version to become in the style of 6.1, by literally
    subtracting 2014 to the major version component.
    This leaves us always with a predictable version system:
        2.6.2  -> 2.6.2 (really old version)
        2017.1 -> 3.1
        2018.0 -> 4.0
        2020.1 -> 6.1 (newer version system starts)
        6.2    -> 6.2 ...

    2017.1.0 represents the first time the 2k style version was introduced
    according to:
    https://docs.substance3d.com/spdoc/all-changes-188973073.html

    Note that this change means that the LooseVersion is good for comparisons
    but NEVER for printing, it would simply print the same version as
    LooseVersion does not support rebuilding of the version string from it's
    components
    """

    version = LooseVersion(str(version))

    if version >= LooseVersion("2017.1"):
        version.version[0] -= 2014
    return version


# logging functionality
def display_error(msg):
    t = time.asctime(time.localtime())
    print("%s - Shotgun Error | Substance Painter engine | %s " % (t, msg))


def display_warning(msg):
    t = time.asctime(time.localtime())
    print("%s - Shotgun Warning | Substance Painter engine | %s " % (t, msg))


def display_info(msg):
    t = time.asctime(time.localtime())
    print("%s - Shotgun Info | Substance Painter engine | %s " % (t, msg))


def display_debug(msg):
    if os.environ.get("TK_DEBUG") == "1":
        t = time.asctime(time.localtime())
        print("%s - Shotgun Debug | Substance Painter engine | %s " % (t, msg))


# methods to support the state when the engine cannot start up
# for example if a non-tank file is loaded in Substance Painter we load the
# project context if exists, so we give a chance to the user to at least
# do the basics operations.


def refresh_engine(scene_name, prev_context):
    """
    refresh the current engine
    """

    engine = tank.platform.current_engine()

    if not engine:
        # If we don't have an engine for some reason then we don't have
        # anything to do.
        sys.stdout.write("refresh_engine | no engine!\n")
        return

    # This is a File->New call, so we just leave the engine in the current
    # context and move on.
    if scene_name in ("", "Untitled.spp"):
        if prev_context and prev_context != engine.context:
            engine.change_context(prev_context)

        # shotgun menu may have been removed, so add it back in if its not
        # already there.
        engine.create_shotgun_menu()
        return

    # determine the tk instance and ctx to use:
    tk = engine.sgtk

    # loading a scene file
    new_path = os.path.abspath(scene_name)

    # this file could be in another project altogether, so create a new
    # API instance.
    try:
        # and construct the new context for this path:
        tk = tank.tank_from_path(new_path)
        ctx = tk.context_from_path(new_path, prev_context)
    except tank.TankError as e:
        try:
            # could not detect context from path, will use the project context
            # for menus if it exists
            ctx = engine.sgtk.context_from_entity_dictionary(engine.context.project)
            message = (
                "Shotgun Substance Painter Engine could not detect "
                "the context\n from the project loaded. "
                "Shotgun menus will be reset \n"
                "to the project '%s' "
                "context."
                "\n" % engine.context.project.get("name")
            )
            engine.show_warning(message)

        except tank.TankError as e:
            (exc_type, exc_value, exc_traceback) = sys.exc_info()
            message = ""
            message += "Shotgun Substance Painter Engine cannot be started:.\n"
            message += "Please contact support@shotgunsoftware.com\n\n"
            message += "Exception: %s - %s\n" % (exc_type, exc_value)
            message += "Traceback (most recent call last):\n"
            message += "\n".join(traceback.format_tb(exc_traceback))

            # disabled menu, could not get project context
            engine.create_shotgun_menu(disabled=True)
            engine.show_error(message)
            return

    if ctx != engine.context:
        engine.change_context(ctx)

    # shotgun menu may have been removed,
    # so add it back in if its not already there.
    engine.create_shotgun_menu()


class SubstancePainterEngine(Engine):
    """
    Toolkit engine for Substance Painter.
    """

    def __init__(self, *args, **kwargs):
        """
        Engine Constructor
        """
        self._qt_app = None
        self._dcc_app = None
        self._menu_generator = None
        self._event_callbacks = {}

        Engine.__init__(self, *args, **kwargs)

    @property
    def app(self):
        """
        Represents the DDC app connection
        """
        return self._dcc_app

    def show_message(self, msg, level="info"):
        """
        Displays a dialog with the message according to  the severity level
        specified.
        """
        if self._qt_app_central_widget:
            from sgtk.platform.qt5 import QtWidgets, QtGui, QtCore

            level_icon = {
                "info": QtWidgets.QMessageBox.Information,
                "error": QtWidgets.QMessageBox.Critical,
                "warning": QtWidgets.QMessageBox.Warning,
            }

            dlg = QtWidgets.QMessageBox(self._qt_app_central_widget)
            dlg.setIcon(level_icon[level])
            dlg.setText(msg)
            dlg.setWindowTitle("Shotgun Substance Painter Engine")
            dlg.setWindowFlags(dlg.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
            dlg.show()
            dlg.exec_()

    def show_error(self, msg):
        """
        Displays an error dialog message
        """
        self.show_message(msg, level="error")

    def show_warning(self, msg):
        """
        Displays a warning dialog message
        """
        self.show_message(msg, level="warning")

    def show_info(self, msg):
        """
        Displays an informative dialog message
        """
        self.show_message(msg, level="info")

    def __get_platform_resource_path(self, filename):
        """
        Returns the full path to the given platform resource file or folder.
        Resources reside in the core/platform/qt folder.
        :return: full path
        """
        tank_platform_folder = os.path.abspath(inspect.getfile(tank.platform))
        return os.path.join(tank_platform_folder, "qt", filename)

    @property
    def register_toggle_debug_command(self):
        """
        Indicates whether the engine should have a toggle debug logging
        command registered during engine initialization.
        :rtype: bool
        """
        return True

    def __toggle_debug_logging(self):
        """
        Toggles global debug logging on and off in the log manager.
        This will affect all logging across all of toolkit.
        """
        self.logger.debug(
            "calling substance painer with debug: %s" % LogManager().global_debug
        )

        # flip debug logging
        LogManager().global_debug = not LogManager().global_debug
        if self.app:
            self.app.toggle_debug_logging(LogManager().global_debug)

    def __open_log_folder(self):
        """
        Opens the file system folder where log files are being stored.
        """
        self.log_info("Log folder is located in '%s'" % LogManager().log_folder)

        if self.has_ui:
            # only import QT if we have a UI
            from sgtk.platform.qt import QtGui, QtCore

            url = QtCore.QUrl.fromLocalFile(LogManager().log_folder)
            status = QtGui.QDesktopServices.openUrl(url)
            if not status:
                self.log_error("Failed to open folder!")

    def __register_open_log_folder_command(self):
        """
        # add a 'open log folder' command to the engine's context menu
        # note: we make an exception for the shotgun engine which is a
        # special case.
        """
        if self.name != SHOTGUN_ENGINE_NAME:
            icon_path = self.__get_platform_resource_path("folder_256.png")

            self.register_command(
                "Open Log Folder",
                self.__open_log_folder,
                {
                    "short_name": "open_log_folder",
                    "icon": icon_path,
                    "description": (
                        "Opens the folder where log files are " "being stored."
                    ),
                    "type": "context_menu",
                },
            )

    def __register_reload_command(self):
        """
        Registers a "Reload and Restart" command with the engine if any
        running apps are registered via a dev descriptor.
        """
        from tank.platform import restart

        self.register_command(
            "Reload and Restart",
            restart,
            {
                "short_name": "restart",
                "icon": self.__get_platform_resource_path("reload_256.png"),
                "type": "context_menu",
            },
        )

    @property
    def context_change_allowed(self):
        """
        Whether the engine allows a context change without the need for a
        restart.
        """
        return True

    @property
    def host_info(self):
        """
        :returns: A dictionary with information about the application hosting
                  his engine.

        The returned dictionary is of the following form on success:

            {
                "name": "SubstancePainter",
                "version": "2018.3.1",
            }

        The returned dictionary is of following form on an error preventing
        the version identification.

            {
                "name": "SubstancePainter",
                "version: "unknown"
            }
        """

        host_info = {"name": "SubstancePainter", "version": "unknown"}
        try:
            painter_version = self._dcc_app.get_application_version()
            host_info["version"] = painter_version
        except:
            pass
        return host_info

    def process_request(self, method, **kwargs):
        """
        This method takes care of requests from the dcc app.
        """
        self.logger.info("process_request. method: %s | kwargs: %s" % (method, kwargs))

        if method == "DISPLAY_MENU":
            menu_position = None
            clicked_info = kwargs.get("clickedPosition")
            if clicked_info:
                menu_position = [clicked_info["x"], clicked_info["y"]]

            self.display_menu(pos=menu_position)

        if method == "NEW_PROJECT_CREATED":
            path = kwargs.get("path")
            change_context = self.get_setting("change_context_on_new_project", False)
            if change_context:
                refresh_engine(path, self.context)
            else:
                self.logger.info(
                    "change_context_on_new_project is off so context won't be changed."
                )

        if method == "PROJECT_OPENED":
            path = kwargs.get("path")
            refresh_engine(path, self.context)

        if method == "QUIT":
            if self._qt_app:
                self.destroy_engine()
                self._qt_app.quit()

        if method in self._event_callbacks:
            self.logger.info("About to run callbacks for %s" % method)
            for fn in self._event_callbacks[method]:
                self.logger.info("  callback: %s" % fn)
                fn(**kwargs)

    def register_event_callback(self, event_type, callback_fn):
        if event_type not in self._event_callbacks:
            self._event_callbacks[event_type] = []
        self._event_callbacks[event_type].append(callback_fn)

    def unregister_event_callback(self, event_type, callback_fn):
        if event_type not in self._event_callbacks:
            return

        if callback_fn in self._event_callbacks[event_type]:
            self._event_callbacks[event_type].remove(callback_fn)

    def pre_app_init(self):
        """
        Initializes the Substance Painter engine.
        """

        self.logger.debug("%s: Initializing...", self)

        self.tk_substancepainter = self.import_module("tk_substancepainter")

        self.init_qt_app()

        port = os.environ["SGTK_SUBSTANCEPAINTER_ENGINE_PORT"]
        url = "ws://localhost:%s" % port

        engine_client_class = self.tk_substancepainter.application.EngineClient
        self._dcc_app = engine_client_class(self, parent=self._qt_app, url=url)

        # check that we are running an ok version of Substance Painter
        current_os = sys.platform
        if current_os not in ["darwin", "win32", "linux64"]:
            raise tank.TankError(
                "The current platform is not supported!"
                " Supported platforms "
                "are Mac, Linux 64 and Windows 64."
            )

        # default menu name is Shotgun but this can be overridden
        # in the configuration to be sgtk in case of conflicts
        self._menu_name = "Shotgun"
        if self.get_setting("use_sgtk_as_menu_name", False):
            self._menu_name = "Sgtk"

        painter_version_str = self._dcc_app.get_application_version()

        # New version system was introduced in version 2020.1, that became
        # version 6.1.0, so we need to do some magic to normalize versions.
        # https://docs.substance3d.com/spdoc/version-2020-1-6-1-0-194216357.html
        painter_version = to_new_version_system(painter_version_str)
        painter_min_supported_version = to_new_version_system(MINIMUM_SUPPORTED_VERSION)

        if painter_version < painter_min_supported_version:
            msg = (
                "Shotgun integration is not compatible with Substance Painter versions"
                " older than %s" % MINIMUM_SUPPORTED_VERSION
            )
            raise tank.TankError(msg)

        if painter_version > painter_min_supported_version:
            # show a warning that this version of Substance Painter isn't yet fully tested
            # with Shotgun:
            msg = (
                "The Shotgun Pipeline Toolkit has not yet been fully "
                "tested with Substance Painter %s.  "
                "You can continue to use Toolkit but you may experience "
                "bugs or instability."
                "\n\n" % (painter_version)
            )

            # determine if we should show the compatibility warning dialog:
            show_warning_dlg = self.has_ui and SHOW_COMP_DLG not in os.environ

            if show_warning_dlg:
                # make sure we only show it once per session
                os.environ[SHOW_COMP_DLG] = "1"

                # check against the compatibility_dialog_min_version
                # setting
                min_version_str = self.get_setting("compatibility_dialog_min_version")

                min_version = to_new_version_system(min_version_str)
                if painter_version < min_version:
                    show_warning_dlg = False

            if show_warning_dlg:
                # Note, title is padded to try to ensure dialog isn't insanely
                # narrow!
                self.show_warning(msg)

            # always log the warning to the script editor:
            self.logger.warning(msg)

            # In the case of Windows, we have the possibility of locking up if
            # we allow the PySide shim to import QtWebEngineWidgets.
            # We can stop that happening here by setting the following
            # environment variable.

            if current_os.startswith("win"):
                self.logger.debug(
                    "Substance Painter on Windows can deadlock if QtWebEngineWidgets "
                    "is imported. Setting "
                    "SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT=1..."
                )
                os.environ["SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT"] = "1"

    def create_shotgun_menu(self, disabled=False):
        """
        Creates the main shotgun menu in substancepainter.
        Note that this only creates the menu, not the child actions
        :return: bool
        """

        # only create the shotgun menu if not in batch mode and menu doesn't
        # already exist
        if self.has_ui:
            # create our menu handler
            self._menu_generator = self.tk_substancepainter.MenuGenerator(
                self, self._menu_name
            )

            self._qt_app.setActiveWindow(self._menu_generator.menu_handle)
            self._menu_generator.create_menu(disabled=disabled)
            return True

        return False

    def display_menu(self, pos=None):
        """
        Shows the engine Shotgun menu.
        """
        if self._menu_generator:
            self._menu_generator.show(pos)

    def init_qt_app(self):
        """
        Initializes if not done already the QT Application for the engine.
        """
        from sgtk.platform.qt5 import QtWidgets, QtGui

        if not QtWidgets.QApplication.instance():
            self._qt_app = QtWidgets.QApplication(sys.argv)
            self._qt_app.setWindowIcon(QtGui.QIcon(self.icon_256))

            self._qt_app_main_window = QtWidgets.QMainWindow()
            self._qt_app_central_widget = QtWidgets.QWidget()
            self._qt_app_main_window.setCentralWidget(self._qt_app_central_widget)
            self._qt_app.setQuitOnLastWindowClosed(False)

            # Make the QApplication use the dark theme. Must be called after the QApplication is instantiated
            self._initialize_dark_look_and_feel()

        else:
            self._qt_app = QtWidgets.QApplication.instance()

    def post_app_init(self):
        """
        Called when all apps have initialized
        """

        # for some reason this engine command get's lost so we add it back
        self.__register_reload_command()

        # Run a series of app instance commands at startup.
        self._run_app_instance_commands()

        # Create the shotgun menu
        self.create_shotgun_menu()

        # Let the app know we are ready for action!
        self._dcc_app.broadcast_event("ENGINE_READY")

        # make sure we setup this engine as the current engine for the platform
        tank.platform.engine.set_current_engine(self)

        # emit an engine started event
        self.sgtk.execute_core_hook(TANK_ENGINE_INIT_HOOK_NAME, engine=self)

        # initalize qt loop
        self._qt_app.exec_()

    def post_context_change(self, old_context, new_context):
        """
        Runs after a context change. The Substance Painter event watching will
        be stopped and new callbacks registered containing the new context
        information.

        :param old_context: The context being changed away from.
        :param new_context: The new context being changed to.
        """

        # restore the open log folder, it get's removed whenever the first time
        # a context is changed
        self.__register_open_log_folder_command()
        self.__register_reload_command()

        if self.get_setting("automatic_context_switch", True):
            # finally create the menu with the new context if needed
            if old_context != new_context:
                self.create_shotgun_menu()

    def _run_app_instance_commands(self):
        """
        Runs the series of app instance commands listed in the
        'run_at_startup' setting of the environment configuration yaml file.
        """

        # Build a dictionary mapping app instance names to dictionaries of
        # commands they registered with the engine.
        app_instance_commands = {}
        if six.PY2:
            command_iter = self.commands.iteritems()
        else:
            command_iter = self.commands.items()

        for (cmd_name, value) in command_iter:
            app_instance = value["properties"].get("app")
            if app_instance:
                # Add entry 'command name: command function' to the command
                # dictionary of this app instance.
                cmd_dict = app_instance_commands.setdefault(
                    app_instance.instance_name, {}
                )
                cmd_dict[cmd_name] = value["callback"]

        # Run the series of app instance commands listed in the
        # 'run_at_startup' setting.
        for app_setting_dict in self.get_setting("run_at_startup", []):
            app_instance_name = app_setting_dict["app_instance"]

            # Menu name of the command to run or '' to run all commands of the
            # given app instance.
            setting_cmd_name = app_setting_dict["name"]

            # Retrieve the command dictionary of the given app instance.
            cmd_dict = app_instance_commands.get(app_instance_name)

            if cmd_dict is None:
                self.logger.warning(
                    "%s configuration setting 'run_at_startup' requests app"
                    " '%s' that is not installed.",
                    self.name,
                    app_instance_name,
                )
            else:
                if not setting_cmd_name:
                    # Run all commands of the given app instance.
                    if six.PY2:
                        command_iter = cmd_dict.iteritems()
                    else:
                        command_iter = cmd_dict.items()

                    for (cmd_name, command_function) in command_iter:
                        msg = (
                            "%s startup running app '%s' command '%s'.",
                            self.name,
                            app_instance_name,
                            cmd_name,
                        )
                        self.logger.debug(msg)

                        command_function()
                else:
                    # Run the command whose name is listed in the
                    # 'run_at_startup' setting.
                    command_function = cmd_dict.get(setting_cmd_name)
                    if command_function:
                        msg = (
                            "%s startup running app '%s' command '%s'.",
                            self.name,
                            app_instance_name,
                            setting_cmd_name,
                        )
                        self.logger.debug(msg)

                        command_function()
                    else:
                        known_commands = ", ".join("'%s'" % name for name in cmd_dict)
                        self.logger.warning(
                            "%s configuration setting 'run_at_startup' "
                            "requests app '%s' unknown command '%s'. "
                            "Known commands: %s",
                            self.name,
                            app_instance_name,
                            setting_cmd_name,
                            known_commands,
                        )

    def destroy_engine(self):
        """
        Cleanup after ourselves
        """
        self.logger.debug("%s: Destroying...", self)

    def _get_dialog_parent(self):
        """
        Get the QWidget parent for all dialogs created through
        show_dialog & show_modal.
        """
        return self._qt_app_main_window

    @property
    def has_ui(self):
        """
        Detect and return if Substance Painter is running in batch mode
        """
        return True

    def _emit_log_message(self, handler, record):
        """
        Called by the engine to log messages.
        All log messages from the toolkit logging namespace will be passed to
        this method.

        :param handler: Log handler that this message was dispatched from.
                        Its default format is "[levelname basename] message".
        :type handler: :class:`~python.logging.LogHandler`
        :param record: Standard python logging record.
        :type record: :class:`~python.logging.LogRecord`
        """
        # Give a standard format to the message:
        #     Shotgun <basename>: <message>
        # where "basename" is the leaf part of the logging record name,
        # for example "tk-multi-shotgunpanel" or "qt_importer".
        if record.levelno < logging.INFO:
            formatter = logging.Formatter("Debug: Shotgun %(basename)s: %(message)s")
        else:
            formatter = logging.Formatter("Shotgun %(basename)s: %(message)s")

        msg = formatter.format(record)

        # Select Substance Painter display function to use according to the logging
        # record level.
        if record.levelno >= logging.ERROR:
            fct = display_error
        elif record.levelno >= logging.WARNING:
            fct = display_warning
        elif record.levelno >= logging.INFO:
            fct = display_info
        else:
            fct = display_debug

        # Display the message in Substance Painter script editor in a thread safe manner.
        self.async_execute_in_main_thread(fct, msg)

    def close_windows(self):
        """
        Closes the various windows (dialogs, panels, etc.) opened by the
        engine.
        """

        # Make a copy of the list of Tank dialogs that have been created by the
        # engine and are still opened since the original list will be updated
        # when each dialog is closed.
        opened_dialog_list = self.created_qt_dialogs[:]

        # Loop through the list of opened Tank dialogs.
        for dialog in opened_dialog_list:
            dialog_window_title = dialog.windowTitle()
            try:
                # Close the dialog and let its close callback remove it from
                # the original dialog list.
                self.logger.debug("Closing dialog %s.", dialog_window_title)
                dialog.close()
            except Exception as exception:
                traceback.print_exc()
                self.logger.error(
                    "Cannot close dialog %s: %s", dialog_window_title, exception
                )
