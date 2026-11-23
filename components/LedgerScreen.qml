import QtQuick

Flickable {
    id: ledRoot
    property var theme
    property var summaryData: ({})
    property string typeFilter: "ALL" // ALL, BUY, SELL, DEPOSIT, WITHDRAWAL, DIVIDEND
    signal runCli(var args, string label)

    contentWidth: width
    contentHeight: ledCol.implicitHeight + 20
    clip: true

    function allEntries() {
        var out = []
        var trs = summaryData.trades || []
        for (var i = 0; i < trs.length; i++) {
            var t = trs[i]
            out.push({ date: t.date, type: String(t.action || "TRADE").toUpperCase(), symbol: t.symbol, desc: t.shares + " sh @ " + t.price, amount: Number(t.shares || 0) * Number(t.price || 0), currency: "USD" })
        }
        var divs = summaryData.dividends || []
        for (var j = 0; j < divs.length; j++) {
            var d = divs[j]
            out.push({ date: d.date, type: "DIVIDEND", symbol: d.symbol, desc: "Cash dividend", amount: Number(d.amount || 0), currency: "USD" })
        }
        var ptx = summaryData.portal_transactions || []
        for (var k = 0; k < ptx.length; k++) {
            var p = ptx[k]
            out.push({ date: p.date, type: String(p.type || "PORTAL").toUpperCase(), symbol: p.symbol || p.provider, desc: p.description || "", amount: Number(p.amount || 0), currency: p.currency || "USD" })
        }
        if (typeFilter === "ALL") return out
        return out.filter(function(r) { return r.type.indexOf(typeFilter) >= 0 })
    }

    Column {
        id: ledCol
        width: parent.width
        spacing: 10

        // 1. Connected Portals & Sync Strip
        Rectangle {
            width: parent.width; height: 68; radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderDefault; border.width: 1
            Row {
                anchors.fill: parent; anchors.margins: 10; spacing: 10
                Repeater {
                    model: ["ctrade", "vfex_direct", "zse_direct"]
                    delegate: Rectangle {
                        width: (parent.width - 130) / 3; height: 48; radius: theme.rSharp
                        color: theme.bgBlack; border.color: theme.borderSubtle; border.width: 1
                        property var pinfo: (summaryData.accounts && summaryData.accounts[modelData]) ? summaryData.accounts[modelData] : ({})
                        Column {
                            anchors.fill: parent; anchors.margins: 7; spacing: 2
                            Row {
                                spacing: 5
                                Rectangle { width: 6; height: 6; radius: 3; anchors.verticalCenter: parent.verticalCenter; color: parent.parent.parent.pinfo.connected ? theme.gain : theme.textDim }
                                Text { text: modelData.toUpperCase().replace("_", " "); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            }
                            Text {
                                text: parent.parent.pinfo.connected ? (String(parent.parent.pinfo.email_masked || "Connected") + " · " + Number(parent.parent.pinfo.holdings_count || 0) + " pos") : "Not connected"
                                color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; elide: Text.ElideRight; width: parent.width
                            }
                        }
                    }
                }
                Rectangle {
                    width: 100; height: 48; radius: theme.rSharp
                    color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                    Text { anchors.centerIn: parent; text: "SYNC ALL\nPORTALS"; horizontalAlignment: Text.AlignHCenter; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: ledRoot.runCli(["account", "sync", "all"], "Synced all connected portals") }
                }
            }
        }

        // 2. Audit Trail Filter + Export
        Row {
            width: parent.width; spacing: 6
            Repeater {
                model: ["ALL", "BUY", "SELL", "DEPOSIT", "WITHDRAWAL", "DIVIDEND"]
                delegate: Rectangle {
                    width: 78; height: 24; radius: theme.rSharp
                    color: ledRoot.typeFilter === modelData ? theme.bgActive : theme.bgPanel
                    border.color: ledRoot.typeFilter === modelData ? theme.accent : theme.borderSubtle; border.width: 1
                    Text { anchors.centerIn: parent; text: modelData; color: ledRoot.typeFilter === modelData ? theme.textPrimary : theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: ledRoot.typeFilter = modelData }
                }
            }
            Item { width: Math.max(4, parent.width - 590); height: 1 }
            Rectangle {
                width: 88; height: 24; radius: theme.rSharp; color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                Text { anchors.centerIn: parent; text: "EXPORT CSV"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: ledRoot.runCli(["export", "--format", "csv", "--out", "vfex_ledger_export.csv"], "Exported vfex_ledger_export.csv") }
            }
        }

        // 3. Full Audit Trail Table
        Rectangle {
            width: parent.width; height: Math.max(160, trListCol.implicitHeight + 20); radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            Column {
                id: trListCol
                anchors.fill: parent; anchors.margins: 10; spacing: 5
                Text { text: "FULL AUDIT TRAIL (" + ledRoot.allEntries().length + " ENTRIES)"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }
                Repeater {
                    model: ledRoot.allEntries().slice(0, 30)
                    delegate: Row {
                        width: parent.width; spacing: 8
                        Text { width: 82; text: String(modelData.date || ""); color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10 }
                        Text { width: 84; text: String(modelData.type || ""); color: theme.info; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                        Text { width: 68; text: String(modelData.symbol || ""); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                        Text { width: parent.width - 340; elide: Text.ElideRight; text: String(modelData.desc || ""); color: theme.textSecondary; font.family: theme.fontSans; font.pixelSize: 10 }
                        Text { width: 86; horizontalAlignment: Text.AlignRight; text: theme.fmtMoney(modelData.amount, modelData.currency, 2); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10 }
                    }
                }
            }
        }
    }
}
