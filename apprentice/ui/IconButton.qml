import QtQuick
import QtQuick.Controls

Button {
    id: control
    property string iconName: "wave"
    property string label: ""
    property bool danger: false
    property bool filled: false
    property bool selected: false
    implicitWidth: 40; implicitHeight: 40
    padding: 10; hoverEnabled: true
    Accessible.name: label
    Accessible.description: label
    scale: down ? 0.95 : 1
    Behavior on scale { NumberAnimation { duration: Theme.quick; easing.type: Easing.OutCubic } }
    contentItem: AppIcon { name: control.iconName; color: !control.enabled ? Theme.disabled : control.danger ? Theme.recording : control.filled ? "white" : Theme.text }
    background: Rectangle {
        radius: width / 2
        color: control.filled ? Theme.ink : control.selected ? Theme.hover : control.hovered ? Theme.subtle : Theme.surface
        border.color: control.visualFocus ? Theme.text : Theme.line
        Behavior on color { ColorAnimation { duration: Theme.quick } }
        SoftShadow { anchors.fill: parent; z: -1; cornerRadius: parent.radius; opacity: control.hovered && control.enabled ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.quick } } }
    }
    ToolTip {
        visible: control.hovered || control.visualFocus
        delay: 400; timeout: 4000
        text: control.label
        y: -implicitHeight - 8
        padding: 9
        contentItem: Text { text: control.label; color: "white"; font.family: Theme.family; font.pixelSize: 11 }
        background: Rectangle { color: Theme.ink; radius: 8 }
    }
}
