import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
    id: root
    moduleName: "io.github.aomine-c2c.vfex-direct"
    manageIpc: false

    property var anchorItem: null
    property var hostWidget: null
    property var summaryData: ({ text: "VFEX --", total_value: 0, total_pnl: 0, total_pnl_pct: 0, items: [], watchlist: [] })
    property string manualMode: "price"
    property string alertDirection: "above"
    property string statusMessage: ""
    property bool statusError: false
    property string lastManualError: ""
    property bool pendingClearInputs: false
    property var dcaPlanData: null
    property string chartSymbol: ""
    property string chartMode: "candles"
    property int hoveredCandleIdx: -1
    readonly property var knownSymbols: ["ASUN", "AXIA", "BIND", "CALD", "ECO", "EDGR", "FCA", "INFR", "INSC", "NTFD", "PHL", "SCIL", "SIM", "WTN"]

    function activeCandles() {
        if (!root.chartSymbol) return []
        var lists = [root.summaryData.watchlist || [], root.summaryData.items || []]
        for (var li = 0; li < lists.length; li++) {
            var arr = lists[li]
            for (var i = 0; i < arr.length; i++) {
                if (arr[i].symbol === root.chartSymbol)
                    return arr[i].candles || []
            }
        }
        return []
    }

    onSummaryDataChanged: candleCanvas.requestPaint()
    onChartSymbolChanged: candleCanvas.requestPaint()
    onChartModeChanged: candleCanvas.requestPaint()
    onHoveredCandleIdxChanged: candleCanvas.requestPaint()

    Process {
        id: dcaProc
        stdout: SplitParser {
            onRead: function(line) {
                try {
                    root.dcaPlanData = JSON.parse(line)
                } catch (e) {
                }
            }
        }
        onExited: function(exitCode) {
            if (exitCode !== 0) {
                root.statusError = true
                root.statusMessage = "DCA failed (code " + exitCode + ")"
            }
        }
    }

    Process {
        id: manualProc
        stderr: SplitParser {
            onRead: function(line) {
                var t = line.trim()
                if (t) root.lastManualError = t
            }
        }
        onExited: function(exitCode) {
            if (exitCode === 0) {
                if (root.pendingClearInputs) {
                    symbolInput.text = ""
                    sharesInput.text = ""
                    priceInput.text = ""
                    dateInput.text = ""
                }
                root.pendingClearInputs = false
                root.statusError = false
                root.statusMessage = "Saved"
                if (root.hostWidget && typeof root.hostWidget.refresh === "function")
                    root.hostWidget.refresh()
            } else {
                root.pendingClearInputs = false
                root.statusError = true
                root.statusMessage = root.lastManualError ? root.lastManualError : ("Failed (code " + exitCode + ")")
            }
        }
    }

    function open() {
        root.controller.show()
    }

    function close() {
        root.controller.hide()
    }

    function switchPanel(direction) {
        if (root.bar && typeof root.bar.switchPanelFrom === "function")
            return root.bar.switchPanelFrom(root.hostWidget || root, direction)
        return false
    }

    function submitManualEntry() {
        if (manualProc.running || dcaProc.running) return
        var sym = symbolInput.text.trim().toUpperCase()
        var prc = priceInput.text.replace(/^\s*\$?/, "").replace(/,/g, "").trim()
        var sh = sharesInput.text.replace(/,/g, "").trim()
        var dt = dateInput.text.trim()
        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
        if (root.manualMode === "dca") {
            if (!prc) {
                root.statusError = true
                root.statusMessage = "Enter budget $"
                return
            }
            root.statusMessage = ""
            root.dcaPlanData = null
            dcaProc.command = ["python3", script, "dca", prc, "--json"]
            dcaProc.running = true
            return
        }
        if (!sym) {
            root.statusError = true
            root.statusMessage = "Enter symbol"
            return
        }
        if (root.manualMode === "watch") {
            manualProc.command = ["python3", script, "watch", "add", sym]
        } else if (root.manualMode === "target") {
            if (!prc) {
                root.statusError = true
                root.statusMessage = "Enter target %"
                return
            }
            manualProc.command = ["python3", script, "target", "set", sym, prc]
        } else if (root.manualMode === "alert") {
            if (!prc) {
                root.statusError = true
                root.statusMessage = "Enter target price"
                return
            }
            manualProc.command = ["python3", script, "alert", "add", sym, root.alertDirection, prc]
        } else if (root.manualMode === "dividend") {
            if (!prc) {
                root.statusError = true
                root.statusMessage = "Enter dividend amount"
                return
            }
            var divCmd = ["python3", script, "dividend", "add", sym, prc]
            if (dt) divCmd.push("--date", dt)
            manualProc.command = divCmd
        } else if (root.manualMode === "price") {
            if (!prc) {
                root.statusError = true
                root.statusMessage = "Enter price"
                return
            }
            manualProc.command = ["python3", script, "price", sym, prc]
        } else {
            if (!sh || !prc) {
                root.statusError = true
                root.statusMessage = "Enter shares and price"
                return
            }
            var tradeCmd = ["python3", script, root.manualMode, sym, sh, prc]
            if (dt) tradeCmd.push("--date", dt)
            manualProc.command = tradeCmd
        }
        root.statusMessage = ""
        root.lastManualError = ""
        root.pendingClearInputs = true
        manualProc.running = true
    }

    KeyboardPanel {
        id: panel
        anchorItem: root.anchorItem
        owner: root.hostWidget || root
        bar: root.bar
        open: root.opened
        focusTarget: panel.loadedContent
        contentWidth: panel.fittedContentWidth(Style.space(390))
        contentHeight: panel.fittedContentHeight(panel.loadedContentHeight)

        content: PanelKeyCatcher {
            id: keyCatcher
            implicitHeight: contentColumn.implicitHeight
            anchors.fill: parent
            onCloseRequested: root.close()
            onTabRequested: function(direction) {
                root.switchPanel(direction)
            }

            Column {
                id: contentColumn
                width: parent.width
                spacing: Style.space(10)

                Row {
                    width: parent.width
                    spacing: Style.space(8)

                    Text {
                        text: "VFEX Direct (USD)"
                        color: "#cdd6f4"
                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                        font.pixelSize: Style.font.subtitle
                        font.bold: true
                        width: parent.width - refreshBtn.width - Style.space(8)
                    }

                    Text {
                        id: refreshBtn
                        readonly property bool busy: root.hostWidget && root.hostWidget.fetching === true
                        text: busy ? "↻ Syncing..." : "↻ Refresh"
                        color: busy ? "#a6adc8" : "#89b4fa"
                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                        font.pixelSize: Style.font.body
                        font.bold: true
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            enabled: !refreshBtn.busy
                            onClicked: {
                                if (root.hostWidget && typeof root.hostWidget.refresh === "function")
                                    root.hostWidget.refresh(true)
                            }
                        }
                    }
                }

                Text {
                    width: parent.width
                    text: {
                        var st = root.summaryData.market_status || "--"
                        var upd = root.summaryData.last_updated || ""
                        return "● " + st + (upd ? (" • Updated " + upd + " CAT") : "")
                    }
                    color: (root.summaryData.market_status === "Open") ? "#a6e3a1" : "#a6adc8"
                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                    font.pixelSize: Style.font.small || Style.font.body
                }

                Text {
                    width: parent.width
                    visible: (root.summaryData.fetch_error || "").length > 0
                    text: root.summaryData.fetch_error || ""
                    color: "#f38ba8"
                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                    font.pixelSize: Style.font.small || Style.font.body
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    id: portfolioCard
                    width: parent.width
                    visible: (root.summaryData.items || []).length > 0
                    height: portfolioCol.implicitHeight + Style.space(16)
                    radius: 8
                    color: "#181825"
                    border.color: "#313244"
                    border.width: 1

                    Column {
                        id: portfolioCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                        spacing: Style.space(6)

                        Row {
                            width: parent.width
                            spacing: Style.space(8)

                            Column {
                                width: parent.width - pnlBadge.width - Style.space(8)
                                spacing: 1
                                Text {
                                    text: "PORTFOLIO VALUE"
                                    color: "#a6adc8"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                    font.bold: true
                                }
                                Text {
                                    text: "$" + Number(root.summaryData.total_value || 0).toFixed(2)
                                    color: "#cdd6f4"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: (Style.font.subtitle || 16) + 2
                                    font.bold: true
                                }
                            }

                            Rectangle {
                                id: pnlBadge
                                anchors.verticalCenter: parent.verticalCenter
                                width: pnlBadgeText.implicitWidth + Style.space(12)
                                height: pnlBadgeText.implicitHeight + Style.space(6)
                                radius: 6
                                color: Number(root.summaryData.total_pnl || 0) >= 0 ? "#243b2c" : "#3d2229"
                                border.color: Number(root.summaryData.total_pnl || 0) >= 0 ? "#a6e3a1" : "#f38ba8"
                                border.width: 1

                                Text {
                                    id: pnlBadgeText
                                    anchors.centerIn: parent
                                    text: {
                                        var pnl = Number(root.summaryData.total_pnl || 0)
                                        var pct = Number(root.summaryData.total_pnl_pct || 0).toFixed(1)
                                        var sign = pnl >= 0 ? "+" : ""
                                        return sign + "$" + pnl.toFixed(2) + " (" + sign + pct + "%)"
                                    }
                                    color: Number(root.summaryData.total_pnl || 0) >= 0 ? "#a6e3a1" : "#f38ba8"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small || Style.font.body
                                    font.bold: true
                                }
                            }
                        }

                        Text {
                            width: parent.width
                            visible: Number(root.summaryData.realized_pnl || 0) !== 0 || Number(root.summaryData.total_dividends || 0) > 0
                            text: {
                                var parts = []
                                var r = Number(root.summaryData.realized_pnl || 0)
                                if (r !== 0) parts.push("Realized: " + (r >= 0 ? "+" : "") + "$" + r.toFixed(2))
                                var d = Number(root.summaryData.total_dividends || 0)
                                if (d > 0) parts.push("Div: +$" + d.toFixed(2))
                                var tr = Number(root.summaryData.total_return || 0)
                                parts.push("Total Return: " + (tr >= 0 ? "+" : "") + "$" + tr.toFixed(2))
                                return parts.join(" • ")
                            }
                            color: Number(root.summaryData.total_return || 0) >= 0 ? "#a6e3a1" : "#f38ba8"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.small || Style.font.body
                        }

                        Rectangle {
                            width: parent.width
                            height: 1
                            color: "#313244"
                        }

                        Repeater {
                            model: root.summaryData.items || []
                            delegate: Column {
                                id: holdingItemCol
                                width: portfolioCol.width
                                spacing: Style.space(2)
                                property bool lotsExpanded: false
                                Rectangle {
                                    width: parent.width
                                    height: holdingRow.implicitHeight + Style.space(6)
                                    radius: 5
                                    color: holdingHover.containsMouse ? "#242436" : "transparent"

                                    MouseArea {
                                        id: holdingHover
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            symbolInput.text = modelData.symbol
                                            root.chartSymbol = modelData.symbol
                                            root.hoveredCandleIdx = -1
                                        }
                                    }

                                    Row {
                                        id: holdingRow
                                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 4; rightMargin: 4 }
                                        spacing: Style.space(6)
                                        Text {
                                            width: portfolioCol.width * 0.22 - 4
                                            text: modelData.symbol
                                            color: "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.body
                                            font.bold: true
                                        }
                                        Text {
                                            width: portfolioCol.width * 0.23
                                            text: Number(modelData.shares) + " sh"
                                            color: "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.body
                                        }
                                        Text {
                                            width: portfolioCol.width * 0.25
                                            text: "$" + Number(modelData.price).toFixed(4)
                                            color: "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.body
                                        }
                                        Text {
                                            width: portfolioCol.width * 0.26 - 4
                                            horizontalAlignment: Text.AlignRight
                                            text: (modelData.pnl >= 0 ? "+" : "") + "$" + Number(modelData.pnl).toFixed(2)
                                            color: modelData.pnl >= 0 ? "#a6e3a1" : "#f38ba8"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.body
                                            font.bold: true
                                        }
                                    }
                                }
                                Row {
                                    width: portfolioCol.width
                                    visible: modelData.target_pct !== null && modelData.target_pct !== undefined
                                    spacing: Style.space(8)

                                    Rectangle {
                                        id: allocTrack
                                        width: parent.width - allocPctLabel.width - Style.space(8)
                                        height: 6
                                        radius: 3
                                        color: "#313244"
                                        anchors.verticalCenter: parent.verticalCenter

                                        Rectangle {
                                            width: Math.max(0, Math.min(1, Number(modelData.alloc_pct || 0) / 100.0)) * parent.width
                                            height: parent.height
                                            radius: 3
                                            color: Number(modelData.alloc_pct || 0) >= Number(modelData.target_pct || 0) ? "#a6e3a1" : "#89b4fa"
                                        }

                                        Rectangle {
                                            x: Math.max(0, Math.min(parent.width - 2, (Number(modelData.target_pct || 0) / 100.0) * parent.width - 1))
                                            y: -2
                                            width: 2
                                            height: parent.height + 4
                                            radius: 1
                                            color: "#f9e2af"
                                        }
                                    }

                                    Text {
                                        id: allocPctLabel
                                        text: Number(modelData.alloc_pct || 0).toFixed(0) + "% / " + Number(modelData.target_pct || 0).toFixed(0) + "%"
                                        color: "#a6adc8"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                    }
                                }
                                Text {
                                    width: portfolioCol.width
                                    visible: (modelData.lots || []).length > 0
                                    text: (holdingItemCol.lotsExpanded ? "▾ " : "▸ ") + (modelData.lots || []).length + ((modelData.lots || []).length === 1 ? " lot" : " lots") + " • avg $" + Number(modelData.avg_cost || 0).toFixed(4)
                                    color: "#89b4fa"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: holdingItemCol.lotsExpanded = !holdingItemCol.lotsExpanded
                                    }
                                }
                                Column {
                                    width: portfolioCol.width
                                    visible: holdingItemCol.lotsExpanded
                                    spacing: 1
                                    Repeater {
                                        model: modelData.lots || []
                                        delegate: Text {
                                            width: portfolioCol.width
                                            text: "  " + modelData.date + ": " + Number(modelData.shares) + " sh @ $" + Number(modelData.price).toFixed(4)
                                            color: "#a6adc8"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small || Style.font.body
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    width: parent.width
                    visible: (root.summaryData.triggered_alerts || []).length > 0
                    height: triggeredAlertsCol.implicitHeight + Style.space(16)
                    radius: 8
                    color: "#2b261d"
                    border.color: "#f9e2af"
                    border.width: 1

                    Column {
                        id: triggeredAlertsCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                        spacing: Style.space(4)

                        Row {
                            width: parent.width
                            Text {
                                width: parent.width - clearAlertsBtn.width
                                text: "⚠ Triggered Alerts"
                                color: "#f9e2af"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                font.bold: true
                            }
                            Text {
                                id: clearAlertsBtn
                                text: "Clear"
                                color: "#89b4fa"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.small || Style.font.body
                                font.bold: true
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    enabled: !manualProc.running
                                    onClicked: {
                                        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                        manualProc.command = ["python3", script, "alert", "clear"]
                                        manualProc.running = true
                                    }
                                }
                            }
                        }

                        Repeater {
                            model: root.summaryData.triggered_alerts || []
                            delegate: Row {
                                width: triggeredAlertsCol.width
                                Text {
                                    width: triggeredAlertsCol.width * 0.90
                                    text: (modelData.direction === "above" ? "▲ " : "▼ ") + modelData.text
                                    color: "#f9e2af"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small || Style.font.body
                                    wrapMode: Text.WordWrap
                                }
                                Text {
                                    width: triggeredAlertsCol.width * 0.10
                                    horizontalAlignment: Text.AlignRight
                                    text: "×"
                                    color: "#f38ba8"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.body
                                    font.bold: true
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        enabled: !manualProc.running
                                        onClicked: {
                                            var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                            manualProc.command = ["python3", script, "alert", "remove", String(modelData.index)]
                                            manualProc.running = true
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    width: parent.width
                    visible: (root.summaryData.active_alerts || []).length > 0
                    height: activeAlertsCol.implicitHeight + Style.space(16)
                    radius: 8
                    color: "#181825"
                    border.color: "#313244"
                    border.width: 1

                    Column {
                        id: activeAlertsCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                        spacing: Style.space(4)

                        Text {
                            text: "Active Alerts"
                            color: "#cdd6f4"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                            font.bold: true
                        }

                        Repeater {
                            model: root.summaryData.active_alerts || []
                            delegate: Row {
                                width: activeAlertsCol.width
                                Text {
                                    width: activeAlertsCol.width * 0.90
                                    text: (modelData.direction === "above" ? "▲ " : "▼ ") + modelData.text
                                    color: "#a6adc8"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small || Style.font.body
                                    wrapMode: Text.WordWrap
                                }
                                Text {
                                    width: activeAlertsCol.width * 0.10
                                    horizontalAlignment: Text.AlignRight
                                    text: "×"
                                    color: "#f38ba8"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.body
                                    font.bold: true
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        enabled: !manualProc.running
                                        onClicked: {
                                            var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                            manualProc.command = ["python3", script, "alert", "remove", String(modelData.index)]
                                            manualProc.running = true
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: watchlistCard
                    width: parent.width
                    visible: (root.summaryData.watchlist || []).length > 0
                    height: watchlistCol.implicitHeight + Style.space(16)
                    radius: 8
                    color: "#181825"
                    border.color: "#313244"
                    border.width: 1

                    Column {
                        id: watchlistCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                        spacing: Style.space(6)

                        Text {
                            width: parent.width
                            text: "Watchlist"
                            color: "#cdd6f4"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                            font.bold: true
                        }

                        Repeater {
                            model: root.summaryData.watchlist || []
                            delegate: Rectangle {
                                width: watchlistCol.width
                                height: watchRow.implicitHeight + Style.space(6)
                                radius: 5
                                color: watchHover.containsMouse ? "#242436" : "transparent"

                                MouseArea {
                                    id: watchHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        symbolInput.text = modelData.symbol
                                        root.chartSymbol = modelData.symbol
                                        root.hoveredCandleIdx = -1
                                    }
                                }

                                Row {
                                    id: watchRow
                                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 4; rightMargin: 4 }
                                    Text {
                                        width: (watchlistCol.width - 8) * 0.17
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: modelData.symbol
                                        color: "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.body
                                        font.bold: true
                                    }
                                    Canvas {
                                        id: sparkline
                                        width: (watchlistCol.width - 8) * 0.18
                                        height: Style.space(18)
                                        anchors.verticalCenter: parent.verticalCenter
                                        property var pts: modelData.history || []
                                        onPtsChanged: requestPaint()
                                        onPaint: {
                                            var ctx = getContext("2d")
                                            ctx.clearRect(0, 0, width, height)
                                            var pts = sparkline.pts
                                            if (!pts || pts.length === 0) return
                                            if (pts.length === 1) {
                                                ctx.save()
                                                ctx.strokeStyle = "#45475a"
                                                ctx.lineWidth = 1
                                                ctx.setLineDash([2, 2])
                                                ctx.beginPath()
                                                ctx.moveTo(2, height / 2)
                                                ctx.lineTo(width - 4, height / 2)
                                                ctx.stroke()
                                                ctx.fillStyle = "#89b4fa"
                                                ctx.beginPath()
                                                ctx.arc(width - 4, height / 2, 2, 0, Math.PI * 2)
                                                ctx.fill()
                                                ctx.restore()
                                                return
                                            }
                                            var minV = Math.min.apply(null, pts)
                                            var maxV = Math.max.apply(null, pts)
                                            var span = maxV - minV || 1
                                            var up = pts[pts.length - 1] >= pts[0]
                                            var strokeCol = up ? "#a6e3a1" : "#f38ba8"
                                            var coords = []
                                            for (var i = 0; i < pts.length; i++) {
                                                var x = (i / (pts.length - 1)) * (width - 6) + 2
                                                var y = height - 3 - ((pts[i] - minV) / span) * (height - 6)
                                                coords.push({ x: x, y: y })
                                            }
                                            var grad = ctx.createLinearGradient(0, 0, 0, height)
                                            grad.addColorStop(0, up ? "rgba(166, 227, 161, 0.28)" : "rgba(243, 139, 168, 0.28)")
                                            grad.addColorStop(1, "rgba(0, 0, 0, 0.0)")
                                            ctx.fillStyle = grad
                                            ctx.beginPath()
                                            ctx.moveTo(coords[0].x, height)
                                            for (var j = 0; j < coords.length; j++) ctx.lineTo(coords[j].x, coords[j].y)
                                            ctx.lineTo(coords[coords.length - 1].x, height)
                                            ctx.closePath()
                                            ctx.fill()

                                            ctx.strokeStyle = strokeCol
                                            ctx.lineWidth = 1.5
                                            ctx.beginPath()
                                            for (var k = 0; k < coords.length; k++) {
                                                if (k === 0) ctx.moveTo(coords[k].x, coords[k].y)
                                                else ctx.lineTo(coords[k].x, coords[k].y)
                                            }
                                            ctx.stroke()

                                            var last = coords[coords.length - 1]
                                            ctx.fillStyle = strokeCol
                                            ctx.beginPath()
                                            ctx.arc(last.x, last.y, 2.2, 0, Math.PI * 2)
                                            ctx.fill()
                                        }
                                    }
                                    Item {
                                        width: (watchlistCol.width - 8) * 0.21
                                        height: Style.space(20)
                                        anchors.verticalCenter: parent.verticalCenter
                                        Rectangle {
                                            visible: modelData.change_pct !== null && modelData.change_pct !== undefined
                                            anchors.centerIn: parent
                                            width: chgText.implicitWidth + 8
                                            height: chgText.implicitHeight + 4
                                            radius: 4
                                            color: Number(modelData.change_pct || 0) >= 0 ? "#243b2c" : "#3d2229"
                                            Text {
                                                id: chgText
                                                anchors.centerIn: parent
                                                text: {
                                                    if (modelData.change_pct === null || modelData.change_pct === undefined) return ""
                                                    var c = Number(modelData.change_pct)
                                                    return (c >= 0 ? "▲" : "▼") + (c >= 0 ? "+" : "") + c.toFixed(1) + "%"
                                                }
                                                color: Number(modelData.change_pct || 0) >= 0 ? "#a6e3a1" : "#f38ba8"
                                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                                font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                                font.bold: true
                                            }
                                        }
                                    }
                                    Item {
                                        width: (watchlistCol.width - 8) * 0.12
                                        height: Style.space(20)
                                        anchors.verticalCenter: parent.verticalCenter
                                        Rectangle {
                                            visible: modelData.buy === true
                                            anchors.centerIn: parent
                                            width: buyText.implicitWidth + 8
                                            height: buyText.implicitHeight + 4
                                            radius: 4
                                            color: "#243b2c"
                                            border.color: "#a6e3a1"
                                            border.width: 1
                                            Text {
                                                id: buyText
                                                anchors.centerIn: parent
                                                text: "BUY"
                                                color: "#a6e3a1"
                                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                                font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                                font.bold: true
                                            }
                                        }
                                    }
                                    Text {
                                        width: (watchlistCol.width - 8) * 0.24
                                        anchors.verticalCenter: parent.verticalCenter
                                        horizontalAlignment: Text.AlignRight
                                        text: modelData.price !== null && modelData.price !== undefined ? ("$" + Number(modelData.price).toFixed(4)) : "N/A"
                                        color: "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.body
                                    }
                                    Text {
                                        width: (watchlistCol.width - 8) * 0.08
                                        anchors.verticalCenter: parent.verticalCenter
                                        horizontalAlignment: Text.AlignRight
                                        text: "×"
                                        color: "#f38ba8"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.body
                                        font.bold: true
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            enabled: !manualProc.running
                                            onClicked: {
                                                var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                manualProc.command = ["python3", script, "watch", "remove", modelData.symbol]
                                                manualProc.running = true
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: chartCard
                    width: parent.width
                    visible: root.chartSymbol.length > 0
                    height: chartCol.implicitHeight + Style.space(16)
                    radius: 8
                    color: "#181825"
                    border.color: "#313244"
                    border.width: 1

                    Column {
                        id: chartCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                        spacing: Style.space(6)

                        Row {
                            width: parent.width
                            spacing: Style.space(6)

                            Text {
                                width: parent.width - chartToggleRow.width - chartCloseBtn.width - Style.space(12)
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.chartSymbol + " • 30D"
                                color: "#cdd6f4"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                font.bold: true
                            }

                            Row {
                                id: chartToggleRow
                                spacing: 4
                                anchors.verticalCenter: parent.verticalCenter
                                Repeater {
                                    model: [
                                        { key: "candles", label: "Candles" },
                                        { key: "line", label: "Line" }
                                    ]
                                    delegate: Rectangle {
                                        width: cModeLbl.implicitWidth + 10
                                        height: cModeLbl.implicitHeight + 4
                                        radius: 4
                                        color: root.chartMode === modelData.key ? "#89b4fa" : "#313244"
                                        Text {
                                            id: cModeLbl
                                            anchors.centerIn: parent
                                            text: modelData.label
                                            color: root.chartMode === modelData.key ? "#1e1e2e" : "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                            font.bold: root.chartMode === modelData.key
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: root.chartMode = modelData.key
                                        }
                                    }
                                }
                            }

                            Text {
                                id: chartCloseBtn
                                anchors.verticalCenter: parent.verticalCenter
                                text: "×"
                                color: "#f38ba8"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                font.bold: true
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.chartSymbol = ""
                                }
                            }
                        }

                        Text {
                            width: parent.width
                            property var curCandle: {
                                var cs = root.activeCandles()
                                if (!cs || cs.length === 0) return null
                                var idx = (root.hoveredCandleIdx >= 0 && root.hoveredCandleIdx < cs.length) ? root.hoveredCandleIdx : (cs.length - 1)
                                return cs[idx]
                            }
                            text: curCandle
                                ? (curCandle.date + "  O:$" + Number(curCandle.open).toFixed(4) + " H:$" + Number(curCandle.high).toFixed(4) + " L:$" + Number(curCandle.low).toFixed(4) + " C:$" + Number(curCandle.close).toFixed(4))
                                : "No OHLC history yet"
                            color: curCandle ? (Number(curCandle.close) >= Number(curCandle.open) ? "#a6e3a1" : "#f38ba8") : "#a6adc8"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                            elide: Text.ElideRight
                        }

                        Canvas {
                            id: candleCanvas
                            width: parent.width
                            height: Style.space(110)
                            onPaint: {
                                var ctx = getContext("2d")
                                ctx.clearRect(0, 0, width, height)
                                var cs = root.activeCandles()
                                if (!cs || cs.length === 0) return

                                var padLeft = 46
                                var padRight = 6
                                var padTop = 6
                                var padBottom = 6
                                var plotW = Math.max(10, width - padLeft - padRight)
                                var plotH = Math.max(10, height - padTop - padBottom)

                                var minV = Number(cs[0].low)
                                var maxV = Number(cs[0].high)
                                for (var i = 0; i < cs.length; i++) {
                                    if (Number(cs[i].low) < minV) minV = Number(cs[i].low)
                                    if (Number(cs[i].high) > maxV) maxV = Number(cs[i].high)
                                }
                                if (maxV === minV) {
                                    var pad = Math.max(0.001, maxV * 0.02)
                                    maxV += pad
                                    minV = Math.max(0, minV - pad)
                                }
                                var span = maxV - minV || 1

                                function yFor(v) {
                                    return padTop + plotH - ((v - minV) / span) * plotH
                                }

                                // Dashed gridlines + price axis labels
                                ctx.font = "10px sans-serif"
                                ctx.textBaseline = "middle"
                                var levels = [maxV, (maxV + minV) / 2, minV]
                                for (var g = 0; g < levels.length; g++) {
                                    var gy = yFor(levels[g])
                                    ctx.save()
                                    ctx.strokeStyle = "#313244"
                                    ctx.lineWidth = 1
                                    ctx.setLineDash([2, 3])
                                    ctx.beginPath()
                                    ctx.moveTo(padLeft, gy)
                                    ctx.lineTo(width - padRight, gy)
                                    ctx.stroke()
                                    ctx.restore()
                                    ctx.fillStyle = "#6c7086"
                                    ctx.fillText("$" + levels[g].toFixed(3), 0, gy)
                                }

                                var n = cs.length
                                var slotW = plotW / n

                                if (root.chartMode === "line") {
                                    var up = Number(cs[n - 1].close) >= Number(cs[0].open)
                                    var strokeCol = up ? "#a6e3a1" : "#f38ba8"
                                    var pts = []
                                    for (var li = 0; li < n; li++) {
                                        var lx = n === 1 ? (padLeft + plotW / 2) : (padLeft + (li / (n - 1)) * plotW)
                                        var ly = yFor(Number(cs[li].close))
                                        pts.push({ x: lx, y: ly })
                                    }
                                    var grad = ctx.createLinearGradient(0, padTop, 0, padTop + plotH)
                                    grad.addColorStop(0, up ? "rgba(166, 227, 161, 0.25)" : "rgba(243, 139, 168, 0.25)")
                                    grad.addColorStop(1, "rgba(0, 0, 0, 0.0)")
                                    ctx.fillStyle = grad
                                    ctx.beginPath()
                                    ctx.moveTo(pts[0].x, padTop + plotH)
                                    for (var j = 0; j < pts.length; j++) ctx.lineTo(pts[j].x, pts[j].y)
                                    ctx.lineTo(pts[pts.length - 1].x, padTop + plotH)
                                    ctx.closePath()
                                    ctx.fill()

                                    ctx.strokeStyle = strokeCol
                                    ctx.lineWidth = 1.8
                                    ctx.beginPath()
                                    for (var k = 0; k < pts.length; k++) {
                                        if (k === 0) ctx.moveTo(pts[k].x, pts[k].y)
                                        else ctx.lineTo(pts[k].x, pts[k].y)
                                    }
                                    ctx.stroke()

                                    var hi = (root.hoveredCandleIdx >= 0 && root.hoveredCandleIdx < n) ? root.hoveredCandleIdx : (n - 1)
                                    ctx.fillStyle = strokeCol
                                    ctx.beginPath()
                                    ctx.arc(pts[hi].x, pts[hi].y, 3, 0, Math.PI * 2)
                                    ctx.fill()
                                    return
                                }

                                // Candlestick mode
                                var bodyW = Math.max(4, Math.min(14, slotW * 0.62))
                                for (var c = 0; c < n; c++) {
                                    var cd = cs[c]
                                    var cx = padLeft + slotW * (c + 0.5)
                                    if (c === root.hoveredCandleIdx) {
                                        ctx.fillStyle = "#242436"
                                        ctx.fillRect(padLeft + slotW * c, padTop, slotW, plotH)
                                    }
                                    var o = Number(cd.open)
                                    var h = Number(cd.high)
                                    var l = Number(cd.low)
                                    var cl = Number(cd.close)
                                    var col = cl >= o ? "#a6e3a1" : "#f38ba8"

                                    // Wick
                                    ctx.strokeStyle = col
                                    ctx.lineWidth = 1.5
                                    ctx.beginPath()
                                    ctx.moveTo(cx, yFor(h))
                                    ctx.lineTo(cx, yFor(l))
                                    ctx.stroke()

                                    // Body
                                    var yo = yFor(o)
                                    var yc = yFor(cl)
                                    var topY = Math.min(yo, yc)
                                    var bh = Math.max(2, Math.abs(yc - yo))
                                    ctx.fillStyle = col
                                    ctx.fillRect(cx - bodyW / 2, topY, bodyW, bh)
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                onPositionChanged: function(mouse) {
                                    var cs = root.activeCandles()
                                    if (!cs || cs.length === 0) {
                                        root.hoveredCandleIdx = -1
                                        return
                                    }
                                    var padLeft = 46
                                    var padRight = 6
                                    var plotW = Math.max(10, width - padLeft - padRight)
                                    var rel = (mouse.x - padLeft) / plotW
                                    if (rel < 0 || rel > 1) {
                                        root.hoveredCandleIdx = -1
                                        return
                                    }
                                    root.hoveredCandleIdx = Math.max(0, Math.min(cs.length - 1, Math.floor(rel * cs.length)))
                                }
                                onExited: root.hoveredCandleIdx = -1
                            }
                        }
                    }
                }

                Rectangle {
                    id: manualCard
                    width: parent.width
                    height: manualCol.implicitHeight + Style.space(16)
                    radius: 8
                    color: "#181825"
                    border.color: "#313244"
                    border.width: 1

                    Column {
                        id: manualCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                        spacing: Style.space(6)

                    Flow {
                        width: parent.width
                        spacing: Style.space(6)

                        Text {
                            text: "Manual Entry"
                            color: "#cdd6f4"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                            font.bold: true
                        }

                        Flow {
                            width: parent.width
                            spacing: Style.space(4)
                            Repeater {
                                model: [
                                    { key: "price", label: "Price" },
                                    { key: "buy", label: "Buy" },
                                    { key: "sell", label: "Sell" },
                                    { key: "watch", label: "+Watch" },
                                    { key: "alert", label: "Alert" },
                                    { key: "dividend", label: "Div" },
                                    { key: "target", label: "Target" },
                                    { key: "dca", label: "DCA" }
                                ]
                                delegate: Rectangle {
                                    width: modeLabel.implicitWidth + Style.space(10)
                                    height: modeLabel.implicitHeight + Style.space(4)
                                    radius: 4
                                    color: root.manualMode === modelData.key ? "#89b4fa" : "#313244"
                                    Text {
                                        id: modeLabel
                                        anchors.centerIn: parent
                                        text: modelData.label
                                        color: root.manualMode === modelData.key ? "#1e1e2e" : "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small || Style.font.body
                                        font.bold: root.manualMode === modelData.key
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            root.manualMode = modelData.key
                                            root.statusMessage = ""
                                            if (modelData.key !== "dca") root.dcaPlanData = null
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: Style.space(6)

                        Rectangle {
                            visible: root.manualMode !== "dca"
                            width: root.manualMode === "watch" ? parent.width * 0.74 : ((root.manualMode === "price" || root.manualMode === "dividend" || root.manualMode === "target") ? parent.width * 0.36 : parent.width * 0.25)
                            height: Style.space(26)
                            radius: 4
                            color: "#313244"
                            border.color: symbolInput.activeFocus ? "#89b4fa" : "#45475a"
                            border.width: 1

                            TextInput {
                                id: symbolInput
                                anchors.fill: parent
                                anchors.margins: Style.space(5)
                                color: "#cdd6f4"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                verticalAlignment: TextInput.AlignVCenter
                                clip: true
                                KeyNavigation.tab: (root.manualMode === "buy" || root.manualMode === "sell") ? sharesInput : (root.manualMode !== "watch" ? priceInput : symbolInput)
                                onAccepted: root.submitManualEntry()
                                Text {
                                    anchors.fill: parent
                                    verticalAlignment: Text.AlignVCenter
                                    text: "Symbol"
                                    color: "#6c7086"
                                    font: symbolInput.font
                                    visible: !symbolInput.text && !symbolInput.activeFocus
                                }
                            }
                        }

                        Rectangle {
                            visible: root.manualMode === "buy" || root.manualMode === "sell"
                            width: parent.width * 0.22
                            height: Style.space(26)
                            radius: 4
                            color: "#313244"
                            border.color: sharesInput.activeFocus ? "#89b4fa" : "#45475a"
                            border.width: 1

                            TextInput {
                                id: sharesInput
                                anchors.fill: parent
                                anchors.margins: Style.space(5)
                                color: "#cdd6f4"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                verticalAlignment: TextInput.AlignVCenter
                                clip: true
                                KeyNavigation.tab: priceInput
                                KeyNavigation.backtab: symbolInput
                                onAccepted: root.submitManualEntry()
                                Text {
                                    anchors.fill: parent
                                    verticalAlignment: Text.AlignVCenter
                                    text: "Shares"
                                    color: "#6c7086"
                                    font: sharesInput.font
                                    visible: !sharesInput.text && !sharesInput.activeFocus
                                }
                            }
                        }

                        Rectangle {
                            visible: root.manualMode === "alert"
                            width: parent.width * 0.22
                            height: Style.space(26)
                            radius: 4
                            color: "#313244"
                            border.color: "#45475a"
                            border.width: 1

                            Text {
                                anchors.centerIn: parent
                                text: root.alertDirection === "above" ? "Above" : "Below"
                                color: "#89b4fa"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.small || Style.font.body
                                font.bold: true
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.alertDirection = root.alertDirection === "above" ? "below" : "above"
                            }
                        }

                        Rectangle {
                            visible: root.manualMode !== "watch"
                            width: root.manualMode === "dca" ? parent.width * 0.74 : ((root.manualMode === "price" || root.manualMode === "dividend" || root.manualMode === "target") ? parent.width * 0.38 : parent.width * 0.27)
                            height: Style.space(26)
                            radius: 4
                            color: "#313244"
                            border.color: priceInput.activeFocus ? "#89b4fa" : "#45475a"
                            border.width: 1

                            TextInput {
                                id: priceInput
                                anchors.fill: parent
                                anchors.margins: Style.space(5)
                                color: "#cdd6f4"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                verticalAlignment: TextInput.AlignVCenter
                                clip: true
                                KeyNavigation.tab: root.manualMode !== "dca" ? symbolInput : priceInput
                                KeyNavigation.backtab: (root.manualMode === "buy" || root.manualMode === "sell") ? sharesInput : (root.manualMode !== "dca" ? symbolInput : priceInput)
                                onAccepted: root.submitManualEntry()
                                Text {
                                    anchors.fill: parent
                                    verticalAlignment: Text.AlignVCenter
                                    text: root.manualMode === "dca" ? "Budget $" : (root.manualMode === "target" ? "Target %" : (root.manualMode === "dividend" ? "Amount $" : (root.manualMode === "alert" ? "Target $" : "Price $")))
                                    color: "#6c7086"
                                    font: priceInput.font
                                    visible: !priceInput.text && !priceInput.activeFocus
                                }
                            }
                        }

                        Rectangle {
                            width: parent.width * 0.20
                            height: Style.space(26)
                            radius: 4
                            color: (manualProc.running || dcaProc.running) ? "#45475a" : "#a6e3a1"

                            Text {
                                anchors.centerIn: parent
                                text: (manualProc.running || dcaProc.running) ? "..." : (root.manualMode === "dca" ? "Plan" : "Save")
                                color: "#1e1e2e"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                font.bold: true
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                enabled: !manualProc.running && !dcaProc.running
                                onClicked: root.submitManualEntry()
                            }
                        }
                    }

                    Rectangle {
                        visible: root.manualMode === "buy" || root.manualMode === "sell" || root.manualMode === "dividend"
                        width: parent.width
                        height: Style.space(26)
                        radius: 4
                        color: "#313244"
                        border.color: dateInput.activeFocus ? "#89b4fa" : "#45475a"
                        border.width: 1

                        TextInput {
                            id: dateInput
                            anchors.fill: parent
                            anchors.margins: Style.space(5)
                            color: "#cdd6f4"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                            verticalAlignment: TextInput.AlignVCenter
                            clip: true
                            KeyNavigation.backtab: priceInput
                            KeyNavigation.tab: symbolInput
                            onAccepted: root.submitManualEntry()
                            Text {
                                anchors.fill: parent
                                verticalAlignment: Text.AlignVCenter
                                text: "Date (YYYY-MM-DD or YYYY/MM/DD, optional)"
                                color: "#6c7086"
                                font: dateInput.font
                                visible: !dateInput.text && !dateInput.activeFocus
                            }
                        }
                    }

                    Text {
                        width: parent.width
                        visible: root.statusMessage.length > 0
                        text: root.statusMessage
                        color: root.statusError ? "#f38ba8" : "#a6e3a1"
                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                        font.pixelSize: Style.font.small || Style.font.body
                        wrapMode: Text.WordWrap
                    }

                    Flow {
                        width: parent.width
                        spacing: Style.space(4)
                        visible: symbolInput.activeFocus || symbolInput.text.length > 0

                        Repeater {
                            model: {
                                var q = symbolInput.text.trim().toUpperCase()
                                var out = []
                                for (var i = 0; i < root.knownSymbols.length; i++) {
                                    if (!q || root.knownSymbols[i].indexOf(q) === 0) {
                                        out.push(root.knownSymbols[i])
                                        if (out.length >= 6) break
                                    }
                                }
                                return out
                            }
                            delegate: Rectangle {
                                width: sugText.implicitWidth + Style.space(10)
                                height: sugText.implicitHeight + Style.space(4)
                                radius: 4
                                color: "#313244"
                                border.color: "#45475a"
                                border.width: 1
                                Text {
                                    id: sugText
                                    anchors.centerIn: parent
                                    text: modelData
                                    color: "#89b4fa"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small || Style.font.body
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: symbolInput.text = modelData
                                }
                            }
                        }
                    }

                    Rectangle {
                        visible: root.dcaPlanData !== null && (root.dcaPlanData.plan || []).length > 0
                        width: parent.width
                        height: dcaTableCol.implicitHeight + Style.space(12)
                        radius: 6
                        color: "#11111b"
                        border.color: "#313244"
                        border.width: 1

                        Column {
                            id: dcaTableCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(6) }
                            spacing: Style.space(4)

                            Row {
                                width: parent.width
                                Text {
                                    width: parent.width - dcaCloseBtn.width
                                    text: root.dcaPlanData ? ("DCA Plan • $" + Number(root.dcaPlanData.budget || 0).toFixed(2) + " (" + (root.dcaPlanData.mode || "equal") + ")") : ""
                                    color: "#89b4fa"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small || Style.font.body
                                    font.bold: true
                                }
                                Text {
                                    id: dcaCloseBtn
                                    text: "×"
                                    color: "#f38ba8"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.body
                                    font.bold: true
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.dcaPlanData = null
                                    }
                                }
                            }

                            Repeater {
                                model: root.dcaPlanData ? (root.dcaPlanData.plan || []) : []
                                delegate: Row {
                                    width: dcaTableCol.width
                                    Text {
                                        width: dcaTableCol.width * 0.20
                                        text: modelData.symbol
                                        color: "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small || Style.font.body
                                        font.bold: true
                                    }
                                    Text {
                                        width: dcaTableCol.width * 0.30
                                        text: Number(modelData.current_pct || 0).toFixed(0) + "%→" + Number(modelData.target_pct || 0).toFixed(0) + "%"
                                        color: "#a6adc8"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small || Style.font.body
                                    }
                                    Text {
                                        width: dcaTableCol.width * 0.25
                                        horizontalAlignment: Text.AlignRight
                                        text: "$" + Number(modelData.alloc_usd || 0).toFixed(2)
                                        color: "#a6e3a1"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small || Style.font.body
                                    }
                                    Text {
                                        width: dcaTableCol.width * 0.25
                                        horizontalAlignment: Text.AlignRight
                                        text: Number(modelData.shares || 0).toFixed(2) + " sh"
                                        color: "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small || Style.font.body
                                    }
                                }
                            }
                        }
                    }
                    }
                }
            }
        }
    }
}
