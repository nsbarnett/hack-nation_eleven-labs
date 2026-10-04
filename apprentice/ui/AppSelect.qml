import QtQuick
import QtQuick.Controls

ComboBox {
    id: select
    implicitHeight: 42
    font.pixelSize: 13; font.family: Theme.family
    contentItem: Text { text: select.displayText; font: select.font; color: Theme.text; verticalAlignment: Text.AlignVCenter; leftPadding: 14; rightPadding: 32; elide: Text.ElideRight }
    indicator: AppIcon { name: "down"; width: 16; height: 16; x: select.width - width - 12; y: (select.height-height)/2; color: Theme.secondary }
    background: Rectangle { radius: 12; color: Theme.canvas; border.color: select.visualFocus ? "#9da3ad" : Theme.line }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: select.width - 8; height: 38
        highlighted: select.highlightedIndex === index
        contentItem: Text { text: modelData; font: select.font; color: Theme.text; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 9; color: parent.highlighted ? Theme.subtle : "transparent" }
    }
    popup: Popup {
        y: select.height + 5; width: select.width; padding: 4
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 240)
        contentItem: ListView { clip: true; implicitHeight: contentHeight; model: select.popup.visible ? select.delegateModel : null; currentIndex: select.highlightedIndex; ScrollIndicator.vertical: ScrollIndicator {} }
        background: Rectangle { radius: 13; color: Theme.surface; border.color: Theme.line; SoftShadow { anchors.fill: parent; z: -1; cornerRadius: 13 } }
    }
}
