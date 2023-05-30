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
import sys
import shutil
import hashlib
import socket
from distutils.version import LooseVersion

##############

import sgtk
from sgtk.platform import SoftwareLauncher, SoftwareVersion, LaunchInformation


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"

logger = sgtk.LogManager.get_logger(__name__)


# We use this to indicate that we could not retrieve the version for the
# binary/executable, so we allow the engine to run with it
UNKNOWN_VERSION = "UNKNOWN_VERSION"

# note that this is the same in engine.py
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


# adapted from:
# https://stackoverflow.com/questions/2270345/finding-the-version-of-an-application-from-python
def get_file_info(filename, info):
    """
    Extract information from a file.
    """
    import array
    from ctypes import windll, create_string_buffer, c_uint, string_at, byref

    # Get size needed for buffer (0 if no info)
    size = windll.version.GetFileVersionInfoSizeA(filename, None)
    # If no info in file -> empty string
    if not size:
        return ""

    # Create buffer
    res = create_string_buffer(size)
    # Load file informations into buffer res
    windll.version.GetFileVersionInfoA(filename, None, size, res)
    r = c_uint()
    l = c_uint()
    # Look for codepages
    windll.version.VerQueryValueA(res, "\\VarFileInfo\\Translation", byref(r), byref(l))
    # If no codepage -> empty string
    if not l.value:
        return ""

    # Take the first codepage (what else ?)
    codepages = array.array("H", string_at(r.value, l.value))
    codepage = tuple(codepages[:2].tolist())

    # Extract information
    windll.version.VerQueryValueA(
        res, ("\\StringFileInfo\\%04x%04x\\" + info) % codepage, byref(r), byref(l)
    )
    return string_at(r.value, l.value)


def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def samefile(file1, file2):
    return md5(file1) == md5(file2)


# based on:
# https://stackoverflow.com/questions/38876945/copying-and-merging-directories-excluding-certain-extensions
def copytree_multi(src, dst, symlinks=False, ignore=None):
    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    if not os.path.isdir(dst):
        os.makedirs(dst)

    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)

        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                copytree_multi(srcname, dstname, symlinks, ignore)
            else:
                if os.path.exists(dstname):
                    if not samefile(srcname, dstname):
                        os.unlink(dstname)
                        shutil.copy2(srcname, dstname)
                        logger.info("File copied: %s" % dstname)
                    else:
                        # same file, so ignore the copy
                        logger.info("Same file, skipping: %s" % dstname)
                        pass
                else:
                    shutil.copy2(srcname, dstname)
        except (IOError, os.error) as why:
            errors.append((srcname, dstname, str(why)))
        except shutil.Error as err:
            errors.extend(err.args[0])
    try:
        shutil.copystat(src, dst)
    except WindowsError:
        pass
    except OSError as why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise shutil.Error(errors)


def ensure_scripts_up_to_date(engine_scripts_path, scripts_folder):
    logger.info("Updating scripts...: %s" % engine_scripts_path)
    logger.info("                     scripts_folder: %s" % scripts_folder)

    copytree_multi(engine_scripts_path, scripts_folder)

    return True


