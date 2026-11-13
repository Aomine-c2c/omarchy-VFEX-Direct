import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui

BarWidget {
    id: root
    moduleName: "io.github.aomine-c2c.vfex-direct"

    readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
    readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false

    property string barText: "VFEX --"
    property string tooltipBody: "VFEX Direct — Click to open portfolio & watchlist"
    property var summaryData: ({ text: "VFEX --", tooltip: "", class: "neutral" })

    function open() {
        if (panelLoader.item) panelLoader.item.open()
    }

    function close() {
        if (panelLoader.item) panelLoader.item.close()
    }

    function toggle() {
        if (panelLoader.item) panelLoader.item.toggle()
    }

    function closeForPopoutSwitch() {
        if (panelLoader.item) panelLoader.item.closeForPopoutSwitch()
    }

    function refresh() {
        if (!vfexProc.running) vfexProc.running = true
    }

    function injectPanel() {
        if (!panelLoader.item) return
        panelLoader.item.bar = root.bar
        panelLoader.item.anchorItem = button
        panelLoader.item.hostWidget = root
        panelLoader.item.summaryData = root.summaryData
    }

    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    onBarChanged: injectPanel()

    Process {
        id: vfexProc
        command: ["python3", Qt.resolvedUrl("vfex.py").toString().replace("file://", ""), "panel-json"]
        running: true
        stdout: SplitParser {
            onRead: function(data) {
                try {
                    var parsed = JSON.parse(data)
                    root.summaryData = parsed
                    root.barText = parsed.text || "VFEX --"
                    root.tooltipBody = parsed.tooltip || "VFEX Direct"
                    if (panelLoader.item) panelLoader.item.summaryData = parsed
                } catch (e) {
                }
            }
        }
    }

    Timer {
        interval: 60000
        running: true
        repeat: true
        onTriggered: root.refresh()
    }

    Loader {
        id: panelLoader
        active: true
        source: Qt.resolvedUrl("Panel.qml")
        visible: false
        onLoaded: {
            root.injectPanel()
            Qt.callLater(root.injectPanel)
        }
    }

    WidgetButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: root.barText
        tooltipText: root.tooltipBody
        onPressed: function(buttonCode) {
            if (buttonCode === Qt.LeftButton) {
                root.refresh()
                root.toggle()
            }
        }
    }
}
