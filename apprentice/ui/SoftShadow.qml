import QtQuick

// Layered translucent outlines work with both native and software Qt rendering.
Item {
    id: shadow
    property real cornerRadius: 20
    property real depth: 1
    Repeater {
        model: 5
        Rectangle {
            required property int index
            x: -(index + 1) * shadow.depth
            y: -(index + 1) * shadow.depth + 3 * shadow.depth
            width: shadow.width + (index + 1) * shadow.depth * 2
            height: shadow.height + (index + 1) * shadow.depth * 2
            radius: shadow.cornerRadius + (index + 1) * shadow.depth
            color: "#151b2c"; opacity: 0.012
        }
    }
}
