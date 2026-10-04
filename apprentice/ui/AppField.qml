import QtQuick
import QtQuick.Controls

TextField {
    id: field
    implicitHeight: 42
    leftPadding: 14; rightPadding: 14
    selectByMouse: true
    color: Theme.text
    placeholderTextColor: Theme.muted
    font.pixelSize: 13; font.family: Theme.family
    selectionColor: "#dfe4ee"; selectedTextColor: Theme.text
    background: Rectangle { radius: 12; color: Theme.canvas; border.color: field.activeFocus ? "#9da3ad" : Theme.line; Behavior on border.color { ColorAnimation { duration: Theme.quick } } }
}
