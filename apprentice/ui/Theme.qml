pragma Singleton
import QtQuick

// Shared visual tokens. Color is reserved for meaningful activity and status.
QtObject {
    readonly property color canvas: "#f7f8fa"
    readonly property color surface: "#ffffff"
    readonly property color subtle: "#f3f4f6"
    readonly property color hover: "#eceef1"
    readonly property color line: "#e7e8ec"
    readonly property color text: "#17181b"
    readonly property color secondary: "#555961"
    readonly property color muted: "#747983"
    readonly property color disabled: "#a5a8b0"
    readonly property color ink: "#191a1d"
    readonly property color recording: "#ed4456"
    readonly property color recordingTint: "#fff0f2"
    readonly property color success: "#33705a"
    readonly property color successTint: "#f0f7f4"
    readonly property color warning: "#8e6228"
    readonly property color warningTint: "#faf5ed"
    readonly property int quick: 140
    readonly property int gentle: 220
    readonly property string family: Qt.platform.os === "osx" ? "Helvetica Neue" : "Segoe UI"
}
