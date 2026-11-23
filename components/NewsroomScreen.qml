import QtQuick

Column {
    id: newsRoot
    property var theme
    property var summaryData: ({})
    property string filterKey: "all" // all, holdings, official, bullish, caution
    property string searchQuery: ""
    signal openStock(string symbol)
    signal runCli(var args, string label)

    spacing: 8

    function filteredNews() {
        var rows = (summaryData.news || []).slice()
        var q = String(searchQuery || "").trim().toLowerCase()
        var out = []
        for (var i = 0; i < rows.length; i++) {
            var r = rows[i]
            if (filterKey === "holdings" && !r.tracked) continue
            if (filterKey === "official" && !r.official) continue
            if (filterKey === "bullish" && r.sentiment !== "Bullish") continue
            if (filterKey === "caution" && r.sentiment !== "Caution") continue
            if (q && String(r.title || "").toLowerCase().indexOf(q) < 0 && String(r.source || "").toLowerCase().indexOf(q) < 0) continue
            out.push(r)
        }
        return out
    }

    // Filter Bar
    Row {
        width: parent.width; spacing: 6
        Rectangle {
            width: 180; height: 26; radius: theme.rSharp
            color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
            TextInput {
                anchors.fill: parent; anchors.margins: 6
                color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11
                onTextChanged: newsRoot.searchQuery = text
                Text { visible: !parent.text; text: "Search headlines..."; color: theme.textDim; font.family: theme.fontMono; font.pixelSize: 10 }
            }
        }
        Repeater {
            model: [
                { k: "all", t: "ALL" },
                { k: "holdings", t: "HOLDINGS" },
                { k: "official", t: "OFFICIAL" },
                { k: "bullish", t: "BULLISH" },
                { k: "caution", t: "CAUTION" }
            ]
            delegate: Rectangle {
                width: 68; height: 26; radius: theme.rSharp
                color: newsRoot.filterKey === modelData.k ? theme.bgActive : theme.bgPanel
                border.color: newsRoot.filterKey === modelData.k ? theme.accent : theme.borderSubtle; border.width: 1
                Text { anchors.centerIn: parent; text: modelData.t; color: newsRoot.filterKey === modelData.k ? theme.textPrimary : theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: newsRoot.filterKey = modelData.k }
            }
        }
        Item { width: Math.max(4, parent.width - 630); height: 1 }
        Rectangle {
            width: 82; height: 26; radius: theme.rSharp
            color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
            Text { anchors.centerIn: parent; text: "SYNC NEWS"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: newsRoot.runCli(["news", "--fetch"], "Refreshed VFEX/ZSE news") }
        }
    }

    // News Feed
    ListView {
        width: parent.width
        height: Math.max(220, parent.height - 38)
        clip: true
        spacing: 4
        model: newsRoot.filteredNews()
        delegate: Rectangle {
            width: ListView.view.width; height: 54; radius: theme.rSharp
            color: nMa.containsMouse ? theme.bgHover : theme.bgPanel
            border.color: theme.borderSubtle; border.width: 1
            Column {
                anchors.fill: parent; anchors.margins: 8; spacing: 4
                Row {
                    width: parent.width; spacing: 8
                    Text {
                        text: String(modelData.sentiment || "NEUTRAL").toUpperCase() + " (" + Number(modelData.impact_score || 0) + ")"
                        color: modelData.sentiment === "Bullish" ? theme.gain : (modelData.sentiment === "Caution" ? theme.loss : theme.textMuted)
                        font.family: theme.fontMono; font.pixelSize: 9; font.bold: true
                    }
                    Text {
                        visible: modelData.official === true
                        text: "OFFICIAL"; color: theme.warn; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true
                    }
                    Text {
                        text: String(modelData.source || "") + " · " + String(modelData.age_label || "")
                        color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9
                    }
                    Item { width: Math.max(4, parent.width - 360); height: 1 }
                    Text {
                        visible: (modelData.symbols || []).length > 0
                        text: (modelData.symbols || []).join(", ")
                        color: theme.info; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true
                    }
                }
                Text {
                    width: parent.width; elide: Text.ElideRight
                    text: String(modelData.title || "")
                    color: theme.textPrimary; font.family: theme.fontSans; font.pixelSize: 11
                }
            }
            MouseArea {
                id: nMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (modelData.symbols && modelData.symbols.length > 0) newsRoot.openStock(modelData.symbols[0])
                    else if (modelData.url) Qt.openUrlExternally(modelData.url)
                }
            }
        }
    }
}
