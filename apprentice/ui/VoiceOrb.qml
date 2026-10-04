import QtQuick

// A restrained voice accent; motion runs only while listening or speaking.
Item {
    id: orb
    property bool active: false
    property bool question: false
    property bool recording: false
    implicitWidth: 64; implicitHeight: 64
    Rectangle {
        anchors.fill: parent; radius: width/2
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: "#d9f2e6" }
            GradientStop { position: 0.52; color: "#c5e7ee" }
            GradientStop { position: 1; color: "#b5ccf4" }
        }
        border.color: "#e8f0fa"
        Rectangle { anchors.fill: parent; anchors.margins: 2; radius: width/2
            gradient: Gradient {
                GradientStop { position: 0; color: "#95ffffff" }
                GradientStop { position: 0.48; color: "#00ffffff" }
                GradientStop { position: 1; color: "#2083bdf0" }
            }
        }
        SoftShadow { anchors.fill: parent; z: -1; cornerRadius: parent.radius; depth: 1.4 }
    }
    AppIcon {
        anchors.centerIn: parent; width: parent.width * 0.44; height: width
        name: "wave"; color: "#25383d"
        SequentialAnimation on scale {
            running: orb.active; loops: Animation.Infinite
            NumberAnimation { from: 0.94; to: 1.06; duration: 650; easing.type: Easing.InOutSine }
            NumberAnimation { from: 1.06; to: 0.94; duration: 650; easing.type: Easing.InOutSine }
        }
    }
    Rectangle {
        visible: orb.recording || orb.question
        width: 14; height: 14; radius: 7
        anchors.right: parent.right; anchors.top: parent.top
        color: orb.recording ? Theme.recording : Theme.ink
        border.width: 2; border.color: "white"
        Text { visible: orb.question && !orb.recording; anchors.centerIn: parent; text: "?"; font.pixelSize: 9; color: "white" }
    }
}
