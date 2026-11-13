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
    readonly property var knownSymbols: ["ASUN", "AXIA", "BIND", "CALD", "ECO", "EDGR", "FCA", "INFR", "INSC", "NTFD", "PHL", "SCIL", "SIM", "WTN"]

    Process {
        id: manualProc
        onExited: function(exitCode) {
            if (exitCode === 0) {
                root.statusError = false
                root.statusMessage = "Saved"
                if (root.hostWidget && typeof root.hostWidget.refresh === "function")
                    root.hostWidget.refresh()
            } else {
                root.statusError = true
                root.statusMessage = "Failed (code " + exitCode + ")"
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

    KeyboardPanel {
        id: panel
        anchorItem: root.anchorItem
        owner: root.hostWidget || root
        bar: root.bar
        open: root.opened
        focusTarget: panel.loadedContent
        contentWidth: panel.fittedContentWidth(Style.space(360))
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
                        text: "↻ Refresh"
                        color: "#89b4fa"
                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                        font.pixelSize: Style.font.body
                        font.bold: true
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.hostWidget && typeof root.hostWidget.refresh === "function")
                                    root.hostWidget.refresh(true)
                            }
                        }
                    }
                }

                Text {
                    width: parent.width
                    visible: (root.summaryData.items || []).length > 0
                    text: {
                        var val = Number(root.summaryData.total_value || 0).toFixed(2)
                        var pnl = Number(root.summaryData.total_pnl || 0)
                        var pct = Number(root.summaryData.total_pnl_pct || 0).toFixed(1)
                        var sign = pnl >= 0 ? "+" : ""
                        return "Portfolio: $" + val + " (" + sign + "$" + pnl.toFixed(2) + " / " + sign + pct + "%)"
                    }
                    color: Number(root.summaryData.total_pnl || 0) >= 0 ? "#a6e3a1" : "#f38ba8"
                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                    font.pixelSize: Style.font.body
                    font.bold: true
                }

                Repeater {
                    model: root.summaryData.items || []
                    delegate: Column {
                        width: contentColumn.width
                        spacing: Style.space(2)
                        Row {
                            width: parent.width
                            spacing: Style.space(6)
                            Text {
                                width: contentColumn.width * 0.22
                                text: modelData.symbol
                                color: "#cdd6f4"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                font.bold: true
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: symbolInput.text = modelData.symbol
                                }
                            }
                            Text {
                                width: contentColumn.width * 0.23
                                text: Number(modelData.shares) + " sh"
                                color: "#cdd6f4"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                            }
                            Text {
                                width: contentColumn.width * 0.25
                                text: "$" + Number(modelData.price).toFixed(4)
                                color: "#cdd6f4"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                            }
                            Text {
                                width: contentColumn.width * 0.30
                                horizontalAlignment: Text.AlignRight
                                text: (modelData.pnl >= 0 ? "+" : "") + "$" + Number(modelData.pnl).toFixed(2)
                                color: modelData.pnl >= 0 ? "#a6e3a1" : "#f38ba8"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                font.bold: true
                            }
                        }
                        Repeater {
                            model: modelData.lots || []
                            delegate: Text {
                                width: contentColumn.width
                                text: "  " + modelData.date + ": " + Number(modelData.shares) + " sh @ $" + Number(modelData.price).toFixed(4)
                                color: "#a6adc8"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.small || Style.font.body
                            }
                        }
                    }
                }

                Column {
                    width: parent.width
                    visible: (root.summaryData.alerts || []).length > 0
                    spacing: Style.space(4)

                    Text {
                        text: "⚠ Triggered Alerts"
                        color: "#f9e2af"
                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                        font.pixelSize: Style.font.body
                        font.bold: true
                    }

                    Repeater {
                        model: root.summaryData.alerts || []
                        delegate: Text {
                            width: contentColumn.width
                            text: "• " + modelData
                            color: "#f9e2af"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.small || Style.font.body
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                Text {
                    width: parent.width
                    visible: (root.summaryData.watchlist || []).length > 0
                    text: "Watchlist"
                    color: "#cdd6f4"
                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                    font.pixelSize: Style.font.body
                    font.bold: true
                }

                Repeater {
                    model: root.summaryData.watchlist || []
                    delegate: Row {
                        width: contentColumn.width
                        Text {
                            width: contentColumn.width * 0.24
                            text: modelData.symbol
                            color: "#cdd6f4"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: symbolInput.text = modelData.symbol
                            }
                        }
                        Canvas {
                            id: sparkline
                            width: contentColumn.width * 0.22
                            height: Style.space(18)
                            anchors.verticalCenter: parent.verticalCenter
                            property var pts: modelData.history || []
                            onPtsChanged: requestPaint()
                            onPaint: {
                                var ctx = getContext("2d")
                                ctx.clearRect(0, 0, width, height)
                                var pts = sparkline.pts
                                if (!pts || pts.length < 2) return
                                var minV = Math.min.apply(null, pts)
                                var maxV = Math.max.apply(null, pts)
                                var span = maxV - minV || 1
                                ctx.strokeStyle = pts[pts.length - 1] >= pts[0] ? "#a6e3a1" : "#f38ba8"
                                ctx.lineWidth = 1.5
                                ctx.beginPath()
                                for (var i = 0; i < pts.length; i++) {
                                    var x = (i / (pts.length - 1)) * (width - 2) + 1
                                    var y = height - 2 - ((pts[i] - minV) / span) * (height - 4)
                                    if (i === 0) ctx.moveTo(x, y)
                                    else ctx.lineTo(x, y)
                                }
                                ctx.stroke()
                            }
                        }
                        Text {
                            width: contentColumn.width * 0.14
                            text: modelData.buy ? "BUY" : ""
                            color: "#a6e3a1"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                            font.bold: true
                        }
                        Text {
                            width: contentColumn.width * 0.30
                            horizontalAlignment: Text.AlignRight
                            text: modelData.price !== null && modelData.price !== undefined ? ("$" + Number(modelData.price).toFixed(4)) : "N/A"
                            color: "#cdd6f4"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                        }
                        Text {
                            width: contentColumn.width * 0.10
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

                Rectangle {
                    width: parent.width
                    height: 1
                    color: "#45475a"
                }

                Column {
                    width: parent.width
                    spacing: Style.space(6)

                    Row {
                        width: parent.width
                        spacing: Style.space(8)

                        Text {
                            text: "Manual Entry"
                            color: "#cdd6f4"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                            font.bold: true
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Row {
                            spacing: Style.space(4)
                            Repeater {
                                model: [
                                    { key: "price", label: "Price" },
                                    { key: "buy", label: "Buy" },
                                    { key: "sell", label: "Sell" },
                                    { key: "watch", label: "+Watch" },
                                    { key: "alert", label: "Alert" }
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
                            width: root.manualMode === "watch" ? parent.width * 0.74 : (root.manualMode === "price" ? parent.width * 0.36 : parent.width * 0.25)
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
                            width: root.manualMode === "price" ? parent.width * 0.38 : parent.width * 0.27
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
                                Text {
                                    anchors.fill: parent
                                    verticalAlignment: Text.AlignVCenter
                                    text: "Price $"
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
                            color: manualProc.running ? "#45475a" : "#a6e3a1"

                            Text {
                                anchors.centerIn: parent
                                text: manualProc.running ? "..." : "Save"
                                color: "#1e1e2e"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                font.bold: true
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                enabled: !manualProc.running
                                onClicked: {
                                    var sym = symbolInput.text.trim().toUpperCase()
                                    var prc = priceInput.text.trim()
                                    var sh = sharesInput.text.trim()
                                    var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                    if (!sym) {
                                        root.statusError = true
                                        root.statusMessage = "Enter symbol"
                                        return
                                    }
                                    if (root.manualMode === "watch") {
                                        manualProc.command = ["python3", script, "watch", "add", sym]
                                    } else if (root.manualMode === "alert") {
                                        if (!prc) {
                                            root.statusError = true
                                            root.statusMessage = "Enter target price"
                                            return
                                        }
                                        manualProc.command = ["python3", script, "alert", "add", sym, root.alertDirection, prc]
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
                                        manualProc.command = ["python3", script, root.manualMode, sym, sh, prc]
                                    }
                                    root.statusMessage = ""
                                    manualProc.running = true
                                    symbolInput.text = ""
                                    sharesInput.text = ""
                                    priceInput.text = ""
                                }
                            }
                        }
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

                    Text {
                        visible: root.statusMessage.length > 0
                        text: root.statusMessage
                        color: root.statusError ? "#f38ba8" : "#a6e3a1"
                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                        font.pixelSize: Style.font.small || Style.font.body
                    }
                }
            }
        }
    }
}
