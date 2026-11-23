import QtQuick

Rectangle {
    id: compactRoot
    property var theme
    property var summaryData: ({})
    property bool busy: false
    signal openFullTerminal(string screenKey)
    signal refreshRequested()

    color: theme.bgBlack
    border.color: theme.borderDefault
    border.width: 1
    radius: theme.rSm

    Column {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        // Top Bar: Brand + Market Status + Refresh
        Row {
            width: parent.width
            spacing: 8
            Rectangle {
                width: 6; height: 6; radius: 3; anchors.verticalCenter: parent.verticalCenter
                color: summaryData.market_status === "Open" ? theme.gain : theme.accent
            }
            Text {
                text: "NOTHING // TERMINAL"
                color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }
            Item { width: Math.max(4, parent.width - 270); height: 1 }
            Text {
                text: String(summaryData.market_status || "Closed").toUpperCase() + " · " + String(summaryData.market_countdown || "")
                color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }

        // Portfolio Value + Daily P&L
        Row {
            width: parent.width
            spacing: 12
            Column {
                width: parent.width * 0.52
                spacing: 2
                Text { text: "TOTAL PORTFOLIO (USD)"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                Text {
                    text: theme.fmtMoney(summaryData.total_value, "USD", 2)
                    color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 22; font.bold: true
                }
                Text {
                    text: theme.fmtSignedMoney(summaryData.total_pnl, "USD", 2) + " (" + theme.fmtPct(summaryData.total_pnl_pct, 2) + ")"
                    color: theme.toneColor(summaryData.total_pnl)
                    font.family: theme.fontMono; font.pixelSize: 11; font.bold: true
                }
            }
            Column {
                width: parent.width * 0.44
                spacing: 4
                Text { text: "AVAILABLE CASH"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                Text {
                    text: "USD  " + theme.fmtMoney(summaryData.wallet_cash_usd, "USD", 2)
                    color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11
                }
                Text {
                    text: "ZWG  " + theme.fmtMoney(summaryData.wallet_cash_zwg, "ZWG", 2)
                    color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 11
                }
            }
        }

        // Agent Activity Strip
        Rectangle {
            width: parent.width; height: 42; radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            property var ag: summaryData.paper_agent || ({})
            Row {
                anchors.fill: parent; anchors.margins: 8; spacing: 10
                Column {
                    width: parent.width - 90
                    spacing: 2
                    Text {
                        text: "MAHORAGA AI · " + (parent.parent.ag.enabled ? "ACTIVE" : "PAUSED")
                        color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true
                    }
                    Text {
                        text: "Equity " + theme.fmtMoney(parent.parent.ag.equity_usd, "USD", 2) + " (" + theme.fmtPct(parent.parent.ag.net_pnl_pct, 2) + ") · " + String((parent.parent.ag.grok && parent.parent.ag.grok.status) ? parent.parent.ag.grok.status : "Ready")
                        elide: Text.ElideRight; width: parent.width
                        color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10
                    }
                }
                Rectangle {
                    width: 72; height: 22; radius: theme.rSharp; anchors.verticalCenter: parent.verticalCenter
                    color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                    Text { anchors.centerIn: parent; text: "AI DESK"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: compactRoot.openFullTerminal("intelligence") }
                }
            }
        }

        // Important Price Alerts / Top Signal
        Rectangle {
            width: parent.width; height: 44; radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            property var alertsList: summaryData.triggered_alerts || summaryData.active_alerts || []
            property var topSig: summaryData.top_signal || null
            Column {
                anchors.fill: parent; anchors.margins: 8; spacing: 2
                Text {
                    text: parent.parent.alertsList.length > 0 ? ("PRICE ALERTS (" + parent.parent.alertsList.length + ")") : "TOP QUANT SIGNAL"
                    color: parent.parent.alertsList.length > 0 ? theme.accent : theme.textMuted
                    font.family: theme.fontMono; font.pixelSize: 9; font.bold: true
                }
                Text {
                    width: parent.width; elide: Text.ElideRight
                    text: parent.parent.alertsList.length > 0
                        ? (String(parent.parent.alertsList[0].symbol || "") + " " + String(parent.parent.alertsList[0].direction || "") + " " + theme.fmtMoney(parent.parent.alertsList[0].target_price, "USD", 4))
                        : (parent.parent.topSig ? (String(parent.parent.topSig.action || "") + " " + String(parent.parent.topSig.symbol || "") + " @ " + theme.fmtMoney(parent.parent.topSig.price, parent.parent.topSig.currency, 4) + " · Score " + Number(parent.parent.topSig.score || 0)) : "No active alerts or signals")
                    color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10
                }
            }
        }

        // Action Buttons
        Row {
            width: parent.width; spacing: 8
            Rectangle {
                width: parent.width - 86; height: 30; radius: theme.rSharp
                color: theme.accent
                Text { anchors.centerIn: parent; text: "OPEN FULL TERMINAL"; color: "#FFFFFF"; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: compactRoot.openFullTerminal("overview") }
            }
            Rectangle {
                width: 78; height: 30; radius: theme.rSharp
                color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                Text { anchors.centerIn: parent; text: compactRoot.busy ? "SYNC..." : "REFRESH"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: compactRoot.refreshRequested() }
            }
        }
    }
}
