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
    property string manualMode: "buy"
    property string alertDirection: "above"
    property string statusMessage: ""
    property bool statusError: false
    property string lastManualError: ""
    property bool pendingClearInputs: false
    property bool calendarOpen: false
    property int calYear: (new Date()).getFullYear()
    property int calMonth: (new Date()).getMonth()
    property string symText: ""
    property string sharesText: ""
    property string priceText: ""
    property string dateText: ""
    property var candleCanvasRef: null
    property var sharesInputRef: null
    property var dcaPlanData: null
    property string chartSymbol: ""
    property string chartMode: "candles"
    property int hoveredCandleIdx: -1
    readonly property var knownSymbols: ["ASUN", "AXIA", "BIND", "CALD", "CMCL", "EAGLE", "EDGR", "FCA", "INFR", "INSC", "NTFD", "PHL", "SCIL", "SIM", "WTN", "ZIMW"]

    function moneyPrefix(cur) {
        return cur === "ZWG" ? "ZiG " : "$"
    }

    function fmtPrice(val, cur) {
        return moneyPrefix(cur) + Number(val || 0).toFixed(4)
    }

    function fmtShortMoney(val, cur) {
        return moneyPrefix(cur) + Number(val || 0).toFixed(2)
    }

    function fmtSignedMoney(val, cur) {
        var n = Number(val || 0)
        var sign = n >= 0 ? "+" : "-"
        return sign + moneyPrefix(cur) + Math.abs(n).toFixed(2)
    }

    function fmtVol(v) {
        var n = Number(v || 0)
        if (n >= 1000000) return (n / 1000000).toFixed(1) + "M"
        if (n >= 1000) return (n / 1000).toFixed(1) + "k"
        return String(Math.round(n))
    }

    function activeQuote() {
        if (!root.chartSymbol) return null
        var lists = [root.summaryData.watchlist || [], root.summaryData.items || []]
        for (var li = 0; li < lists.length; li++) {
            var arr = lists[li]
            for (var i = 0; i < arr.length; i++) {
                if (arr[i].symbol === root.chartSymbol) return arr[i]
            }
        }
        return null
    }

    function activeCurrency() {
        var q = activeQuote()
        if (q && q.currency) return q.currency
        return String(root.chartSymbol || "").slice(-3) === ".ZW" ? "ZWG" : "USD"
    }

    function pad2(n) {
        return (n < 10 ? "0" : "") + n
    }

    function fmtDate(d) {
        return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate())
    }

    function parseDateString(raw) {
        var s = (raw || "").trim()
        if (!s) return null
        var m = s.match(/^(\d{4})[-\/.](\d{1,2})[-\/.](\d{1,2})$/)
        if (m) return new Date(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10))
        m = s.match(/^(\d{1,2})[-\/](\d{1,2})[-\/](\d{4})$/)
        if (m) return new Date(parseInt(m[3], 10), parseInt(m[2], 10) - 1, parseInt(m[1], 10))
        return null
    }

    function syncCalendarFromInput() {
        var parsed = parseDateString(root.dateText)
        var d = parsed && !isNaN(parsed.getTime()) ? parsed : new Date()
        root.calYear = d.getFullYear()
        root.calMonth = d.getMonth()
    }

    function shiftMonth(delta) {
        var d = new Date(root.calYear, root.calMonth + delta, 1)
        root.calYear = d.getFullYear()
        root.calMonth = d.getMonth()
    }

    function selectPresetOffset(daysBack, monthsBack) {
        var d = new Date()
        if (monthsBack > 0) d.setMonth(d.getMonth() - monthsBack)
        if (daysBack > 0) d.setDate(d.getDate() - daysBack)
        root.dateText = root.fmtDate(d)
        root.calYear = d.getFullYear()
        root.calMonth = d.getMonth()
        root.calendarOpen = false
    }

    function monthLabel(year, month) {
        var names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return names[month] + " " + year
    }

    function calendarCells(year, month) {
        var firstDow = new Date(year, month, 1).getDay()
        var daysInMonth = new Date(year, month + 1, 0).getDate()
        var todayStr = root.fmtDate(new Date())
        var parsedSel = parseDateString(root.dateText)
        var selStr = (parsedSel && !isNaN(parsedSel.getTime())) ? root.fmtDate(parsedSel) : ""
        var cells = []
        for (var i = 0; i < firstDow; i++) {
            cells.push({ day: 0, dateStr: "", isToday: false, isSelected: false, isFuture: false })
        }
        for (var d = 1; d <= daysInMonth; d++) {
            var ds = year + "-" + pad2(month + 1) + "-" + pad2(d)
            cells.push({
                day: d,
                dateStr: ds,
                isToday: ds === todayStr,
                isSelected: ds === selStr,
                isFuture: ds > todayStr
            })
        }
        while (cells.length % 7 !== 0) {
            cells.push({ day: 0, dateStr: "", isToday: false, isSelected: false, isFuture: false })
        }
        return cells
    }

    function quickTrade(mode, sym) {
        root.manualMode = mode
        root.statusMessage = ""
        root.dcaPlanData = null
        root.calendarOpen = false
        root.symText = sym
        if (root.sharesInputRef) root.sharesInputRef.forceActiveFocus()
    }

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

    onSummaryDataChanged: if (root.candleCanvasRef) root.candleCanvasRef.requestPaint()
    onChartSymbolChanged: if (root.candleCanvasRef) root.candleCanvasRef.requestPaint()
    onChartModeChanged: if (root.candleCanvasRef) root.candleCanvasRef.requestPaint()
    onHoveredCandleIdxChanged: if (root.candleCanvasRef) root.candleCanvasRef.requestPaint()

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
                    root.symText = ""
                    root.sharesText = ""
                    root.priceText = ""
                    root.dateText = ""
                }
                root.pendingClearInputs = false
                root.calendarOpen = false
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
        var sym = root.symText.trim().toUpperCase()
        var prc = root.priceText.replace(/^\s*\$?/, "").replace(/,/g, "").trim()
        var sh = root.sharesText.replace(/,/g, "").trim()
        var dt = root.dateText.trim()
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
                                Text {
                                    text: "Cost $" + Number(root.summaryData.total_cost || 0).toFixed(2)
                                    color: "#a6adc8"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
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

                        Text {
                            width: parent.width
                            visible: root.summaryData.has_zwg === true
                            text: {
                                var zv = Number(root.summaryData.zwg_value || 0)
                                var zc = Number(root.summaryData.zwg_cost || 0)
                                var zp = Number(root.summaryData.zwg_pnl || 0)
                                var zpct = Number(root.summaryData.zwg_pnl_pct || 0)
                                return "ZSE (ZWG): ZiG " + zv.toFixed(2) + " • Cost ZiG " + zc.toFixed(2) + " (" + root.fmtSignedMoney(zp, "ZWG") + " / " + (zpct >= 0 ? "+" : "") + zpct.toFixed(1) + "%)"
                            }
                            color: Number(root.summaryData.zwg_pnl || 0) >= 0 ? "#f9e2af" : "#f38ba8"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                            wrapMode: Text.WordWrap
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
                                        spacing: Style.space(4)
                                        Text {
                                            id: holdSymTxt
                                            width: portfolioCol.width * 0.21
                                            text: modelData.symbol
                                            color: modelData.currency === "ZWG" ? "#f9e2af" : "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small || Style.font.body
                                            font.bold: true
                                            elide: Text.ElideRight
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Text {
                                            id: holdShTxt
                                            width: portfolioCol.width * 0.16
                                            text: Number(modelData.shares) + " sh"
                                            color: "#a6adc8"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small || Style.font.body
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Text {
                                            id: holdPrcTxt
                                            width: portfolioCol.width * 0.23
                                            text: root.fmtPrice(modelData.price, modelData.currency)
                                            color: "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small || Style.font.body
                                            elide: Text.ElideRight
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Text {
                                            width: Math.max(40, holdingRow.width - holdSymTxt.width - holdShTxt.width - holdPrcTxt.width - Style.space(12))
                                            horizontalAlignment: Text.AlignRight
                                            elide: Text.ElideLeft
                                            text: {
                                                var pct = Number(modelData.pnl_pct || 0)
                                                var sign = pct >= 0 ? "+" : ""
                                                return root.fmtSignedMoney(modelData.pnl, modelData.currency) + " (" + sign + pct.toFixed(1) + "%)"
                                            }
                                            color: modelData.pnl >= 0 ? "#a6e3a1" : "#f38ba8"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small || Style.font.body
                                            font.bold: true
                                            anchors.verticalCenter: parent.verticalCenter
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
                                Row {
                                    width: portfolioCol.width
                                    spacing: Style.space(6)

                                    Text {
                                        width: Math.max(40, parent.width - quickBtnsRow.width - Style.space(6))
                                        anchors.verticalCenter: parent.verticalCenter
                                        elide: Text.ElideRight
                                        text: {
                                            var lc = (modelData.lots || []).length
                                            var prefix = lc > 0 ? ((holdingItemCol.lotsExpanded ? "▾ " : "▸ ") + lc + (lc === 1 ? " lot" : " lots") + " • ") : ""
                                            var base = prefix + "avg " + root.fmtPrice(modelData.avg_cost || 0, modelData.currency) + " • Cost " + root.fmtShortMoney(modelData.cost !== undefined ? modelData.cost : (Number(modelData.shares || 0) * Number(modelData.avg_cost || 0)), modelData.currency)
                                            if (modelData.days_held !== null && modelData.days_held !== undefined)
                                                base += " • " + modelData.days_held + "d"
                                            return base
                                        }
                                        color: (modelData.lots || []).length > 0 ? "#89b4fa" : "#a6adc8"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                        MouseArea {
                                            anchors.fill: parent
                                            enabled: (modelData.lots || []).length > 0
                                            cursorShape: (modelData.lots || []).length > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                                            onClicked: holdingItemCol.lotsExpanded = !holdingItemCol.lotsExpanded
                                        }
                                    }

                                    Row {
                                        id: quickBtnsRow
                                        spacing: Style.space(4)
                                        anchors.verticalCenter: parent.verticalCenter

                                        Rectangle {
                                            width: qbBuyTxt.implicitWidth + Style.space(8)
                                            height: qbBuyTxt.implicitHeight + 2
                                            radius: 3
                                            color: "#243b2c"
                                            border.color: "#45475a"
                                            border.width: 1
                                            Text {
                                                id: qbBuyTxt
                                                anchors.centerIn: parent
                                                text: "+Buy"
                                                color: "#a6e3a1"
                                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                                font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                                font.bold: true
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: root.quickTrade("buy", modelData.symbol)
                                            }
                                        }

                                        Rectangle {
                                            width: qbSellTxt.implicitWidth + Style.space(8)
                                            height: qbSellTxt.implicitHeight + 2
                                            radius: 3
                                            color: "#3d2229"
                                            border.color: "#45475a"
                                            border.width: 1
                                            Text {
                                                id: qbSellTxt
                                                anchors.centerIn: parent
                                                text: "Sell"
                                                color: "#f38ba8"
                                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                                font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                                font.bold: true
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: root.quickTrade("sell", modelData.symbol)
                                            }
                                        }
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
                                height: watchInnerCol.implicitHeight + Style.space(6)
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

                                Column {
                                    id: watchInnerCol
                                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 4; rightMargin: 4 }
                                    spacing: 2

                                    Row {
                                        id: watchRow
                                        width: parent.width
                                        Text {
                                            width: watchInnerCol.width * 0.21
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: modelData.symbol
                                            color: modelData.currency === "ZWG" ? "#f9e2af" : "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small || Style.font.body
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }
                                        Canvas {
                                            id: sparkline
                                            width: watchInnerCol.width * 0.16
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
                                            width: watchInnerCol.width * 0.20
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
                                            width: watchInnerCol.width * 0.11
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
                                            width: watchInnerCol.width * 0.25
                                            anchors.verticalCenter: parent.verticalCenter
                                            horizontalAlignment: Text.AlignRight
                                            elide: Text.ElideLeft
                                            text: modelData.price !== null && modelData.price !== undefined ? root.fmtPrice(modelData.price, modelData.currency) : "N/A"
                                            color: "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small || Style.font.body
                                        }
                                        Text {
                                            width: watchInnerCol.width * 0.07
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

                                    Row {
                                        width: parent.width
                                        visible: Number(modelData.best_bid || 0) > 0 || Number(modelData.best_ask || 0) > 0
                                        spacing: Style.space(8)

                                        Text {
                                            width: parent.width * 0.48
                                            visible: Number(modelData.best_bid || 0) > 0
                                            text: "Bid " + root.fmtPrice(modelData.best_bid, modelData.currency) + " × " + root.fmtVol(modelData.bid_volume || 0)
                                            color: "#a6e3a1"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            width: Number(modelData.best_bid || 0) > 0 ? parent.width * 0.48 : parent.width
                                            visible: Number(modelData.best_ask || 0) > 0
                                            horizontalAlignment: Number(modelData.best_bid || 0) > 0 ? Text.AlignRight : Text.AlignLeft
                                            text: "Ask " + root.fmtPrice(modelData.best_ask, modelData.currency) + " × " + root.fmtVol(modelData.ask_volume || 0)
                                            color: "#f38ba8"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                            elide: Text.ElideRight
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

                        Rectangle {
                            width: parent.width
                            visible: {
                                var q = root.activeQuote()
                                return q && (Number(q.best_bid || 0) > 0 || Number(q.best_ask || 0) > 0)
                            }
                            height: depthStripRow.implicitHeight + Style.space(8)
                            radius: 5
                            color: "#11111b"
                            border.color: "#313244"
                            border.width: 1

                            Row {
                                id: depthStripRow
                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 6; rightMargin: 6 }
                                spacing: Style.space(6)
                                Text {
                                    width: parent.width * 0.36
                                    elide: Text.ElideRight
                                    text: {
                                        var q = root.activeQuote()
                                        var cur = root.activeCurrency()
                                        return (q && Number(q.best_bid || 0) > 0) ? ("Bid " + root.fmtPrice(q.best_bid, cur) + " (" + root.fmtVol(q.bid_volume || 0) + ")") : "Bid --"
                                    }
                                    color: "#a6e3a1"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                }
                                Text {
                                    width: parent.width * 0.36
                                    elide: Text.ElideRight
                                    horizontalAlignment: Text.AlignHCenter
                                    text: {
                                        var q = root.activeQuote()
                                        var cur = root.activeCurrency()
                                        return (q && Number(q.best_ask || 0) > 0) ? ("Ask " + root.fmtPrice(q.best_ask, cur) + " (" + root.fmtVol(q.ask_volume || 0) + ")") : "Ask --"
                                    }
                                    color: "#f38ba8"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                }
                                Text {
                                    width: parent.width * 0.24
                                    elide: Text.ElideLeft
                                    horizontalAlignment: Text.AlignRight
                                    text: {
                                        var q = root.activeQuote()
                                        var cur = root.activeCurrency()
                                        return (q && q.spread !== undefined && q.spread !== null) ? ("Spr " + root.fmtPrice(q.spread, cur)) : ""
                                    }
                                    color: "#a6adc8"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
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
                            text: {
                                if (!curCandle) return "No OHLC history yet"
                                var cur = root.activeCurrency()
                                var pf = root.moneyPrefix(cur)
                                return curCandle.date + "  O:" + pf + Number(curCandle.open).toFixed(4) + " H:" + pf + Number(curCandle.high).toFixed(4) + " L:" + pf + Number(curCandle.low).toFixed(4) + " C:" + pf + Number(curCandle.close).toFixed(4)
                            }
                            color: curCandle ? (Number(curCandle.close) >= Number(curCandle.open) ? "#a6e3a1" : "#f38ba8") : "#a6adc8"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                            elide: Text.ElideRight
                        }

                        Canvas {
                            id: candleCanvas
                            width: parent.width
                            height: Style.space(110)
                            Component.onCompleted: {
                                root.candleCanvasRef = candleCanvas
                                candleCanvas.requestPaint()
                            }
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
                                    var yPref = root.activeCurrency() === "ZWG" ? "Z" : "$"
                                    ctx.fillText(yPref + levels[g].toFixed(3), 0, gy)
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

                        Grid {
                            width: parent.width
                            columns: 4
                            columnSpacing: Style.space(4)
                            rowSpacing: Style.space(4)
                            Repeater {
                                model: [
                                    { key: "buy", label: "Buy" },
                                    { key: "sell", label: "Sell" },
                                    { key: "dividend", label: "Div" },
                                    { key: "watch", label: "+Watch" },
                                    { key: "alert", label: "Alert" },
                                    { key: "target", label: "Target" },
                                    { key: "dca", label: "DCA" },
                                    { key: "price", label: "Price" }
                                ]
                                delegate: Rectangle {
                                    width: (manualCol.width - Style.space(4) * 3) / 4
                                    height: modeLabel.implicitHeight + Style.space(6)
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
                                            if (modelData.key !== "buy" && modelData.key !== "sell" && modelData.key !== "dividend") root.calendarOpen = false
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
                                Component.onCompleted: text = root.symText
                                onTextChanged: if (root.symText !== text) root.symText = text
                                Connections {
                                    target: root
                                    function onSymTextChanged() {
                                        if (symbolInput.text !== root.symText) symbolInput.text = root.symText
                                    }
                                }
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
                                Component.onCompleted: {
                                    root.sharesInputRef = sharesInput
                                    text = root.sharesText
                                }
                                onTextChanged: if (root.sharesText !== text) root.sharesText = text
                                Connections {
                                    target: root
                                    function onSharesTextChanged() {
                                        if (sharesInput.text !== root.sharesText) sharesInput.text = root.sharesText
                                    }
                                }
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
                                Component.onCompleted: text = root.priceText
                                onTextChanged: if (root.priceText !== text) root.priceText = text
                                Connections {
                                    target: root
                                    function onPriceTextChanged() {
                                        if (priceInput.text !== root.priceText) priceInput.text = root.priceText
                                    }
                                }
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

                    Row {
                        visible: root.manualMode === "buy" || root.manualMode === "sell" || root.manualMode === "dividend"
                        width: parent.width
                        spacing: Style.space(4)

                        Rectangle {
                            width: parent.width - calToggleBtn.width - (clearDateBtn.visible ? clearDateBtn.width + Style.space(4) : 0) - Style.space(4)
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
                                Component.onCompleted: text = root.dateText
                                onTextChanged: if (root.dateText !== text) root.dateText = text
                                Connections {
                                    target: root
                                    function onDateTextChanged() {
                                        if (dateInput.text !== root.dateText) dateInput.text = root.dateText
                                    }
                                }
                                KeyNavigation.backtab: priceInput
                                KeyNavigation.tab: symbolInput
                                onAccepted: root.submitManualEntry()
                                Text {
                                    anchors.fill: parent
                                    verticalAlignment: Text.AlignVCenter
                                    text: "Date (blank = Today)"
                                    color: "#6c7086"
                                    font: dateInput.font
                                    visible: !dateInput.text && !dateInput.activeFocus
                                }
                            }
                        }

                        Rectangle {
                            id: clearDateBtn
                            visible: dateInput.text.length > 0
                            width: Style.space(26)
                            height: Style.space(26)
                            radius: 4
                            color: "#313244"
                            border.color: "#45475a"
                            border.width: 1
                            Text {
                                anchors.centerIn: parent
                                text: "×"
                                color: "#f38ba8"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                font.bold: true
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    dateInput.text = ""
                                    root.calendarOpen = false
                                }
                            }
                        }

                        Rectangle {
                            id: calToggleBtn
                            width: Style.space(52)
                            height: Style.space(26)
                            radius: 4
                            color: root.calendarOpen ? "#89b4fa" : "#313244"
                            border.color: root.calendarOpen ? "#89b4fa" : "#45475a"
                            border.width: 1
                            Text {
                                anchors.centerIn: parent
                                text: root.calendarOpen ? "Cal ▴" : "Cal ▾"
                                color: root.calendarOpen ? "#1e1e2e" : "#cdd6f4"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.small || Style.font.body
                                font.bold: true
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (!root.calendarOpen) root.syncCalendarFromInput()
                                    root.calendarOpen = !root.calendarOpen
                                }
                            }
                        }
                    }

                    Rectangle {
                        id: miniCalendarCard
                        visible: root.calendarOpen && (root.manualMode === "buy" || root.manualMode === "sell" || root.manualMode === "dividend")
                        width: parent.width
                        height: calInnerCol.implicitHeight + Style.space(12)
                        radius: 6
                        color: "#11111b"
                        border.color: "#45475a"
                        border.width: 1

                        Column {
                            id: calInnerCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(6) }
                            spacing: Style.space(5)

                            Grid {
                                width: parent.width
                                columns: 4
                                columnSpacing: Style.space(4)
                                Repeater {
                                    model: [
                                        { label: "Today", days: 0, months: 0 },
                                        { label: "Yest.", days: 1, months: 0 },
                                        { label: "-1W", days: 7, months: 0 },
                                        { label: "-1M", days: 0, months: 1 }
                                    ]
                                    delegate: Rectangle {
                                        width: (calInnerCol.width - Style.space(4) * 3) / 4
                                        height: presetTxt.implicitHeight + Style.space(4)
                                        radius: 4
                                        color: "#313244"
                                        border.color: "#45475a"
                                        border.width: 1
                                        Text {
                                            id: presetTxt
                                            anchors.centerIn: parent
                                            text: modelData.label
                                            color: "#89b4fa"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                            font.bold: true
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: root.selectPresetOffset(modelData.days, modelData.months)
                                        }
                                    }
                                }
                            }

                            Row {
                                width: parent.width
                                spacing: Style.space(4)

                                Rectangle {
                                    width: Style.space(24); height: Style.space(22); radius: 4; color: "#1e1e2e"
                                    Text { anchors.centerIn: parent; text: "«"; color: "#a6adc8"; font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small || Style.font.body; font.bold: true }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.calYear = root.calYear - 1 }
                                }
                                Rectangle {
                                    width: Style.space(24); height: Style.space(22); radius: 4; color: "#1e1e2e"
                                    Text { anchors.centerIn: parent; text: "‹"; color: "#cdd6f4"; font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small || Style.font.body; font.bold: true }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.shiftMonth(-1) }
                                }
                                Text {
                                    width: calInnerCol.width - Style.space(24) * 4 - Style.space(4) * 4
                                    height: Style.space(22)
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    text: root.monthLabel(root.calYear, root.calMonth)
                                    color: "#cdd6f4"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small || Style.font.body
                                    font.bold: true
                                }
                                Rectangle {
                                    width: Style.space(24); height: Style.space(22); radius: 4; color: "#1e1e2e"
                                    Text { anchors.centerIn: parent; text: "›"; color: "#cdd6f4"; font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small || Style.font.body; font.bold: true }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.shiftMonth(1) }
                                }
                                Rectangle {
                                    width: Style.space(24); height: Style.space(22); radius: 4; color: "#1e1e2e"
                                    Text { anchors.centerIn: parent; text: "»"; color: "#a6adc8"; font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small || Style.font.body; font.bold: true }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.calYear = root.calYear + 1 }
                                }
                            }

                            Grid {
                                width: parent.width
                                columns: 7
                                columnSpacing: 2
                                Repeater {
                                    model: ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]
                                    delegate: Text {
                                        width: (calInnerCol.width - 12) / 7
                                        horizontalAlignment: Text.AlignHCenter
                                        text: modelData
                                        color: "#6c7086"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                        font.bold: true
                                    }
                                }
                            }

                            Grid {
                                width: parent.width
                                columns: 7
                                columnSpacing: 2
                                rowSpacing: 2
                                Repeater {
                                    model: root.calendarCells(root.calYear, root.calMonth)
                                    delegate: Rectangle {
                                        width: (calInnerCol.width - 12) / 7
                                        height: Style.space(21)
                                        radius: 4
                                        color: modelData.day === 0 ? "transparent" : (modelData.isSelected ? "#89b4fa" : (modelData.isToday ? "#313244" : "#1e1e2e"))
                                        border.color: modelData.isToday && !modelData.isSelected ? "#a6e3a1" : "transparent"
                                        border.width: modelData.isToday && !modelData.isSelected ? 1 : 0
                                        Text {
                                            anchors.centerIn: parent
                                            visible: modelData.day > 0
                                            text: modelData.day > 0 ? String(modelData.day) : ""
                                            color: modelData.isSelected ? "#1e1e2e" : (modelData.isFuture ? "#45475a" : (modelData.isToday ? "#a6e3a1" : "#cdd6f4"))
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                            font.bold: modelData.isSelected || modelData.isToday
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            enabled: modelData.day > 0 && !modelData.isFuture
                                            cursorShape: (modelData.day > 0 && !modelData.isFuture) ? Qt.PointingHandCursor : Qt.ArrowCursor
                                            onClicked: {
                                                dateInput.text = modelData.dateStr
                                                root.calendarOpen = false
                                            }
                                        }
                                    }
                                }
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
                                var zse = root.summaryData.zse_symbols || []
                                var pool = root.knownSymbols.concat(zse)
                                var out = []
                                var seen = {}
                                for (var i = 0; i < pool.length; i++) {
                                    var s = String(pool[i])
                                    if (seen[s]) continue
                                    if (!q || s.indexOf(q) === 0) {
                                        seen[s] = true
                                        out.push(s)
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
                                border.color: String(modelData).slice(-3) === ".ZW" ? "#f9e2af" : "#45475a"
                                border.width: 1
                                Text {
                                    id: sugText
                                    anchors.centerIn: parent
                                    text: modelData
                                    color: String(modelData).slice(-3) === ".ZW" ? "#f9e2af" : "#89b4fa"
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
