import QtQuick
import Quickshell.Io

Column {
    id: arenaRoot
    property var theme
    property var arenaData: null

    spacing: 8

    Component.onCompleted: refreshArena()

    Process {
        id: arenaProc
        property string buf: ""
        stdout: SplitParser { splitMarker: ""; onRead: function(c) { arenaProc.buf += c } }
        onExited: function(code) {
            if (code === 0 && arenaProc.buf.trim() !== "") {
                try { arenaRoot.arenaData = JSON.parse(arenaProc.buf) } catch (e) {}
            }
            arenaProc.buf = ""
        }
    }

    function refreshArena() {
        if (arenaProc.running) return
        arenaProc.buf = ""
        var script = Qt.resolvedUrl("../paper_arena.py").toString().replace("file://", "")
        arenaProc.command = ["python3", script]
        arenaProc.running = true
    }

    // 1. Multi-Provider BYOK AI Manager Strip
    Rectangle {
        width: parent.width; height: 82; radius: theme.rSharp
        color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
        property var ai: (arenaRoot.arenaData && arenaRoot.arenaData.ai_providers) ? arenaRoot.arenaData.ai_providers : ({})
        Column {
            anchors.fill: parent; anchors.margins: 10; spacing: 6
            Row {
                width: parent.width; spacing: 10
                Text { text: "BYOK AI PROVIDERS (KEYS ISOLATED IN SECRET STORE)"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                Text {
                    text: parent.parent.parent.ai.usage ? ("BUDGET $" + Number(parent.parent.parent.ai.usage.estimated_cost_usd || 0).toFixed(4) + " / $" + Number(parent.parent.parent.ai.monthly_budget_usd || 10).toFixed(2)) : ""
                    color: theme.gain; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true
                }
            }
            Row {
                spacing: 6
                Repeater {
                    model: parent.parent.parent.ai.providers || []
                    delegate: Rectangle {
                        width: 112; height: 36; radius: theme.rSharp
                        color: theme.bgBlack; border.color: modelData.enabled ? theme.gain : theme.borderSubtle; border.width: 1
                        Column {
                            anchors.fill: parent; anchors.margins: 5; spacing: 1
                            Text { text: String(modelData.name || "").toUpperCase(); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 8; font.bold: true; elide: Text.ElideRight; width: parent.width }
                            Text { text: modelData.key_configured ? String(modelData.model || "") : "NO KEY"; color: modelData.key_configured ? theme.textSecondary : theme.textDim; font.family: theme.fontMono; font.pixelSize: 8; elide: Text.ElideRight; width: parent.width }
                        }
                    }
                }
            }
        }
    }

    // 2. 5-Strategy Paper Trading Arena Rankings & Performance Analytics (Logically Isolated)
    Rectangle {
        width: parent.width; height: Math.max(160, rkCol.implicitHeight + 20); radius: theme.rSharp
        color: theme.bgPanel; border.color: theme.warn; border.width: 1
        Column {
            id: rkCol
            anchors.fill: parent; anchors.margins: 10; spacing: 5
            Row {
                width: parent.width; spacing: 8
                Rectangle {
                    width: 118; height: 16; radius: theme.rSharp; color: theme.warnBg; border.color: theme.warn; border.width: 1
                    Text { anchors.centerIn: parent; text: "◆ PAPER PORTFOLIO"; color: theme.warn; font.family: theme.fontMono; font.pixelSize: 8; font.bold: true }
                }
                Text { text: "STRATEGY ARENA, PERFORMANCE ANALYTICS & DECISION JOURNAL (ISOLATED)"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                Item { width: Math.max(4, parent.width - 590); height: 1 }
                Text {
                    text: "REFRESH"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: arenaRoot.refreshArena() }
                }
            }
            Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }
            Repeater {
                model: (arenaRoot.arenaData && arenaRoot.arenaData.arena_rankings) ? arenaRoot.arenaData.arena_rankings : []
                delegate: Row {
                    width: parent.width; spacing: 10
                    Text { width: 150; text: String(modelData.name || "") + " v" + modelData.version; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                    Text { width: 84; horizontalAlignment: Text.AlignRight; text: theme.fmtMoney(modelData.equity_usd, "USD", 2); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10 }
                    Text { width: 70; horizontalAlignment: Text.AlignRight; text: theme.fmtPct(modelData.return_pct, 2); color: theme.toneColor(modelData.return_pct); font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                    Text { width: 70; horizontalAlignment: Text.AlignRight; text: "DD " + Number(modelData.max_drawdown_pct || 0).toFixed(1) + "%"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                    Text { width: 80; horizontalAlignment: Text.AlignRight; text: modelData.trades_count + " trd / " + modelData.journal_count + " jrn"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 9 }
                }
            }
        }
    }
}
