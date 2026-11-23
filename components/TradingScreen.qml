import QtQuick

Flickable {
    id: trRoot
    property var theme
    property var summaryData: ({})
    property string side: "buy" // buy, sell, price, alert
    property string symText: "INFR"
    property string qtyText: "100"
    property string pxText: "0.24"
    property string statusFilter: "ALL" // ALL, PENDING, EXECUTED, CANCELLED
    signal runCli(var args, string label)

    contentWidth: width
    contentHeight: trCol.implicitHeight + 20
    clip: true

    function estGross() { return Math.max(0, Number(qtyText || 0) * Number(pxText || 0)) }
    function estFee() { return estGross() * 0.0104 }

    Column {
        id: trCol
        width: parent.width
        spacing: 10

        // 1. Available Balances Strip
        Row {
            width: parent.width; spacing: 8
            Rectangle {
                width: (parent.width - 8) / 2; height: 54; radius: theme.rSharp
                color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                Column {
                    anchors.fill: parent; anchors.margins: 8; spacing: 2
                    Text { text: "AVAILABLE USD CASH (VFEX / C-TRADE)"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                    Text { text: theme.fmtMoney(summaryData.wallet_cash_usd, "USD", 2); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 16; font.bold: true }
                }
            }
            Rectangle {
                width: (parent.width - 8) / 2; height: 54; radius: theme.rSharp
                color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                Column {
                    anchors.fill: parent; anchors.margins: 8; spacing: 2
                    Text { text: "AVAILABLE ZWG CASH (ZSE / C-TRADE)"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                    Text { text: theme.fmtMoney(summaryData.wallet_cash_zwg, "ZWG", 2); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 16; font.bold: true }
                }
            }
        }

        // 2. Order Ticket
        Rectangle {
            width: parent.width; height: 175; radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderDefault; border.width: 1
            Column {
                anchors.fill: parent; anchors.margins: 12; spacing: 8
                Row {
                    spacing: 6
                    Repeater {
                        model: [
                            { k: "buy", t: "BUY", c: theme.gain },
                            { k: "sell", t: "SELL", c: theme.loss },
                            { k: "price", t: "SET PRICE", c: theme.info },
                            { k: "alert", t: "PRICE ALERT", c: theme.warn }
                        ]
                        delegate: Rectangle {
                            width: 88; height: 26; radius: theme.rSharp
                            color: trRoot.side === modelData.k ? theme.bgActive : theme.bgBlack
                            border.color: trRoot.side === modelData.k ? modelData.c : theme.borderSubtle; border.width: 1
                            Text { anchors.centerIn: parent; text: modelData.t; color: trRoot.side === modelData.k ? modelData.c : theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: trRoot.side = modelData.k }
                        }
                    }
                }

                Row {
                    width: parent.width; spacing: 8
                    Column {
                        spacing: 3
                        Text { text: "SYMBOL"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                        Rectangle {
                            width: 100; height: 28; radius: theme.rSharp; color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
                            TextInput { anchors.fill: parent; anchors.margins: 6; text: trRoot.symText; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; onTextChanged: trRoot.symText = text.toUpperCase() }
                        }
                    }
                    Column {
                        visible: trRoot.side === "buy" || trRoot.side === "sell"
                        spacing: 3
                        Text { text: "QUANTITY"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                        Rectangle {
                            width: 100; height: 28; radius: theme.rSharp; color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
                            TextInput { anchors.fill: parent; anchors.margins: 6; text: trRoot.qtyText; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; onTextChanged: trRoot.qtyText = text }
                        }
                    }
                    Column {
                        spacing: 3
                        Text { text: "PRICE"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                        Rectangle {
                            width: 110; height: 28; radius: theme.rSharp; color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
                            TextInput { anchors.fill: parent; anchors.margins: 6; text: trRoot.pxText; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; onTextChanged: trRoot.pxText = text }
                        }
                    }
                }

                // Fee & Commission Estimator + Submit
                Row {
                    width: parent.width; spacing: 12
                    Text {
                        text: "EST. GROSS " + theme.fmtMoney(trRoot.estGross(), "USD", 2) + "  |  STATUTORY FEES ~" + theme.fmtMoney(trRoot.estFee(), "USD", 2) + "  |  NET " + theme.fmtMoney(trRoot.estGross() + trRoot.estFee(), "USD", 2)
                        color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter
                    }
                    Item { width: Math.max(4, parent.width - 510); height: 1 }
                    Rectangle {
                        width: 130; height: 30; radius: theme.rSharp
                        color: trRoot.side === "sell" ? theme.loss : (trRoot.side === "buy" ? theme.gain : theme.accent)
                        Text { anchors.centerIn: parent; text: "SUBMIT " + trRoot.side.toUpperCase(); color: "#000000"; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                        MouseArea {
                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (trRoot.side === "buy") trRoot.runCli(["buy", trRoot.symText, trRoot.qtyText, trRoot.pxText], "BUY " + trRoot.qtyText + " " + trRoot.symText)
                                else if (trRoot.side === "sell") trRoot.runCli(["sell", trRoot.symText, trRoot.qtyText, trRoot.pxText], "SELL " + trRoot.qtyText + " " + trRoot.symText)
                                else if (trRoot.side === "price") trRoot.runCli(["price", trRoot.symText, trRoot.pxText], "Updated price " + trRoot.symText)
                                else if (trRoot.side === "alert") trRoot.runCli(["alert", "add", trRoot.symText, "above", trRoot.pxText], "Added alert for " + trRoot.symText)
                            }
                        }
                    }
                }
            }
        }

        // 3. Order History & Confirmations
        Rectangle {
            width: parent.width; height: Math.max(120, ordCol.implicitHeight + 20); radius: theme.rSharp
            color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
            Column {
                id: ordCol
                anchors.fill: parent; anchors.margins: 10; spacing: 6
                Text { text: "ORDER HISTORY, PENDING PORTAL ORDERS & CONFIRMATIONS"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }
                Repeater {
                    model: (summaryData.portal_orders || []).concat(summaryData.trades || []).slice(0, 12)
                    delegate: Row {
                        width: parent.width; spacing: 10
                        Text { width: 80; text: String(modelData.date || ""); color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10 }
                        Text { width: 54; text: String(modelData.action || modelData.side || "ORD").toUpperCase(); color: String(modelData.action || modelData.side) === "BUY" ? theme.gain : theme.loss; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                        Text { width: 64; text: String(modelData.symbol || ""); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                        Text { width: 70; text: Number(modelData.shares || 0).toFixed(0) + " sh"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10 }
                        Text { width: 84; text: theme.fmtMoney(modelData.price, "USD", 4); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10 }
                        Text { text: String(modelData.status || "EXECUTED").toUpperCase(); color: theme.info; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                    }
                }
                Text { visible: ((summaryData.portal_orders || []).length + (summaryData.trades || []).length) === 0; text: "No pending or executed orders recorded yet."; color: theme.textDim; font.family: theme.fontMono; font.pixelSize: 10 }
            }
        }
    }
}
