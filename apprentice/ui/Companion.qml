import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// A separate native window. The orb's screen position stays fixed on expansion;
// the bar opens toward available space and dragging moves the complete control.
Window {
    id: companion
    objectName: "bubbleWindow"
    property var session: ({})
    property bool expanded: false
    property bool expandLeft: true
    property real dockX: Screen.virtualX + Screen.width - 118
    property real spread: expanded ? actions.implicitWidth + 18 : 0
    signal contextRequested()
    width: 100 + spread; height: 128
    x: dockX - (expandLeft ? spread : 0)
    y: Screen.virtualY + Screen.height - height - 64
    visible: false; color: "transparent"
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    Behavior on spread { NumberAnimation { duration: Theme.gentle; easing.type: Easing.OutCubic } }

    function toggleExpanded() {
        if (!expanded) expandLeft = dockX - Screen.virtualX >= actions.implicitWidth + 28;
        expanded = !expanded;
    }
    function keepOnScreen() {
        var left = Screen.virtualX + 8 + (expandLeft ? spread : 0);
        var right = Screen.virtualX + Screen.width - 108 - (expandLeft ? 0 : spread);
        dockX = Math.max(left, Math.min(right, dockX));
        y = Math.max(Screen.virtualY, Math.min(Screen.virtualY + Screen.height - height, y));
    }
    Rectangle {
        x: 14; y: 48; width: companion.width - 28; height: 64; radius: 32
        color: Theme.surface; border.color: Theme.line
        opacity: Math.min(1, companion.spread / 40)
        SoftShadow { anchors.fill: parent; cornerRadius: 32; depth: 2; z: -1 }
    }
    RowLayout {
        id: actions
        x: companion.expandLeft ? 23 : 91; y: 60
        spacing: 7
        opacity: Math.min(1, companion.spread / Math.max(1, implicitWidth))
        visible: companion.spread > 1
        enabled: companion.expanded
        IconButton { objectName: "companionRecord"; iconName: session.recording ? "stop" : "record"; label: session.recording ? "Stop recording" : "Start recording"; danger: true
            enabled: !!session.sessionId && session.mode !== "demo"
            onClicked: session.recording ? backend.stopRecording() : backend.startRecording()
        }
        IconButton { visible: !!session.recording; iconName: session.paused ? "play" : "pause"; label: session.paused ? "Resume recording" : "Pause recording"; onClicked: backend.togglePause() }
        IconButton { iconName: "context"; label: "Add context"; enabled: !!session.sessionId; onClicked: companion.contextRequested() }
        IconButton { iconName: session.listening ? "stop" : "mic"; label: session.listening ? "Finish voice note" : "Voice note"; selected: !!session.listening; enabled: !!session.sessionId && !session.paused && !session.offRecord; onClicked: backend.toggleVoiceNote() }
        IconButton { objectName: "companionMute"; iconName: session.prompts || session.voiceEnabled ? "mute" : "sound"; label: session.prompts || session.voiceEnabled ? "Mute assistant" : "Unmute assistant"; selected: !session.prompts && !session.voiceEnabled
            onClicked: { var enable = !session.prompts && !session.voiceEnabled; backend.setPrompts(enable); if (session.elevenReady) backend.setVoice(enable); }
        }
        IconButton { iconName: "open"; label: "Open application"; onClicked: backend.reveal() }
    }
    VoiceOrb {
        id: orb; objectName: "companionOrb"
        x: companion.expandLeft ? companion.spread + 18 : 18
        y: 46; width: 68; height: 68
        active: !!session.listening || !!session.speaking
        question: !!session.pendingQuestion
        recording: !!session.recording && !session.paused
        scale: drag.pressed ? 0.96 : drag.containsMouse ? 1.025 : 1
        Behavior on scale { NumberAnimation { duration: Theme.quick } }
        Rectangle { anchors.fill: parent; anchors.margins: -3; radius: width/2; color: "transparent"; border.color: orb.activeFocus ? Theme.secondary : "transparent" }
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: companion.expanded ? "Collapse assistant controls" : "Expand assistant controls"
        Accessible.onPressAction: companion.toggleExpanded()
        Keys.onSpacePressed: companion.toggleExpanded()
        Keys.onReturnPressed: companion.toggleExpanded()
        MouseArea {
            id: drag; anchors.fill: parent; hoverEnabled: true
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.PointingHandCursor
            property point origin
            property real startX
            property real startY
            property bool moved: false
            onPressed: function(mouse) { orb.forceActiveFocus(); origin = mapToGlobal(mouse.x, mouse.y); startX = companion.dockX; startY = companion.y; moved = false; }
            onPositionChanged: function(mouse) {
                if (!pressed) return;
                var point = mapToGlobal(mouse.x, mouse.y);
                if (Math.abs(point.x-origin.x) + Math.abs(point.y-origin.y) > 5) moved = true;
                if (moved) { companion.dockX = startX + point.x-origin.x; companion.y = startY + point.y-origin.y; }
            }
            onReleased: { if (moved) companion.keepOnScreen(); else companion.toggleExpanded(); }
        }
    }
}
