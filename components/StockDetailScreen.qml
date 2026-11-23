import QtQuick

Flickable {
    id: sdRoot
    property var theme
    property var summaryData: ({})
    property string symbol: "INFR"
    property string thesisInput: ""
    property string planShares: "100"
    signal runCli(var args, string label)

    contentWidth: width
    contentHeight: sdCol.implicitHeight + 20
    clip: true

    function findCounter() {
        var scr = summaryData.screener || []
        for (var i = 0; i < scr.length; i++) if (String(scr[i].symbol || "") === symbol) return scr[i]
        var items = summaryData.items || []
        for (var j = 0; j < items.length; j++) if (String(items[j].symbol || "") === symbol) return items[j]
        return scr.length > 0 ? scr[0] : ({ symbol: symbol, price: 0, currency: "USD" })
    }

    function findHolding() {
        var items = summaryData.items || []
        for (var i = 0; i < items.length; i++) if (String(items[i].symbol || "") === symbol) return items[i]
        return null
    }

    function symbolNews() {
        var news = summaryData.news || []
        var out = []
        for (var i = 0; i < news.length; i++) {
            var syms = news[i].symbols || []
            if (syms.indexOf(symbol) >= 0) out.push(news[i])
        }
        return out.slice(0, 6)
    }

    property var counter: findCounter()
    property var holding: findHolding()

    Column {
        id: sdCol
        width: parent.width
        spacing: 10

        // Header Strip
        Rectangle {
            width: parent.width; height: 58; radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderDefault; border.width: 1
            Row {
                anchors.fill: parent; anchors.margins: 10; spacing: 14
                Column {
                    spacing: 2
                    Row {
                        spacing: 8
                        Text { text: String(sdRoot.counter.symbol || sdRoot.symbol); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 18; font.bold: true }
                        Text { text: sdRoot.counter.currency === "ZWG" ? "ZSE" : "VFEX"; color: theme.accent; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                    }
                    Text { text: String(sdRoot.counter.company_name || "Listed Counter"); color: theme.textSecondary; font.family: theme.fontSans; font.pixelSize: 11 }
                }
                Item { width: Math.max(8, parent.width - 420); height: 1 }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    Text { horizontalAlignment: Text.AlignRight; text: theme.fmtMoney(sdRoot.counter.price, sdRoot.counter.currency, 4); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 18; font.bold: true }
                    Text { horizontalAlignment: Text.AlignRight; text: theme.fmtPct(sdRoot.counter.change_pct, 2) + "  |  RSI " + (sdRoot.counter.rsi14 ? Number(sdRoot.counter.rsi14).toFixed(0) : "--"); color: theme.toneColor(sdRoot.counter.change_pct); font.family: theme.fontMono; font.pixelSize: 10 }
                }
            }
        }

        // Interactive Price Chart
        TerminalChart {
            width: parent.width
            height: 220
            theme: sdRoot.theme
            symbol: String(sdRoot.counter.symbol || sdRoot.symbol)
            currency: String(sdRoot.counter.currency || "USD")
            candles: sdRoot.counter.candles || []
            history: sdRoot.counter.history || []
            breakevenPrice: sdRoot.holding ? Number(sdRoot.holding.breakeven_price || 0) : 0
            optimalLimit: Number(sdRoot.counter.optimal_limit || 0)
        }

        // Order Depth + Fundamentals + Portfolio Exposure
        Row {
            width: parent.width; spacing: 8
            Rectangle {
                width: (parent.width - 8) / 2; height: 126; radius: theme.rSharp
                color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                Column {
                    anchors.fill: parent; anchors.margins: 10; spacing: 5
                    Text { text: "ORDER BOOK & TRADING ACTIVITY"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    Text { text: "BEST BID: " + theme.fmtMoney(sdRoot.counter.best_bid, sdRoot.counter.currency, 4) + "  (" + Number(sdRoot.counter.bid_volume || 0) + " sh)"; color: theme.gain; font.family: theme.fontMono; font.pixelSize: 11 }
                    Text { text: "BEST ASK: " + theme.fmtMoney(sdRoot.counter.best_ask, sdRoot.counter.currency, 4) + "  (" + Number(sdRoot.counter.ask_volume || 0) + " sh)"; color: theme.loss; font.family: theme.fontMono; font.pixelSize: 11 }
                    Text { text: "SPREAD: " + Number(sdRoot.counter.spread_pct || 0).toFixed(2) + "%  |  LIQUIDITY: " + Number(sdRoot.counter.liquidity_score || 0).toFixed(0) + "/100"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10 }
                    Text { text: "OPT LIMIT: " + theme.fmtMoney(sdRoot.counter.optimal_limit, sdRoot.counter.currency, 4) + "  |  FOREIGN NET: " + theme.fmtSignedMoney(sdRoot.counter.foreign_net, "USD", 0); color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10 }
                }
            }
            Rectangle {
                width: (parent.width - 8) / 2; height: 126; radius: theme.rSharp
                color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                Column {
                    anchors.fill: parent; anchors.margins: 10; spacing: 5
                    Text { text: "PORTFOLIO EXPOSURE & AI RESEARCH"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    Text {
                        text: sdRoot.holding
                            ? ("HELD: " + Number(sdRoot.holding.shares).toFixed(0) + " sh @ " + theme.fmtMoney(sdRoot.holding.avg_cost, sdRoot.holding.currency, 4) + "  (" + theme.fmtPct(sdRoot.holding.pnl_pct, 2) + ")")
                            : "NOT CURRENTLY HELD IN PORTFOLIO"
                        color: sdRoot.holding ? theme.toneColor(sdRoot.holding.pnl_pct) : theme.textSecondary
                        font.family: theme.fontMono; font.pixelSize: 10; font.bold: true
                    }
                    Text {
                        text: "QUANT SIGNAL: " + (sdRoot.counter.signal_action ? (sdRoot.counter.signal_action + " (Score " + sdRoot.counter.signal_score + ")") : "NEUTRAL")
                        color: sdRoot.counter.signal_action === "BUY" ? theme.gain : (sdRoot.counter.signal_action === "SELL" ? theme.loss : theme.textSecondary)
                        font.family: theme.fontMono; font.pixelSize: 10; font.bold: true
                    }
                    Text {
                        width: parent.width; wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
                        text: (sdRoot.counter.reasons && sdRoot.counter.reasons.length > 0) ? sdRoot.counter.reasons.join(" · ") : "No active catalyst or quant trigger."
                        color: theme.textSecondary; font.family: theme.fontSans; font.pixelSize: 10
                    }
                }
            }
        }

        // Quick Buy / Sell Planning + Thesis Note
        Row {
            width: parent.width; spacing: 8
            Rectangle {
                width: (parent.width - 8) / 2; height: 92; radius: theme.rSharp
                color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                Column {
                    anchors.fill: parent; anchors.margins: 10; spacing: 6
                    Text { text: "QUICK BUY / SELL PLANNING"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    Row {
                        spacing: 6
                        Rectangle {
                            width: 72; height: 26; radius: theme.rSharp; color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
                            TextInput { anchors.fill: parent; anchors.margins: 5; text: sdRoot.planShares; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; onTextChanged: sdRoot.planShares = text }
                        }
                        Rectangle {
                            width: 76; height: 26; radius: theme.rSharp; color: theme.gainBg; border.color: theme.gain; border.width: 1
                            Text { anchors.centerIn: parent; text: "RECORD BUY"; color: theme.gain; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: sdRoot.runCli(["buy", sdRoot.counter.symbol, sdRoot.planShares, String(sdRoot.counter.price || 0)], "Recorded BUY " + sdRoot.counter.symbol) }
                        }
                        Rectangle {
                            width: 80; height: 26; radius: theme.rSharp; color: theme.lossBg; border.color: theme.loss; border.width: 1
                            Text { anchors.centerIn: parent; text: "RECORD SELL"; color: theme.loss; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: sdRoot.runCli(["sell", sdRoot.counter.symbol, sdRoot.planShares, String(sdRoot.counter.price || 0)], "Recorded SELL " + sdRoot.counter.symbol) }
                        }
                        Rectangle {
                            width: 64; height: 26; radius: theme.rSharp; color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                            Text { anchors.centerIn: parent; text: "+WATCH"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: sdRoot.runCli(["watch", "add", sdRoot.counter.symbol], "Added " + sdRoot.counter.symbol + " to watchlist") }
                        }
                    }
                }
            }
            Rectangle {
                width: (parent.width - 8) / 2; height: 92; radius: theme.rSharp
                color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                Column {
                    anchors.fill: parent; anchors.margins: 10; spacing: 6
                    Text { text: "INVESTMENT THESIS NOTE"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    Row {
                        width: parent.width; spacing: 6
                        Rectangle {
                            width: parent.width - 68; height: 26; radius: theme.rSharp; color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
                            TextInput {
                                anchors.fill: parent; anchors.margins: 5
                                text: (summaryData.notes && summaryData.notes[sdRoot.symbol]) ? String(summaryData.notes[sdRoot.symbol]) : ""
                                color: theme.textPrimary; font.family: theme.fontSans; font.pixelSize: 10
                                onTextChanged: sdRoot.thesisInput = text
                            }
                        }
                        Rectangle {
                            width: 62; height: 26; radius: theme.rSharp; color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                            Text { anchors.centerIn: parent; text: "SAVE"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: sdRoot.runCli(["note", "set", sdRoot.counter.symbol, sdRoot.thesisInput], "Saved thesis for " + sdRoot.counter.symbol) }
                        }
                    }
                }
            }
        }

        // Announcements & News for this counter
        Rectangle {
            width: parent.width; height: Math.max(70, snCol.implicitHeight + 20); radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            Column {
                id: snCol
                anchors.fill: parent; anchors.margins: 10; spacing: 4
                Text { text: "COMPANY ANNOUNCEMENTS & NEWS"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                Repeater {
                    model: sdRoot.symbolNews()
                    delegate: Row {
                        width: parent.width; spacing: 8
                        Text { width: 58; text: String(modelData.age_label || ""); color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                        Text { width: 64; text: String(modelData.sentiment || "Neutral").toUpperCase(); color: modelData.sentiment === "Bullish" ? theme.gain : (modelData.sentiment === "Caution" ? theme.loss : theme.textSecondary); font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                        Text { width: parent.width - 140; elide: Text.ElideRight; text: String(modelData.title || ""); color: theme.textPrimary; font.family: theme.fontSans; font.pixelSize: 10 }
                    }
                }
                Text { visible: sdRoot.symbolNews().length === 0; text: "No recent company-specific announcements found."; color: theme.textDim; font.family: theme.fontMono; font.pixelSize: 10 }
            }
        }
    }
}
