import QtQuick
import Quickshell.Io

Flickable {
    id: aiRoot
    property var theme
    property var summaryData: ({})
    property string deskQuery: "Full desk analysis"
    property var lastReport: null
    property string deskErr: ""
    signal openStock(string symbol)
    signal runCli(var args, string label)

    contentWidth: width
    contentHeight: aiCol.implicitHeight + 20
    clip: true

    property var ag: summaryData.paper_agent || ({})
    property var gk: (ag && ag.grok) ? ag.grok : ({})
    property var gm: (gk && gk.metrics) ? gk.metrics : ({})

    Process {
        id: deskProc
        property string buf: ""
        stdout: SplitParser {
            splitMarker: ""
            onRead: function(chunk) { deskProc.buf += chunk }
        }
        stderr: SplitParser {
            onRead: function(line) { var t = line.trim(); if (t) aiRoot.deskErr = t }
        }
        onExited: function(exitCode) {
            if (exitCode === 0 && deskProc.buf.trim() !== "") {
                try {
                    aiRoot.lastReport = JSON.parse(deskProc.buf)
                    aiRoot.deskErr = ""
                } catch (e) {
                    aiRoot.deskErr = "Could not parse intelligence report JSON"
                }
            } else if (exitCode !== 0 && !aiRoot.deskErr) {
                aiRoot.deskErr = "Intelligence desk exited with code " + exitCode
            }
            deskProc.buf = ""
        }
    }

    function runDesk(q) {
        if (deskProc.running) return
        aiRoot.deskErr = ""
        deskProc.buf = ""
        var script = Qt.resolvedUrl("../intelligence.py").toString().replace("file://", "")
        deskProc.command = ["python3", script, q || aiRoot.deskQuery || "Full desk analysis"]
        deskProc.running = true
    }

    Column {
        id: aiCol
        width: parent.width
        spacing: 10

        // 1. Live 8-Agent Investment Intelligence Desk Query Bar
        Rectangle {
            width: parent.width; height: 78; radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderDefault; border.width: 1
            Column {
                anchors.fill: parent; anchors.margins: 10; spacing: 6
                Row {
                    width: parent.width; spacing: 8
                    Text { text: "8-AGENT INVESTMENT INTELLIGENCE DESK"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                    Text { visible: deskProc.running; text: "● COLLECTING DATA & RUNNING AGENTS..."; color: theme.warn; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    Text { visible: aiRoot.deskErr !== ""; text: aiRoot.deskErr; color: theme.loss; font.family: theme.fontMono; font.pixelSize: 9 }
                }
                Row {
                    width: parent.width; spacing: 6
                    Rectangle {
                        width: parent.width - 280; height: 28; radius: theme.rSharp
                        color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
                        TextInput {
                            anchors.fill: parent; anchors.margins: 6
                            text: aiRoot.deskQuery
                            color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11
                            onTextChanged: aiRoot.deskQuery = text
                            Keys.onReturnPressed: aiRoot.runDesk(aiRoot.deskQuery)
                        }
                    }
                    Rectangle {
                        width: 100; height: 28; radius: theme.rSharp; color: theme.accent
                        Text { anchors.centerIn: parent; text: deskProc.running ? "RUNNING..." : "RUN DESK"; color: "#FFFFFF"; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: aiRoot.runDesk(aiRoot.deskQuery) }
                    }
                    Rectangle {
                        width: 82; height: 28; radius: theme.rSharp; color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                        Text { anchors.centerIn: parent; text: "SCAN OPP"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { aiRoot.deskQuery = "Scan VFEX and ZSE opportunities"; aiRoot.runDesk(aiRoot.deskQuery) } }
                    }
                    Rectangle {
                        width: 82; height: 28; radius: theme.rSharp; color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                        Text { anchors.centerIn: parent; text: "RISK AUDIT"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { aiRoot.deskQuery = "Audit portfolio risk and concentration"; aiRoot.runDesk(aiRoot.deskQuery) } }
                    }
                }
            }
        }

        // 2. Agent Disagreements Banner (if any)
        Rectangle {
            visible: aiRoot.lastReport && (aiRoot.lastReport.disagreements || []).length > 0
            width: parent.width; height: 52; radius: theme.rSharp
            color: theme.warnBg; border.color: theme.warn; border.width: 1
            Column {
                anchors.fill: parent; anchors.margins: 8; spacing: 2
                Text { text: "AGENT DISAGREEMENT DETECTED — REVIEW BOTH SIDES"; color: theme.warn; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                Text {
                    width: parent.width; elide: Text.ElideRight
                    text: (aiRoot.lastReport && aiRoot.lastReport.disagreements && aiRoot.lastReport.disagreements.length > 0) ? String(aiRoot.lastReport.disagreements[0].topic || "") : ""
                    color: theme.textPrimary; font.family: theme.fontSans; font.pixelSize: 10
                }
            }
        }

        // 3. Active / Completed Agent Findings
        Rectangle {
            visible: aiRoot.lastReport !== null
            width: parent.width; height: Math.max(80, agCol.implicitHeight + 20); radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            Column {
                id: agCol
                anchors.fill: parent; anchors.margins: 10; spacing: 6
                Text { text: "SPECIALISED AGENT FINDINGS (" + (aiRoot.lastReport ? (aiRoot.lastReport.findings || []).length : 0) + " AGENTS)"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }
                Repeater {
                    model: aiRoot.lastReport ? (aiRoot.lastReport.findings || []) : []
                    delegate: Column {
                        width: parent.width; spacing: 2
                        Row {
                            width: parent.width; spacing: 8
                            Text { width: 150; text: String(modelData.agent_name || "").toUpperCase(); color: theme.info; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            Text {
                                width: 62
                                text: String(modelData.stance || "NEUTRAL")
                                color: modelData.stance === "BUY" ? theme.gain : ((modelData.stance === "CAUTION" || modelData.stance === "SELL") ? theme.loss : theme.textSecondary)
                                font.family: theme.fontMono; font.pixelSize: 9; font.bold: true
                            }
                            Text { width: 54; text: String(modelData.confidence || "LOW"); color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                            Text { width: parent.width - 290; elide: Text.ElideRight; text: String(modelData.summary || ""); color: theme.textPrimary; font.family: theme.fontSans; font.pixelSize: 10 }
                        }
                    }
                }
            }
        }

        // 4. Structured Recommendations Awaiting Review
        Rectangle {
            visible: aiRoot.lastReport && (aiRoot.lastReport.recommendations || []).length > 0
            width: parent.width; height: Math.max(90, recCol.implicitHeight + 20); radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderDefault; border.width: 1
            Column {
                id: recCol
                anchors.fill: parent; anchors.margins: 10; spacing: 5
                Text { text: "RECOMMENDATIONS AWAITING HUMAN REVIEW (ANALYTICAL OPINIONS ONLY)"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }
                Repeater {
                    model: aiRoot.lastReport ? (aiRoot.lastReport.recommendations || []) : []
                    delegate: Column {
                        width: parent.width; spacing: 3
                        Row {
                            spacing: 10
                            Text { text: String(modelData.recommendation_type || "WATCH") + " " + String(modelData.security || "") + " (" + String(modelData.exchange || "") + ")"; color: modelData.recommendation_type === "BUY" ? theme.gain : theme.warn; font.family: theme.fontMono; font.pixelSize: 11; font.bold: true }
                            Text { text: "PRICE: " + String(modelData.verified_price || "--") + "  |  CONFIDENCE: " + String(modelData.confidence_level || "LOW") + "  |  HORIZON: " + String(modelData.expected_horizon || ""); color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                        }
                        Text { width: parent.width; wrapMode: Text.WordWrap; text: "THESIS: " + String(modelData.investment_thesis || ""); color: theme.textPrimary; font.family: theme.fontSans; font.pixelSize: 10 }
                        Text { width: parent.width; wrapMode: Text.WordWrap; text: "LIMITATIONS: " + ((modelData.data_limitations || []).join(" · ")); color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                    }
                }
            }
        }

        // 5. Mahoraga Foundation Brain Controls (Preserved)
        Rectangle {
            width: parent.width; height: 68; radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            Row {
                anchors.fill: parent; anchors.margins: 10; spacing: 12
                Column {
                    width: parent.width - 250; spacing: 3
                    Text { text: "MAHORAGA FOUNDATION BRAIN  //  " + String(aiRoot.gk.status || "READY").toUpperCase(); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                    Text {
                        text: "PAPER EQUITY " + theme.fmtMoney(aiRoot.ag.equity_usd, "USD", 2) + " (" + theme.fmtPct(aiRoot.ag.net_pnl_pct, 2) + ")  |  OOS VAL " + Number(aiRoot.gm.val_acc_pct || 0).toFixed(1) + "%  |  GAP " + Number(aiRoot.gm.generalization_gap_pct || 0).toFixed(2) + "%"
                        color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10
                    }
                }
                Row {
                    anchors.verticalCenter: parent.verticalCenter; spacing: 6
                    Repeater {
                        model: [
                            { t: "STEP", cmd: ["agent", "step"], lbl: "Ran Mahoraga step" },
                            { t: "TRAIN", cmd: ["agent", "train", "--days", "365"], lbl: "Trained Mahoraga brain" },
                            { t: aiRoot.ag.enabled ? "PAUSE" : "RESUME", cmd: ["agent", aiRoot.ag.enabled ? "pause" : "resume"], lbl: "Toggled Mahoraga agent" }
                        ]
                        delegate: Rectangle {
                            width: 68; height: 26; radius: theme.rSharp
                            color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                            Text { anchors.centerIn: parent; text: modelData.t; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: aiRoot.runCli(modelData.cmd, modelData.lbl) }
                        }
                    }
                }
            }
        }
    }
}
