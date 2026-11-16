import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui

BarWidget {
    id: root
    moduleName: "io.github.aomine-c2c.vfex-direct"

    readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
    readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false
    readonly property bool fetching: fetchProc.running || vfexProc.running

    property string barText: "VFEX --"
    property string tooltipBody: "VFEX Direct — Click to open portfolio & watchlist"
    property var summaryData: ({ text: "VFEX --", tooltip: "", class: "neutral", watchlist: [], signals: [] })
    property int rotIndex: 0

    readonly property string cfgBarMode: String(root.setting("barMode", "Rotating"))
    readonly property int cfgRotSec: Math.max(2, Number(root.setting("rotationIntervalSec", 5)))
    readonly property int cfgRefreshSec: Math.max(30, Number(root.setting("refreshIntervalSec", 60)))
    readonly property bool cfgWideLayout: String(root.setting("panelLayout", "Dashboard (Wide)")) !== "Compact"
    readonly property string cfgSignalMarket: String(root.setting("signalMarket", "VFEX + ZSE")) === "VFEX Only" ? "vfex" : "all"
    readonly property int cfgDiscountPct: Math.max(1, Number(root.setting("discountPct", 3)))
    readonly property bool cfgNotifySignals: root.setting("notifySignals", true) === true
    readonly property real cfgVfexFeePct: Math.max(0, Number(root.setting("vfexFeePct", "0.0")) || 0)
    readonly property real cfgZseFeePct: Math.max(0, Number(root.setting("zseFeePct", "0.0")) || 0)
    readonly property int cfgMaxStockPct: Math.max(5, Number(root.setting("maxStockPct", 25)))
    readonly property int cfgProfitTakePct: Math.max(5, Number(root.setting("profitTakePct", 15)))

    function panelJsonCmd() {
        var cmd = [
            "python3",
            Qt.resolvedUrl("vfex.py").toString().replace("file://", ""),
            "panel-json",
            "--market", root.cfgSignalMarket,
            "--discount", String(root.cfgDiscountPct),
            "--vfex-fee", String(root.cfgVfexFeePct),
            "--zse-fee", String(root.cfgZseFeePct),
            "--max-stock-pct", String(root.cfgMaxStockPct),
            "--profit-take-pct", String(root.cfgProfitTakePct)
        ]
        if (root.cfgNotifySignals) cmd.push("--notify-signals")
        return cmd
    }

    function fmtWatchTicker(item) {
        if (!item) return ""
        var pref = item.currency === "ZWG" ? "ZiG " : "$"
        var p = (item.price !== null && item.price !== undefined) ? (pref + Number(item.price).toFixed(4)) : "--"
        var c = (item.change_pct !== null && item.change_pct !== undefined)
            ? (" " + (Number(item.change_pct) >= 0 ? "▲+" : "▼") + Number(item.change_pct).toFixed(1) + "%")
            : ""
        return item.symbol + " " + p + c
    }

    function updateBarDisplay() {
        var d = root.summaryData || ({})
        var alerts = d.alerts || []
        var sigs = d.signals || []
        var prefix = alerts.length > 0 ? "⚠ " : (d.market_status === "Open" ? "● " : "")
        var baseText = d.text || "VFEX --"

        if (root.cfgBarMode === "Compact") {
            root.barText = prefix + baseText
            return
        }
        if (root.cfgBarMode === "Portfolio") {
            var sigSuffix = sigs.length > 0 ? (" • ★" + sigs.length) : ""
            root.barText = prefix + baseText + sigSuffix
            return
        }

        // Rotating mode: cycle Portfolio -> Watched quotes -> Top Signal
        var frames = [baseText]
        var wl = d.watchlist || []
        for (var i = 0; i < wl.length; i++) {
            frames.push(root.fmtWatchTicker(wl[i]))
        }
        if (sigs.length > 0) {
            var top = sigs[0]
            var more = sigs.length > 1 ? (" (+" + (sigs.length - 1) + ")") : ""
            frames.push("★ " + top.action + " " + top.symbol + more)
        }
        var idx = frames.length > 0 ? (root.rotIndex % frames.length) : 0
        root.barText = prefix + frames[idx]
    }

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

    function refresh(forceFetch) {
        if (forceFetch) {
            if (!fetchProc.running) fetchProc.running = true
            return
        }
        vfexProc.command = root.panelJsonCmd()
        if (!vfexProc.running) vfexProc.running = true
    }

    function injectPanel() {
        if (!panelLoader.item) return
        panelLoader.item.bar = root.bar
        panelLoader.item.anchorItem = button
        panelLoader.item.hostWidget = root
        panelLoader.item.summaryData = root.summaryData
        panelLoader.item.wideLayout = root.cfgWideLayout
    }

    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    onBarChanged: injectPanel()
    onSettingsChanged: {
        root.injectPanel()
        root.updateBarDisplay()
        root.refresh(false)
    }
    onCfgWideLayoutChanged: injectPanel()
    onCfgBarModeChanged: updateBarDisplay()

    Process {
        id: fetchProc
        command: ["python3", Qt.resolvedUrl("vfex.py").toString().replace("file://", ""), "fetch"]
        running: false
        onExited: function() {
            vfexProc.command = root.panelJsonCmd()
            if (!vfexProc.running) vfexProc.running = true
        }
    }

    Process {
        id: vfexProc
        command: root.panelJsonCmd()
        running: true
        stdout: SplitParser {
            onRead: function(data) {
                try {
                    var parsed = JSON.parse(data)
                    root.summaryData = parsed
                    var alerts = parsed.alerts || []
                    var sigs = parsed.signals || []
                    var sigTip = ""
                    if (sigs.length > 0) {
                        var slines = []
                        for (var si = 0; si < Math.min(3, sigs.length); si++) {
                            slines.push("  " + sigs[si].headline)
                        }
                        sigTip = "\n\nTop Trade Signals:\n" + slines.join("\n")
                    }
                    root.tooltipBody = (alerts.length > 0 ? ("Alerts:\n" + alerts.join("\n") + "\n\n") : "") + (parsed.tooltip || "VFEX Direct") + sigTip
                    root.updateBarDisplay()
                    if (panelLoader.item) {
                        panelLoader.item.summaryData = parsed
                        panelLoader.item.wideLayout = root.cfgWideLayout
                    }
                } catch (e) {
                }
            }
        }
    }

    Timer {
        interval: root.cfgRefreshSec * 1000
        running: true
        repeat: true
        onTriggered: root.refresh(false)
    }

    Timer {
        interval: root.cfgRotSec * 1000
        running: root.cfgBarMode === "Rotating"
        repeat: true
        onTriggered: {
            root.rotIndex = root.rotIndex + 1
            root.updateBarDisplay()
        }
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
        active: (root.summaryData.alerts || []).length > 0
        onPressed: function(buttonCode) {
            if (buttonCode === Qt.LeftButton) {
                root.refresh()
                root.toggle()
            }
        }
    }
}
