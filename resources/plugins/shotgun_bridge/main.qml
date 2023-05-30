// Substance Painter plugin to communicate with it's related Shotgun engine.
// The idea is to communicate with the engine through websockets since
// the engine is written in python.

// __author__ = "Diego Garcia Huerta"
// __email__ = "diegogh2000@gmail.com"


import QtQuick 2.2
import Painter 1.0
import Qt.labs.platform 1.0
import QtQuick.Dialogs 1.2
import QtQuick.Window 2.2
import "."


PainterPlugin
{
  id: root
  property var openMenuButton: null
  property bool isEngineLoaded: false
  // property double shotgun_heartbeat_interval: 1.0; 
  property bool debug: true;

  function log_info(data)
  {
    var message = data
    if (data.hasOwnProperty("message"))
        message = data.message;

    alg.log.info("Shotgun engine | " + message.toString());
  }
 
  function log_warning(data)
  {
    var message =  data.message ? ("message" in data) : data;
    if (data.hasOwnProperty("message"))
        message = data.message;

    alg.log.warning("Shotgun engine | " + message.toString());
  }
 
  function log_debug(data)
  {
    var message =  data.message ? ("message" in data) : data;
    if (data.hasOwnProperty("message"))
        message = data.message;

    if (root.debug)
      alg.log.info("(DEBUG) Shotgun engine | " + message.toString());
  }
 
  function log_error(data)
  {
    var message =  data.message ? ("message" in data) : data;
    if (data.hasOwnProperty("message"))
        message = data.message;

    alg.log.error("Shotgun engine | " + message.toString());
  }
 
  function log_exception(data)
  {
    var message =  data.message ? ("message" in data) : data;
    if (data.hasOwnProperty("message"))
        message = data.message;

    alg.log.exception("Shotgun engine | " + message.toString());
  }

  Component.onCompleted:
  {
    log_debug("Initializing Shotgun Bridge Plugin.");

    // get the port we have been assigned from sthe startup software launcher
    var args = Qt.application.arguments[1];
    var query = getQueryParams(args);

    if (typeof(query.SGTK_SUBSTANCEPAINTER_ENGINE_PORT) === "undefined" ||
        typeof(query.SGTK_SUBSTANCEPAINTER_ENGINE_STARTUP) === "undefined" ||
        typeof(query.SGTK_SUBSTANCEPAINTER_ENGINE_PYTHON) === "undefined")
    {
      // we are not in a shotgun toolkit environment, so we bail out as soon as
      // possible
      log_warning("Not in an shotgun toolkit environment so the engine won't be run. Have you launched Substance Painter through the Shotgun Desktop application ?");
      return;
    }

    var sgtk_substancepainter_engine_port = query.SGTK_SUBSTANCEPAINTER_ENGINE_PORT;
    
    server.port = parseInt(sgtk_substancepainter_engine_port);
    log_debug("Engine port:" + server.port);
    server.listen = true;

    openMenuButton = alg.ui.addWidgetToPluginToolBar("menu.qml");

    openMenuButton.clicked.connect(displayMenu);
    openMenuButton.enabled = Qt.binding(function() { return root.isEngineLoaded; });
    openMenuButton.isEngineLoaded = Qt.binding(function() { return root.isEngineLoaded; });

    // We initialize here the engine instead of when the app has finished 
    // loading because the user can always reload the plugin from the Plugins
    // menu and that event does not get called in that case.
    if (!isEngineLoaded)
    {
      bootstrapEngine();
    }
  }

  onNewProjectCreated:
  {
    // Called when a new project is created, before the onProjectOpened callback

    // no chance this project is saved, but if a mesh that is known by
    // toolkit is loaded, we can change the context of teh engine
    var mesh_url = alg.project.lastImportedMeshUrl();
    if (mesh_url)
    {
      var mesh_path = alg.fileIO.urlToLocalFile(mesh_url);
      server.sendCommand("NEW_PROJECT_CREATED", {path:mesh_path});
    }
  }

  onProjectOpened:
  {
    // Called when the project is fully loaded
    server.sendCommand("PROJECT_OPENED", {path:currentProjectPath()});
  }

  // Timer {
  //   id: checkConnectionTimer
  //   repeat: true
  //   interval: root.shotgun_heartbeat_interval * 1000
  //   onTriggered: checkConnection()
  // }

  function getQueryParams(qs)
  {
    // This takes care of parsing the parameters passed in the command line
    // to substance painter
    var params = {};

    try
    {
      qs = qs.split('+').join(' ');

      var tokens,
          re = /[?&]?([^=]+)=([^&]*)/g;

      while (tokens = re.exec(qs))
      {
          params[decodeURIComponent(tokens[1])] = decodeURIComponent(tokens[2]);
      }
    }
    catch (err) 
    {
    }

    return params;
  }


  function onProcessEndedCallback(result)
  {
    // We try to keep the engine alive by restarting it if something went wrong.
    log_warning("Shotgun Substance Painter Engine connection was lost. Restarting engine...");
    if (result.crashed)
    {
      bootstrapEngine();
    }
  }

  function bootstrapEngine()
  {
    // Initializes the toolkit engine by reading the argument passed by the
    // startup module in the command line. The argument is in the form of an
    // url parameters and contains the location to python, the location to the
    // bootstrap engine and the port to use for the server<->client connection.
    var args = Qt.application.arguments[1];
    var query = getQueryParams(args);

    var sgtk_substancepainter_engine_startup = '"' + query.SGTK_SUBSTANCEPAINTER_ENGINE_STARTUP+ '"'
    var sgtk_substancepainter_engine_python = '"' + query.SGTK_SUBSTANCEPAINTER_ENGINE_PYTHON + '"'
    
    log_debug("Starting tk-substancepainter engine with params: " + sgtk_substancepainter_engine_python + " " + sgtk_substancepainter_engine_startup)
    alg.subprocess.start(sgtk_substancepainter_engine_python + " " + sgtk_substancepainter_engine_startup, onProcessEndedCallback)
  }

  function checkConnection(data) 
  {
      // TODO: check if the subprocess where the engine is running is still alive.
      // Might not be needed as if we use a callback in the start of the process
      // that tell us when the process is finished, and also the server knows
      // when the client drops it's connection.
  }

  function displayMenu(data) 
  {
    // tells the engine to show the menu
    server.sendCommand("DISPLAY_MENU", {clickedPosition: root.openMenuButton.clickedPosition});
  }

 function sendProjectInfo() 
 {
    try
    {
        server.sendCommand("OPENED_PROJECT_INFO", {
          projectUrl: alg.project.url()
        });
    }
    catch(err) {}
  }

  function disconnect() 
  {
    root.isEngineLoaded = false;

    log_warning("Shotgun Substance Painter Engine connection was lost. Reconnecting ...");
    bootstrapEngine();
  }

  function getVersion(data) 
  {
    return {
             painter: alg.version.painter,
             api: alg.version.api
           };
  }
  
  function engineReady(data) 
  {
    log_info("Engine is ready.")  
    root.isEngineLoaded = true;
    
    // update the engine context accoding to the current project loaded
    server.sendCommand("PROJECT_OPENED", {path:currentProjectPath()});
  }

  function cleanUrl(url) 
  {
    return alg.fileIO.localFileToUrl(alg.fileIO.urlToLocalFile(url));
  }

  function openProject(data) 
  {
    var projectOpened = alg.project.isOpen();
    var isAlreadyOpen = false;

    var url = alg.fileIO.localFileToUrl(data.path);

    try 
    {
      isAlreadyOpen = cleanUrl(alg.project.url()) == cleanUrl(url);
    }
    catch (err) 
    {
      alg.log.exception(err);
    }

    // If the project is already opened, keep it
    try
    {
      if (!isAlreadyOpen)
      {
        if (projectOpened)
        {
          // TODO: Ask the user if he wants to save its current opened project
          alg.project.close();
        }    
        alg.project.open(url);
      }
    }
    catch (err) 
    {
      alg.log.exception(err)
      return false;
    }

    return true;
  }

  function currentProjectPath(data)
  {
    try 
    {
      var projectOpened = alg.project.isOpen();
      if (projectOpened)
      {
        var path = alg.fileIO.urlToLocalFile(alg.project.url());
        return path
      }
      else
      {
        return "Untitled.spp"
      }    
    }
    catch (err)
    {
      return "Untitled.spp"
    }
  }

  function currentProjectMesh(data)
  {
    try
    {
      var projectOpened = alg.project.isOpen();
      if (projectOpened)
      {
        var path = alg.fileIO.urlToLocalFile(alg.project.lastImportedMeshUrl());
        return path
      }
      else
      {
        return null;
      }    
    }
    catch (err)
    {
      return null;
    }
  }

  
  function saveProjectAs(data)
  {
    try
    {
      var url = alg.fileIO.localFileToUrl(data.path);
      alg.project.save(url, alg.project.SaveMode.Full);
    }
    catch (err)
    {
      alg.log.exception(err)
      return false;
    }

    return true;
  }


  function saveProject(data)
  {
    try
    {
      alg.project.save("", alg.project.SaveMode.Full);
    }
    catch (err)
    {
      alg.log.exception(err)
      return false;
    }
    
    return true;
  }

  function needsSavingProject(data)
  {
    try
    {
      return alg.project.needSaving();
    }
    catch (err)
    {
      alg.log.exception(err)
      return false;
    }
    
    return false;
  }

  function closeProject(data)
  {
    try
    {
      var projectOpened = alg.project.isOpen();
      if (projectOpened)
        return alg.project.close();
    }
    catch (err)
    {
      alg.log.exception(err)
      return false;
    }
    return false;
  }

  function executeStatement(data)
  {
    try
    {
      return eval(data.statement);
    }
    catch (err)
    {
      alg.log.exception(err)
      return false;
    }
    
    return false;
  }

  function importProjectResource(data)
  {
    try
    {
      var result = alg.resources.importProjectResource(data.path, [data.usage], data.destination);
      
      // we store the info as a project settings as it will be reused later 
      // when tk-multi-breakdown tries to figure out what resources are
      // up to date and which are not.

      var settings = alg.project.settings.value("tk-multi-loader2", {});    
      settings[result] = data.path;

      alg.project.settings.setValue("tk-multi-loader2", settings);

      return result;
    }
    catch (err)
    {
      alg.log.exception(err)
    }
    
    return null;
  }

  function getProjectSettings(data)
  {
    return alg.project.settings.value(data.key, {});
  }

  function getResourceInfo(data)
  {
    try
    {
      return alg.resources.getResourceInfo(data.url);
    }
    catch (err)
    {
      alg.log.exception(err)
    }

    return null;
  }

  function getProjectExportPath(data)
  {
    return alg.mapexport.exportPath();
  }

  function saveProjectAsAction(data)
  {
    return saveSessionDialog.open();
  }

  function getMapExportInformation(data)
  {
    var export_preset = alg.mapexport.getProjectExportPreset();
    var export_options = alg.mapexport.getProjectExportOptions();
    var export_path = alg.mapexport.exportPath();
    return alg.mapexport.getPathsExportDocumentMaps(export_preset, export_path, export_options.fileFormat)
  }

  function exportDocumentMaps(data)
  {
    server.sendCommand("EXPORT_STARTED", {});
    var result = alg.mapexport.exportDocumentMaps(data.preset, data.destination, data.format, data.mapInfo)
    server.sendCommand("EXPORT_FINISHED", {map_infos:result});
    return true;
  }

  function updateDocumentResources(data)
  {
    return alg.resources.updateDocumentResources(data.old_url, data.new_url);
  }

  function documentResources(data)
  {
    return alg.resources.documentResources();
  }

  function toggleDebugLogging(data)
  {
    alg.log.debug("Debug Logging is : " + data.enabled);
    root.debug = data.enabled;
    server.debug = data.enabled;
  }

  CommandServer
  {
    id: server
    Component.onCompleted:
    {
      registerCallback("LOG_INFO", log_info);
      registerCallback("LOG_WARNING", log_warning);
      registerCallback("LOG_DEBUG", log_debug);
      registerCallback("LOG_ERROR", log_error);
      registerCallback("LOG_EXCEPTION", log_exception);

      registerCallback("SEND_PROJECT_INFO", sendProjectInfo);
      registerCallback("GET_VERSION", getVersion);
      registerCallback("ENGINE_READY", engineReady);
      registerCallback("OPEN_PROJECT", openProject);
      registerCallback("GET_CURRENT_PROJECT_PATH", currentProjectPath);
      registerCallback("SAVE_PROJECT", saveProject);
      registerCallback("SAVE_PROJECT_AS", saveProjectAs);
      registerCallback("SAVE_PROJECT_AS_ACTION", saveProjectAsAction);
      registerCallback("NEEDS_SAVING", needsSavingProject);
      registerCallback("CLOSE_PROJECT", closeProject);
      registerCallback("EXECUTE_STATEMENT", executeStatement);
      registerCallback("IMPORT_PROJECT_RESOURCE", importProjectResource);
      registerCallback("GET_PROJECT_SETTINGS", getProjectSettings);
      registerCallback("GET_RESOURCE_INFO", getResourceInfo);
      registerCallback("GET_PROJECT_EXPORT_PATH", getProjectExportPath);
      registerCallback("GET_MAP_EXPORT_INFORMATION", getMapExportInformation);
      registerCallback("EXPORT_DOCUMENT_MAPS", exportDocumentMaps);
      registerCallback("UPDATE_DOCUMENT_RESOURCES", updateDocumentResources);
      registerCallback("DOCUMENT_RESOURCES", documentResources);
      registerCallback("TOGGLE_DEBUG_LOGGING", toggleDebugLogging);
      //checkConnectionTimer.start();
    }

    onConnectedChanged: 
    {
      if (!connected)
      {
        disconnect();
      }
    }
  }

  FileDialog
  {
    id: saveSessionDialog
    title: "Save Project"
    selectExisting : false
    nameFilters: [ "Substance Painter files (*.spp)" ]

    onAccepted:
    {
      var url = fileUrl.toString();
      alg.project.save(url, alg.project.SaveMode.Full);
      return true;
    }
    onRejected:
    {
      return false;
    }
  }
}
