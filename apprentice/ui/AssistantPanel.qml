import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One quiet conversation surface. Secondary controls are disclosed on demand.
Panel {
    id: panel
    property var session: ({messages: []})
    property bool tutoring: false
    property bool showPreferences: false
    function focusComposer() { note.forceActiveFocus(); }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 18; spacing: 14
        RowLayout {
            Layout.fillWidth: true; spacing: 11
            AppIcon { name: "wave"; Layout.preferredWidth: 23; Layout.preferredHeight: 23 }
            ColumnLayout { spacing: 4; Layout.fillWidth: true
                Label { text: panel.tutoring ? "Your tutor" : "AI assistant"; font.pixelSize: 15; font.weight: Font.Medium; color: Theme.text }
                Label { text: session.listening ? "Listening to you…" : session.speaking ? "Speaking…" : session.busy ? "Connecting the details…" : "Here when you need me"; color: Theme.muted; font.pixelSize: 11 }
            }
            IconButton { iconName: "settings"; label: "Assistant preferences"; implicitWidth: 32; implicitHeight: 32; padding: 8; selected: panel.showPreferences; onClicked: panel.showPreferences = !panel.showPreferences }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
        ListView {
            id: conversation
            Layout.fillWidth: true; Layout.fillHeight: true
            model: session.messages; spacing: 12; clip: true
            onCountChanged: Qt.callLater(function() { conversation.positionViewAtEnd(); })
            delegate: Item {
                required property var modelData
                width: ListView.view.width; height: messageBody.implicitHeight + 29
                Rectangle {
                    x: modelData.role === "user" ? 16 : 0
                    width: parent.width - 16; height: parent.height
                    radius: 16; color: modelData.role === "user" ? Theme.subtle : Theme.surface
                    border.color: modelData.role === "user" ? "transparent" : Theme.line
                    Label { id: messageBody; anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 14
                        text: modelData.text; textFormat: Text.PlainText; wrapMode: Text.WordWrap
                        color: Theme.secondary; font.pixelSize: 13; lineHeight: 1.35
                    }
                }
            }
            ColumnLayout {
                visible: !session.messages || session.messages.length === 0
                anchors.centerIn: parent; width: parent.width - 18; spacing: 15
                AppIcon { name: "wave"; Layout.alignment: Qt.AlignHCenter; Layout.preferredWidth: 27; Layout.preferredHeight: 27; color: Theme.disabled }
                Label { text: "A little context goes a long way."; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; color: Theme.secondary; font.pixelSize: 13 }
                Label { text: "Share what you’re working toward.\nI’ll ask when something needs explaining."; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; color: Theme.muted; font.pixelSize: 12; lineHeight: 1.5 }
            }
        }
        AppButton { visible: !!session.pendingQuestion; text: "Not now"; compact: true; Layout.alignment: Qt.AlignRight; onClicked: backend.deferQuestion() }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 134
            radius: 16; color: Theme.canvas; border.color: note.activeFocus ? "#9da3ad" : Theme.line
            ColumnLayout { anchors.fill: parent; anchors.margins: 10; spacing: 6
                AppTextArea { id: note; objectName: "contextComposer"; Layout.fillWidth: true; Layout.fillHeight: true
                    placeholderText: panel.tutoring ? "Ask about the confirmed map…" : "Add context or ask a question…"
                    padding: 4; background: Item {}
                }
                RowLayout { Layout.fillWidth: true
                    IconButton { iconName: session.listening ? "stop" : "mic"; label: session.listening ? "Finish voice note" : "Add a voice note"; implicitWidth: 32; implicitHeight: 32; padding: 8; selected: !!session.listening; enabled: !!session.sessionId && !session.offRecord && !session.paused; onClicked: backend.toggleVoiceNote() }
                    Label { text: session.listening ? "Listening…" : ""; font.pixelSize: 11; color: Theme.secondary; Layout.fillWidth: true }
                    IconButton { iconName: "arrow"; label: "Send message"; filled: true; implicitWidth: 32; implicitHeight: 32; padding: 8
                        enabled: !!session.sessionId && note.text.trim().length > 0 && !session.offRecord && !session.paused
                        onClicked: { if (panel.tutoring) backend.askTutor(note.text); else backend.addNote(note.text); note.clear(); }
                    }
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 4
            visible: panel.showPreferences
            AppSwitch { text: "Ask at natural pauses"; Layout.fillWidth: true; checked: !!session.prompts; onToggled: backend.setPrompts(checked) }
            AppSwitch { text: "Assistant voice"; Layout.fillWidth: true; checked: !!session.voiceEnabled; onToggled: backend.setVoice(checked) }
            Label { text: "The microphone opens for voice notes or after a spoken question."; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 11; color: Theme.muted }
        }
        RowLayout { Layout.alignment: Qt.AlignHCenter; spacing: 6
            Rectangle { width: 5; height: 5; radius: 3; color: session.listening ? Theme.success : Theme.disabled }
            Label { text: session.listening ? "Microphone on" : "Microphone off"; color: Theme.muted; font.pixelSize: 10 }
        }
    }
}
