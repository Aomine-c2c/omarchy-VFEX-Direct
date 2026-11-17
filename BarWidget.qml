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
    property color barForeground: bar ? bar.barForeground : "#cdd6f4"
    property string tooltipBody: "VFEX Direct — Click to open portfolio & watchlist"
    property var summaryData: ({ text: "VFEX --", tooltip: "", class: "neutral", watchlist: [], signals: [] })
    property int rotIndex: 0

    readonly property string cfgBarMode: String(root.setting("barMode", "Rotating"))
    readonly property int cfgRotSec: Math.max(2, Number(root.setting("rotationIntervalSec", 5)))
    readonly property int cfgRefreshSec: Math.max(30, Number(root.setting("refreshIntervalSec", 60)))
    readonly property bool cfgWideLayout: String(root.setting("panelLayout", "Dashboard (Wide)")) !== "Compact"
    readonly property string cfgSignalScope: String(root.setting("signalMarket", "Tracked Only"))
    readonly property string cfgSignalMarket: (cfgSignalScope === "Tracked VFEX Only" || cfgSignalScope === "VFEX Only") ? "vfex" : "all"
    readonly property bool cfgAllMarketSignals: cfgSignalScope === "All Market (VFEX + ZSE)"
    readonly property string cfgTradingGoal: String(root.setting("tradingGoal", "Hybrid (Both)"))
    readonly property string cfgTradingGoalKey: cfgTradingGoal === "Long-Term Compounder" ? "long" : (cfgTradingGoal === "Short-Term Swing" ? "short" : "hybrid")
    readonly property int cfgDiscountPct: Math.max(1, Number(root.setting("discountPct", 3)))
    readonly property bool cfgNotifySignals: root.setting("notifySignals", true) === true
    readonly property string cfgVfexFeeStr: String(root.setting("vfexFeePct", "statutory") || "statutory").trim()
    readonly property string cfgZseFeeStr: String(root.setting("zseFeePct", "statutory") || "statutory").trim()
    readonly property int cfgMaxStockPct: Math.max(5, Number(root.setting("maxStockPct", 25)))
    readonly property int cfgProfitTakePct: Math.max(5, Number(root.setting("profitTakePct", 15)))
    readonly property bool cfgNewsEnabled: root.setting("newsEnabled", true) === true
    readonly property bool cfgAgentEnabled: root.setting("agentEnabled", true) === true
    readonly property real cfgAgentZwgRate: Math.max(1, Number(root.setting("agentZwgRate", "26.5")) || 26.5)

    function panelJsonCmd() {
        var cmd = [
            "python3",
            Qt.resolvedUrl("vfex.py").toString().replace("file://", ""),
            "panel-json",
            "--market", root.cfgSignalMarket,
            "--discount", String(root.cfgDiscountPct),
            "--vfex-fee", root.cfgVfexFeeStr,
            "--zse-fee", root.cfgZseFeeStr,
            "--max-stock-pct", String(root.cfgMaxStockPct),
            "--profit-take-pct", String(root.cfgProfitTakePct),
            "--goal", root.cfgTradingGoalKey,
            "--agent-zwg-rate", String(root.cfgAgentZwgRate)
        ]
        if (root.cfgAllMarketSignals) cmd.push("--all-market")
        if (root.cfgNotifySignals) cmd.push("--notify-signals")
        if (!root.cfgNewsEnabled) cmd.push("--no-news")
        if (!root.cfgAgentEnabled) cmd.push("--no-agent")
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

    function sparkAscii(vals) {
        if (!vals || vals.length < 2) return ""
        var blocks = "▁▂▃▄▅▆▇█"
        var slice = vals.slice(-10)
        var mn = Number(slice[0])
        var mx = Number(slice[0])
        for (var i = 1; i < slice.length; i++) {
            var v = Number(slice[i])
            if (v < mn) mn = v
            if (v > mx) mx = v
        }
        var span = mx - mn
        var out = ""
        for (var j = 0; j < slice.length; j++) {
            var norm = span > 1e-9 ? (Number(slice[j]) - mn) / span : 0.5
            var bi = Math.min(7, Math.max(0, Math.round(norm * 7)))
            out += blocks.charAt(bi)
        }
        return out
    }

    function buildTooltip(parsed) {
        var d = parsed || ({})
        var alerts = d.alerts || []
        var sigs = d.signals || []
        var wl = d.watchlist || []
        var br = d.breadth || ({})
        var lines = []
        if (alerts.length > 0) {
            lines.push("⚠ Alerts:\n" + alerts.join("\n"))
        }
        // Section 1: Market Status + Goal + DTR Regime
        var gMap = ({ "long": "Long-Term", "short": "Short-Term", "hybrid": "Hybrid" })
        var gLabel = gMap[d.trading_goal || root.cfgTradingGoalKey] || "Hybrid"
        var hdr = "VFEX Direct & C-TRADE  •  " + (d.market_status || "Closed")
        if (d.market_countdown) hdr += " (" + d.market_countdown + ")"
        hdr += "\nGoal: " + gLabel
        if ((br.total || 0) > 0) {
            hdr += "  |  Breadth ▲" + (br.advancers || 0) + " ▼" + (br.decliners || 0)
        }
        var vx = ((d.market_intel || ({})).vfex || ({}))
        if (vx.index_value !== undefined) {
            var fn = Number(vx.foreign_net || 0)
            hdr += "\nVFEX " + Number(vx.index_value).toFixed(2) + " (" + (Number(vx.index_chg_pct || 0) >= 0 ? "+" : "") + Number(vx.index_chg_pct || 0).toFixed(2) + "%) • $" + (Number(vx.turnover || 0) / 1000).toFixed(0) + "k • Foreign " + (fn >= 0 ? "+" : "-") + "$" + Math.abs(fn / 1000).toFixed(1) + "k"
        }
        lines.push(hdr)

        // Section 2: Portfolio & Watchlist Compact Digest
        var sec2 = []
        if (d.tooltip) sec2.push(d.tooltip)
        if (wl.length > 0) {
            sec2.push("Watchlist:")
            for (var wi = 0; wi < Math.min(4, wl.length); wi++) {
                var w = wl[wi]
                var sp = root.sparkAscii(w.history)
                sec2.push("  " + root.fmtWatchTicker(w) + (sp ? ("  " + sp) : ""))
            }
        }
        if (sec2.length > 0) lines.push(sec2.join("\n"))

        // Section 3: Top Actionable Signals
        if (sigs.length > 0) {
            var sLines = ["Top Signals:"]
            for (var si = 0; si < Math.min(3, sigs.length); si++) {
                var sg = sigs[si]
                var hz = sg.horizon ? ("[" + sg.horizon + "] ") : ""
                sLines.push("  " + hz + sg.action + " " + sg.symbol + " (" + (sg.score || 0) + "%)")
            }
            lines.push(sLines.join("\n"))
        }

        // Section 4: $100 Agent + Top Catalyst + Controls
        var foot = []
        var pa = d.paper_agent || null
        if (pa && pa.equity_usd !== undefined) {
            var paSign = Number(pa.net_pnl_pct || 0) >= 0 ? "+" : ""
            foot.push("🤖 Agent: $" + Number(pa.equity_usd || 100).toFixed(2) + " (" + paSign + Number(pa.net_pnl_pct || 0).toFixed(1) + "%, " + (pa.positions || []).length + " pos)")
        }
        var nw = d.news_top || d.news || []
        if (nw.length > 0) {
            var n0 = nw[0]
            var nSyms = (n0.symbols || []).length > 0 ? (n0.symbols[0] + ": ") : ""
            foot.push("📰 [" + (n0.category || "Market") + "] " + nSyms + String(n0.title || "").slice(0, 56))
        }
        foot.push("Left=Panel • Scroll=Cycle • Middle=Live Fetch")
        lines.push(foot.join("\n"))
        return lines.join("\n\n")
    }

    function updateBarDisplay() {
        var d = root.summaryData || ({})
        var alerts = d.alerts || []
        var sigs = d.signals || []
        var br = d.breadth || ({})
        var prefix = alerts.length > 0 ? "⚠ " : (d.market_status === "Open" ? "● " : "")
        var baseText = d.text || "VFEX --"
        var defaultFg = root.bar ? root.bar.barForeground : "#cdd6f4"

        if (alerts.length > 0) {
            root.barForeground = "#f9e2af"
        } else if (d.class === "gain") {
            root.barForeground = "#a6e3a1"
        } else if (d.class === "loss") {
            root.barForeground = "#f38ba8"
        } else {
            root.barForeground = defaultFg
        }

        if (root.cfgBarMode === "Compact") {
            root.barText = prefix + baseText
            return
        }
        if (root.cfgBarMode === "Portfolio") {
            var sigSuffix = sigs.length > 0 ? (" • ★" + sigs.length) : ""
            root.barText = prefix + baseText + sigSuffix
            return
        }

        // Rotating mode: Portfolio -> Watched quotes -> Top Signal -> Market Breadth
        var frames = [{ text: baseText, tone: d.class === "gain" ? "#a6e3a1" : (d.class === "loss" ? "#f38ba8" : defaultFg) }]
        var wl = d.watchlist || []
        for (var i = 0; i < wl.length; i++) {
            var chg = wl[i].change_pct
            var tone = (chg !== null && chg !== undefined) ? (Number(chg) > 0 ? "#a6e3a1" : (Number(chg) < 0 ? "#f38ba8" : defaultFg)) : defaultFg
            frames.push({ text: root.fmtWatchTicker(wl[i]), tone: tone })
        }
        if (sigs.length > 0) {
            var top = sigs[0]
            var more = sigs.length > 1 ? (" +" + (sigs.length - 1)) : ""
            frames.push({
                text: "★ " + top.action + " " + top.symbol + " " + (top.score || 0) + "%" + more,
                tone: top.action === "SELL" ? "#f38ba8" : "#a6e3a1"
            })
        }
        if ((br.total || 0) > 0) {
            frames.push({
                text: "MKT ▲" + (br.advancers || 0) + " ▼" + (br.decliners || 0),
                tone: Number(br.advancers || 0) >= Number(br.decliners || 0) ? "#a6e3a1" : "#f38ba8"
            })
        }
        var len = frames.length || 1
        var idx = ((root.rotIndex % len) + len) % len
        root.barText = prefix + frames[idx].text
        root.barForeground = alerts.length > 0 ? "#f9e2af" : frames[idx].tone
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
    onCfgTradingGoalChanged: {
        if (!goalAutoProc.running) goalAutoProc.running = true
    }

    Process {
        id: goalAutoProc
        command: ["python3", Qt.resolvedUrl("vfex.py").toString().replace("file://", ""), "goal", "auto"]
        running: false
        onExited: function() {
            root.refresh(false)
        }
    }

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
                    root.tooltipBody = root.buildTooltip(parsed)
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
        foreground: root.barForeground
        tooltipText: root.tooltipBody
        active: (root.summaryData.alerts || []).length > 0
        onWheelMoved: function(delta) {
            root.rotIndex = delta > 0 ? (root.rotIndex - 1) : (root.rotIndex + 1)
            root.updateBarDisplay()
        }
        onPressed: function(buttonCode) {
            if (buttonCode === Qt.LeftButton) {
                root.refresh()
                root.toggle()
            } else if (buttonCode === Qt.MiddleButton) {
                root.refresh(true)
            } else if (buttonCode === Qt.RightButton) {
                root.rotIndex = root.rotIndex + 1
                root.updateBarDisplay()
            }
        }
    }
}
