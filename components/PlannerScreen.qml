import QtQuick
import Quickshell.Io

Flickable {
    id: plRoot
    property var theme
    property var summaryData: ({})
    property var plannerData: null
    property real monthlyContrib: 50
    property int horizonYears: 5
    property string targetSym: "INFR"
    property string targetPct: "25"
    signal runCli(var args, string label)

    contentWidth: width
    contentHeight: plCol.implicitHeight + 20
    clip: true

    Component.onCompleted: loadPlanner()

    Process {
        id: plProc
        property string buf: ""
        stdout: SplitParser { splitMarker: ""; onRead: function(c) { plProc.buf += c } }
        onExited: function(code) {
            if (code === 0 && plProc.buf.trim() !== "") {
                try { plRoot.plannerData = JSON.parse(plProc.buf) } catch (e) {}
            }
            plProc.buf = ""
        }
    }

    function loadPlanner() {
        if (plProc.running) return
        plProc.buf = ""
        var script = Qt.resolvedUrl("../planner.py").toString().replace("file://", "")
        plProc.command = ["python3", script]
        plProc.running = true
    }

    function projVal(cagrPct) {
        var pv = Number(summaryData.total_value || 0) + Number(summaryData.wallet_cash_usd || 0)
        var r = (cagrPct / 100.0) / 12.0
        var n = plRoot.horizonYears * 12
        var pmt = plRoot.monthlyContrib * (1.0 - 0.0104)
        return pv * Math.pow(1 + r, n) + (r > 0 ? pmt * ((Math.pow(1 + r, n) - 1) / r) : pmt * n)
    }

    Column {
        id: plCol
        width: parent.width
        spacing: 10

        // 1. Contribution Planner Presets ($5 / $10 / $25 / $50 / $100) + Bull/Base/Bear Scenarios
        Rectangle {
            width: parent.width; height: 158; radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderDefault; border.width: 1
            Column {
                anchors.fill: parent; anchors.margins: 10; spacing: 8
                Row {
                    width: parent.width; spacing: 8
                    Text { text: "CONTRIBUTION PLANNER & HYPOTHETICAL SCENARIOS (NOT GUARANTEED)"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                }
                Row {
                    spacing: 6
                    Text { text: "MONTHLY:"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                    Repeater {
                        model: [5, 10, 25, 50, 100]
                        delegate: Rectangle {
                            width: 48; height: 24; radius: theme.rSharp
                            color: plRoot.monthlyContrib === modelData ? theme.bgActive : theme.bgBlack
                            border.color: plRoot.monthlyContrib === modelData ? theme.accent : theme.borderDefault; border.width: 1
                            Text { anchors.centerIn: parent; text: "$" + modelData; color: plRoot.monthlyContrib === modelData ? theme.textPrimary : theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: plRoot.monthlyContrib = modelData }
                        }
                    }
                    Text { text: "  YEARS:"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                    Repeater {
                        model: [1, 3, 5, 10]
                        delegate: Rectangle {
                            width: 36; height: 24; radius: theme.rSharp
                            color: plRoot.horizonYears === modelData ? theme.bgActive : theme.bgBlack
                            border.color: plRoot.horizonYears === modelData ? theme.info : theme.borderDefault; border.width: 1
                            Text { anchors.centerIn: parent; text: modelData + "Y"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9 }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: plRoot.horizonYears = modelData }
                        }
                    }
                }
                // Bull / Base / Bear Cards
                Row {
                    width: parent.width; spacing: 8
                    Repeater {
                        model: [
                            { t: "BEAR CASE (2% CAGR)", r: 2, c: theme.loss },
                            { t: "BASE CASE (10% CAGR)", r: 10, c: theme.textPrimary },
                            { t: "BULL CASE (18% CAGR)", r: 18, c: theme.gain }
                        ]
                        delegate: Rectangle {
                            width: (parent.width - 16) / 3; height: 66; radius: theme.rSharp
                            color: theme.bgBlack; border.color: theme.borderSubtle; border.width: 1
                            Column {
                                anchors.centerIn: parent; spacing: 3
                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.t; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: theme.fmtMoney(plRoot.projVal(modelData.r), "USD", 0); color: modelData.c; font.family: theme.fontMono; font.pixelSize: 16; font.bold: true }
                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "HYPOTHETICAL · NET OF 1.04% FEE"; color: theme.textDim; font.family: theme.fontMono; font.pixelSize: 8 }
                            }
                        }
                    }
                }
            }
        }

        // 2. Non-Destructive What-If Simulator + Goal Selector
        Row {
            width: parent.width; spacing: 8
            Rectangle {
                width: (parent.width - 8) / 2; height: 112; radius: theme.rSharp
                color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                property var wf: (plRoot.plannerData && plRoot.plannerData.what_if_examples) ? plRoot.plannerData.what_if_examples : ({})
                Column {
                    anchors.fill: parent; anchors.margins: 10; spacing: 5
                    Text { text: "WHAT-IF PORTFOLIO SIMULATOR (READ-ONLY)"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    Text { text: "• Invest +$20: " + (parent.parent.wf.invest_20 ? theme.fmtMoney(parent.parent.wf.invest_20.after_total_usd, "USD", 2) : "--"); color: theme.gain; font.family: theme.fontMono; font.pixelSize: 10 }
                    Text { text: "• Market -10% Shock: " + (parent.parent.wf.market_drop_10pct ? theme.fmtMoney(parent.parent.wf.market_drop_10pct.after_total_usd, "USD", 2) : "--"); color: theme.loss; font.family: theme.fontMono; font.pixelSize: 10 }
                    Text { text: "• Market +20% Rally: " + (parent.parent.wf.market_rise_20pct ? theme.fmtMoney(parent.parent.wf.market_rise_20pct.after_total_usd, "USD", 2) : "--"); color: theme.gain; font.family: theme.fontMono; font.pixelSize: 10 }
                }
            }
            Rectangle {
                width: (parent.width - 8) / 2; height: 112; radius: theme.rSharp
                color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                Column {
                    anchors.fill: parent; anchors.margins: 10; spacing: 6
                    Text { text: "TARGET ALLOCATION & REBALANCING"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    Row {
                        spacing: 6
                        Rectangle { width: 72; height: 26; radius: theme.rSharp; color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1; TextInput { anchors.fill: parent; anchors.margins: 5; text: plRoot.targetSym; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; onTextChanged: plRoot.targetSym = text.toUpperCase() } }
                        Rectangle { width: 52; height: 26; radius: theme.rSharp; color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1; TextInput { anchors.fill: parent; anchors.margins: 5; text: plRoot.targetPct; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; onTextChanged: plRoot.targetPct = text } }
                        Rectangle {
                            width: 96; height: 26; radius: theme.rSharp; color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                            Text { anchors.centerIn: parent; text: "SET TARGET %"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { plRoot.runCli(["target", "set", plRoot.targetSym, plRoot.targetPct], "Set target " + plRoot.targetSym); plRoot.loadPlanner() } }
                        }
                    }
                    Row {
                        spacing: 6
                        Repeater {
                            model: ["hybrid", "long", "short"]
                            delegate: Rectangle {
                                width: 74; height: 24; radius: theme.rSharp
                                color: String(summaryData.trading_goal || "hybrid") === modelData ? theme.bgActive : theme.bgBlack
                                border.color: String(summaryData.trading_goal || "hybrid") === modelData ? theme.accent : theme.borderSubtle; border.width: 1
                                Text { anchors.centerIn: parent; text: modelData.toUpperCase(); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9 }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: plRoot.runCli(["goal", modelData], "Set goal " + modelData) }
                            }
                        }
                    }
                }
            }
        }

        // 3. Investment Calendar
        Rectangle {
            width: parent.width; height: Math.max(90, calCol.implicitHeight + 20); radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            Column {
                id: calCol
                anchors.fill: parent; anchors.margins: 10; spacing: 5
                Text { text: "INVESTMENT CALENDAR (CONTRIBUTIONS, REVIEWS, DIVIDENDS & FILINGS)"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }
                Repeater {
                    model: (plRoot.plannerData && plRoot.plannerData.calendar) ? plRoot.plannerData.calendar.slice(0, 6) : []
                    delegate: Row {
                        width: parent.width; spacing: 10
                        Text { width: 82; text: String(modelData.date || ""); color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10 }
                        Text { width: 96; text: String(modelData.type || ""); color: theme.info; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                        Text { width: parent.width - 200; elide: Text.ElideRight; text: String(modelData.title || ""); color: theme.textPrimary; font.family: theme.fontSans; font.pixelSize: 10 }
                    }
                }
            }
        }
    }
}
