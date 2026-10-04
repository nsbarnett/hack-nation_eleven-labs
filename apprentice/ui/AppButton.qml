import QtQuick
import QtQuick.Controls

Button {
    id: control
    property bool primary: false
    property bool danger: false
    property bool compact: false
    property string iconName: ""
    implicitHeight: compact ? 34 : 42
    implicitWidth: Math.max(compact ? 64 : 88, contentItem.implicitWidth + 32)
    hoverEnabled: true
    padding: 12
    font.pixelSize: compact ? 12 : 13
    font.weight: Font.Medium
    font.family: Theme.family
    scale: down ? 0.98 : 1
    Behavior on scale { NumberAnimation { duration: Theme.quick } }
    contentItem: Item {
        implicitWidth: buttonText.implicitWidth + (control.iconName ? 24 : 0)
        implicitHeight: 20
        readonly property color foreground: !control.enabled ? Theme.disabled : control.primary || control.danger ? "white" : Theme.text
        AppIcon { visible: !!control.iconName; name: control.iconName; width: 17; height: 17; anchors.verticalCenter: parent.verticalCenter; color: parent.foreground }
        Text {
            id: buttonText; text: control.text; font: control.font; color: parent.foreground
            x: control.iconName ? 24 : 0; width: parent.width - x; anchors.verticalCenter: parent.verticalCenter
            horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
        }
    }
    background: Rectangle {
        radius: height / 2
        color: !control.enabled ? Theme.subtle : control.danger ? (control.hovered ? "#d8374a" : Theme.recording) : control.primary ? (control.hovered ? "#35373c" : Theme.ink) : control.hovered ? Theme.subtle : Theme.surface
        border.width: 1
        border.color: control.visualFocus ? Theme.muted : control.primary || control.danger ? "transparent" : Theme.line
        Behavior on color { ColorAnimation { duration: Theme.quick } }
        SoftShadow { anchors.fill: parent; z: -1; cornerRadius: parent.radius; opacity: control.hovered && control.enabled ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.quick } } }
    }
}
