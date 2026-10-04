import QtQuick
import QtQuick.Controls

Switch {
    id: control
    implicitHeight: 36
    implicitWidth: label.implicitWidth + 65
    hoverEnabled: true
    padding: 0
    font.pixelSize: 12
    contentItem: Text {
        id: label; text: control.text; font: control.font
        color: control.enabled ? Theme.secondary : Theme.disabled
        verticalAlignment: Text.AlignVCenter; rightPadding: 58
    }
    indicator: Rectangle {
        width: 38; height: 23
        x: control.width - width; y: (control.height-height)/2
        radius: height/2
        color: control.checked ? Theme.ink : "#dfe1e5"
        border.color: control.visualFocus ? Theme.muted : "transparent"
        Behavior on color { ColorAnimation { duration: Theme.quick } }
        Rectangle {
            width: 19; height: 19; radius: 10; y: 2
            x: control.checked ? 17 : 2
            color: "white"; border.color: "#18000000"
            Behavior on x { NumberAnimation { duration: Theme.quick; easing.type: Easing.OutCubic } }
        }
    }
}
