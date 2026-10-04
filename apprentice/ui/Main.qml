import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: app
    objectName: "mainWindow"
    width: 1480; height: 940
    minimumWidth: 1120; minimumHeight: 760
    visible: true
    title: "AI Apprentice — Learn the judgment behind the work"
    color: Theme.canvas
    font.family: Theme.family
    font.pixelSize: 13
    palette.windowText: Theme.text
    palette.text: Theme.text
    palette.buttonText: Theme.text
    palette.base: Theme.surface
    palette.window: Theme.surface
    palette.highlight: Theme.ink
    palette.highlightedText: "white"
    property var s: backend.state
    property string page: "Overview"
    property bool quitting: false
    property var selectedRule: ({})
    property var deleteTarget: ({})
    property string selectedCheck: "null"
    property var tutorResult: ({verdict: "", explanation: "Review a case before saving. The tutor uses only your confirmed map.", knowledge_ids: []})
    onClosing: function(close) {
        if (!quitting) { close.accepted = false; app.hide(); bubble.show(); }
    }
    onVisibilityChanged: {
        if (visibility === Window.Minimized || visibility === Window.Hidden) bubble.show();
        else if (!s.recording) bubble.hide();
    }
    Connections {
        target: backend
        function onNavigate(destination) { app.page = destination; }
        function onShowMain() { app.showNormal(); app.raise(); app.requestActivate(); }
        function onMinimizeMain() { app.showMinimized(); bubble.show(); }
        function onQuitReady() { app.quitting = true; bubble.close(); app.close(); Qt.quit(); }
    }

    function showRule(item) {
        selectedRule = item;
        ruleTitle.text = item.title;
        actionEdit.text = item.action;
        decisionEdit.text = item.decision;
        reasonEdit.text = item.reason;
        ruleEdit.text = item.rule;
        exceptionEdit.text = item.exception;
        guardrailEdit.text = item.guardrail;
        escalationEdit.text = item.escalation;
        checkEdit.text = JSON.stringify(item.check, null, 2);
        editDialog.open();
    }
    function caseData() {
        return JSON.stringify({amount: amount.text, category: category.currentText,
            asset_number: asset.text, supplier_status: supplier.currentText,
            purchase_type: purchase.currentText, currency: currency.currentText});
    }

    RowLayout {
        anchors.fill: parent; spacing: 0
        Rectangle {
            Layout.preferredWidth: 178; Layout.fillHeight: true
            color: Theme.surface
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.line }
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 18; spacing: 8
                RowLayout {
                    Layout.topMargin: 15; Layout.bottomMargin: 24; spacing: 10
                    Rectangle { width: 32; height: 32; radius: 16; color: Theme.ink
                        AppIcon { anchors.centerIn: parent; width: 20; height: 20; color: "white"; name: "wave" }
                    }
                    ColumnLayout { spacing: 0
                        Label { text: "apprentice"; font.pixelSize: 17; font.weight: Font.Medium; color: Theme.text }
                        Label { text: "Your AI apprentice"; font.pixelSize: 10; color: Theme.muted }
                    }
                }
                Label { text: "WORKSPACE"; font.pixelSize: 10; font.letterSpacing: 1.3; color: Theme.muted; Layout.leftMargin: 12; Layout.bottomMargin: 7 }
                Repeater {
                    model: ["Overview", "Capture", "Work Map", "Teach", "Evidence", "Library", "Settings"]
                    delegate: ItemDelegate {
                        required property string modelData
                        required property int index
                        Layout.fillWidth: true; implicitHeight: 42
                        onClicked: app.page = modelData
                        background: Rectangle { radius: 12; color: app.page === modelData ? Theme.hover : parent.hovered ? Theme.subtle : "transparent"; Behavior on color { ColorAnimation { duration: Theme.quick } } }
                        contentItem: RowLayout { spacing: 13
                            AppIcon { name: ["home", "capture", "map", "teach", "evidence", "library", "settings"][index]; Layout.preferredWidth: 18; Layout.preferredHeight: 18; color: app.page === modelData ? Theme.text : Theme.secondary }
                            Label { text: modelData; color: Theme.text; font.weight: app.page === modelData ? Font.Medium : Font.Normal; Layout.fillWidth: true }
                        }
                    }
                }
                Item { Layout.fillHeight: true }
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 146; radius: 12; color: "transparent"
                    ColumnLayout { anchors.fill: parent; anchors.margins: 14; spacing: 8
                        Label { text: "Learn as you work."; color: Theme.secondary; font.pixelSize: 12; font.weight: Font.Normal; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                        Label { text: "Capture the why.\nShare what works."; color: Theme.muted; font.pixelSize: 11; lineHeight: 1.4; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    }
                }
                AppButton { Layout.fillWidth: true; text: "Quit application"; compact: true; onClicked: quitDialog.open() }
                Label { text: "AI APPRENTICE  /  0.1"; color: Theme.muted; font.pixelSize: 9; Layout.topMargin: 6; Layout.alignment: Qt.AlignHCenter }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            Layout.margins: 24; spacing: 16
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout { spacing: 4; Layout.fillWidth: true
                    Label { text: app.page === "Overview" ? "Your work, understood." : app.page; font.pixelSize: 27; font.weight: Font.Medium; color: Theme.text }
                    Label { text: s.sessionId ? s.title : "Turn experience into knowledge someone else can use."; color: Theme.muted; elide: Text.ElideRight; Layout.fillWidth: true }
                }
                Rectangle { visible: s.mode === "demo" && !!s.sessionId; implicitWidth: 115; implicitHeight: 30; radius: 15; color: Theme.subtle
                    Label { anchors.centerIn: parent; text: "OFFLINE DEMO"; font.pixelSize: 10; font.weight: Font.Medium; color: Theme.secondary }
                }
                AppButton { text: "New session"; iconName: "plus"; primary: true; onClicked: newDialog.open() }
            }

            // Overview is deliberately usable before API keys or a recording exist.
            ColumnLayout {
                visible: app.page === "Overview"; Layout.fillWidth: true; Layout.fillHeight: true; spacing: 20
                Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: app.height < 840 ? 276 : 300; radius: 22; color: Theme.surface; border.color: Theme.line
                    RowLayout { anchors.fill: parent; anchors.margins: app.height < 840 ? 28 : 32; spacing: 30
                        ColumnLayout { Layout.fillWidth: true; spacing: 12
                            Label { text: "YOUR EVERYDAY EXPERTISE"; color: Theme.muted; font.pixelSize: 11; font.letterSpacing: 2 }
                            Label { text: "Good work is worth\nunderstanding."; color: Theme.text; font.pixelSize: 31; font.weight: Font.Medium; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                            Label { text: "Learn an expert’s decisions, exceptions, and guardrails.\nBuild a Work Map that teaches the next person."; color: Theme.secondary; font.pixelSize: 14; lineHeight: 1.4; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                            RowLayout { spacing: 10
                                AppButton { text: "Start a session"; primary: true; onClicked: newDialog.open() }
                                AppButton { text: "Explore a demonstration"; onClicked: backend.loadDemo() }
                            }
                        }
                        Item { Layout.preferredWidth: 162; Layout.preferredHeight: 170
                            Rectangle { anchors.centerIn: parent; width: 155; height: 155; radius: 78; color: Theme.canvas; border.color: Theme.line }
                            VoiceOrb { anchors.centerIn: parent; width: 104; height: 104 }
                        }
                    }
                }
                RowLayout { Layout.fillWidth: true; spacing: 16
                    Repeater { model: [{number:"01",title:"Capture the judgment",body:"Record a task and explain the decisions a screenshot cannot."}, {number:"02",title:"Review the Work Map",body:"Trace every rule to evidence. Correct it and confirm what is true."}, {number:"03",title:"Teach a new case",body:"Apply confirmed rules, catch mistakes, and explain the reasoning."}]
                        delegate: Panel { required property var modelData; Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: app.height < 840 ? 168 : 180
                            ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 10
                                Label { text: modelData.number; color: Theme.muted; font.pixelSize: 23 }
                                Label { text: modelData.title; color: Theme.text; font.weight: Font.Medium; font.pixelSize: 15 }
                                Label { text: modelData.body; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.muted; lineHeight: 1.4 }
                                Item { Layout.fillHeight: true }
                            }
                        }
                    }
                }
                Label { text: "Saved sessions"; font.pixelSize: 18; font.weight: Font.Medium; color: Theme.text }
                ListView {
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 8; model: s.history
                    delegate: Panel { required property var modelData; width: ListView.view.width; height: 65
                        RowLayout { anchors.fill: parent; anchors.margins: 14
                            Label { text: modelData.title; Layout.fillWidth: true; color: Theme.text; font.weight: Font.Medium }
                            Label { text: modelData.updated.slice(0,10); color: Theme.muted }
                            AppButton { text: "Open"; compact: true; onClicked: backend.openSession(modelData.id) }
                        }
                    }
                    Label { visible: s.history.length === 0; text: "Your first session will appear here."; color: Theme.muted }
                }
            }

            RowLayout {
                visible: ["Capture", "Work Map", "Teach", "Evidence"].indexOf(app.page) >= 0
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: 16
                ColumnLayout {
                    Layout.fillWidth: true; Layout.fillHeight: true; spacing: 12
                    Panel {
                        Layout.fillWidth: true; Layout.preferredHeight: 62
                        RowLayout { anchors.fill: parent; anchors.margins: 12; spacing: 10
                            Rectangle { width: 10; height: 10; radius: 5; color: s.recording && !s.paused ? Theme.recording : Theme.muted }
                            Label { text: s.offRecord ? "Off the record" : s.paused ? "Paused" : s.recording ? "Recording" : "Ready"; color: Theme.text; font.weight: Font.Medium }
                            Label { text: backend.clock; color: Theme.text; font.family: "Consolas"; font.pixelSize: 16 }
                            Item { Layout.fillWidth: true }
                            AppButton { visible: !s.recording; text: app.page === "Teach" ? "Watch trainee" : "Record"; iconName: "record"; primary: true; enabled: !!s.sessionId && s.mode !== "demo"; onClicked: app.page === "Teach" ? backend.startTeaching() : backend.startRecording() }
                            AppButton { visible: s.recording; text: s.paused ? "Resume" : "Pause"; iconName: s.paused ? "play" : "pause"; compact: true; onClicked: backend.togglePause() }
                            AppButton { visible: s.recording; text: "Stop"; iconName: "stop"; danger: true; compact: true; onClicked: backend.stopRecording() }
                            AppButton { text: "Off record"; compact: true; enabled: s.recording && !s.offRecord; onClicked: backend.offRecord() }
                        }
                    }

                    ColumnLayout {
                        visible: app.page === "Capture"; Layout.fillWidth: true; Layout.fillHeight: true; spacing: 12
                        Panel {
                            Layout.fillWidth: true; Layout.preferredHeight: 285; clip: true
                            Image { anchors.fill: parent; anchors.margins: 8; fillMode: Image.PreserveAspectFit; source: backend.previewUrl; cache: false; visible: s.evidenceCount > 0 && s.mode !== "demo" && !s.recording }
                            ColumnLayout { anchors.centerIn: parent; width: parent.width - 50; visible: s.recording || s.evidenceCount === 0 || s.mode === "demo"; spacing: 14
                                AppIcon { name: s.recording ? "capture" : "screen"; Layout.preferredWidth: 38; Layout.preferredHeight: 38; color: s.recording && !s.paused ? Theme.recording : Theme.disabled; Layout.alignment: Qt.AlignHCenter }
                                Label { text: s.recording ? (s.paused ? "Observation is paused" : "Learning from your screen") : "A window into your workflow"; font.pixelSize: 21; font.weight: Font.Medium; color: Theme.text; Layout.alignment: Qt.AlignHCenter }
                                Label { text: s.recording ? "Recording continues while you work. Preview is hidden during capture to prevent recording itself." : "Choose a screen and start recording.\nAdd your intent in the assistant panel as you go."; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true; color: Theme.muted; lineHeight: 1.4 }
                            }
                        }
                        RowLayout { Layout.fillWidth: true
                            Label { text: "Meaningful moments"; font.pixelSize: 16; font.weight: Font.Medium; color: Theme.text; Layout.fillWidth: true }
                            AppButton { text: "Analyze latest"; compact: true; enabled: s.cloudEnabled && !s.busy && !s.paused; onClicked: backend.analyzeLatest() }
                        }
                        ListView { Layout.fillWidth: true; Layout.fillHeight: true; model: s.observations; spacing: 8; clip: true
                            delegate: Panel { required property var modelData; required property int index; width: ListView.view.width; height: Math.max(78, momentText.implicitHeight + 36)
                                RowLayout { anchors.fill: parent; anchors.margins: 15; spacing: 14
                                    Rectangle { width: 30; height: 30; radius: 15; color: Theme.line; Label { anchors.centerIn: parent; text: index + 1; color: Theme.muted } }
                                    ColumnLayout { Layout.fillWidth: true; spacing: 5
                                        Label { id: momentText; text: modelData.summary; color: Theme.text; font.weight: Font.Medium; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                        Label { visible: !!modelData.question; text: modelData.asked ? "Question delivered" : "Question queued for a pause"; color: Theme.muted; font.pixelSize: 11 }
                                    }
                                }
                            }
                            Label { visible: s.observations.length === 0; text: "Meaningful changes will appear after analysis.\nManual notes are always available."; color: Theme.muted; lineHeight: 1.5 }
                        }
                        RowLayout { Layout.fillWidth: true
                            AppButton { text: "Ask a debrief question"; enabled: !!s.sessionId && !s.recording && !s.busy; onClicked: backend.debrief() }
                            Item { Layout.fillWidth: true }
                            AppButton { text: "Build Work Map"; primary: true; enabled: !!s.sessionId && !s.recording && !s.busy; onClicked: backend.buildMap() }
                        }
                    }

                    ColumnLayout {
                        visible: app.page === "Work Map"; Layout.fillWidth: true; Layout.fillHeight: true; spacing: 12
                        RowLayout { Layout.fillWidth: true
                            Label { text: s.confirmed ? "✓ Expert-confirmed map" : "Draft · ready for expert review"; color: s.confirmed ? Theme.success : Theme.secondary; Layout.fillWidth: true }
                            Label { text: s.coverage + "% field coverage"; color: Theme.muted; font.pixelSize: 11 }
                        }
                        ListView { Layout.fillWidth: true; Layout.fillHeight: true; spacing: 12; clip: true; model: s.knowledge
                            delegate: Panel { required property var modelData; required property int index; width: ListView.view.width; height: ruleBody.implicitHeight + 36; opacity: modelData.status === "rejected" ? 0.5 : 1
                                ColumnLayout { id: ruleBody; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 18; spacing: 10
                                    RowLayout { Layout.fillWidth: true
                                        Label { text: (index + 1) + ". " + modelData.title; font.pixelSize: 16; font.weight: Font.Medium; color: Theme.text; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                        Label { text: modelData.status.replace("_", " "); font.pixelSize: 10; color: modelData.status === "verified" ? Theme.success : Theme.muted }
                                    }
                                    Label { text: modelData.rule; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.secondary; lineHeight: 1.4 }
                                    Label { text: "Why · " + modelData.reason; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.muted; font.pixelSize: 12 }
                                    Rectangle { Layout.fillWidth: true; implicitHeight: guardText.implicitHeight + 18; radius: 8; color: Theme.subtle
                                        Label { id: guardText; anchors.fill: parent; anchors.margins: 9; text: "Guardrail · " + modelData.guardrail; wrapMode: Text.WordWrap; color: Theme.secondary; font.pixelSize: 12 }
                                    }
                                    RowLayout { Layout.fillWidth: true
                                        AppButton { text: "Edit & inspect checks"; compact: true; enabled: !s.recording; onClicked: app.showRule(modelData) }
                                        AppButton { text: "Evidence"; compact: true; onClicked: { app.page = "Evidence"; } }
                                        Item { Layout.fillWidth: true }
                                        IconButton { iconName: "up"; label: "Move step up"; implicitWidth: 30; implicitHeight: 30; padding: 7; enabled: !s.recording && index > 0; onClicked: backend.moveKnowledge(modelData.id, -1) }
                                        IconButton { iconName: "down"; label: "Move step down"; implicitWidth: 30; implicitHeight: 30; padding: 7; enabled: !s.recording && index < s.knowledge.length - 1; onClicked: backend.moveKnowledge(modelData.id, 1) }
                                        AppButton { text: "Reject"; compact: true; enabled: !s.recording && modelData.status !== "rejected"; onClicked: backend.rejectKnowledge(modelData.id) }
                                    }
                                }
                            }
                            Label { visible: s.knowledge.length === 0; text: "Your map starts with evidence.\nCapture a workflow or load the offline demo,\nthen build a draft for review."; color: Theme.muted; lineHeight: 1.6 }
                        }
                        RowLayout { Layout.fillWidth: true
                            AppButton { text: "Rebuild draft"; enabled: !s.recording && !s.busy && !!s.sessionId; onClicked: rebuildDialog.open() }
                            AppButton { text: "Export"; enabled: s.knowledge.length > 0; onClicked: backend.exportMap() }
                            Item { Layout.fillWidth: true }
                            AppButton { text: s.confirmed ? "Open Teach" : "Confirm understanding"; primary: true; enabled: s.knowledge.length > 0 && !s.recording; onClicked: s.confirmed ? app.page = "Teach" : confirmDialog.open() }
                        }
                    }

                    ScrollView {
                        id: teachScroll; contentWidth: availableWidth
                        visible: app.page === "Teach"; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                        ColumnLayout { width: teachScroll.availableWidth; spacing: 15
                            Panel { Layout.fillWidth: true; implicitHeight: 108
                                ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 7
                                    Label { text: "Practice the reasoning"; font.pixelSize: 20; font.weight: Font.Medium; color: Theme.text }
                                    Label { text: "This controlled case is checked before saving. Other desktop apps receive advisory guidance only."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.muted }
                                }
                            }
                            Panel { Layout.fillWidth: true; implicitHeight: practiceFields.implicitHeight + 40
                                ColumnLayout { id: practiceFields; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 20; spacing: 14
                                    Label { text: "Purchase review · unseen case"; color: Theme.text; font.pixelSize: 16; font.weight: Font.Medium }
                                    GridLayout { columns: 2; columnSpacing: 18; rowSpacing: 10; Layout.fillWidth: true
                                        Label { text: "Amount"; color: Theme.secondary }
                                        AppField { id: amount; objectName: "caseAmount"; text: "7200"; Layout.fillWidth: true; onTextChanged: app.tutorResult = ({verdict:"",explanation:"Case changed. Review again before saving.",knowledge_ids:[]}) }
                                        Label { text: "Currency"; color: Theme.secondary }
                                        AppSelect { id: currency; model: ["EUR", "USD", "GBP"]; Layout.fillWidth: true; onCurrentIndexChanged: app.tutorResult = ({verdict:"",explanation:"Case changed. Review again.",knowledge_ids:[]}) }
                                        Label { text: "Purchase type"; color: Theme.secondary }
                                        AppSelect { id: purchase; model: ["equipment", "service", "other"]; Layout.fillWidth: true; onCurrentIndexChanged: app.tutorResult = ({verdict:"",explanation:"Case changed. Review again.",knowledge_ids:[]}) }
                                        Label { text: "Classification"; color: Theme.secondary }
                                        AppSelect { id: category; objectName: "caseCategory"; model: ["OPEX", "CAPEX"]; Layout.fillWidth: true; onCurrentIndexChanged: app.tutorResult = ({verdict:"",explanation:"Case changed. Review again.",knowledge_ids:[]}) }
                                        Label { text: "Asset number"; color: Theme.secondary }
                                        AppField { id: asset; objectName: "caseAsset"; placeholderText: "Required for CAPEX in the demo"; Layout.fillWidth: true; onTextChanged: app.tutorResult = ({verdict:"",explanation:"Case changed. Review again.",knowledge_ids:[]}) }
                                        Label { text: "Supplier status"; color: Theme.secondary }
                                        AppSelect { id: supplier; model: ["known", "unknown"]; Layout.fillWidth: true; onCurrentIndexChanged: app.tutorResult = ({verdict:"",explanation:"Case changed. Review again.",knowledge_ids:[]}) }
                                    }
                                    AppButton { objectName: "reviewCaseButton"; text: "Review before saving"; primary: true; enabled: s.confirmed; onClicked: app.tutorResult = JSON.parse(backend.checkCase(app.caseData())) }
                                }
                            }
                            Panel { Layout.fillWidth: true; implicitHeight: tutorText.implicitHeight + 70; color: app.tutorResult.verdict === "warn" ? Theme.warningTint : Theme.subtle
                                ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 9
                                    Label { text: app.tutorResult.verdict === "warn" ? "Pause and reconsider" : app.tutorResult.verdict === "ok" ? "Applicable checks passed" : "Tutor guidance"; font.weight: Font.Medium; font.pixelSize: 16; color: Theme.secondary }
                                    Label { id: tutorText; text: app.tutorResult.explanation; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.secondary; lineHeight: 1.4 }
                                }
                            }
                            AppButton { objectName: "savePracticeButton"; text: "Save practice attempt"; enabled: s.confirmed && app.tutorResult.verdict === "ok"; onClicked: {
                                app.tutorResult = JSON.parse(backend.checkCase(app.caseData()));
                                if (app.tutorResult.verdict === "ok" && backend.savePractice(app.caseData())) practiceSaved.open();
                            } }
                            Label { text: "Coverage is limited to the confirmed checks. Unknown cases should be escalated. This form does not submit anything to an external system."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.muted; font.pixelSize: 11 }
                        }
                    }

                    ColumnLayout {
                        visible: app.page === "Evidence"; Layout.fillWidth: true; Layout.fillHeight: true; spacing: 12
                        RowLayout { Layout.fillWidth: true
                            Label { text: s.evidenceCount + " source moments · latest 80 shown"; color: Theme.muted; Layout.fillWidth: true }
                            AppButton { text: "+ Reference"; compact: true; enabled: !!s.sessionId && !s.offRecord; onClicked: referenceDialog.open() }
                        }
                        ListView { Layout.fillWidth: true; Layout.fillHeight: true; model: s.evidence; spacing: 9; clip: true
                            delegate: Panel { required property var modelData; width: ListView.view.width; height: Math.max(125, sourceText.implicitHeight + 80)
                                RowLayout { anchors.fill: parent; anchors.margins: 14; spacing: 14
                                    Image { visible: !!modelData.imageUrl; source: modelData.imageUrl; sourceSize.width: 280; sourceSize.height: 180; Layout.preferredWidth: 140; Layout.preferredHeight: 86; fillMode: Image.PreserveAspectFit }
                                    ColumnLayout { Layout.fillWidth: true; spacing: 7
                                        Label { text: modelData.kind.toUpperCase() + " · " + Number(modelData.timestamp).toFixed(1) + "s · " + modelData.id.slice(0,8); font.pixelSize: 10; color: Theme.muted }
                                        Label { id: sourceText; text: modelData.text; wrapMode: Text.WordWrap; maximumLineCount: 7; elide: Text.ElideRight; color: Theme.text; Layout.fillWidth: true }
                                        RowLayout {
                                            AppButton { text: "View"; compact: true; onClicked: backend.openEvidence(modelData.id) }
                                            AppButton { text: "Forget"; compact: true; enabled: !s.recording; onClicked: { app.deleteTarget = modelData; deleteDialog.open(); } }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                AssistantPanel {
                    id: assistantPanel
                    Layout.preferredWidth: app.width < 1250 ? 288 : 320
                    Layout.fillHeight: true
                    session: app.s
                    tutoring: app.page === "Teach"
                }
            }

            ListView {
                visible: app.page === "Library"; Layout.fillWidth: true; Layout.fillHeight: true; model: s.history; spacing: 12; clip: true
                delegate: Panel { required property var modelData; width: ListView.view.width; height: 90
                    RowLayout { anchors.fill: parent; anchors.margins: 22
                        ColumnLayout { Layout.fillWidth: true; spacing: 8
                            Label { text: modelData.title; font.pixelSize: 18; font.weight: Font.Medium; color: Theme.text }
                            Label { text: "Updated " + modelData.updated.slice(0,19).replace("T", " ") + " UTC"; color: Theme.muted }
                        }
                        AppButton { text: "Open session"; onClicked: backend.openSession(modelData.id) }
                    }
                }
                Label { visible: s.history.length === 0; text: "No saved sessions yet. Start a session or explore the demo."; color: Theme.muted }
            }

            ColumnLayout {
                visible: app.page === "Settings"; Layout.fillWidth: true; Layout.fillHeight: true; spacing: 18
                Panel { Layout.fillWidth: true; Layout.preferredHeight: 220
                    ColumnLayout { anchors.fill: parent; anchors.margins: 24; spacing: 12
                        Label { text: "Connected intelligence"; font.pixelSize: 20; font.weight: Font.Medium; color: Theme.text }
                        Label { text: "OpenAI: " + (s.openaiReady ? "Configured" : "Not configured") + "   ·   Model: " + s.model; color: Theme.muted }
                        Label { text: "ElevenLabs: " + (s.elevenReady ? "Configured" : "Not configured"); color: Theme.muted }
                        Label { text: "Set credentials in the local .env file and restart. Keys never appear in session files or exports."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.muted }
                        AppSwitch { text: "Allow cloud analysis for this session"; checked: s.cloudEnabled; onToggled: checked ? cloudDialog.open() : backend.setCloud(false) }
                    }
                }
                Panel { Layout.fillWidth: true; Layout.preferredHeight: 195
                    ColumnLayout { anchors.fill: parent; anchors.margins: 24; spacing: 12
                        Label { text: "Local data & privacy"; font.pixelSize: 20; font.weight: Font.Medium; color: Theme.text }
                        Label { text: s.dataPath; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true; color: Theme.muted }
                        Label { text: "Cloud analysis sends selected screenshots, notes, and reference excerpts to OpenAI. Voice notes are transcribed by ElevenLabs. Pausing stops new capture and uploads; it cannot recall data already sent."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.muted }
                        AppButton { text: "Open data folder"; compact: true; onClicked: backend.openDataFolder() }
                    }
                }
                Panel { Layout.fillWidth: true; Layout.preferredHeight: 130
                    ColumnLayout { anchors.fill: parent; anchors.margins: 24; spacing: 10
                        Label { text: "Question timing"; font.pixelSize: 20; font.weight: Font.Medium; color: Theme.text }
                        Label { text: "8 seconds input idle · 3 seconds stable screen · 90 seconds between questions · up to 3 questions per 10 minutes. Idle time cannot tell whether you are reading or speaking with the microphone off."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.muted }
                    }
                }
                Item { Layout.fillHeight: true }
            }

            Rectangle { Layout.fillWidth: true; implicitHeight: 30; radius: 10; color: "transparent"
                RowLayout { anchors.fill: parent; anchors.margins: 12; spacing: 10
                    BusyIndicator { running: s.busy; visible: s.busy; implicitWidth: 22; implicitHeight: 22 }
                    Label { text: s.notice; Layout.fillWidth: true; elide: Text.ElideRight; color: Theme.secondary; font.pixelSize: 11; ToolTip.visible: statusHover.hovered; ToolTip.text: s.notice; HoverHandler { id: statusHover } }
                }
            }
        }
    }

    AppDialog {
        id: newDialog; objectName: "newSessionDialog"; title: "Start a learning session"; modal: true; anchors.centerIn: parent; width: 560
        standardButtons: Dialog.Cancel
        ColumnLayout { width: parent.width; spacing: 14
            Label { text: "What should your apprentice learn?"; color: Theme.secondary }
            AppField { id: sessionTitle; Layout.fillWidth: true; placeholderText: "e.g. Review an equipment purchase" }
            AppTextArea { id: sessionContext; Layout.fillWidth: true; Layout.preferredHeight: 95; placeholderText: "Goal, audience, and useful context…"; wrapMode: TextEdit.Wrap; selectByMouse: true }
            AppSelect { id: monitorChoice; Layout.fillWidth: true; model: s.monitors }
            CheckBox { id: allowCloud; text: "Enable AI analysis (sends screenshots and context to OpenAI)"; enabled: s.openaiReady; checked: false; font.pixelSize: 11 }
            Label { text: "Recording starts only when you press Record. Choose an appropriate screen. The current version captures the entire selected monitor without automatic redaction."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.muted; font.pixelSize: 11 }
            AppButton { text: "Create session"; primary: true; onClicked: { backend.newSession(sessionTitle.text, sessionContext.text, monitorChoice.currentIndex, allowCloud.checked); newDialog.close(); } }
        }
    }
    AppDialog { id: confirmDialog; title: "Confirm this Work Map"; modal: true; anchors.centerIn: parent; width: 510; standardButtons: Dialog.Ok | Dialog.Cancel
        Label { width: parent.width; wrapMode: Text.WordWrap; text: "I have reviewed the retained rules, their source evidence, and their exact structured checks. They accurately represent my explanation within the stated scope.\n\nItems needing clarification must be corrected or rejected first." }
        onAccepted: backend.confirmMap()
    }
    AppDialog { id: rebuildDialog; title: "Rebuild the draft?"; modal: true; anchors.centerIn: parent; width: 470; standardButtons: Dialog.Ok | Dialog.Cancel
        Label { width: parent.width; wrapMode: Text.WordWrap; text: "A successful generation replaces the current draft, including manual edits, and requires confirmation again. Evidence is retained." }
        onAccepted: backend.buildMap()
    }
    AppDialog { id: deleteDialog; title: "Forget this evidence?"; modal: true; anchors.centerIn: parent; width: 520; standardButtons: Dialog.Ok | Dialog.Cancel
        Label { width: parent.width; wrapMode: Text.WordWrap; text: "This deletes the source screenshot, dependent answers, the derived Work Map, and ALL video segments for this session so the moment is not retained in raw footage. Retained evidence can be used to rebuild the map.\n\nPreviously exported or uploaded copies cannot be recalled." }
        onAccepted: backend.forgetEvidence(app.deleteTarget.id)
    }
    AppDialog { id: cloudDialog; title: "Enable cloud analysis?"; modal: true; anchors.centerIn: parent; width: 460; standardButtons: Dialog.Ok | Dialog.Cancel
        Label { width: parent.width; wrapMode: Text.WordWrap; text: "Selected screenshots, notes, answers, and reference excerpts from this session may be sent to OpenAI. Continue only with content you intend to share with the provider." }
        onAccepted: backend.setCloud(true)
        onRejected: backend.setCloud(false)
    }
    AppDialog { id: quitDialog; title: "Quit AI Apprentice?"; modal: true; anchors.centerIn: parent; standardButtons: Dialog.Ok | Dialog.Cancel
        Label { text: "Any active recording will be stopped and saved." }
        onAccepted: backend.quit()
    }
    AppDialog { id: practiceSaved; title: "Practice attempt reviewed"; modal: true; anchors.centerIn: parent; standardButtons: Dialog.Ok
        Label { text: "The checked attempt is saved in the session evidence.\nNothing was sent to an external application." }
    }
    AppDialog { id: referenceDialog; title: "Add a reference excerpt"; modal: true; anchors.centerIn: parent; width: 570; standardButtons: Dialog.Cancel
        ColumnLayout { width: parent.width; spacing: 12
            AppField { id: referenceName; placeholderText: "Source name and version"; Layout.fillWidth: true }
            AppTextArea { id: referenceText; placeholderText: "Paste the relevant policy or process excerpt…"; Layout.fillWidth: true; Layout.preferredHeight: 240; wrapMode: TextEdit.Wrap; selectByMouse: true }
            AppButton { text: "Save reference"; primary: true; enabled: referenceText.text.trim().length > 0; onClicked: { backend.addReference(referenceName.text, referenceText.text); referenceDialog.close(); referenceText.clear(); } }
        }
    }
    AppDialog { id: editDialog; title: "Review the rule and its exact check"; modal: true; anchors.centerIn: parent; width: 660; height: Math.min(app.height - 70, 820); standardButtons: Dialog.Cancel
        ColumnLayout { anchors.fill: parent; spacing: 12
            ScrollView { Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                ColumnLayout { width: parent.width - 15; spacing: 10
                    Label { text: "Title" } AppField { id: ruleTitle; Layout.fillWidth: true }
                    Label { text: "Action" } AppTextArea { id: actionEdit; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; selectByMouse: true }
                    Label { text: "Decision" } AppTextArea { id: decisionEdit; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; selectByMouse: true }
                    Label { text: "Reason" } AppTextArea { id: reasonEdit; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; selectByMouse: true }
                    Label { text: "Rule" } AppTextArea { id: ruleEdit; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; selectByMouse: true }
                    Label { text: "Exception" } AppTextArea { id: exceptionEdit; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; selectByMouse: true }
                    Label { text: "Guardrail" } AppTextArea { id: guardrailEdit; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; selectByMouse: true }
                    Label { text: "Escalation" } AppTextArea { id: escalationEdit; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; selectByMouse: true }
                    Label { text: "Structured check (JSON, or null for guidance-only rules)"; font.pixelSize: 11 }
                    AppTextArea { id: checkEdit; Layout.fillWidth: true; font.family: "Consolas"; font.pixelSize: 11; wrapMode: TextEdit.Wrap; selectByMouse: true }
                    Label { text: "A rule’s wording and check must agree. Saving clears confirmation. Reference IDs stay attached to the original evidence."; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.muted; font.pixelSize: 11 }
                }
            }
            AppButton { text: "Save draft changes"; primary: true; onClicked: {
                try {
                    backend.editKnowledge(app.selectedRule.id, JSON.stringify({title:ruleTitle.text,action:actionEdit.text,decision:decisionEdit.text,reason:reasonEdit.text,rule:ruleEdit.text,exception:exceptionEdit.text,guardrail:guardrailEdit.text,escalation:escalationEdit.text,check:JSON.parse(checkEdit.text)}));
                    editDialog.close();
                } catch (e) { checkEdit.text = "Invalid JSON. Use null to remove the structured check."; }
            } }
        }
    }

    Companion {
        id: bubble
        session: app.s
        onContextRequested: {
            backend.reveal();
            if (["Capture", "Work Map", "Teach", "Evidence"].indexOf(app.page) < 0) app.page = "Capture";
            assistantPanel.focusComposer();
        }
    }
}
