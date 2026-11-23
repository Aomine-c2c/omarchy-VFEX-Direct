import QtQuick

Item {
    id: chartRoot
    property var theme
    property string symbol: ""
    property string currency: "USD"
    property var candles: []
    property var history: []
    property var ma20Series: []
    property real breakevenPrice: 0
    property real optimalLimit: 0
    property string rangeKey: "ALL" // "1W", "1M", "3M", "ALL"
    property string chartType: "candle" // "candle" or "line"
    property int hoveredIdx: -1

    function slicedCandles() {
        var src = candles && candles.length > 0 ? candles : []
        if (src.length === 0 && history && history.length > 0) {
            var out = []
            for (var i = 0; i < history.length; i++) {
                var p = Number(history[i] || 0)
                if (p > 0) out.push({ date: "D" + (i + 1), open: p, high: p, low: p, close: p })
            }
            src = out
        }
        if (rangeKey === "1W") return src.slice(-7)
        if (rangeKey === "1M") return src.slice(-30)
        if (rangeKey === "3M") return src.slice(-90)
        return src
    }

    onCandlesChanged: canvas.requestPaint()
    onHistoryChanged: canvas.requestPaint()
    onRangeKeyChanged: { hoveredIdx = -1; canvas.requestPaint() }
    onChartTypeChanged: canvas.requestPaint()
    onHoveredIdxChanged: canvas.requestPaint()

    Column {
        anchors.fill: parent
        spacing: 6

        // Header bar: Symbol + Time-range selectors + Chart mode
        Row {
            width: parent.width
            spacing: 6
            Text {
                text: (chartRoot.symbol || "SELECT COUNTER") + "  //  PRICE ACTION"
                color: theme.textPrimary
                font.family: theme.fontMono
                font.pixelSize: 11
                font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }
            Item { width: Math.max(8, parent.width - 360); height: 1 }

            Repeater {
                model: ["1W", "1M", "3M", "ALL"]
                delegate: Rectangle {
                    width: 34; height: 20; radius: theme.rSharp
                    color: chartRoot.rangeKey === modelData ? theme.bgActive : "transparent"
                    border.color: chartRoot.rangeKey === modelData ? theme.borderStrong : theme.borderSubtle
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: modelData
                        color: chartRoot.rangeKey === modelData ? theme.textPrimary : theme.textMuted
                        font.family: theme.fontMono
                        font.pixelSize: 10
                        font.bold: chartRoot.rangeKey === modelData
                    }
                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: chartRoot.rangeKey = modelData
                    }
                }
            }
            Rectangle {
                width: 56; height: 20; radius: theme.rSharp
                color: theme.bgElevated
                border.color: theme.borderDefault; border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: chartRoot.chartType === "candle" ? "CANDLE" : "LINE"
                    color: theme.textSecondary
                    font.family: theme.fontMono
                    font.pixelSize: 9
                    font.bold: true
                }
                MouseArea {
                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    onClicked: chartRoot.chartType = (chartRoot.chartType === "candle" ? "line" : "candle")
                }
            }
        }

        // Canvas area
        Rectangle {
            width: parent.width
            height: Math.max(120, parent.height - 28)
            color: theme.bgBlack
            border.color: theme.borderSubtle
            border.width: 1
            radius: theme.rSharp
            clip: true

            Canvas {
                id: canvas
                anchors.fill: parent
                anchors.margins: 6
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    var data = chartRoot.slicedCandles()
                    if (!data || data.length === 0) {
                        ctx.fillStyle = String(theme.textMuted)
                        ctx.font = "11px monospace"
                        ctx.fillText("NO HISTORICAL OHLC BARS FOR " + (chartRoot.symbol || "--"), 12, height / 2)
                        return
                    }

                    var padL = 8, padR = 54, padT = 10, padB = 18
                    var plotW = Math.max(10, width - padL - padR)
                    var plotH = Math.max(10, height - padT - padB)

                    var mn = 1e18, mx = -1e18
                    for (var i = 0; i < data.length; i++) {
                        var h = Number(data[i].high || data[i].close || 0)
                        var l = Number(data[i].low || data[i].close || 0)
                        if (h > mx) mx = h
                        if (l < mn) mn = l
                    }
                    if (chartRoot.breakevenPrice > 0) {
                        mn = Math.min(mn, chartRoot.breakevenPrice)
                        mx = Math.max(mx, chartRoot.breakevenPrice)
                    }
                    if (mx - mn < 1e-6) { mx += 0.01; mn = Math.max(0, mn - 0.01) }
                    var span = mx - mn

                    function yOf(p) { return padT + plotH - ((p - mn) / span) * plotH }
                    function xOf(idx) { return padL + (data.length > 1 ? (idx / (data.length - 1)) * plotW : plotW * 0.5) }

                    // Horizontal grid & price axis
                    ctx.strokeStyle = "#16161C"
                    ctx.lineWidth = 1
                    ctx.fillStyle = "#6C6C78"
                    ctx.font = "9px monospace"
                    for (var g = 0; g <= 4; g++) {
                        var gy = padT + (g / 4) * plotH
                        var gp = mx - (g / 4) * span
                        ctx.beginPath(); ctx.moveTo(padL, gy); ctx.lineTo(padL + plotW, gy); ctx.stroke()
                        ctx.fillText(gp.toFixed(4), padL + plotW + 4, gy + 3)
                    }

                    // Breakeven line
                    if (chartRoot.breakevenPrice > 0) {
                        var bey = yOf(chartRoot.breakevenPrice)
                        ctx.strokeStyle = String(theme.warn)
                        ctx.setLineDash([3, 3])
                        ctx.beginPath(); ctx.moveTo(padL, bey); ctx.lineTo(padL + plotW, bey); ctx.stroke()
                        ctx.setLineDash([])
                    }

                    // Plot candles or line
                    if (chartRoot.chartType === "line" || data.length === 1) {
                        ctx.strokeStyle = String(theme.textPrimary)
                        ctx.lineWidth = 1.5
                        ctx.beginPath()
                        for (var li = 0; li < data.length; li++) {
                            var lx = xOf(li), ly = yOf(Number(data[li].close || 0))
                            if (li === 0) ctx.moveTo(lx, ly); else ctx.lineTo(lx, ly)
                        }
                        ctx.stroke()
                    } else {
                        var cw = Math.max(2, Math.min(10, (plotW / data.length) * 0.65))
                        for (var ci = 0; ci < data.length; ci++) {
                            var c = data[ci]
                            var o = Number(c.open || c.close || 0)
                            var cl = Number(c.close || 0)
                            var hi = Number(c.high || Math.max(o, cl))
                            var lo = Number(c.low || Math.min(o, cl))
                            var cx = xOf(ci)
                            var up = cl >= o
                            ctx.strokeStyle = up ? String(theme.gain) : String(theme.loss)
                            ctx.fillStyle = up ? String(theme.gain) : String(theme.loss)
                            ctx.lineWidth = 1
                            ctx.beginPath(); ctx.moveTo(cx, yOf(hi)); ctx.lineTo(cx, yOf(lo)); ctx.stroke()
                            var topY = yOf(Math.max(o, cl)), botY = yOf(Math.min(o, cl))
                            ctx.fillRect(cx - cw / 2, topY, cw, Math.max(1.5, botY - topY))
                        }
                    }

                    // Crosshair hover
                    if (chartRoot.hoveredIdx >= 0 && chartRoot.hoveredIdx < data.length) {
                        var hc = data[chartRoot.hoveredIdx]
                        var hx = xOf(chartRoot.hoveredIdx)
                        var hy = yOf(Number(hc.close || 0))
                        ctx.strokeStyle = "#3A3A47"
                        ctx.setLineDash([2, 2])
                        ctx.beginPath(); ctx.moveTo(hx, padT); ctx.lineTo(hx, padT + plotH); ctx.stroke()
                        ctx.beginPath(); ctx.moveTo(padL, hy); ctx.lineTo(padL + plotW, hy); ctx.stroke()
                        ctx.setLineDash([])
                    }
                }
            }

            // Hover readout bar
            Rectangle {
                visible: chartRoot.hoveredIdx >= 0 && chartRoot.hoveredIdx < chartRoot.slicedCandles().length
                anchors.top: parent.top; anchors.left: parent.left; anchors.margins: 8
                width: hoverTxt.implicitWidth + 12; height: 20; radius: theme.rSharp
                color: "#CC09090B"; border.color: theme.borderDefault; border.width: 1
                Text {
                    id: hoverTxt
                    anchors.centerIn: parent
                    property var hc: (chartRoot.hoveredIdx >= 0 && chartRoot.hoveredIdx < chartRoot.slicedCandles().length) ? chartRoot.slicedCandles()[chartRoot.hoveredIdx] : null
                    text: hc ? (String(hc.date || "") + "  O:" + Number(hc.open || 0).toFixed(4) + " H:" + Number(hc.high || 0).toFixed(4) + " L:" + Number(hc.low || 0).toFixed(4) + " C:" + Number(hc.close || 0).toFixed(4)) : ""
                    color: theme.textPrimary
                    font.family: theme.fontMono; font.pixelSize: 9
                }
            }

            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                onPositionChanged: function(mouse) {
                    var data = chartRoot.slicedCandles()
                    if (data.length === 0) return
                    var frac = Math.max(0, Math.min(1, (mouse.x - 14) / Math.max(1, width - 68)))
                    chartRoot.hoveredIdx = Math.round(frac * (data.length - 1))
                }
                onExited: chartRoot.hoveredIdx = -1
            }
        }
    }
}
