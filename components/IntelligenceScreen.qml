import QtQuick

Flickable {
    id: aiRoot
    property var theme
    property var summaryData: ({})
    signal openStock(string symbol)
    signal runCli(var args, string label)

    contentWidth: width
    contentHeight: aiCol.implicitHeight + 20
    clip: true

    property var ag: summaryData.paper_agent || ({})
    property var gk: (ag && ag.grok) ? ag.grok : ({})
    property var gm: (gk && gk.metrics) ? gk.metrics : ({})

    Column {
        id: aiCol
        width: parent.width
        spacing: 10

        // Top Bar: Running Agent Status & Controls
        Rectangle {
            width: parent.width; height: 74; radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderDefault; border.width: 1
            Row {
                anchors.fill: parent; anchors.margins: 10; spacing: 12
                Column {
                    width: parent.width - 310; spacing: 3
                    Row {
                        spacing: 6
                        Rectangle { width: 7; height: 7; radius: 3.5; anchors.verticalCenter: parent.verticalCenter; color: aiRoot.ag.enabled ? theme.gain : theme.textMuted }
                        Text { text: "MAHORAGA FOUNDATION BRAIN  //  " + String(aiRoot.gk.status || "READY").toUpperCase(); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; font.bold: true }
                    }
                    Text {
                        text: "PAPER EQUITY " + theme.fmtMoney(aiRoot.ag.equity_usd, "USD", 2) + " (" + theme.fmtPct(aiRoot.ag.net_pnl_pct, 2) + ")  |  WIN RATE " + Number(aiRoot.ag.win_rate_pct || 0).toFixed(1) + "%  |  EPISODES " + Number(aiRoot.gm.episodes_total || 0)
                        color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10
                    }
                    Text {
                        text: "OOS VAL " + Number(aiRoot.gm.val_acc_pct || 0).toFixed(1) + "%  |  GEN GAP " + Number(aiRoot.gm.generalization_gap_pct || 0).toFixed(2) + "%  |  CONFIDENCE: " + (aiRoot.gk.enabled ? "HIGH (GROKKED)" : "CALIBRATING")
                        color: aiRoot.gk.enabled ? theme.gain : theme.warn; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true
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
                            width: 68; height: 28; radius: theme.rSharp
                            color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                            Text { anchors.centerIn: parent; text: modelData.t; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: aiRoot.runCli(modelData.cmd, modelData.lbl) }
                        }
                    }
                }
            }
        }

        // Opportunity Alerts & Recommendations (from Quant Signals)
        Rectangle {
            width: parent.width; height: Math.max(90, sigCol.implicitHeight + 20); radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            Column {
                id: sigCol
                anchors.fill: parent; anchors.margins: 10; spacing: 6
                Text { text: "OPPORTUNITY ALERTS & QUANT RECOMMENDATIONS"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }
                Repeater {
                    model: (summaryData.signals || []).concat(summaryData.market_top_signals || []).slice(0, 6)
                    delegate: Rectangle {
                        width: parent.width; height: 34; radius: theme.rSharp; color: sigMa.containsMouse ? theme.bgHover : "transparent"
                        Row {
                            anchors.fill: parent; anchors.leftMargin: 6; anchors.rightMargin: 6; spacing: 8
                            Text { width: 46; text: String(modelData.action || modelData.signal_action || "WATCH"); color: (modelData.action === "BUY" || modelData.signal_action === "BUY") ? theme.gain : theme.loss; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                            Text { width: 62; text: String(modelData.symbol || ""); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                            Text { width: 64; text: "SCORE " + Number(modelData.score || modelData.signal_score || 0); color: theme.warn; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                            Text { width: parent.width - 200; elide: Text.ElideRight; text: (modelData.reasons && modelData.reasons.length > 0) ? modelData.reasons.join(" · ") : "Quant technical & flow alignment"; color: theme.textSecondary; font.family: theme.fontSans; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                        }
                        MouseArea { id: sigMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: aiRoot.openStock(modelData.symbol) }
                    }
                }
            }
        }

        // Agent Reasoning Summaries & Lessons (with Playbook Citations)
        Rectangle {
            width: parent.width; height: Math.max(90, lesCol.implicitHeight + 20); radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            Column {
                id: lesCol
                anchors.fill: parent; anchors.margins: 10; spacing: 6
                Text { text: "AGENT REASONING LOG, ADAPTATIONS & RISK SHIELDS"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }
                Repeater {
                    model: (aiRoot.ag.lessons || []).slice(-8).reverse()
                    delegate: Column {
                        width: parent.width; spacing: 2
                        Row {
                            width: parent.width; spacing: 8
                            Text { text: String(modelData.date || ""); color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                            Text { text: "[" + String(modelData.playbook || modelData.type || "AI") + "]"; color: theme.info; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            Text { width: parent.width - 180; elide: Text.ElideRight; text: String(modelData.summary || ""); color: theme.textPrimary; font.family: theme.fontSans; font.pixelSize: 10 }
                        }
                        Text { visible: String(modelData.adjustment || "") !== ""; text: "  ↳ " + String(modelData.adjustment || ""); color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 9 }
                    }
                }
            }
        }
    }
}
