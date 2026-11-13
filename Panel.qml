import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

Panel {
    id: root
    moduleName: "io.github.aomine-c2c.vfex-direct"
    manageIpc: false

    property var anchorItem: null
    property var hostWidget: null
    property var summaryData: ({ text: "VFEX --", total_value: 0, total_pnl: 0, total_pnl_pct: 0, items: [], watchlist: [] })

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
        focusTarget: keyCatcher
        contentWidth: panel.fittedContentWidth(Style.space(360))
        contentHeight: panel.fittedContentHeight(content.implicitHeight)

        PanelKeyCatcher {
            id: keyCatcher
            anchors.fill: parent
            onCloseRequested: root.close()
            onTabRequested: function(direction) {
                root.switchPanel(direction)
            }

            Column {
                id: content
                width: parent.width
                spacing: Style.space(10)

                Row {
                    width: parent.width
                    spacing: Style.space(8)

                    Text {
                        text: "VFEX Direct (USD)"
                        color: root.barForeground
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
                        width: content.width
                        spacing: Style.space(6)
                        Text {
                            width: content.width * 0.22
                            text: modelData.symbol
                            color: root.barForeground
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                            font.bold: true
                        }
                        Text {
                            width: content.width * 0.23
                            text: Number(modelData.shares) + " sh"
                            color: root.barForeground
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                        }
                        Text {
                            width: content.width * 0.25
                            text: "$" + Number(modelData.price).toFixed(4)
                            color: root.barForeground
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                        }
                        Text {
                            width: content.width * 0.30
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
                    color: root.barForeground
                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                    font.pixelSize: Style.font.body
                    font.bold: true
                }

                Repeater {
                    model: root.summaryData.watchlist || []
                    delegate: Row {
                        width: content.width
                        Text {
                            width: content.width * 0.5
                            text: modelData.symbol
                            color: root.barForeground
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                        }
                        Text {
                            width: content.width * 0.5
                            horizontalAlignment: Text.AlignRight
                            text: modelData.price !== null && modelData.price !== undefined ? ("$" + Number(modelData.price).toFixed(4)) : "N/A"
                            color: root.barForeground
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                        }
                    }
                }
            }
        }
    }
}
