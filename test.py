import sys
sys.path.insert(0, r"D:\demo\configs\anim_cuts\install\core\python")

sys.path.insert(0, r"C:\Users\diego\GoogleDrive\Development\factor64\tk-substancepainter\python")

sys.path.insert(0, r"D:\demo\configs\anim_cuts\install\gitbranch\tk-framework-unrealqt.git\58c2f7b\resources\pyside2-5.9.0a1")


import tank

from PySide2 import QtCore, QtGui, QtWidgets

print QtCore, QtGui, QtWidgets

import tk_substancepainter.menu_generation
import logging

logger = logging.getLogger("test")


class Bundle(object):
    def __init__(self):
        pass

class Engine(object):
    def __init__(self):
        self.logger = logger 
        self.context = Bundle()
        self.context.shotgun_url = ""

        self.init_qt_app()
        self.create_menu()
        self.post_app_init()

    def init_qt_app(self):
        print("Initializing QtApp for Substance Painter...")

        if not QtWidgets.QApplication.instance():
            self._qt_app = QtWidgets.QApplication(sys.argv)
            self.logger.debug("New QtApp created: %s", self._qt_app)
            self._qt_app.setQuitOnLastWindowClosed(False)

        else:
            self._qt_app = QtWidgets.QApplication.instance()
        print("Initializing QtApp for Substance Painter. Done")

    def show(self):
        pos = QtGui.QCursor.pos()
        self.menu.exec_(pos)

    def create_menu(self):
        #w = QtWidgets.QWidget()
        self.menu = QtWidgets.QMenu("Menu")
        act = self.menu.addAction("MENU")


        #self.menu = tk_substancepainter.menu_generation.MenuGenerator(self, "Shotgun")
        QtCore.QTimer.singleShot(5000, self.show)

    def post_app_init(self):
        #self.menu.show()
        self._qt_app.exec_()

engine = Engine()
