import QtQuick

Column {
    id: portRoot
    property var theme
    property var summaryData: ({})
    property string searchQuery: ""
    property string exchangeFilter: "ALL" // ALL, VFEX, ZSE, C-TRADE
    property string sortKey: "value"
    property bool sortDesc: true
    signal openStock(string symbol)

    spacing: 8

    function filteredHoldings() {
        var rows = (summaryData.items || []).slice()
        var q = String(searchQuery || "").trim().toLowerCase()
        var out = []
        for (var i = 0; i < rows.length; i++) {
            var r = rows[i]
            var ex = theme.exchangeLabel(r)
            if (exchangeFilter !== "ALL" && ex !== exchangeFilter) continue
            if (q && String(r.symbol || "").toLowerCase().indexOf(q) < 0 && String(r.company_name || "").toLowerCase().indexOf(q) < 0) continue
            out.push(r)
        }
        out.sort(function(a, b) {
            var va = Number(a[sortKey] || 0), vb = Number(b[sortKey] || 0)
            if (sortKey === "symbol") {
                va = String(a.symbol || ""); vb = String(b.symbol || "")
                return sortDesc ? vb.localeCompare(va) : va.localeCompare(vb)
            }
            return sortDesc ? (vb - va) : (va - vb)
        })
        return out
    }

    // Toolbar: Search + Exchange Filters + Sort
    Row {
        width: parent.width; spacing: 8
        Rectangle {
            width: 210; height: 26; radius: theme.rSharp
            color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
            TextInput {
                anchors.fill: parent; anchors.margins: 6
                color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11
                onTextChanged: portRoot.searchQuery = text
                Text { visible: !parent.text; text: "Filter holdings..."; color: theme.textDim; font.family: theme.fontMono; font.pixelSize: 10 }
            }
        }
        Repeater {
            model: ["ALL", "VFEX", "ZSE", "C-TRADE"]
            delegate: Rectangle {
                width: 66; height: 26; radius: theme.rSharp
                color: portRoot.exchangeFilter === modelData ? theme.bgActive : theme.bgPanel
                border.color: portRoot.exchangeFilter === modelData ? theme.accent : theme.borderSubtle; border.width: 1
                Text { anchors.centerIn: parent; text: modelData; color: portRoot.exchangeFilter === modelData ? theme.textPrimary : theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: portRoot.exchangeFilter = modelData }
            }
        }
    }

    // Holdings Table Header
    Rectangle {
        width: parent.width; height: 26; radius: theme.rSharp
        color: theme.bgElevated; border.color: theme.borderSubtle; border.width: 1
        Row {
            anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8; spacing: 6
            Repeater {
                model: [
                    { k: "symbol", t: "SYMBOL", w: 72 },
                    { k: "shares", t: "QTY", w: 60 },
                    { k: "avg_cost", t: "AVG COST", w: 76 },
                    { k: "price", t: "LAST", w: 76 },
                    { k: "cost", t: "COST BASIS", w: 84 },
                    { k: "value", t: "VALUATION", w: 86 },
                    { k: "pnl", t: "UNREALISED", w: 92 },
                    { k: "dividends", t: "DIVIDENDS", w: 72 },
                    { k: "alloc_pct", t: "ALLOC", w: 54 }
                ]
                delegate: Text {
                    width: modelData.w
                    horizontalAlignment: modelData.k === "symbol" ? Text.AlignLeft : Text.AlignRight
                    text: modelData.t + (portRoot.sortKey === modelData.k ? (portRoot.sortDesc ? " ▼" : " ▲") : "")
                    color: portRoot.sortKey === modelData.k ? theme.textPrimary : theme.textMuted
                    font.family: theme.fontMono; font.pixelSize: 9; font.bold: true
                    anchors.verticalCenter: parent.verticalCenter
                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (portRoot.sortKey === modelData.k) portRoot.sortDesc = !portRoot.sortDesc
                            else { portRoot.sortKey = modelData.k; portRoot.sortDesc = true }
                        }
                    }
                }
            }
        }
    }

    // Holdings Table Body
    ListView {
        width: parent.width
        height: Math.max(200, parent.height - 130)
        clip: true
        spacing: 2
        model: portRoot.filteredHoldings()
        delegate: Rectangle {
            width: ListView.view.width; height: 32; radius: theme.rSharp
            color: pMa.containsMouse ? theme.bgHover : theme.bgPanel
            border.color: theme.borderSubtle; border.width: 1
            Row {
                anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8; spacing: 6
                Text { width: 72; text: String(modelData.symbol || ""); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                Text { width: 60; horizontalAlignment: Text.AlignRight; text: Number(modelData.shares || 0).toFixed(0); color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                Text { width: 76; horizontalAlignment: Text.AlignRight; text: theme.fmtMoney(modelData.avg_cost, modelData.currency, 4); color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                Text { width: 76; horizontalAlignment: Text.AlignRight; text: theme.fmtMoney(modelData.price, modelData.currency, 4); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                Text { width: 84; horizontalAlignment: Text.AlignRight; text: theme.fmtMoney(modelData.cost, modelData.currency, 2); color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                Text { width: 86; horizontalAlignment: Text.AlignRight; text: theme.fmtMoney(modelData.value, modelData.currency, 2); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                Text { width: 92; horizontalAlignment: Text.AlignRight; text: theme.fmtSignedMoney(modelData.pnl, modelData.currency, 2) + " (" + theme.fmtPct(modelData.pnl_pct, 1) + ")"; color: theme.toneColor(modelData.pnl); font.family: theme.fontMono; font.pixelSize: 10; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                Text { width: 72; horizontalAlignment: Text.AlignRight; text: theme.fmtMoney(modelData.dividends, modelData.currency, 2); color: theme.gain; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                Text { width: 54; horizontalAlignment: Text.AlignRight; text: Number(modelData.alloc_pct || 0).toFixed(1) + "%"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
            }
            MouseArea { id: pMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: portRoot.openStock(modelData.symbol) }
        }
    }

    // Dividend History Strip
    Rectangle {
        width: parent.width; height: 52; radius: theme.rSharp
        color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
        Row {
            anchors.fill: parent; anchors.margins: 10; spacing: 16
            Column {
                Text { text: "TOTAL DIVIDENDS"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                Text { text: theme.fmtMoney(summaryData.total_dividends, "USD", 2); color: theme.gain; font.family: theme.fontMono; font.pixelSize: 13; font.bold: true }
            }
            Column {
                Text { text: "TOTAL COST BASIS"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                Text { text: theme.fmtMoney(summaryData.total_cost, "USD", 2); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 13; font.bold: true }
            }
            Column {
                Text { text: "CLICK ANY HOLDING"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                Text { text: "Opens full Stock Detail & Thesis Research"; color: theme.textSecondary; font.family: theme.fontSans; font.pixelSize: 11 }
            }
        }
    }
}
