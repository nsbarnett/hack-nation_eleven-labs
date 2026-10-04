import QtQuick
import QtQuick.Controls

Dialog {
    id: dialog
    padding: 24
    topPadding: 12
    font.family: Theme.family
    palette.windowText: Theme.text
    palette.text: Theme.text
    palette.buttonText: Theme.text
    palette.button: Theme.surface
    palette.base: Theme.surface
    palette.highlight: Theme.ink
    background: Rectangle {
        color: Theme.surface; radius: 22; border.color: Theme.line
        SoftShadow { anchors.fill: parent; z: -1; cornerRadius: 22; depth: 3 }
    }
    header: Label {
        text: dialog.title; visible: !!text; color: Theme.text
        font.pixelSize: 19; font.weight: Font.Medium
        padding: 24; bottomPadding: 16
    }
    footer: DialogButtonBox {
        padding: 18; spacing: 8
        standardButtons: dialog.standardButtons
        delegate: AppButton { }
        background: Item { }
    }
    Overlay.modal: Rectangle { color: "#30131620" }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.quick } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 100 } }
}
