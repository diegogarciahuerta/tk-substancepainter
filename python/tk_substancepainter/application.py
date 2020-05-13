"""
Module that encapsulates access to the actual application

"""

import os
import sys
import json
import time
import threading
import uuid
from functools import partial

import signal

signal.signal(signal.SIGINT, signal.SIG_DFL)

from tank.platform.qt5 import QtGui, QtCore, QtWebSockets, QtNetwork

QCoreApplication = QtCore.QCoreApplication
QUrl = QtCore.QUrl
QAbstractSocket = QtNetwork.QAbstractSocket


__author__ = "Diego Garcia Huerta"
__email__ = "diegogh2000@gmail.com"


class Client(QtCore.QObject):

    requestReceived = QtCore.Signal(str, object)

    def __init__(self, engine, parent=None, url="ws://localhost:12345"):
        super(Client, self).__init__(parent)
        self.engine = engine
        self.url = url
        self.client = QtWebSockets.QWebSocket(
            "", QtWebSockets.QWebSocketProtocol.Version13, None
        )

        self.client.connected.connect(self.on_connected)
        self.client.disconnected.connect(self.on_disconnected)
        self.client.error.connect(self.on_error)
        self.client.stateChanged.connect(self.on_state_changed)

        self.client.pong.connect(self.on_pong)
        self.client.textMessageReceived.connect(self.on_text_message_received)

        self.callbacks = {}
        self.max_attemps = 5
        self.wait_period = 1

        # borrow the engine logger
        self.log_info = engine.log_info
        self.log_debug = engine.log_debug
        self.log_warning = engine.log_warning
        self.log_error = engine.log_error

        self.log_debug("Client started. - %s " % url)

        # A bit of a hack to get responses from the server
        # I cannot wait for python3 concurrency!
        # reference: https://stackoverflow.com/questions/9523370/adding-attributes-to-instance-methods-in-python
        def send_and_receive(self, command, **kwargs):
            # self.log_debug("send_and_receive: message %s" % command)

            # exit the loop if timeout happens
            timeout_timer = QtCore.QTimer(parent=QtCore.QCoreApplication.instance())

            loop = QtCore.QEventLoop()

            data = None

            def await_for_response(result):
                self.send_and_receive.data = result
                # self.log_debug("exiting the loop: result %s" % result)
                loop.quit()

            # self.log_debug("in the loop...")
            self.send_text_message(command, callback=await_for_response, **kwargs)

            timeout_timer.timeout.connect(loop.quit)
            timeout_timer.start(5 * 1000.0)

            loop.exec_()

            return self.send_and_receive.data

        self.send_and_receive = partial(send_and_receive, self)

        # connect to server
        self.connect_to_server()

    def connect_to_server(self):
        self.log_debug("Client start connection | %s " % QtCore.QUrl(self.url))
        result = self.client.open(QtCore.QUrl(self.url))
        self.log_debug("Client start connection | result | %s " % result)

    def ping(self):
        self.log_debug("client: do_ping")
        self.client.ping()

    def on_connected(self):
        pass
        self.log_debug("client: on_connected")

    def on_disconnected(self):
        self.log_debug("client: on_disconnected")
        self.engine.process_request("QUIT")

    def on_error(self, error_code):
        self.log_error("client: on_error: {}".format(error_code))
        self.log_error(self.client.errorString())
        self.engine.process_request("QUIT")

    def on_state_changed(self, state):
        self.log_debug("client: on_state_changed: %s" % state)
        state = self.client.state()
        if state == QAbstractSocket.SocketState.ConnectingState:
            return

        attempts = 0
        while attempts < self.max_attemps and self.client.state() not in (
            QAbstractSocket.SocketState.ConnectedState,
        ):
            attempts += 1
            self.log_debug("client: attempted to reconnect : %s" % attempts)
            self.connect_to_server()
            time.sleep(self.wait_period)

    def on_text_message_received(self, message):
        # self.log_debug("client: on_text_message_received: %s" % (message))
        jsonData = json.loads(message)
        message_id = jsonData.get("id")

        # requesting data
        if jsonData.has_key("method"):
            # self.log_debug("client: request detected: %s" % (message))
            method = jsonData.get("method")
            params = jsonData.get("params")
            self.engine.process_request(method, **params)

        if jsonData.has_key("result"):
            # self.log_debug("client: result detected: %s" % (message))
            if message_id in self.callbacks:
                # self.log_debug(
                #     "client: requesting callback result for message: %s"
                #     % message_id
                # )
                result = jsonData.get("result")
                self.callbacks[message_id](result)
                del self.callbacks[message_id]

    def send_text_message(self, command, message_id=None, callback=None, **kwargs):
        if self.client.state() in (
            QAbstractSocket.SocketState.ClosingState,
            QAbstractSocket.SocketState.UnconnectedState,
        ):
            # self.log_debug(
            #     "client: is not connected!, ignoring message: %s" % message_id
            # )
            return

        # wait until connected
        while self.client.state() == QAbstractSocket.SocketState.ConnectingState:
            QCoreApplication.processEvents()
            # self.log_debug("client: waiting state: %s" % self.client.state())
            time.sleep(self.wait_period)
            pass

        if message_id is None:
            message_id = uuid.uuid4().hex

        if callback:
            self.callbacks[message_id] = callback

        message = json.dumps(
            {"jsonrpc": "2.0", "method": command, "params": kwargs, "id": message_id,}
        )

        # self.log_debug("client: send_message: %s" % message)
        self.client.sendTextMessage(message)
        return message_id

    def on_pong(self, elapsedTime, payload):
        # self.log_debug(
        #     "client: onPong - time: {} ; payload: {}".format(
        #         elapsedTime, payload
        #     )
        # )
        pass

    def close(self):
        self.log_debug("client: closed.")
        self.client.close()


