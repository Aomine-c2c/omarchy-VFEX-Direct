import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import qs.Commons

PanelWindow {
    id: notchWin

    property var bar: null
    property var hostWidget: null
    property var summaryData: ({})
    property string displayText: "VFEX --"
    property color displayColor: "#f4f4f6"
    property bool enabled: true
    property bool hostOpened: false
    property bool isFetching: false
    property bool barHovered: false

    readonly property var targetScreen: {
        var monitor = Hyprland.focusedMonitor
        var name = monitor ? String(monitor.name || "") : ""
        for (var i = 0; i < Quickshell.screens.length; i++) {
            if (Quickshell.screens[i].name === name) return Quickshell.screens[i]
        }
        return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    }
    readonly property var targetMonitor: targetScreen ? Hyprland.monitorFor(targetScreen) : null
    readonly property int workspaceId: (targetMonitor && targetMonitor.activeWorkspace) ? targetMonitor.activeWorkspace.id : -1
    readonly property int fullscreenMode: {
        var mode = 0
        var toplevels = Hyprland.toplevels.values
        for (var i = 0; i < toplevels.length; i++) {
            var tl = toplevels[i]
            if (!tl.workspace || tl.workspace.id !== workspaceId) continue
            var ipc = tl.lastIpcObject
            mode = Math.max(mode, ipc && ipc.fullscreen ? ipc.fullscreen : 0)
        }
        return mode
    }

    readonly property bool alertsActive: ((summaryData.alerts || []).length > 0)
    readonly property bool marketOpen: (String(summaryData.market_status || "") === "Open")
    property bool hovered: true
    readonly property bool shouldPeek: barHovered || notchMouse.containsMouse || peekBtnsHover.hovered
    readonly property bool shown: enabled && !hostOpened && fullscreenMode < 2 && !!targetScreen && hovered

    onShouldPeekChanged: {
        if (hostWidget) {
            hostWidget.notchSurfaceHovered = (notchMouse.containsMouse || peekBtnsHover.hovered)
            hostWidget.updateNotchPeekState()
        }
    }

    visible: shown
    screen: targetScreen
    anchors { top: true }
    margins.top: (bar && bar.height ? Number(bar.height) : 34) + 2
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.namespace: "omarchy-vfex-notch"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

    implicitWidth: Math.max(notchPill.width, 416)
    implicitHeight: Math.max(notchPill.height, 240)
    mask: Region { item: notchPill }

    // Pure-QML 5x7 LED Dot-Matrix Glyph Map for authentic Nothing OS / Ndot pixel rendering
    readonly property var glyphMap: ({
        "A": [14,17,17,31,17,17,17], "B": [30,17,17,30,17,17,30], "C": [14,17,16,16,16,17,14],
        "D": [28,18,17,17,17,18,28], "E": [31,16,16,30,16,16,31], "F": [31,16,16,30,16,16,16],
        "G": [14,17,16,23,17,17,14], "H": [17,17,17,31,17,17,17], "I": [14,4,4,4,4,4,14],
        "J": [7,2,2,2,18,18,12],     "K": [17,18,20,24,20,18,17], "L": [16,16,16,16,16,16,31],
        "M": [17,27,21,21,17,17,17], "N": [17,25,21,19,17,17,17], "O": [14,17,17,17,17,17,14],
        "P": [30,17,17,30,16,16,16], "Q": [14,17,17,17,21,18,13], "R": [30,17,17,30,20,18,17],
        "S": [15,16,16,14,1,1,30],   "T": [31,4,4,4,4,4,4],       "U": [17,17,17,17,17,17,14],
        "V": [17,17,17,17,17,10,4],  "W": [17,17,17,21,21,27,17], "X": [17,17,10,4,10,17,17],
        "Y": [17,17,10,4,4,4,4],     "Z": [31,1,2,4,8,16,31],
        "0": [14,17,19,21,25,17,14], "1": [4,12,4,4,4,4,14],     "2": [14,17,1,6,8,16,31],
        "3": [30,1,1,14,1,1,30],     "4": [2,6,10,18,31,2,2],     "5": [31,16,30,1,1,17,14],
        "6": [14,16,16,30,17,17,14], "7": [31,1,2,4,8,8,8],       "8": [14,17,17,14,17,17,14],
        "9": [14,17,17,15,1,1,14],
        "$": [4,15,20,14,5,30,4],    ".": [0,0,0,0,0,12,12],      ",": [0,0,0,0,4,4,8],
        ":": [0,12,12,0,12,12,0],    "%": [24,25,2,4,8,19,3],     "+": [0,4,4,31,4,4,0],
        "-": [0,0,0,31,0,0,0],       "/": [1,2,2,4,8,8,16],       "•": [0,0,14,14,14,0,0],
        "!": [4,4,4,4,4,0,4],        "?": [14,17,2,4,4,0,4],      "(": [2,4,8,8,8,4,2],
        ")": [8,4,2,2,2,4,8],        "▲": [0,4,14,31,0,0,0],     "▼": [0,0,0,31,14,4,0],
        "★": [4,4,31,14,14,27,17],   "⚠": [4,14,14,31,31,31,4],   " ": [0,0,0,0,0,0,0]
    })

    readonly property var sparkValues: {
        var wl = summaryData.watchlist || []
        if (wl.length > 0 && wl[0].history && wl[0].history.length >= 2) {
            return wl[0].history
        }
        var eq = ((summaryData.paper_agent || ({})).equity_history || [])
        var out = []
        for (var i = 0; i < eq.length; i++) out.push(Number(eq[i].equity_usd || 100))
        return out
    }

    function measureMatrixWidth(txt, dotStep) {
        var s = String(txt || "").toUpperCase()
        if (!s.length) return 10
        return s.length * (dotStep * 6) - dotStep
    }

    onDisplayTextChanged: { pillMatrixCanvas.requestPaint(); peekTitleCanvas.requestPaint() }
    onDisplayColorChanged: pillMatrixCanvas.requestPaint()
    onSummaryDataChanged: {
        pillMatrixCanvas.requestPaint()
        pillSparkCanvas.requestPaint()
        peekSparkCanvas.requestPaint()
    }
    onHoveredChanged: if (hovered) {
        peekTitleCanvas.requestPaint()
        peekSparkCanvas.requestPaint()
    }

    Item {
        id: pillAnchorWrap
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: notchPill.width
        height: notchPill.height

        Rectangle {
            id: notchPill
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top

            readonly property int compactW: Math.max(210, Math.min(340, notchWin.measureMatrixWidth(notchWin.displayText, 2.1) + 74))
            width: notchWin.hovered ? 404 : compactW
            height: notchWin.hovered ? (peekContentCol.implicitHeight + 24) : 30
            radius: notchWin.hovered ? 20 : 15
            color: "#000000"
            border.color: notchWin.alertsActive ? "#ff2a3c" : (notchWin.hovered ? "#3f3f46" : "#222226")
            border.width: 1

            Behavior on width { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }
            Behavior on height { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }
            Behavior on radius { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }

            // Subtle Nothing Glyph Corner Micro-Dots
            Rectangle { x: 8; y: 8; width: 2; height: 2; radius: 1; color: "#27272a"; visible: notchWin.hovered }
            Rectangle { x: parent.width - 10; y: 8; width: 2; height: 2; radius: 1; color: "#27272a"; visible: notchWin.hovered }

            MouseArea {
                id: notchMouse
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                cursorShape: Qt.PointingHandCursor
                onWheel: function(wheel) {
                    if (notchWin.hostWidget) {
                        notchWin.hostWidget.rotIndex = wheel.angleDelta.y > 0
                            ? (notchWin.hostWidget.rotIndex - 1)
                            : (notchWin.hostWidget.rotIndex + 1)
                        notchWin.hostWidget.updateBarDisplay()
                    }
                }
                onClicked: function(mouse) {
                    if (!notchWin.hostWidget) return
                    if (mouse.button === Qt.LeftButton) {
                        notchWin.hostWidget.notchSurfaceHovered = false
                        notchWin.hostWidget.notchPeekOpen = false
                        notchWin.hostWidget.refresh(false)
                        notchWin.hostWidget.toggle()
                    } else if (mouse.button === Qt.MiddleButton) {
                        notchWin.hostWidget.refresh(true)
                    } else if (mouse.button === Qt.RightButton) {
                        notchWin.hostWidget.rotIndex = notchWin.hostWidget.rotIndex + 1
                        notchWin.hostWidget.updateBarDisplay()
                    }
                }
            }

            // Compact Rest Strip (Always visible in pill header)
            Item {
                id: compactHeaderRow
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 30
                visible: !notchWin.hovered

                // Signature Nothing Red Recording / Live LED Pixel Dot
                Rectangle {
                    id: ledDot
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    width: 6
                    height: 6
                    radius: 3
                    color: (notchWin.alertsActive || notchWin.marketOpen || notchWin.isFetching) ? "#ff2a3c" : "#3f3f46"
                    opacity: 1.0
                    SequentialAnimation on opacity {
                        running: notchWin.shown && (notchWin.marketOpen || notchWin.alertsActive || notchWin.isFetching)
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.28; duration: notchWin.alertsActive ? 450 : 1200; easing.type: Easing.InOutSine }
                        NumberAnimation { from: 0.28; to: 1.0; duration: notchWin.alertsActive ? 450 : 1200; easing.type: Easing.InOutSine }
                    }
                }

                // Pure Canvas 5x7 Dot-Matrix Readout
                Canvas {
                    id: pillMatrixCanvas
                    anchors.left: ledDot.right
                    anchors.leftMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.max(80, parent.width - 70)
                    height: 16
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        var txt = String(notchWin.displayText || "VFEX --").replace(/^●\s*/, "").toUpperCase()
                        var step = 2.05
                        var r = 0.85
                        var y0 = Math.floor((height - step * 7) / 2) + 1
                        var curX = 0
                        var fillCol = notchWin.alertsActive ? "#ff2a3c" : String(notchWin.displayColor)
                        if (fillCol === "#cdd6f4") fillCol = "#f4f4f6"
                        ctx.fillStyle = fillCol
                        for (var c = 0; c < txt.length; c++) {
                            var ch = txt.charAt(c)
                            var rows = notchWin.glyphMap[ch] || notchWin.glyphMap[" "]
                            if (curX + step * 5 > width) break
                            for (var row = 0; row < 7; row++) {
                                var maskBits = rows[row]
                                for (var col = 0; col < 5; col++) {
                                    if (maskBits & (16 >> col)) {
                                        ctx.beginPath()
                                        ctx.arc(curX + col * step + r, y0 + row * step + r, r, 0, Math.PI * 2)
                                        ctx.fill()
                                    }
                                }
                            }
                            curX += step * 6
                        }
                    }
                }

                // Miniature 7-Column Nothing Pixel Sparkline
                Canvas {
                    id: pillSparkCanvas
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    width: 28
                    height: 14
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        var vals = notchWin.sparkValues
                        var cols = 7
                        var rows = 5
                        var stepX = 4
                        var stepY = 2.8
                        if (!vals || vals.length < 2) {
                            ctx.fillStyle = "#27272a"
                            for (var gx = 0; gx < cols; gx++) {
                                ctx.beginPath(); ctx.arc(gx * stepX + 1.2, 6.5, 0.9, 0, Math.PI * 2); ctx.fill()
                            }
                            return
                        }
                        var slice = vals.slice(-cols)
                        var mn = Number(slice[0]), mx = Number(slice[0])
                        for (var i = 1; i < slice.length; i++) {
                            var v = Number(slice[i])
                            if (v < mn) mn = v
                            if (v > mx) mx = v
                        }
                        var sp = mx - mn
                        var isUp = Number(slice[slice.length - 1]) >= Number(slice[0])
                        var activeCol = isUp ? "#4ade80" : "#ff2a3c"
                        for (var c = 0; c < slice.length; c++) {
                            var norm = sp > 1e-9 ? (Number(slice[c]) - mn) / sp : 0.5
                            var lit = Math.min(rows - 1, Math.max(0, Math.round(norm * (rows - 1))))
                            for (var ry = 0; ry < rows; ry++) {
                                var fromBottom = (rows - 1) - ry
                                ctx.fillStyle = (fromBottom === lit) ? activeCol : (fromBottom < lit ? "#27272a" : "#141418")
                                ctx.beginPath()
                                ctx.arc(c * stepX + 1.2, ry * stepY + 1.2, 0.95, 0, Math.PI * 2)
                                ctx.fill()
                            }
                        }
                    }
                }
            }

            // Expanded Dynamic Island Nothing Peek Card (shown on hover)
            Column {
                id: peekContentCol
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
                spacing: 8
                visible: notchWin.hovered
                opacity: notchWin.hovered ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 150 } }

                HoverHandler { id: peekBtnsHover }

                // Top Row: Dot-Matrix Header + Market LED Pill
                Row {
                    width: parent.width
                    spacing: 6
                    Rectangle {
                        width: 7; height: 7; radius: 3.5; anchors.verticalCenter: parent.verticalCenter
                        color: notchWin.alertsActive || notchWin.marketOpen ? "#ff2a3c" : "#52525b"
                    }
                    Canvas {
                        id: peekTitleCanvas
                        width: Math.max(120, parent.width - mktBadgeRect.width - 20)
                        height: 14
                        anchors.verticalCenter: parent.verticalCenter
                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.clearRect(0, 0, width, height)
                            var txt = "VFEX // NOTHING"
                            var step = 1.9
                            var r = 0.8
                            var curX = 0
                            ctx.fillStyle = "#f4f4f6"
                            for (var c = 0; c < txt.length; c++) {
                                var rows = notchWin.glyphMap[txt.charAt(c)] || notchWin.glyphMap[" "]
                                if (curX + step * 5 > width) break
                                for (var row = 0; row < 7; row++) {
                                    var mb = rows[row]
                                    for (var col = 0; col < 5; col++) {
                                        if (mb & (16 >> col)) {
                                            ctx.beginPath()
                                            ctx.arc(curX + col * step + r, row * step + r, r, 0, Math.PI * 2)
                                            ctx.fill()
                                        }
                                    }
                                }
                                curX += step * 6
                            }
                        }
                    }
                    Rectangle {
                        id: mktBadgeRect
                        width: mktLedTxt.implicitWidth + 10; height: 16; radius: 8
                        color: notchWin.marketOpen ? "#220a0d" : "#18181b"
                        border.color: notchWin.marketOpen ? "#ff2a3c" : "#27272a"; border.width: 1
                        Text {
                            id: mktLedTxt; anchors.centerIn: parent
                            text: notchWin.marketOpen ? "OPEN" : "CLOSED"
                            color: notchWin.marketOpen ? "#ff2a3c" : "#a1a1aa"
                            font.pixelSize: 8; font.bold: true; font.letterSpacing: 1
                        }
                    }
                }

                // Hairline Dotted Separator
                Rectangle { width: parent.width; height: 1; color: "#27272a" }

                // KPI Grid: Portfolio Value + Unused Portal Cash
                Row {
                    width: parent.width
                    spacing: 8
                    Rectangle {
                        width: (parent.width - 8) / 2
                        height: pfCell.implicitHeight + 10; radius: 8; color: "#0c0c0f"; border.color: "#1f1f24"; border.width: 1
                        Column {
                            id: pfCell
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 7 }
                            spacing: 2
                            Text { text: "PORTFOLIO"; color: "#71717a"; font.pixelSize: 8; font.bold: true; font.letterSpacing: 1 }
                            Text {
                                property real tv: Number(notchWin.summaryData.total_value || 0)
                                property real pnl: Number(notchWin.summaryData.total_pnl || 0)
                                property real pct: Number(notchWin.summaryData.total_pnl_pct || 0)
                                text: "$" + tv.toFixed(2) + " (" + (pnl >= 0 ? "+" : "") + pct.toFixed(1) + "%)"
                                color: pnl >= 0 ? "#4ade80" : "#ff2a3c"
                                font.pixelSize: 10; font.bold: true; elide: Text.ElideRight; width: parent.width
                            }
                        }
                    }
                    Rectangle {
                        width: (parent.width - 8) / 2
                        height: cashCell.implicitHeight + 10; radius: 8; color: "#0c0c0f"; border.color: "#1f1f24"; border.width: 1
                        Column {
                            id: cashCell
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 7 }
                            spacing: 2
                            Text { text: "UNUSED BALANCES"; color: "#71717a"; font.pixelSize: 8; font.bold: true; font.letterSpacing: 1 }
                            Text {
                                property var icp: (notchWin.summaryData.idle_cash_plan || ({}))
                                property real du: Number(icp.total_deployable_usd || notchWin.summaryData.wallet_cash_usd || 0)
                                property real dz: Number(icp.total_deployable_zwg || notchWin.summaryData.wallet_cash_zwg || 0)
                                text: "$" + du.toFixed(2) + " USD • ZiG " + dz.toFixed(2)
                                color: "#f4f4f6"; font.pixelSize: 10; font.bold: true; elide: Text.ElideRight; width: parent.width
                            }
                        }
                    }
                }

                // Signal & Mahoraga Grokking Strip
                Row {
                    width: parent.width
                    spacing: 8
                    Rectangle {
                        width: parent.width
                        height: sigCell.implicitHeight + 10; radius: 8; color: "#0c0c0f"; border.color: "#1f1f24"; border.width: 1
                        Row {
                            id: sigCell
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 7 }
                            spacing: 6
                            Text {
                                width: parent.width * 0.56; elide: Text.ElideRight
                                property var topSig: ((notchWin.summaryData.signals || []).length > 0 ? notchWin.summaryData.signals[0] : null)
                                text: topSig ? ("SIGNAL: " + topSig.action + " " + topSig.symbol + " (" + topSig.score + ")") : "SIGNALS: ALL TRACKED CALM"
                                color: topSig ? (topSig.action === "SELL" ? "#ff2a3c" : "#4ade80") : "#a1a1aa"
                                font.pixelSize: 9; font.bold: true
                            }
                            Text {
                                width: parent.width * 0.44 - 6; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight
                                property var gk: (((notchWin.summaryData.paper_agent || ({})).brain || ({})).grok || ({}))
                                text: String(gk.status || "Accumulating History").toUpperCase()
                                color: gk.enabled ? "#4ade80" : "#f4f4f6"
                                font.pixelSize: 8; font.bold: true; font.letterSpacing: 0.6
                            }
                        }
                    }
                }

                // Pixel Dot-Matrix Expanded Sparkline Row
                Rectangle {
                    width: parent.width; height: 28; radius: 8; color: "#0c0c0f"; border.color: "#1f1f24"; border.width: 1
                    Row {
                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 8 }
                        spacing: 8
                        Text {
                            width: 112; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight
                            property var wl0: ((notchWin.summaryData.watchlist || []).length > 0 ? notchWin.summaryData.watchlist[0] : null)
                            text: (wl0 && notchWin.hostWidget) ? notchWin.hostWidget.fmtWatchTicker(wl0) : (notchWin.displayText || "VFEX")
                            color: "#f4f4f6"; font.pixelSize: 9; font.bold: true
                        }
                        Canvas {
                            id: peekSparkCanvas
                            width: parent.width - 120
                            height: 18
                            anchors.verticalCenter: parent.verticalCenter
                            onPaint: {
                                var ctx = getContext("2d")
                                ctx.clearRect(0, 0, width, height)
                                var vals = notchWin.sparkValues
                                var cols = Math.max(10, Math.floor(width / 6))
                                var rows = 5
                                var stepX = width / cols
                                var stepY = height / rows
                                if (!vals || vals.length < 2) {
                                    ctx.fillStyle = "#27272a"
                                    for (var gx = 0; gx < cols; gx++) {
                                        ctx.beginPath(); ctx.arc(gx * stepX + 2, height / 2, 1.2, 0, Math.PI * 2); ctx.fill()
                                    }
                                    return
                                }
                                var rawSlice = vals.slice(-Math.min(vals.length, cols))
                                var sampled = []
                                if (rawSlice.length >= cols) {
                                    sampled = rawSlice.slice(-cols)
                                } else {
                                    for (var si = 0; si < cols; si++) {
                                        var pos = (cols <= 1) ? 0 : (si / (cols - 1)) * (rawSlice.length - 1)
                                        var lo = Math.floor(pos)
                                        var hi = Math.min(rawSlice.length - 1, lo + 1)
                                        var frac = pos - lo
                                        sampled.push(Number(rawSlice[lo]) * (1 - frac) + Number(rawSlice[hi]) * frac)
                                    }
                                }
                                var mn = Number(sampled[0]), mx = Number(sampled[0])
                                for (var i = 1; i < sampled.length; i++) {
                                    var v = Number(sampled[i])
                                    if (v < mn) mn = v
                                    if (v > mx) mx = v
                                }
                                var sp = mx - mn
                                var isUp = Number(sampled[sampled.length - 1]) >= Number(sampled[0])
                                var col = isUp ? "#4ade80" : "#ff2a3c"
                                for (var c = 0; c < sampled.length; c++) {
                                    var norm = sp > 1e-9 ? (Number(sampled[c]) - mn) / sp : 0.5
                                    var lit = Math.min(rows - 1, Math.max(0, Math.round(norm * (rows - 1))))
                                    for (var ry = 0; ry < rows; ry++) {
                                        var fb = (rows - 1) - ry
                                        ctx.fillStyle = (fb === lit) ? col : (fb < lit ? "#27272a" : "#141418")
                                        ctx.beginPath()
                                        ctx.arc(c * stepX + 2, ry * stepY + 1.8, 1.15, 0, Math.PI * 2)
                                        ctx.fill()
                                    }
                                }
                            }
                        }
                    }
                }

                // Footer Quick Actions
                Row {
                    width: parent.width
                    spacing: 6
                    Rectangle {
                        width: (parent.width - 12) * 0.44; height: 22; radius: 11; color: "#f4f4f6"
                        Text { anchors.centerIn: parent; text: "OPEN TERMINAL"; color: "#000000"; font.pixelSize: 8; font.bold: true; font.letterSpacing: 0.8 }
                        MouseArea {
                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: if (notchWin.hostWidget) { notchWin.hostWidget.notchSurfaceHovered = false; notchWin.hostWidget.notchPeekOpen = false; notchWin.hostWidget.refresh(false); notchWin.hostWidget.toggle() }
                        }
                    }
                    Rectangle {
                        width: (parent.width - 12) * 0.32; height: 22; radius: 11; color: "#141418"; border.color: "#ff2a3c"; border.width: 1
                        Text { anchors.centerIn: parent; text: notchWin.isFetching ? "SYNC..." : "LIVE FETCH"; color: "#ff2a3c"; font.pixelSize: 8; font.bold: true; font.letterSpacing: 0.7 }
                        MouseArea {
                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: if (notchWin.hostWidget) notchWin.hostWidget.refresh(true)
                        }
                    }
                    Rectangle {
                        width: (parent.width - 12) * 0.24; height: 22; radius: 11; color: "#141418"; border.color: "#27272a"; border.width: 1
                        Text { anchors.centerIn: parent; text: "NEXT •"; color: "#a1a1aa"; font.pixelSize: 8; font.bold: true; font.letterSpacing: 0.6 }
                        MouseArea {
                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: if (notchWin.hostWidget) { notchWin.hostWidget.rotIndex = notchWin.hostWidget.rotIndex + 1; notchWin.hostWidget.updateBarDisplay() }
                        }
                    }
                }
            }
        }
    }
}
