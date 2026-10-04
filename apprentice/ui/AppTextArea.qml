import QtQuick
import QtQuick.Controls

TextArea {
    id: field
    color: Theme.text; placeholderTextColor: Theme.muted
    font.pixelSize: 13; font.family: Theme.family
    padding: 14
    selectByMouse: true; wrapMode: TextEdit.Wrap
    selectionColor: "#dfe4ee"; selectedTextColor: Theme.text
    background: Rectangle {
        radius: 14; color: Theme.canvas
        border.color: field.activeFocus ? "#9da3ad" : Theme.line
        Behavior on border.color { ColorAnimation { duration: Theme.quick } }
    }
}
