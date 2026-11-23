import QtQuick

Flickable {
    id: ovRoot
    property var theme
    property var summaryData: ({})
    property bool showAlertsSection: true
    property bool showTxSection: true
    signal openStock(string symbol)
    signal navigateScreen(string screenKey)
    signal runCli(var args, string label)

    contentWidth: width
    contentHeight: ovCol.implicitHeight + 20
    clip: true

    function calcFlowTotals() {
        var txs = summaryData.portal_transactions || []
        var dep = 0, wdr = 0
        for (var i = 0; i < txs.length; i++) {
            var tp = String(txs[i].type || "").toLowerCase()
            var amt = Math.abs(Number(txs[i].amount || 0))
            if (tp.indexOf("deposit") >= 0 || tp.indexOf("credit") >= 0) dep += amt
            else if (tp.indexOf("withdraw") >= 0) wdr += amt
        }
        return { dep: dep, wdr: wdr }
    }

    function topMovers(desc) {
        var scr = (summaryData.screener || []).slice()
        scr.sort(function(a, b) {
            var ca = Number(a.change_pct || 0), cb = Number(b.change_pct || 0)
            return desc ? (cb - ca) : (ca - cb)
        })
        return scr.slice(0, 5)
    }

    Column {
        id: ovCol
        width: parent.width
        spacing: 10

        // 1. Top KPI Strip (Bloomberg-style dense strip)
        Grid {
            width: parent.width
            columns: width > 780 ? 4 : 2
            spacing: 8
            property real cellW: (width - (columns - 1) * spacing) / columns
            property var flows: ovRoot.calcFlowTotals()

            // KPI 1: Total Portfolio Value
            Rectangle {
                width: parent.cellW; height: 74; radius: theme.rSharp
                color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                Column {
                    anchors.fill: parent; anchors.margins: 10; spacing: 3
                    Text { text: "TOTAL PORTFOLIO VALUE"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    Text { text: theme.fmtMoney(summaryData.total_value, "USD", 2); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 20; font.bold: true }
                    Text {
                        text: "UNREALISED " + theme.fmtSignedMoney(summaryData.total_pnl, "USD", 2) + " (" + theme.fmtPct(summaryData.total_pnl_pct, 2) + ")"
                        color: theme.toneColor(summaryData.total_pnl); font.family: theme.fontMono; font.pixelSize: 10
                    }
                }
            }

            // KPI 2: Performance Horizons (1D / 1W / 1M / 1Y / XIRR)
            Rectangle {
                width: parent.cellW; height: 74; radius: theme.rSharp
                color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                Column {
                    anchors.fill: parent; anchors.margins: 10; spacing: 3
                    Text { text: "RETURNS & REALISED"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    Text {
                        text: "NET " + theme.fmtSignedMoney(summaryData.net_total_pnl, "USD", 2) + " (" + theme.fmtPct(summaryData.net_total_pnl_pct, 2) + ")"
                        color: theme.toneColor(summaryData.net_total_pnl); font.family: theme.fontMono; font.pixelSize: 13; font.bold: true
                    }
                    Text {
                        text: "REALISED " + theme.fmtSignedMoney(summaryData.realized_pnl, "USD", 2) + " · DIV " + theme.fmtMoney(summaryData.total_dividends, "USD", 2)
                        color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10
                    }
                }
            }

            // KPI 3: Available Cash by Exchange
            Rectangle {
                width: parent.cellW; height: 74; radius: theme.rSharp
                color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                Column {
                    anchors.fill: parent; anchors.margins: 10; spacing: 3
                    Text { text: "AVAILABLE CASH & FLOWS"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    Text {
                        text: "USD " + theme.fmtMoney(summaryData.wallet_cash_usd, "USD", 2) + "  |  ZWG " + theme.fmtMoney(summaryData.wallet_cash_zwg, "ZWG", 2)
                        color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; font.bold: true
                    }
                    Text {
                        text: "DEP " + theme.fmtMoney(parent.parent.parent.flows.dep, "USD", 2) + " · WDR " + theme.fmtMoney(parent.parent.parent.flows.wdr, "USD", 2)
                        color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10
                    }
                }
            }

            // KPI 4: Mahoraga AI Agent Activity
            Rectangle {
                width: parent.cellW; height: 74; radius: theme.rSharp
                color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                property var ag: summaryData.paper_agent || ({})
                Column {
                    anchors.fill: parent; anchors.margins: 10; spacing: 3
                    Row {
                        width: parent.width; spacing: 6
                        Rectangle { width: 6; height: 6; radius: 3; anchors.verticalCenter: parent.verticalCenter; color: parent.parent.parent.ag.enabled ? theme.gain : theme.textMuted }
                        Text { text: "MAHORAGA AI AGENT"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    }
                    Text {
                        text: theme.fmtMoney(parent.parent.ag.equity_usd, "USD", 2) + " (" + theme.fmtPct(parent.parent.ag.net_pnl_pct, 2) + ")"
                        color: theme.toneColor(parent.parent.ag.net_pnl_pct); font.family: theme.fontMono; font.pixelSize: 14; font.bold: true
                    }
                    Text {
                        text: String((parent.parent.ag.grok && parent.parent.ag.grok.status) ? parent.parent.ag.grok.status : "Foundation Ready")
                        elide: Text.ElideRight; width: parent.width
                        color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 9
                    }
                }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: ovRoot.navigateScreen("intelligence") }
            }
        }

        // 2. Holdings Performance & Allocation
        Rectangle {
            width: parent.width
            height: holdCol.implicitHeight + 20
            radius: theme.rSharp; color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            Column {
                id: holdCol
                anchors.fill: parent; anchors.margins: 10; spacing: 6
                Row {
                    width: parent.width
                    Text { text: "HOLDINGS PERFORMANCE & ALLOCATION"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                    Item { width: Math.max(8, parent.width - 330); height: 1 }
                    Text {
                        text: "FULL PORTFOLIO →"; color: theme.accent; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: ovRoot.navigateScreen("portfolio") }
                    }
                }
                Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }
                Repeater {
                    model: (summaryData.items || []).slice(0, 8)
                    delegate: Rectangle {
                        width: parent.width; height: 28; radius: theme.rSharp
                        color: hMa.containsMouse ? theme.bgHover : "transparent"
                        Row {
                            anchors.fill: parent; anchors.leftMargin: 6; anchors.rightMargin: 6; spacing: 8
                            Text { width: 64; text: String(modelData.symbol || ""); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                            Text { width: 54; text: theme.exchangeLabel(modelData); color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                            Text { width: 70; horizontalAlignment: Text.AlignRight; text: Number(modelData.shares || 0).toFixed(0) + " sh"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                            Text { width: 82; horizontalAlignment: Text.AlignRight; text: theme.fmtMoney(modelData.value, modelData.currency, 2); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                            Text { width: 96; horizontalAlignment: Text.AlignRight; text: theme.fmtPct(modelData.pnl_pct, 2); color: theme.toneColor(modelData.pnl_pct); font.family: theme.fontMono; font.pixelSize: 11; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                            // Allocation mini-bar
                            Rectangle {
                                width: Math.max(40, parent.width - 420); height: 6; radius: 1; anchors.verticalCenter: parent.verticalCenter
                                color: theme.bgElevated
                                Rectangle {
                                    width: Math.min(parent.width, parent.width * (Number(modelData.alloc_pct || 0) / 100.0))
                                    height: parent.height; radius: 1; color: theme.textSecondary
                                }
                            }
                            Text { width: 42; horizontalAlignment: Text.AlignRight; text: Number(modelData.alloc_pct || 0).toFixed(0) + "%"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                        }
                        MouseArea { id: hMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: ovRoot.openStock(modelData.symbol) }
                    }
                }
                Text {
                    visible: (summaryData.items || []).length === 0
                    text: "No holdings recorded. Use Trading Desk (8) or Ledger (9) to sync portals or record trades."
                    color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10
                }
            }
        }

        // 3. Biggest Winners & Losers (2-column split)
        Row {
            width: parent.width; spacing: 8
            // Winners
            Rectangle {
                width: (parent.width - 8) / 2; height: 170; radius: theme.rSharp
                color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                Column {
                    anchors.fill: parent; anchors.margins: 10; spacing: 5
                    Text { text: "TOP GAINERS (VFEX / ZSE)"; color: theme.gain; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                    Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }
                    Repeater {
                        model: ovRoot.topMovers(true)
                        delegate: Rectangle {
                            width: parent.width; height: 22; color: gMa.containsMouse ? theme.bgHover : "transparent"
                            Row {
                                anchors.fill: parent; anchors.leftMargin: 4; anchors.rightMargin: 4
                                Text { width: 62; text: String(modelData.symbol || ""); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                                Text { width: parent.width - 140; text: theme.fmtMoney(modelData.price, modelData.currency, 4); color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                                Text { width: 70; horizontalAlignment: Text.AlignRight; text: theme.fmtPct(modelData.change_pct, 2); color: theme.toneColor(modelData.change_pct); font.family: theme.fontMono; font.pixelSize: 10; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                            }
                            MouseArea { id: gMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: ovRoot.openStock(modelData.symbol) }
                        }
                    }
                }
            }
            // Losers
            Rectangle {
                width: (parent.width - 8) / 2; height: 170; radius: theme.rSharp
                color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                Column {
                    anchors.fill: parent; anchors.margins: 10; spacing: 5
                    Text { text: "TOP DECLINERS (VFEX / ZSE)"; color: theme.loss; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                    Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }
                    Repeater {
                        model: ovRoot.topMovers(false)
                        delegate: Rectangle {
                            width: parent.width; height: 22; color: lMa.containsMouse ? theme.bgHover : "transparent"
                            Row {
                                anchors.fill: parent; anchors.leftMargin: 4; anchors.rightMargin: 4
                                Text { width: 62; text: String(modelData.symbol || ""); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                                Text { width: parent.width - 140; text: theme.fmtMoney(modelData.price, modelData.currency, 4); color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                                Text { width: 70; horizontalAlignment: Text.AlignRight; text: theme.fmtPct(modelData.change_pct, 2); color: theme.toneColor(modelData.change_pct); font.family: theme.fontMono; font.pixelSize: 10; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                            }
                            MouseArea { id: lMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: ovRoot.openStock(modelData.symbol) }
                        }
                    }
                }
            }
        }

        // 4. Collapsible Alerts & Recent Transactions
        Rectangle {
            width: parent.width; height: ovRoot.showTxSection ? (txCol.implicitHeight + 20) : 34; radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            Column {
                id: txCol
                anchors.fill: parent; anchors.margins: 10; spacing: 6
                Row {
                    width: parent.width
                    Text {
                        text: (ovRoot.showTxSection ? "▾ " : "▸ ") + "RECENT TRANSACTIONS & PORTAL ACTIVITY (" + (summaryData.portal_transactions || []).length + ")"
                        color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: ovRoot.showTxSection = !ovRoot.showTxSection }
                    }
                    Item { width: Math.max(8, parent.width - 360); height: 1 }
                    Text {
                        text: "OPEN LEDGER →"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 9
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: ovRoot.navigateScreen("ledger") }
                    }
                }
                Column {
                    visible: ovRoot.showTxSection
                    width: parent.width; spacing: 4
                    Repeater {
                        model: (summaryData.portal_transactions || []).slice(0, 6)
                        delegate: Row {
                            width: parent.width; spacing: 8
                            Text { width: 80; text: String(modelData.date || ""); color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10 }
                            Text { width: 72; text: String(modelData.type || "").toUpperCase(); color: theme.info; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            Text { width: parent.width - 260; elide: Text.ElideRight; text: String(modelData.description || modelData.symbol || ""); color: theme.textPrimary; font.family: theme.fontSans; font.pixelSize: 10 }
                            Text { width: 90; horizontalAlignment: Text.AlignRight; text: theme.fmtMoney(modelData.amount, modelData.currency, 2); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10 }
                        }
                    }
                }
            }
        }
    }
}
