import QtQuick

Column {
    id: scrRoot
    property var theme
    property var summaryData: ({})
    property string marketFilter: "ALL" // ALL, VFEX, ZSE
    property string strategyFilter: "all" // all, signals, gainers, losers, unusual, liquid
    property string searchQuery: ""
    property string sortKey: "signal_score"
    property bool sortDesc: true
    property bool showRsiCol: true
    property bool showSpreadCol: true
    signal openStock(string symbol)

    spacing: 8

    function filteredCounters() {
        var rows = (summaryData.screener || []).slice()
        var q = String(searchQuery || "").trim().toLowerCase()
        var out = []
        for (var i = 0; i < rows.length; i++) {
            var r = rows[i]
            var isZse = String(r.currency || "USD") === "ZWG"
            if (marketFilter === "VFEX" && isZse) continue
            if (marketFilter === "ZSE" && !isZse) continue
            if (strategyFilter === "signals" && !(Number(r.signal_score || 0) >= 35)) continue
            if (strategyFilter === "gainers" && !(Number(r.change_pct || 0) > 0)) continue
            if (strategyFilter === "losers" && !(Number(r.change_pct || 0) < 0)) continue
            if (strategyFilter === "unusual" && !(Math.abs(Number(r.z_score || 0)) >= 1.5 || Math.abs(Number(r.change_pct || 0)) >= 4.0)) continue
            if (strategyFilter === "liquid" && !(Number(r.liquidity_score || 0) >= 50)) continue
            if (q && String(r.symbol || "").toLowerCase().indexOf(q) < 0 && String(r.company_name || "").toLowerCase().indexOf(q) < 0) continue
            out.push(r)
        }
        out.sort(function(a, b) {
            if (sortKey === "symbol") return sortDesc ? String(b.symbol || "").localeCompare(String(a.symbol || "")) : String(a.symbol || "").localeCompare(String(b.symbol || ""))
            return sortDesc ? (Number(b[sortKey] || 0) - Number(a[sortKey] || 0)) : (Number(a[sortKey] || 0) - Number(b[sortKey] || 0))
        })
        return out
    }

    // Market Selector + Saved Strategies + Search
    Row {
        width: parent.width; spacing: 6
        Rectangle {
            width: 170; height: 26; radius: theme.rSharp
            color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
            TextInput {
                anchors.fill: parent; anchors.margins: 6
                color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11
                onTextChanged: scrRoot.searchQuery = text
                Text { visible: !parent.text; text: "Search 61 counters..."; color: theme.textDim; font.family: theme.fontMono; font.pixelSize: 10 }
            }
        }
        Repeater {
            model: ["ALL", "VFEX", "ZSE"]
            delegate: Rectangle {
                width: 48; height: 26; radius: theme.rSharp
                color: scrRoot.marketFilter === modelData ? theme.bgActive : theme.bgPanel
                border.color: scrRoot.marketFilter === modelData ? theme.accent : theme.borderSubtle; border.width: 1
                Text { anchors.centerIn: parent; text: modelData; color: scrRoot.marketFilter === modelData ? theme.textPrimary : theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: scrRoot.marketFilter = modelData }
            }
        }
        Repeater {
            model: [
                { k: "all", t: "ALL" },
                { k: "signals", t: "SIGNALS" },
                { k: "gainers", t: "WINNERS" },
                { k: "losers", t: "LOSERS" },
                { k: "unusual", t: "UNUSUAL" },
                { k: "liquid", t: "LIQUID" }
            ]
            delegate: Rectangle {
                width: 62; height: 26; radius: theme.rSharp
                color: scrRoot.strategyFilter === modelData.k ? theme.bgElevated : "transparent"
                border.color: scrRoot.strategyFilter === modelData.k ? theme.borderStrong : theme.borderSubtle; border.width: 1
                Text { anchors.centerIn: parent; text: modelData.t; color: scrRoot.strategyFilter === modelData.k ? theme.textPrimary : theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: scrRoot.strategyFilter = modelData.k }
            }
        }
    }

    // Table Header
    Rectangle {
        width: parent.width; height: 24; radius: theme.rSharp
        color: theme.bgElevated; border.color: theme.borderSubtle; border.width: 1
        Row {
            anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8; spacing: 6
            Repeater {
                model: [
                    { k: "symbol", t: "COUNTER", w: 68 },
                    { k: "price", t: "PRICE", w: 80 },
                    { k: "change_pct", t: "CHG %", w: 66 },
                    { k: "liquidity_score", t: "LIQ", w: 46 },
                    { k: "spread_pct", t: "SPREAD", w: 58 },
                    { k: "rsi14", t: "RSI14", w: 48 },
                    { k: "signal_score", t: "SIGNAL", w: 84 }
                ]
                delegate: Text {
                    width: modelData.w
                    horizontalAlignment: modelData.k === "symbol" ? Text.AlignLeft : Text.AlignRight
                    text: modelData.t + (scrRoot.sortKey === modelData.k ? (scrRoot.sortDesc ? " ▼" : " ▲") : "")
                    color: scrRoot.sortKey === modelData.k ? theme.textPrimary : theme.textMuted
                    font.family: theme.fontMono; font.pixelSize: 9; font.bold: true
                    anchors.verticalCenter: parent.verticalCenter
                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (scrRoot.sortKey === modelData.k) scrRoot.sortDesc = !scrRoot.sortDesc
                            else { scrRoot.sortKey = modelData.k; scrRoot.sortDesc = true }
                        }
                    }
                }
            }
            Text { text: "COMPANY / CATALYST"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
        }
    }

    // Table Rows
    ListView {
        width: parent.width
        height: Math.max(220, parent.height - 66)
        clip: true
        spacing: 2
        model: scrRoot.filteredCounters()
        delegate: Rectangle {
            width: ListView.view.width; height: 28; radius: theme.rSharp
            color: sMa.containsMouse ? theme.bgHover : theme.bgPanel
            border.color: theme.borderSubtle; border.width: 1
            Row {
                anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8; spacing: 6
                Text { width: 68; text: String(modelData.symbol || ""); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                Text { width: 80; horizontalAlignment: Text.AlignRight; text: theme.fmtMoney(modelData.price, modelData.currency, 4); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                Text { width: 66; horizontalAlignment: Text.AlignRight; text: theme.fmtPct(modelData.change_pct, 2); color: theme.toneColor(modelData.change_pct); font.family: theme.fontMono; font.pixelSize: 10; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                Text { width: 46; horizontalAlignment: Text.AlignRight; text: Number(modelData.liquidity_score || 0).toFixed(0); color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                Text { width: 58; horizontalAlignment: Text.AlignRight; text: Number(modelData.spread_pct || 0).toFixed(1) + "%"; color: modelData.wide_spread ? theme.warn : theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                Text { width: 48; horizontalAlignment: Text.AlignRight; text: modelData.rsi14 !== null && modelData.rsi14 !== undefined ? Number(modelData.rsi14).toFixed(0) : "--"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                Text {
                    width: 84; horizontalAlignment: Text.AlignRight
                    text: modelData.signal_action ? (String(modelData.signal_action) + " " + Number(modelData.signal_score || 0)) : "--"
                    color: modelData.signal_action === "BUY" ? theme.gain : (modelData.signal_action === "SELL" ? theme.loss : theme.textDim)
                    font.family: theme.fontMono; font.pixelSize: 10; font.bold: true; anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    width: Math.max(80, parent.width - 510); elide: Text.ElideRight
                    text: String(modelData.company_name || "")
                    color: theme.textSecondary; font.family: theme.fontSans; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter
                }
            }
            MouseArea { id: sMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: scrRoot.openStock(modelData.symbol) }
        }
    }
}