class EngineClient(Client):
    def __init__(self, engine, parent=None, url="ws://localhost:12345"):
        super(EngineClient, self).__init__(engine, parent=parent, url=url)

    def get_application_version(self):
        version = self.send_and_receive("GET_VERSION")
        self.log_debug("version: %s (%s)" % (version, type(version)))
        painter_version = version["painter"]
        self.log_debug("painter_version: %s" % painter_version)
        return painter_version

    def get_current_project_path(self):
        path = self.send_and_receive("GET_CURRENT_PROJECT_PATH")
        self.log_debug("CURRENT_PROJECT_PATH: %s (%s)" % (path, type(path)))
        return path

    def need_saving(self):
        result = self.send_and_receive("NEEDS_SAVING", path=path)
        return result

    def open_project(self, path):
        path = self.send_and_receive("OPEN_PROJECT", path=path)

    def save_project_as(self, path):
        success = self.send_and_receive("SAVE_PROJECT_AS", path=path)
        return success

    def save_project_as_action(self):
        result = self.send_and_receive("SAVE_PROJECT_AS_ACTION")
        return result

    def save_project(self):
        success = self.send_and_receive("SAVE_PROJECT")
        return success

    def close_project(self):
        success = self.send_and_receive("CLOSE_PROJECT")
        return success

    def broadcast_event(self, event_name):
        self.send_text_message(event_name)

    def execute(self, statement_str):
        result = self.send_and_receive("EXECUTE_STATEMENT", statement=statement_str)
        return result

    def extract_thumbnail(self, filename):
        result = self.send_and_receive("EXTRACT_THUMBNAIL", path=filename)
        return result

    def import_project_resource(self, filename, usage, destination):
        result = self.send_and_receive(
            "IMPORT_PROJECT_RESOURCE",
            path=filename,
            usage=usage,
            destination=destination,
        )
        return result

    def get_project_settings(self, key):
        result = self.send_and_receive("GET_PROJECT_SETTINGS", key=key)
        return result

    def get_resource_info(self, resource_url):
        result = self.send_and_receive("GET_RESOURCE_INFO", url=resource_url)
        return result

    def get_project_export_path(self):
        result = self.send_and_receive("GET_PROJECT_EXPORT_PATH")
        return result

    def get_map_export_information(self):
        result = self.send_and_receive("GET_MAP_EXPORT_INFORMATION")
        return result

    def export_document_maps(self, destination):
        # This is a trick to wait until the async process of
        # exporting textures finishes.
        self.__export_results = None

        def run_once_finished_exporting_maps(**kwargs):
            self.__export_results = kwargs.get("map_infos", {})

        self.engine.register_event_callback(
            "EXPORT_FINISHED", run_once_finished_exporting_maps
        )

        self.log_debug("Starting map export...")
        result = self.send_and_receive("EXPORT_DOCUMENT_MAPS", destination=destination)

        while self.__export_results is None:
            self.log_debug("Waiting for maps to be exported ...")
            QCoreApplication.processEvents()
            time.sleep(self.wait_period)

        self.engine.unregister_event_callback(
            "EXPORT_FINISHED", run_once_finished_exporting_maps
        )

        result = self.__export_results

        # no need for this variable anymore
        del self.__export_results

        self.log_debug("Map export ended.")
        return result

    def update_document_resources(self, old_url, new_url):
        result = self.send_and_receive(
            "UPDATE_DOCUMENT_RESOURCES", old_url=old_url, new_url=new_url
        )
        return result

    def document_resources(self):
        result = self.send_and_receive("DOCUMENT_RESOURCES")
        return result

    def log_info(self, message):
        self.send_text_message("LOG_INFO", message=message)

    def log_debug(self, message):
        self.send_text_message("LOG_DEBUG", message=message)

    def log_warning(self, message):
        self.send_text_message("LOG_WARNING", message=message)

    def log_error(self, message):
        self.send_text_message("LOG_ERROR", message=message)

    def log_exception(self, message):
        self.send_text_message("LOG_EXCEPTION", message=message)

    def toggle_debug_logging(self, enabled):
        self.send_text_message("TOGGLE_DEBUG_LOGGING", enabled=enabled)


if __name__ == "__main__":
    global client
    app = QApplication(sys.argv)
    client = Client(app)
    version = get_application_version(client)
    client.log_debug("application_version: %s" % version)
    version2 = get_application_version(client)
    client.log_debug("application_version2: %s" % version2)

    app.exec_()