def get_free_port():
    # Ask the OS to allocate a port.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class SubstancePainterLauncher(SoftwareLauncher):
    """
    Handles launching SubstancePainter executables. Automatically starts up
    a tk-substancepainter engine with the current context in the new session
    of SubstancePainter.
    """

    # Named regex strings to insert into the executable template paths when
    # matching against supplied versions and products. Similar to the glob
    # strings, these allow us to alter the regex matching for any of the
    # variable components of the path in one place.

    # It seems that Substance Painter does not use any version number in the
    # installation folders, as if they do not support multiple versions of
    # the same software.
    COMPONENT_REGEX_LOOKUP = {}

    # This dictionary defines a list of executable template strings for each
    # of the supported operating systems. The templates are used for both
    # globbing and regex matches by replacing the named format placeholders
    # with an appropriate glob or regex string.

    EXECUTABLE_TEMPLATES = {
        "darwin": ["/Applications/Allegorithmic/Substance Painter.app"],
        "win32": ["C:/Program Files/Adobe/Adobe Substance 3D Painter/Adobe Substance 3D Painter.exe"],
        "linux2": [
            "/usr/Allegorithmic/Substance Painter",
            "/usr/Allegorithmic/Substance_Painter/Substance Painter",
            "/opt/Allegorithmic/Substance_Painter/Substance Painter",
        ],
    }

    @property
    def minimum_supported_version(self):
        """
        The minimum software version that is supported by the launcher.
        """
        return MINIMUM_SUPPORTED_VERSION

    def prepare_launch(self, exec_path, args, file_to_open=None):
        """
        Prepares an environment to launch SubstancePainter in that will automatically
        load Toolkit and the tk-substancepainter engine when SubstancePainter starts.

        :param str exec_path: Path to SubstancePainter executable to launch.
        :param str args: Command line arguments as strings.
        :param str file_to_open: (optional) Full path name of a file to open on
                                            launch.
        :returns: :class:`LaunchInformation` instance
        """
        required_env = {}

        resources_plugins_path = os.path.join(self.disk_location, "resources", "plugins")

        # Run the engine's init.py file when SubstancePainter starts up
        # TODO, maybe start engine here
        startup_path = os.path.join(self.disk_location, "startup", "bootstrap.py")

        # Prepare the launch environment with variables required by the
        # classic bootstrap approach.
        self.logger.debug(
            "Preparing SubstancePainter Launch via Toolkit Classic methodology ..."
        )

        required_env["SGTK_SUBSTANCEPAINTER_ENGINE_STARTUP"] = startup_path.replace("\\", "/")

        required_env["SGTK_SUBSTANCEPAINTER_ENGINE_PYTHON"] = sys.executable.replace("\\", "/")

        required_env["SGTK_SUBSTANCEPAINTER_SGTK_MODULE_PATH"] = sgtk.get_sgtk_module_path()

        required_env["SGTK_SUBSTANCEPAINTER_ENGINE_PORT"] = str(get_free_port())

        if file_to_open:
            # Add the file name to open to the launch environment
            required_env["SGTK_FILE_TO_OPEN"] = file_to_open

        # First big disclaimer: qml does not support environment variables for safety reasons
        # the only way to pass information inside substance painter is to actually encode
        # as a string and trick the program to think it is opening a substance painter project
        # The reason why this works is because inside substance painter the original file is
        # used with an URL, ie. //file/serve/filename, so we add to the URL using & to pass
        # our now fake environment variables.
        # Only the startup script, the location of python and potentially the file to open
        # are needed.
        args = ""
        args = ["%s=%s" % (k, v) for k, v in required_env.items()]
        args = '"&%s"' % "&".join(args)
        logger.info("running %s" % args)

        required_env["SGTK_ENGINE"] = self.engine_name
        required_env["SGTK_CONTEXT"] = sgtk.context.serialize(self.context)

        # ensure scripts are up to date on the substance painter side

        # Platform-specific plug-in paths

        if sys.platform == "win32":
            import ctypes.wintypes

            CSIDL_PERSONAL = 5  # My Documents
            SHGFP_TYPE_CURRENT = 0  # Get current My Documents folder, not default value

            path_buffer = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(
                None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, path_buffer
            )

            user_scripts_path = path_buffer.value + r"\Adobe\Adobe Substance 3D Painter\plugins"

        else:
            user_scripts_path = os.path.expanduser(
                r"~/Documents/Adobe/Adobe Substance 3D Painter/plugins"
            )

        ensure_scripts_up_to_date(resources_plugins_path, user_scripts_path)

        # args = '&SGTK_SUBSTANCEPAINTER_ENGINE_STARTUP=%s;SGTK_SUBSTANCEPAINTER_ENGINE_PYTHON=%s' % (startup_path, sys.executable)
        return LaunchInformation(exec_path, args, required_env)

    def _icon_from_engine(self):
        """
        Use the default engine icon as substancepainter does not supply
        an icon in their software directory structure.

        :returns: Full path to application icon as a string or None.
        """

        # the engine icon
        engine_icon = os.path.join(self.disk_location, "icon_256.png")
        return engine_icon

    def _is_supported(self, sw_version):
        """
        Inspects the supplied :class:`SoftwareVersion` object to see if it
        aligns with this launcher's known product and version limitations. Will
        check the :meth:`~minimum_supported_version` as well as the list of
        product and version filters.
        :param sw_version: :class:`SoftwareVersion` object to test against the
            launcher's product and version limitations.
        :returns: A tuple of the form: ``(bool, str)`` where the first item
            is a boolean indicating whether the supplied :class:`SoftwareVersion` is
            supported or not. The second argument is ``""`` if supported, but if
            not supported will be a string representing the reason the support
            check failed.
        This helper method can be used by subclasses in the :meth:`scan_software`
        method.

        To check if the version is supported:
        
        First we make an exception for cases were we cannot retrieve the 
        version number, we accept the software as valid.

        Second, checks against the minimum supported version. If the
        supplied version is greater it then checks to ensure that it is in the
        launcher's ``versions`` constraint. If there are no constraints on the
        versions, we will accept the software version.

        :param str version: A string representing the version to check against.
        :return: Boolean indicating if the supplied version string is supported.
        """

        # we support cases were we could not extract the version number
        # from the binary/executable
        if sw_version.version == UNKNOWN_VERSION:
            return (True, "")

        # convert to new version system if required
        version = to_new_version_system(sw_version.version)

        # second, compare against the minimum version
        if self.minimum_supported_version:
            min_version = to_new_version_system(self.minimum_supported_version)

            if version < min_version:
                # the version is older than the minimum supported version
                return (
                    False,
                    "Executable '%s' didn't meet the version requirements, "
                    "%s is older than the minimum supported %s"
                    % (sw_version.path, sw_version.version, self.minimum_supported_version),
                )

        # third if the version is new enough, we check if we have any
        # version restrictions
        if not self.versions:
            # No version restriction. All versions supported
            return (True, "")

        # if so, check versions list
        supported = sw_version.version in self.versions
        if not supported:
            return (
                False,
                "Executable '%s' didn't meet the version requirements"
                "(%s not in %s)" % (sw_version.path, sw_version.version, self.versions),
            )

        # passed all checks. must be supported!
        return (True, "")

    def scan_software(self):
        """
        Scan the filesystem for substancepainter executables.

        :return: A list of :class:`SoftwareVersion` objects.
        """
        self.logger.debug("Scanning for SubstancePainter executables...")

        supported_sw_versions = []
        for sw_version in self._find_software():
            (supported, reason) = self._is_supported(sw_version)

            if supported:
                supported_sw_versions.append(sw_version)
            else:
                self.logger.debug(
                    "SoftwareVersion %s is not supported: %s" % (sw_version, reason)
                )

        return supported_sw_versions

    def _find_software(self):
        """
        Find executables in the default install locations.
        """

        # all the executable templates for the current OS
        executable_templates = self.EXECUTABLE_TEMPLATES.get(sys.platform, [])

        # all the discovered executables
        sw_versions = []

        for executable_template in executable_templates:

            self.logger.debug("Processing template %s.", executable_template)

            executable_matches = self._glob_and_match(
                executable_template, self.COMPONENT_REGEX_LOOKUP
            )

            # Extract all products from that executable.
            for (executable_path, key_dict) in executable_matches:

                # extract the matched keys form the key_dict (default to None
                # if not included)
                if sys.platform == "win32":
                    executable_version = get_file_info(executable_path, "FileVersion")
                    # make sure we remove those pesky \x00 characters
                    executable_version = executable_version.strip("\x00")
                else:
                    executable_version = key_dict.get("version", UNKNOWN_VERSION)

                self.logger.debug(
                    "Software found: %s | %s.", executable_version, executable_template
                )
                sw_versions.append(
                    SoftwareVersion(
                        executable_version,
                        "Substance Painter",
                        executable_path,
                        self._icon_from_engine(),
                    )
                )

        return sw_versions
