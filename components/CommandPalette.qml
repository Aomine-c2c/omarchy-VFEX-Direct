import QtQuick

Rectangle {
    id: paletteRoot
    property var theme
    property var summaryData: ({})
    property bool open: false
    property string query: ""
    signal jumpSection(string sectionKey)
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
            { kind: "SECTION", key: "summary", label: "/overview /summary — Section 2: Portfolio Summary", hint: "Scroll" },
            { kind: "SECTION", key: "analytics", label: "/portfolio /analytics — Section 3: Portfolio Analytics & Holdings", hint: "Scroll" },
            { kind: "SECTION", key: "markets", label: "/markets /vfex /zse /ctrade /screener — Section 4: Market Intelligence", hint: "Scroll" },
            { kind: "SECTION", key: "research", label: "/research — Section 5: Investment Research & Chart", hint: "Scroll" },
            { kind: "SECTION", key: "newsroom", label: "/news — Section 6: Live Newsroom", hint: "Scroll" },
            { kind: "SECTION", key: "agents", label: "/intelligence — Section 7: AI Agent Workspace", hint: "Scroll" },
            { kind: "SECTION", key: "planning", label: "/planner — Section 8: Investment Planning & Scenarios", hint: "Scroll" },
            { kind: "SECTION", key: "trading", label: "/trading /ledger /alerts — Section 9: Trading & Ledger", hint: "Scroll" },
            { kind: "SECTION", key: "assistant", label: "/assistant — Section 10: Conversational Investment Assistant", hint: "Scroll" },
            { kind: "ACTION", key: "refresh", label: "/refresh — Fetch Live Market Data", hint: "Action" },
            { kind: "ACTION", key: "toggle_dock", label: "/watchlist — Toggle Watchlist Dock", hint: "Layout" },
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
        if (it.kind === "SECTION") jumpSection(it.key)
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

        MouseArea { anchors.fill: parent }

        Column {
            anchors.fill: parent; anchors.margins: 10; spacing: 8
            Rectangle {
                width: parent.width; height: 34; radius: theme.rSharp
                color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
                Row {
                    anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 8
                    Text { text: ">"; color: theme.accent; font.family: theme.fontMono; font.pixelSize: 13; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                    TextInput {
                        id: searchInput
                        width: parent.width - 50; anchors.verticalCenter: parent.verticalCenter
                        color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 12
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
                width: parent.width; height: parent.height - 44; clip: true; spacing: 2
                model: paletteRoot.filteredItems()
                delegate: Rectangle {
                    width: ListView.view.width; height: 28; radius: theme.rSharp
                    color: rowMa.containsMouse ? theme.bgHover : "transparent"
                    Row {
                        anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8; spacing: 10
                        Text { width: 68; text: modelData.kind; color: modelData.kind === "COUNTER" ? theme.gain : (modelData.kind === "ACTION" ? theme.accent : theme.info); font.family: theme.fontMono; font.pixelSize: 9; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                        Text { width: parent.width - 170; text: modelData.label; elide: Text.ElideRight; color: theme.textPrimary; font.family: theme.fontSans; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text { width: 84; horizontalAlignment: Text.AlignRight; text: modelData.hint; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                    }
                    MouseArea { id: rowMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: paletteRoot.executeItem(modelData) }
                }
            }
        }
    }
}
