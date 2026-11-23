import QtQuick

Flickable {
    id: plRoot
    property var theme
    property var summaryData: ({})
    property string dcaBudget: "100"
    property real monthlyContrib: 50
    property real annualCagrPct: 12
    property string targetSym: "INFR"
    property string targetPct: "25"
    signal runCli(var args, string label)

    contentWidth: width
    contentHeight: plCol.implicitHeight + 20
    clip: true

    function projectYears(yrs) {
        var pv = Number(summaryData.total_value || 0)
        var r = annualCagrPct / 100.0 / 12.0
        var n = yrs * 12
        var fv = pv * Math.pow(1 + r, n) + (r > 0 ? monthlyContrib * ((Math.pow(1 + r, n) - 1) / r) : monthlyContrib * n)
        return fv
    }

    Column {
        id: plCol
        width: parent.width
        spacing: 10

        // 1. Investment Goal Selector
        Rectangle {
            width: parent.width; height: 64; radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            Column {
                anchors.fill: parent; anchors.margins: 10; spacing: 6
                Text { text: "INVESTMENT GOAL & STRATEGY HORIZON"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                Row {
                    spacing: 8
                    Repeater {
                        model: [
                            { k: "hybrid", t: "HYBRID (CORE + SWING)" },
                            { k: "long", t: "LONG-TERM COMPOUNDER" },
                            { k: "short", t: "SHORT-TERM SWING" }
                        ]
                        delegate: Rectangle {
                            width: 165; height: 26; radius: theme.rSharp
                            property bool active: String(summaryData.trading_goal || "hybrid") === modelData.k
                            color: active ? theme.bgActive : theme.bgBlack
                            border.color: active ? theme.accent : theme.borderDefault; border.width: 1
                            Text { anchors.centerIn: parent; text: modelData.t; color: active ? theme.textPrimary : theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: active }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: plRoot.runCli(["goal", modelData.k], "Set trading goal to " + modelData.k) }
                        }
                    }
                }
            }
        }

        // 2. Asset Allocation Targets & Rebalancing
        Rectangle {
            width: parent.width; height: Math.max(100, tgtCol.implicitHeight + 20); radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            Column {
                id: tgtCol
                anchors.fill: parent; anchors.margins: 10; spacing: 8
                Text { text: "TARGET ASSET ALLOCATION & REBALANCING"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                Row {
                    spacing: 6
                    Rectangle {
                        width: 80; height: 26; radius: theme.rSharp; color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
                        TextInput { anchors.fill: parent; anchors.margins: 5; text: plRoot.targetSym; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; onTextChanged: plRoot.targetSym = text.toUpperCase() }
                    }
                    Rectangle {
                        width: 60; height: 26; radius: theme.rSharp; color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
                        TextInput { anchors.fill: parent; anchors.margins: 5; text: plRoot.targetPct; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; onTextChanged: plRoot.targetPct = text }
                    }
                    Rectangle {
                        width: 96; height: 26; radius: theme.rSharp; color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                        Text { anchors.centerIn: parent; text: "SET TARGET %"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: plRoot.runCli(["target", "set", plRoot.targetSym, plRoot.targetPct], "Set target " + plRoot.targetSym + " = " + plRoot.targetPct + "%") }
                    }
                }
                Row {
                    spacing: 6
                    Text { text: "DCA BUDGET ($):"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                    Rectangle {
                        width: 80; height: 26; radius: theme.rSharp; color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
                        TextInput { anchors.fill: parent; anchors.margins: 5; text: plRoot.dcaBudget; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; onTextChanged: plRoot.dcaBudget = text }
                    }
                    Rectangle {
                        width: 120; height: 26; radius: theme.rSharp; color: theme.accent
                        Text { anchors.centerIn: parent; text: "COMPUTE DCA PLAN"; color: "#FFFFFF"; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: plRoot.runCli(["dca", plRoot.dcaBudget], "Computed $" + plRoot.dcaBudget + " DCA plan") }
                    }
                }
            }
        }

        // 3. Scenario Simulation & Future Portfolio Projections
        Rectangle {
            width: parent.width; height: 150; radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            Column {
                anchors.fill: parent; anchors.margins: 10; spacing: 8
                Text { text: "SCENARIO SIMULATION & WEALTH PROJECTION"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                Row {
                    spacing: 12
                    Row {
                        spacing: 4
                        Text { text: "MONTHLY ($" + plRoot.monthlyContrib.toFixed(0) + ")"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                        Rectangle { width: 22; height: 22; radius: theme.rSharp; color: theme.bgElevated; Text { anchors.centerIn: parent; text: "-"; color: theme.textPrimary; font.family: theme.fontMono } MouseArea { anchors.fill: parent; onClicked: plRoot.monthlyContrib = Math.max(0, plRoot.monthlyContrib - 25) } }
                        Rectangle { width: 22; height: 22; radius: theme.rSharp; color: theme.bgElevated; Text { anchors.centerIn: parent; text: "+"; color: theme.textPrimary; font.family: theme.fontMono } MouseArea { anchors.fill: parent; onClicked: plRoot.monthlyContrib += 25 } }
                    }
                    Row {
                        spacing: 4
                        Text { text: "CAGR (" + plRoot.annualCagrPct.toFixed(0) + "%)"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                        Rectangle { width: 22; height: 22; radius: theme.rSharp; color: theme.bgElevated; Text { anchors.centerIn: parent; text: "-"; color: theme.textPrimary; font.family: theme.fontMono } MouseArea { anchors.fill: parent; onClicked: plRoot.annualCagrPct = Math.max(2, plRoot.annualCagrPct - 2) } }
                        Rectangle { width: 22; height: 22; radius: theme.rSharp; color: theme.bgElevated; Text { anchors.centerIn: parent; text: "+"; color: theme.textPrimary; font.family: theme.fontMono } MouseArea { anchors.fill: parent; onClicked: plRoot.annualCagrPct = Math.min(40, plRoot.annualCagrPct + 2) } }
                    }
                }
                Row {
                    width: parent.width; spacing: 8
                    Repeater {
                        model: [1, 3, 5, 10]
                        delegate: Rectangle {
                            width: (parent.width - 24) / 4; height: 64; radius: theme.rSharp
                            color: theme.bgBlack; border.color: theme.borderSubtle; border.width: 1
                            Column {
                                anchors.centerIn: parent; spacing: 3
                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData + " YEAR" + (modelData > 1 ? "S" : ""); color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: theme.fmtMoney(plRoot.projectYears(modelData), "USD", 0); color: theme.gain; font.family: theme.fontMono; font.pixelSize: 15; font.bold: true }
                            }
                        }
                    }
                }
            }
        }
    }
}
