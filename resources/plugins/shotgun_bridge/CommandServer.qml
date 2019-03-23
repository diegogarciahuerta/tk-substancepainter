import Painter 1.0
import QtQuick 2.7
import QtWebSockets 1.0

Item {
  id: root

  property alias host : server.host
  property alias listen: server.listen
  property alias port: server.port
  property alias currentWebSocket: server.currentWebSocket
  readonly property bool connected: currentWebSocket !== null
  property bool debug: false;

  signal jsonMessageReceived(var command, var jsonData)

  property var _callbacks: null
  property var m_id: 1


  function log_info(message)
  {
    alg.log.info("Shotgun bridge: " + message.toString());
  }
 
  function log_warning(message)
  {
    alg.log.warning("Shotgun bridge: " + message.toString());
  }
 
  function log_debug(message)
  {
    if (root.debug)
      alg.log.info("(DEBUG) Shotgun bridge: " + message.toString());
  }
 
  function log_error(message)
  {
    alg.log.error("Shotgun bridge: " + message.toString());
  }
 
  function log_exception(message)
  {
    alg.log.exception("Shotgun bridge: " + message.toString());
  }

  function registerCallback(command, callback) {
    if (_callbacks === null) {
      _callbacks = {};
    }
    _callbacks[command.toUpperCase()] = callback;
  }

  function sendCommand(command, data) {
    if (!connected) {
      alg.log.warn(qsTr("Can't send \"%1\" command as there is no client connected").arg(command));
      return;
    }
    try {
          m_id +=1;
          var jsonData = {"jsonrpc": "2.0",
                      "method": command,
                      "params": data,
                      "id": m_id};

      log_debug("Sending:" + JSON.stringify(jsonData));
      server.currentWebSocket.sendTextMessage(JSON.stringify(jsonData));
    }
    catch(err) {
      alg.log.error(qsTr("Unexpected error while sending \"%1\" command: %2").arg(command).arg(err.message));
    }
  }

  function sendResult(message_id, result)
  {
    var jsonData;

    if (!connected)
    {
      alg.log.warn(qsTr("Can't send \"%1\" result for message  \"%2\" as there is no client connected").arg(result).arg(message_id));
      return;
    }
    try 
    {
      jsonData = {"jsonrpc": "2.0", "result": result, "id": message_id};
      log_debug("Sending Response:" + JSON.stringify(jsonData));
      server.currentWebSocket.sendTextMessage(JSON.stringify(jsonData));
      log_debug("Sent.");
    }
    catch(err) {
      jsonData = {"jsonrpc": "2.0", "error": err || null, "id": message_id};
      log_debug("Sending error:" + JSON.stringify(jsonData));
      server.currentWebSocket.sendTextMessage(JSON.stringify(jsonData));
      alg.log.error(qsTr("Unexpected error while sending \"%1\" message id: %2").arg(message_id).arg(err.message));
    }
  }

  WebSocketServer {
    id: server

    listen: true
    port: 12345
    property var currentWebSocket: null
    name: "Substance Painter Bridge"
    accept: !root.connected // Ensure only one connection at a time

    onClientConnected: {
      currentWebSocket = webSocket;

      webSocket.statusChanged.connect(function onWSStatusChanged() {
          if (root && root.connected && (
                webSocket.status == WebSocket.Closed ||
                webSocket.status == WebSocket.Error))
          {
            server.currentWebSocket = null;
          }
          if (webSocket.status == WebSocket.Error) {
            alg.log.warn(qsTr("Command server connection error: %1").arg(webSocket.errorString));
          }
      });
      webSocket.onTextMessageReceived.connect(function onWSTxtMessageReceived(message) {
        // Try to retrieve command and json data
        var command, jsonData, message_id;
        try {
          //var separator = message.indexOf(" ");
          // var jsonString = message.substring(separator + 1, message.length);
          //jsonData = JSON.parse(jsonString);
          //command = message.substring(0, separator).toUpperCase();
          
          jsonData = JSON.parse(message);
          message_id = jsonData.id
          command = jsonData.method.toUpperCase(); 
        }
        catch(err) {
          alg.log.warn(qsTr("Command connection received badly formated message starting with: \"%1\"...: %2")
            .arg(message.substring(0, 30))
            .arg(err.message));
          return;
        }
        log_debug("Message received: " + message)

        if (root._callbacks && command in root._callbacks) {
          try {
            var result = root._callbacks[command](jsonData.params)
            root.sendResult(jsonData.id, result);
          }
          catch(err) {
            alg.log.warn(err.message);
          }
        }
        else
        {
          log_debug("Message received was ignored: " + message)        
        }
        root.jsonMessageReceived(command, jsonData);
      })
    }

    onErrorStringChanged: {
      alg.log.warn(qsTr("Command server error: %1").arg(errorString));
    }
  }
}
