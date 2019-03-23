import os
import sys

dir_path = os.path.dirname(os.path.realpath(__file__))

# let's add the thirparty python libraries first
websocket_path = os.path.join(dir_path, "..", "ext", "websocket-client")
if websocket_path not in sys.path:
    sys.path.append(websocket_path)

backports_ssl_match_hostname_path = os.path.join(dir_path, "ext", "backports.ssl_match_hostname")
if backports_ssl_match_hostname_path not in sys.path:
    sys.path.append(backports_ssl_match_hostname_path)

import websocket
print websocket

websocket.enableTrace(True)

try:
    import thread
except ImportError:
    import thread as thread
import time

def on_message(ws, message):
    print("Received!: %s" % message)
    if message == "close":
        ws.close()
    if "DISPLAY_MENU" in message:
        print("DISPLAY_MENU >> %s" % message)
    if "PING" in message:
        send("PING_BACK", "{status:true}")

def on_error(ws, error):
    print(error)

def on_close(ws):
    print("### closed ###")

def send(ws, message):
    def run(*args):
        ws.send(message)
        print("thread terminating...")
    thread.start_new_thread(run, ())

def on_open(ws):
    print("Connected.")


if __name__ == "__main__":
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp("ws://localhost:12345/",
                              on_message = on_message,
                              on_error = on_error,
                              on_close = on_close)
    ws.on_open = on_open
    ws.run_forever()