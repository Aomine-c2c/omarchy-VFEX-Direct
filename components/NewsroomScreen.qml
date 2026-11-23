import QtQuick
import Quickshell.Io

Column {
    id: newsRoot
    property var theme
    property var summaryData: ({})
    property string filterKey: "all" // all, breaking, holdings, official, dividends, macro
    property string searchQuery: ""
    property var newsroomData: null
    property var selectedItem: null
    signal openStock(string symbol)
    signal runCli(var args, string label)

    spacing: 8

    Component.onCompleted: loadNewsroom()

    Process {
        id: nrProc
        property string buf: ""
        stdout: SplitParser {
            splitMarker: ""
            onRead: function(chunk) { nrProc.buf += chunk }
        }
        onExited: function(exitCode) {
            if (exitCode === 0 && nrProc.buf.trim() !== "") {
                try {
                    newsRoot.newsroomData = JSON.parse(nrProc.buf)
                    if (!newsRoot.selectedItem && newsRoot.newsroomData.all_items && newsRoot.newsroomData.all_items.length > 0)
                        newsRoot.selectedItem = newsRoot.newsroomData.all_items[0]
                } catch (e) {}
            }
            nrProc.buf = ""
        }
    }

    function loadNewsroom() {
        if (nrProc.running) return
        nrProc.buf = ""
        var script = Qt.resolvedUrl("../newsroom.py").toString().replace("file://", "")
        nrProc.command = ["python3", script]
        nrProc.running = true
    }

    function activeItems() {
        var rows = (newsroomData && newsroomData.all_items) ? newsroomData.all_items : (summaryData.news || [])
        var q = String(searchQuery || "").trim().toLowerCase()
        var out = []
        for (var i = 0; i < rows.length; i++) {
            var r = rows[i]
            if (filterKey === "breaking" && !r.is_breaking) continue
            if (filterKey === "holdings" && !r.affects_portfolio && !r.tracked) continue
            if (filterKey === "official" && r.source_type !== "CONFIRMED_ANNOUNCEMENT" && !r.official) continue
            if (filterKey === "dividends" && r.category !== "Dividends") continue
            if (filterKey === "macro" && ["Monetary policy", "Fiscal policy", "Currency developments", "Inflation"].indexOf(r.category) < 0) continue
            var title = String(r.headline || r.title || "")
            if (q && title.toLowerCase().indexOf(q) < 0 && String(r.publisher || r.source || "").toLowerCase().indexOf(q) < 0) continue
            out.push(r)
        }
        return out
    }

    // Daily Briefing Banner
    Rectangle {
        width: parent.width; height: 34; radius: theme.rSharp
        color: theme.bgPanel; border.color: theme.borderDefault; border.width: 1
        Row {
            anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 10
            Text { text: "AI DAILY BRIEFING"; color: theme.accent; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
            Text {
                width: parent.width - 210; elide: Text.ElideRight
                text: (newsRoot.newsroomData && newsRoot.newsroomData.daily_briefing) ? newsRoot.newsroomData.daily_briefing.summary : "Loading deduplicated VFEX / ZSE / macro intelligence..."
                color: theme.textPrimary; font.family: theme.fontSans; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter
            }
            Rectangle {
                width: 78; height: 22; radius: theme.rSharp; anchors.verticalCenter: parent.verticalCenter
                color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                Text { anchors.centerIn: parent; text: nrProc.running ? "SYNC..." : "REFRESH"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { newsRoot.runCli(["news", "--fetch"], "Refreshed news"); newsRoot.loadNewsroom() } }
            }
        }
    }

    // Filter Tabs + Search
    Row {
        width: parent.width; spacing: 6
        Rectangle {
            width: 160; height: 26; radius: theme.rSharp; color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
            TextInput {
                anchors.fill: parent; anchors.margins: 6
                color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11
                onTextChanged: newsRoot.searchQuery = text
                Text { visible: !parent.text; text: "Search news..."; color: theme.textDim; font.family: theme.fontMono; font.pixelSize: 10 }
            }
        }
        Repeater {
            model: [
                { k: "all", t: "ALL" },
                { k: "breaking", t: "BREAKING" },
                { k: "holdings", t: "MY PORTFOLIO" },
                { k: "official", t: "OFFICIAL" },
                { k: "dividends", t: "DIVIDENDS" },
                { k: "macro", t: "ECON / MACRO" }
            ]
            delegate: Rectangle {
                width: tabT.implicitWidth + 14; height: 26; radius: theme.rSharp
                color: newsRoot.filterKey === modelData.k ? theme.bgActive : theme.bgPanel
                border.color: newsRoot.filterKey === modelData.k ? theme.accent : theme.borderSubtle; border.width: 1
                Text { id: tabT; anchors.centerIn: parent; text: modelData.t; color: newsRoot.filterKey === modelData.k ? theme.textPrimary : theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: newsRoot.filterKey = modelData.k }
            }
        }
    }

    // Split View: Left Feed | Right "Why This Matters To My Portfolio" Analysis
    Row {
        width: parent.width
        height: Math.max(240, parent.height - 76)
        spacing: 8

        // Left: Deduplicated News Feed
        ListView {
            width: parent.width * 0.54
            height: parent.height
            clip: true; spacing: 4
            model: newsRoot.activeItems()
            delegate: Rectangle {
                width: ListView.view.width; height: 56; radius: theme.rSharp
                property bool sel: newsRoot.selectedItem && newsRoot.selectedItem.id === modelData.id
                color: sel ? theme.bgActive : (nMa.containsMouse ? theme.bgHover : theme.bgPanel)
                border.color: sel ? theme.accent : theme.borderSubtle; border.width: 1
                Column {
                    anchors.fill: parent; anchors.margins: 7; spacing: 3
                    Row {
                        width: parent.width; spacing: 6
                        Text {
                            text: (modelData.source_type === "CONFIRMED_ANNOUNCEMENT" || modelData.official) ? "CONFIRMED" : "REPORT"
                            color: (modelData.source_type === "CONFIRMED_ANNOUNCEMENT" || modelData.official) ? theme.warn : theme.textMuted
                            font.family: theme.fontMono; font.pixelSize: 8; font.bold: true
                        }
                        Text { text: String(modelData.category || "").toUpperCase(); color: theme.info; font.family: theme.fontMono; font.pixelSize: 8; font.bold: true }
                        Text { visible: modelData.affects_portfolio === true; text: "● HELD"; color: theme.gain; font.family: theme.fontMono; font.pixelSize: 8; font.bold: true }
                        Text { text: String(modelData.age_label || ""); color: theme.textDim; font.family: theme.fontMono; font.pixelSize: 8 }
                    }
                    Text {
                        width: parent.width; elide: Text.ElideRight; maximumLineCount: 2; wrapMode: Text.WordWrap
                        text: String(modelData.headline || modelData.title || "")
                        color: theme.textPrimary; font.family: theme.fontSans; font.pixelSize: 10
                    }
                }
                MouseArea { id: nMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: newsRoot.selectedItem = modelData }
            }
        }

        // Right: "Why This Matters To My Portfolio" 7-Section Analysis Panel
        Rectangle {
            width: parent.width * 0.46 - 8
            height: parent.height
            radius: theme.rSharp; color: theme.bgPanel; border.color: theme.borderDefault; border.width: 1
            Flickable {
                anchors.fill: parent; anchors.margins: 10
                contentWidth: width; contentHeight: detCol.implicitHeight + 12; clip: true
                Column {
                    id: detCol
                    width: parent.width; spacing: 7
                    property var it: newsRoot.selectedItem
                    property var ai: (it && it.ai_analysis) ? it.ai_analysis : null

                    Text { text: "WHY THIS MATTERS TO MY PORTFOLIO"; color: theme.accent; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                    Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }

                    Text {
                        visible: detCol.it !== null
                        width: parent.width; wrapMode: Text.WordWrap
                        text: detCol.it ? String(detCol.it.headline || detCol.it.title || "") : ""
                        color: theme.textPrimary; font.family: theme.fontSans; font.pixelSize: 12; font.bold: true
                    }
                    Text {
                        visible: detCol.it !== null
                        text: detCol.it ? (String(detCol.it.publisher || detCol.it.source || "") + " · " + String(detCol.it.published_at || detCol.it.date || "")) : ""
                        color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9
                    }

                    Repeater {
                        model: detCol.ai ? [
                            { h: "WHAT HAPPENED", b: detCol.ai.what_happened },
                            { h: "WHY IT MATTERS", b: detCol.ai.why_it_matters },
                            { h: "PORTFOLIO IMPACT", b: detCol.ai.portfolio_impact },
                            { h: "MARKET IMPACT", b: detCol.ai.market_impact },
                            { h: "WHAT TO WATCH", b: detCol.ai.what_to_watch },
                            { h: "CONFIDENCE & LIMITATIONS", b: detCol.ai.confidence }
                        ] : []
                        delegate: Column {
                            width: parent.width; spacing: 2
                            Text { text: modelData.h; color: theme.info; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            Text { width: parent.width; wrapMode: Text.WordWrap; text: String(modelData.b || ""); color: theme.textSecondary; font.family: theme.fontSans; font.pixelSize: 10 }
                        }
                    }

                    Rectangle {
                        visible: detCol.it && String(detCol.it.url || "") !== ""
                        width: 170; height: 26; radius: theme.rSharp; color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                        Text { anchors.centerIn: parent; text: "OPEN ORIGINAL SOURCE ↗"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: Qt.openUrlExternally(detCol.it.url) }
                    }
                }
            }
        }
    }
}
