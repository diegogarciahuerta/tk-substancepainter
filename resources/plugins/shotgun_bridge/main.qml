// Copyright (C) 2016 Allegorithmic
//
// This software may be modified and distributed under the terms
// of the MIT license.  See the LICENSE file for details.

import QtQuick 2.2
import Painter 1.0
import Qt.labs.platform 1.0
import QtQuick.Dialogs 1.2
import QtQuick.Window 2.2
import "."


PainterPlugin {
  id: root
  property var openMenuButton: null
  property bool isEngineLoaded: false
  // property double shotgun_heartbeat_interval: 1.0; 
  property bool debug: false;

  function log_info(message)
  {
    alg.log.info("Shotgun engine: " + message.toString());
  }
 
  function log_warning(message)
  {
    alg.log.warning("Shotgun engine: " + message.toString());
  }
 
  function log_debug(message)
  {
    if (root.debug)
      alg.log.info("(DEBUG) Shotgun engine: " + message.toString());
  }
 
  function log_error(message)
  {
    alg.log.error("Shotgun engine: " + message.toString());
  }
 
  function log_exception(message)
  {
    alg.log.exception("Shotgun engine: " + message.toString());
  }

  Component.onCompleted: {
    log_info("onCompleted")

    openMenuButton = alg.ui.addWidgetToPluginToolBar("menu.qml");

    openMenuButton.clicked.connect(displayMenu);
    openMenuButton.enabled = Qt.binding(function() { return root.isEngineLoaded; });
    openMenuButton.isEngineLoaded = Qt.binding(function() { return root.isEngineLoaded; });

    if (!isEngineLoaded)
    {
      bootstrapEngine();
    }
  }

  onApplicationStarted: {
    // Called when the application is started
    log_debug("onApplicationStarted")
  }

  onNewProjectCreated: {
    // Called when a new project is created, before the onProjectOpened callback
    log_debug("onNewProjectCreated")
    
    // no chance this project is saved, but if a mesh that is known by
    // toolkit is loaded, we can change the context of teh engine
    var mesh_url = alg.project.lastImportedMeshUrl();
    if (mesh_url)
    {
      var mesh_path = alg.fileIO.urlToLocalFile(mesh_url);
      server.sendCommand("NEW_PROJECT_CREATED", {path:mesh_path});
    }
  }

  onProjectOpened: {
    // Called when the project is fully loaded
    log_debug("onProjectOpened")
    server.sendCommand("PROJECT_OPENED", {path:currentProjectPath()});
  }

  // Timer {
  //   id: checkConnectionTimer
  //   repeat: true
  //   interval: root.shotgun_heartbeat_interval * 1000
  //   onTriggered: checkConnection()
  // }

  function getQueryParams(qs) {
    // This takes care of parsing the parameters passed in the command line
    // to substance painter
    qs = qs.split('+').join(' ');

    var params = {},
        tokens,
        re = /[?&]?([^=]+)=([^&]*)/g;

    while (tokens = re.exec(qs)) {
        params[decodeURIComponent(tokens[1])] = decodeURIComponent(tokens[2]);
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
    var args = Qt.application.arguments[1];
    var query = getQueryParams(args);

    var sgtk_substancepainter_engine_startup = '"' + query.SGTK_SUBSTANCEPAINTER_ENGINE_STARTUP+ '"'
    var sgtk_substancepainter_engine_python = '"' + query.SGTK_SUBSTANCEPAINTER_ENGINE_PYTHON + '"'
    log_info("starting tk-substancepainter engine with params: " + sgtk_substancepainter_engine_python + " " + sgtk_substancepainter_engine_startup)
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
    log_debug("requesting menu: " + root.openMenuButton.clickedPosition.toString());
    server.sendCommand("DISPLAY_MENU", {clickedPosition: root.openMenuButton.clickedPosition});
  }

 function sendProjectInfo() {
    try {
        server.sendCommand("OPENED_PROJECT_INFO", {
          projectUrl: alg.project.url()
        });
    }
    catch(err) {}
  }

  function disconnect() {
    log_debug("Disconnected")
    root.isEngineLoaded = false;

    log_warning("Shotgun Substance Painter Engine connection was lost. Reconnecting ...");
    bootstrapEngine();
  }

  function getVersion(data) {
    log_debug("getVersion called with params:" + data)
    return {
          painter: alg.version.painter,
          api: alg.version.api
        };
  }
  
  function engineReady(data) {
    log_info("Engine is ready.")  
    root.isEngineLoaded = true;
    
    // update the engine with the current project loaded
    server.sendCommand("PROJECT_OPENED", {path:currentProjectPath()});
  }

  function cleanUrl(url) {
    return alg.fileIO.localFileToUrl(alg.fileIO.urlToLocalFile(url));
  }

  function openProject(data) {
    log_debug("openProject called with params:" + data)

    var projectOpened = alg.project.isOpen();
    var isAlreadyOpen = false;

    var url = alg.fileIO.localFileToUrl(data.path);

    try {
      isAlreadyOpen =
        cleanUrl(alg.project.url()) == cleanUrl(url);
    }
    catch (err) {
      alg.log.exception(err);
    }

    // If the project is already opened, keep it
    try {
      if (!isAlreadyOpen) {
        if (projectOpened) {
          // TODO: Ask the user if he wants to save its current opened project
          alg.project.close();
        }
        alg.project.open(url);
      }
    }
    catch (err) {
      alg.log.exception(err)
      return false;
    }
    return true;
  }

  function currentProjectPath(data)
  {
    try {
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
    catch (err) {
      return "Untitled.spp"
    }
  }

  function currentProjectMesh(data)
  {
    try {
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
    catch (err) {
      return null;
    }
  }

  
  function saveProjectAs(data) {
    log_debug("saveProjectAs called with params:" + data)
    for (var i in data)
      log_debug("param:" + i + " = " + data[i])

    try {
      var url = alg.fileIO.localFileToUrl(data.path);
      alg.project.save(url, alg.project.SaveMode.Full);
    }
    catch (err) {
      alg.log.exception(err)
      return false;
    }
    return true;
  }


  function saveProject(data) {
    log_debug("saveProject called with params:" + data)

    try {
      alg.project.save("", alg.project.SaveMode.Full);
    }
    catch (err) {
      alg.log.exception(err)
      return false;
    }
    return true;
  }

  function needsSavingProject(data){
    log_debug("saveProject called with params:" + data)

    try {
      return alg.project.needSaving();
    }
    catch (err) {
      alg.log.exception(err)
      return false;
    }
    return false;
  }

  function closeProject(data){
    log_debug("closeProject called with params:" + data)

    try {
      var projectOpened = alg.project.isOpen();
      if (projectOpened)
        return alg.project.close();
    }
    catch (err) {
      alg.log.exception(err)
      return false;
    }
    return false;
  }

  function executeStatement(data){
    try {
      return eval(data.statement);
    }
    catch (err) {
      alg.log.exception(err)
      return false;
    }
    return false;
  }

  function info(data){
    return alg.settings.keys(); //StandardPaths.standardLocations(StandardPaths.AppLocalDataLocation)[0]
  }

  function extractThumbnail(data)
  {
      return root.grabToImage(function(result) {result.saveToFile(data.path)});
  }

  function importProjectResource(data)
  {
    try {
      var result = alg.resources.importProjectResource(data.path, [data.usage], data.destination);
      
      // we store the info as a project settings as it will be reused later 
      // when tk-multi-breakdown tries to figure out what resources are
      // up to date and which are not.

      var settings = alg.project.settings.value("tk-multi-loader2", {});    
      settings[result] = data.path;

      alg.project.settings.setValue("tk-multi-loader2", settings);

      return settings;
    }
    catch (err) {
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
    try {
      return alg.resources.getResourceInfo(data.url);
    }
    catch (err) {
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
    var export_preset = alg.mapexport.getProjectExportPreset();
    var export_options = alg.mapexport.getProjectExportOptions();
    var export_path = data.destination;
    return alg.mapexport.exportDocumentMaps(export_preset, export_path, export_options.fileFormat)
  }


  CommandServer {
    id: server
    Component.onCompleted: {
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
      registerCallback("EXTRACT_THUMBNAIL", extractThumbnail);
      registerCallback("IMPORT_PROJECT_RESOURCE", importProjectResource);
      registerCallback("GET_PROJECT_SETTINGS", getProjectSettings);
      registerCallback("GET_RESOURCE_INFO", getResourceInfo);
      registerCallback("GET_PROJECT_EXPORT_PATH", getProjectExportPath);
      registerCallback("GET_MAP_EXPORT_INFORMATION", getMapExportInformation);
      registerCallback("EXPORT_DOCUMENT_MAPS", exportDocumentMaps);

      registerCallback("INFO", info);
      //checkConnectionTimer.start();
    }

    onConnectedChanged: {
      if (!connected) {
        disconnect();
      }
    }
  }

  FileDialog {
    id: saveSessionDialog
    title: "Save Project"
    selectExisting : false
    nameFilters: [ "Substance Painter files (*.spp)" ]

    onAccepted: {
      var url = fileUrl.toString();
      alg.project.save(url, alg.project.SaveMode.Full);
      return true;
    }
    onRejected: {
      return false;
    }
  }

}
