// Substance Painter menu in the toolbar.
// We track is the engine has been loaded and enable/diable the Shotgun icon
// accordingly.

// __author__ = "Diego Garcia Huerta"
// __email__ = "diegogh2000@gmail.com"


import AlgWidgets.Style 1.0
import QtQuick 2.7
import QtQuick.Controls 1.4
import QtQuick.Controls.Styles 1.4

Button {
  id: control
  antialiasing: true
  height: 32
  width: 32
  tooltip: "Open Shotgun Menu"
  property var clickedPosition: null
  property bool isEngineLoaded: false
  property bool isHovered: false

  enabled: control.isEngineLoaded

  style: ButtonStyle {
    background: Rectangle {
        implicitWidth: control.width
        implicitHeight: control.height
        color: control.isHovered ?
          "#262626" :
          "transparent"
    }
  }

  Image {
    id: controlImage
    anchors.fill: parent
    antialiasing: true
    anchors.margins: 8
    fillMode:Image.PreserveAspectFit
    source: control.isHovered ? "icons/sg_hover.png" : "icons/sg_idle.png"
    mipmap: true
    opacity: control.enabled ?
      1.0:
      0.3
    sourceSize.width: control.width
    sourceSize.height: control.height
  }

  MouseArea {
    hoverEnabled: true
    anchors.fill: control

      onEntered: {
        control.isHovered = true
      }


      onExited: {
        control.isHovered = false
      }

      onClicked: {
        if (control.isEngineLoaded)
        {
          control.clickedPosition = mapToGlobal(mouse.x, mouse.y);
          control.clicked()
        }
        else{
          alg.log.warn("SubstancePainter Shotgun Engine is being loaded. Please wait...");
        }
      }
  }

  Rectangle {
    id: autoLinkButton
    height: 5
    width: height
    x: 2
    y: 2

    radius: width

    visible: !control.isEngineLoaded
    color: !control.isEngineLoaded ? "#9C2FB2" : "#EF4E35"

  }

}
