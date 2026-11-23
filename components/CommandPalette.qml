import QtQuick

Rectangle {
    id: paletteRoot
    property var theme
    property var summaryData: ({})
    property bool open: false
    property string query: ""
    signal navigateScreen(string screenKey)
    signal selectWorkspace(string wsKey)
    signal openStock(string symbol)
    signal runAction(string actionKey)
    signal closeRequested()

    visible: open
    anchors.fill: parent
    color: "#B8000000"
    z: 999

    onOpenChanged: {
        if (open) {
            query = ""
            searchInput.text = ""
            searchInput.forceActiveFocus()
        }
    }

    function filteredItems() {
        var q = String(query || "").trim().toLowerCase()
        var items = [
            { kind: "CMD", key: "overview", label: "/overview — Portfolio Overview", hint: "Key 1" },
            { kind: "CMD", key: "portfolio", label: "/portfolio — Complete Holdings", hint: "Key 2" },
            { kind: "CMD", key: "screener", label: "/markets /screener /vfex /zse /ctrade — Market Screener", hint: "Key 3" },
            { kind: "CMD", key: "stock", label: "/research — Stock Detail & Research", hint: "Key 4" },
            { kind: "CMD", key: "intelligence", label: "/intelligence — 8-Agent AI Desk & Mahoraga", hint: "Key 5" },
            { kind: "CMD", key: "newsroom", label: "/news — Newsroom & Why This Matters", hint: "Key 6" },
            { kind: "CMD", key: "planner", label: "/planner — Investment Planner & Scenarios", hint: "Key 7" },
            { kind: "CMD", key: "trading", label: "/trading /alerts — Order Ticket & Price Alerts", hint: "Key 8" },
            { kind: "CMD", key: "ledger", label: "/ledger — Audit Trail & Portal Sync", hint: "Key 9" },
            { kind: "CMD", key: "overview", label: "/watchlist — Watchlist Tape", hint: "Dock" },
            { kind: "WORKSPACE", key: "portfolio_overview", label: "Workspace: Portfolio Overview", hint: "Layout" },
            { kind: "WORKSPACE", key: "market_watch", label: "Workspace: Market Watch", hint: "Layout" },
            { kind: "WORKSPACE", key: "research_desk", label: "Workspace: Research Desk", hint: "Layout" },
            { kind: "WORKSPACE", key: "trading_desk", label: "Workspace: Trading Desk", hint: "Layout" },
            { kind: "WORKSPACE", key: "intelligence_desk", label: "Workspace: Intelligence Desk", hint: "Layout" },
            { kind: "ACTION", key: "refresh", label: "/refresh — Fetch Live Market Data", hint: "Key R" },
            { kind: "ACTION", key: "agent_step", label: "Run Mahoraga Agent Step", hint: "AI" },
            { kind: "ACTION", key: "agent_train", label: "Train Mahoraga Brain", hint: "AI" },
            { kind: "ACTION", key: "sync_all", label: "Sync All Connected Portals", hint: "Sync" }
        ]
        var scr = (summaryData && summaryData.screener) ? summaryData.screener : []
        for (var i = 0; i < scr.length; i++) {
            var r = scr[i]
            items.push({
                kind: "COUNTER",
                key: String(r.symbol || ""),
                label: String(r.symbol || "") + " — " + String(r.company_name || ""),
                hint: (r.currency === "ZWG" ? "ZSE" : "VFEX") + " " + theme.fmtMoney(r.price, r.currency, 4)
            })
        }
        if (!q) return items.slice(0, 14)
        var out = []
        for (var j = 0; j < items.length; j++) {
            var it = items[j]
            if (it.label.toLowerCase().indexOf(q) >= 0 || it.key.toLowerCase().indexOf(q) >= 0 || it.kind.toLowerCase().indexOf(q) >= 0) {
                out.push(it)
                if (out.length >= 14) break
            }
        }
        return out
    }

    function executeItem(it) {
        if (!it) return
        if (it.kind === "SCREEN" || it.kind === "CMD") navigateScreen(it.key)
        else if (it.kind === "WORKSPACE") selectWorkspace(it.key)
        else if (it.kind === "COUNTER") openStock(it.key)
        else if (it.kind === "ACTION") runAction(it.key)
        closeRequested()
    }

    MouseArea { anchors.fill: parent; onClicked: paletteRoot.closeRequested() }

    Rectangle {
        width: Math.min(560, parent.width - 40)
        height: Math.min(440, parent.height - 80)
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 48
        color: theme.bgSurface
        border.color: theme.borderStrong
        border.width: 1
        radius: theme.rSm

        MouseArea { anchors.fill: parent } // swallow backdrop clicks

        Column {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 8

            Rectangle {
                width: parent.width; height: 34; radius: theme.rSharp
                color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
                Row {
                    anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 8
                    Text { text: ">"; color: theme.accent; font.family: theme.fontMono; font.pixelSize: 13; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                    TextInput {
                        id: searchInput
                        width: parent.width - 50
                        anchors.verticalCenter: parent.verticalCenter
                        color: theme.textPrimary
                        font.family: theme.fontMono; font.pixelSize: 12
                        selectByMouse: true
                        onTextChanged: paletteRoot.query = text
                        Keys.onEscapePressed: paletteRoot.closeRequested()
                        Keys.onReturnPressed: {
                            var list = paletteRoot.filteredItems()
                            if (list.length > 0) paletteRoot.executeItem(list[0])
                        }
                    }
                    Text { text: "ESC"; color: theme.textDim; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                }
            }

            ListView {
                width: parent.width
                height: parent.height - 44
                clip: true
                spacing: 2
                model: paletteRoot.filteredItems()
                delegate: Rectangle {
                    width: ListView.view.width; height: 28; radius: theme.rSharp
                    color: rowMa.containsMouse ? theme.bgHover : "transparent"
                    Row {
                        anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8; spacing: 10
                        Text {
                            width: 72
                            text: modelData.kind
                            color: modelData.kind === "COUNTER" ? theme.gain : (modelData.kind === "ACTION" ? theme.accent : theme.textMuted)
                            font.family: theme.fontMono; font.pixelSize: 9; font.bold: true
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            width: parent.width - 190
                            text: modelData.label
                            elide: Text.ElideRight
                            color: theme.textPrimary
                            font.family: theme.fontSans; font.pixelSize: 11
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            width: 100
                            horizontalAlignment: Text.AlignRight
                            text: modelData.hint
                            color: theme.textMuted
                            font.family: theme.fontMono; font.pixelSize: 10
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: rowMa
                        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: paletteRoot.executeItem(modelData)
                    }
                }
            }
        }
    }
}
