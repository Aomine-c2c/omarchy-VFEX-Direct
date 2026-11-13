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
    property string statusMessage: ""
    property bool statusError: false

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
                                    root.hostWidget.refresh()
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
                    delegate: Row {
                        width: contentColumn.width
                        spacing: Style.space(6)
                        Text {
                            width: contentColumn.width * 0.22
                            text: modelData.symbol
                            color: "#cdd6f4"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                            font.bold: true
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
                            width: contentColumn.width * 0.35
                            text: modelData.symbol
                            color: "#cdd6f4"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                        }
                        Text {
                            width: contentColumn.width * 0.25
                            text: modelData.buy ? "BUY" : ""
                            color: "#a6e3a1"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                            font.bold: true
                        }
                        Text {
                            width: contentColumn.width * 0.40
                            horizontalAlignment: Text.AlignRight
                            text: modelData.price !== null && modelData.price !== undefined ? ("$" + Number(modelData.price).toFixed(4)) : "N/A"
                            color: "#cdd6f4"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
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
                                    { key: "sell", label: "Sell" }
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
                            width: root.manualMode === "price" ? parent.width * 0.36 : parent.width * 0.25
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
                            visible: root.manualMode !== "price"
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
                                    if (!sym || !prc) {
                                        root.statusError = true
                                        root.statusMessage = "Enter symbol and price"
                                        return
                                    }
                                    var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                    if (root.manualMode === "price") {
                                        manualProc.command = ["python3", script, "price", sym, prc]
                                    } else {
                                        if (!sh) {
                                            root.statusError = true
                                            root.statusMessage = "Enter shares"
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
