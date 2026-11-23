import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
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
    property var activeFrame: ({ kind: "portfolio", tag: "VFEX", value: "$--", delta: "", tone: "neutral", adv: 0, dec: 0 })
    property bool notchPeekOpen: false
    property bool notchSurfaceHovered: false

    Timer {
        id: notchCloseTimer
        interval: 240
        onTriggered: {
            if (!barHover.hovered && !button.tooltipHovered && !root.notchSurfaceHovered) {
                root.notchPeekOpen = false
            }
        }
    }

    function updateNotchPeekState() {
        var want = root.cfgNothingNotch && !root.opened && (barHover.hovered || button.tooltipHovered || root.notchSurfaceHovered)
        if (want) {
            notchCloseTimer.stop()
            root.notchPeekOpen = true
        } else {
            notchCloseTimer.restart()
        }
        root.injectNotch()
    }

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
    readonly property bool cfgNothingNotch: root.setting("nothingNotchEnabled", true) !== false
    readonly property bool cfgNothingMatrixBar: root.setting("nothingMatrixBar", true) !== false

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
        var c = ""
        if (item.change_pct !== null && item.change_pct !== undefined) {
            var ch = Number(item.change_pct)
            c = " " + (ch >= 0 ? ("+" + Math.abs(ch).toFixed(1) + "% ▲") : (Math.abs(ch).toFixed(1) + "% ▼"))
        }
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
        var isGainClass = (d.class === "profit" || d.class === "gain")
        var isLossClass = (d.class === "loss")
        var pfVal = Number(d.total_value || 0) > 0 ? ("$" + Number(d.total_value || 0).toFixed(2)) : ((d.zwg_value || 0) > 0 ? ("ZiG " + Number(d.zwg_value).toFixed(2)) : baseText.replace(/^VFEX\s*/, ""))
        var pfPnl = Number(d.total_value || 0) > 0 ? Number(d.total_pnl || 0) : 0
        var pfDelta = Number(d.total_value || 0) > 0 ? ((pfPnl >= 0 ? "+" : "-") + "$" + Math.abs(pfPnl).toFixed(2)) : ""
        var pfTone = alerts.length > 0 ? "warn" : (isGainClass ? "gain" : (isLossClass ? "loss" : "neutral"))
        var pfFrame = {
            kind: "portfolio",
            tag: "VFEX",
            value: pfVal || "--",
            delta: pfDelta,
            tone: pfTone,
            text: baseText,
            fg: isGainClass ? "#a6e3a1" : (isLossClass ? "#f38ba8" : defaultFg)
        }

        if (alerts.length > 0) {
            root.barForeground = "#f9e2af"
        } else if (isGainClass) {
            root.barForeground = "#a6e3a1"
        } else if (isLossClass) {
            root.barForeground = "#f38ba8"
        } else {
            root.barForeground = defaultFg
        }

        if (root.cfgBarMode === "Compact") {
            root.barText = prefix + baseText
            root.activeFrame = pfFrame
            return
        }
        if (root.cfgBarMode === "Portfolio") {
            var sigSuffix = sigs.length > 0 ? (" • ★" + sigs.length) : ""
            root.barText = prefix + baseText + sigSuffix
            root.activeFrame = ({
                kind: "portfolio",
                tag: "VFEX",
                value: pfFrame.value,
                delta: sigs.length > 0 ? (pfDelta + " • ★" + sigs.length) : pfDelta,
                tone: pfFrame.tone
            })
            return
        }

        // Rotating mode: Portfolio -> Watched quotes -> Top Signal -> Market Breadth
        var frames = [pfFrame]
        var wl = d.watchlist || []
        for (var i = 0; i < wl.length; i++) {
            var wItem = wl[i]
            var chg = wItem.change_pct
            var wPref = wItem.currency === "ZWG" ? "ZiG " : "$"
            var wPx = (wItem.price !== null && wItem.price !== undefined) ? (wPref + Number(wItem.price).toFixed(4)) : "--"
            var wDelta = ""
            var wToneName = "neutral"
            if (chg !== null && chg !== undefined) {
                var cNum = Number(chg)
                wDelta = (cNum >= 0 ? "+" : "") + Math.abs(cNum).toFixed(1) + "% " + (cNum >= 0 ? "▲" : "▼")
                wToneName = cNum > 0 ? "gain" : (cNum < 0 ? "loss" : "neutral")
            }
            var tone = (chg !== null && chg !== undefined) ? (Number(chg) > 0 ? "#a6e3a1" : (Number(chg) < 0 ? "#f38ba8" : defaultFg)) : defaultFg
            frames.push({
                kind: "quote",
                tag: String(wItem.symbol || ""),
                value: wPx,
                delta: wDelta,
                tone: wToneName,
                text: root.fmtWatchTicker(wItem),
                fg: tone
            })
        }
        if (sigs.length > 0) {
            var top = sigs[0]
            var more = sigs.length > 1 ? (" +" + (sigs.length - 1)) : ""
            frames.push({
                kind: "signal",
                tag: top.action,
                value: top.symbol,
                delta: String(top.score || 0) + "%" + more,
                tone: top.action === "SELL" ? "loss" : "gain",
                text: "★ " + top.action + " " + top.symbol + " " + (top.score || 0) + "%" + more,
                fg: top.action === "SELL" ? "#f38ba8" : "#a6e3a1"
            })
        }
        if ((br.total || 0) > 0) {
            frames.push({
                kind: "breadth",
                tag: "MKT",
                value: "",
                delta: "",
                adv: Number(br.advancers || 0),
                dec: Number(br.decliners || 0),
                tone: Number(br.advancers || 0) >= Number(br.decliners || 0) ? "gain" : "loss",
                text: "MKT " + (br.advancers || 0) + "▲ / " + (br.decliners || 0) + "▼",
                fg: Number(br.advancers || 0) >= Number(br.decliners || 0) ? "#a6e3a1" : "#f38ba8"
            })
        }
        var len = frames.length || 1
        var idx = ((root.rotIndex % len) + len) % len
        root.barText = prefix + frames[idx].text
        root.barForeground = alerts.length > 0 ? "#f9e2af" : frames[idx].fg
        root.activeFrame = frames[idx]
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

    function injectNotch() {
        if (!notchLoader.item) return
        notchLoader.item.bar = root.bar
        notchLoader.item.hostWidget = root
        notchLoader.item.summaryData = root.summaryData
        notchLoader.item.displayText = root.barText
        notchLoader.item.displayColor = root.barForeground
        notchLoader.item.enabled = root.cfgNothingNotch
        notchLoader.item.hostOpened = root.opened
        notchLoader.item.isFetching = root.fetching
        notchLoader.item.barHovered = barHover.hovered || button.tooltipHovered
        notchLoader.item.hovered = true
    }

    readonly property real matrixCapsuleWidth: Math.max(Style.space(84), Math.ceil(nothingBarRow.implicitWidth) + 22)
    implicitWidth: root.cfgNothingMatrixBar ? root.matrixCapsuleWidth : button.implicitWidth
    implicitHeight: button.implicitHeight
    onBarChanged: { injectPanel(); injectNotch() }
    onBarTextChanged: injectNotch()
    onBarForegroundChanged: injectNotch()
    onOpenedChanged: {
        if (root.opened) {
            notchCloseTimer.stop()
            root.notchPeekOpen = false
        }
        injectNotch()
    }
    onFetchingChanged: injectNotch()
    onSettingsChanged: {
        root.injectPanel()
        root.injectNotch()
        root.updateBarDisplay()
        root.refresh(false)
    }
    onCfgNothingNotchChanged: injectNotch()
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
                    root.injectNotch()
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

    Loader {
        id: notchLoader
        active: root.cfgNothingNotch && root.notchPeekOpen && !root.opened
        source: Qt.resolvedUrl("NothingNotch.qml")
        onLoaded: {
            root.injectNotch()
            Qt.callLater(root.injectNotch)
        }
    }

    WidgetButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: root.barText
        labelVisible: !root.cfgNothingMatrixBar
        fixedWidth: root.cfgNothingMatrixBar ? root.matrixCapsuleWidth : -1
        foreground: root.barForeground
        tooltipText: root.cfgNothingNotch ? "" : root.tooltipBody
        active: (root.summaryData.alerts || []).length > 0
        onTooltipHoveredChanged: root.updateNotchPeekState()

        HoverHandler {
            id: barHover
            onHoveredChanged: root.updateNotchPeekState()
        }

        Rectangle {
            id: nothingBarCapsule
            z: -1
            visible: root.cfgNothingMatrixBar && root.barText !== ""
            clip: true
            anchors.centerIn: parent
            width: Math.max(24, parent.width - 2)
            height: Math.max(20, parent.height - 6)
            radius: height / 2
            scale: button.pressScale
            color: "#050507"
            border.color: (root.summaryData.alerts || []).length > 0 ? "#ff2a3c" : "#27272a"
            border.width: 1

            Row {
                id: nothingBarRow
                anchors.centerIn: parent
                spacing: 6
                property var af: (root.activeFrame || ({}))

                // Status LED Pixel Dot
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 5
                    height: 5
                    radius: 2.5
                    color: (root.summaryData.market_status === "Open" || (root.summaryData.alerts || []).length > 0 || root.fetching) ? "#ff2a3c" : "#52525b"
                }

                // Category / Ticker Tag
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: String(nothingBarRow.af.tag || "") !== ""
                    text: String(nothingBarRow.af.tag || "VFEX")
                    color: nothingBarRow.af.kind === "signal"
                        ? (nothingBarRow.af.tone === "loss" ? "#ff2a3c" : "#4ade80")
                        : "#a1a1aa"
                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                    font.pixelSize: Math.max(9, Style.font.body - 1)
                    font.bold: true
                }

                // Crisp Monochrome Readout ($9.43, $0.2481, ZIMW)
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: String(nothingBarRow.af.value || "") !== ""
                    text: String(nothingBarRow.af.value || "")
                    color: "#f4f4f6"
                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                    font.pixelSize: Style.font.body
                    font.bold: true
                }

                // Breadth Mode: Separate Green Advancers + Mini Split Meter + Red Decliners
                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: nothingBarRow.af.kind === "breadth"
                    spacing: 4
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Number(nothingBarRow.af.adv || 0) + "▲"
                        color: "#4ade80"
                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                        font.pixelSize: Math.max(9, Style.font.body - 1)
                        font.bold: true
                    }
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        property real aN: Number(nothingBarRow.af.adv || 0)
                        property real dN: Number(nothingBarRow.af.dec || 0)
                        width: 18
                        height: 4
                        radius: 2
                        color: "#ff2a3c"
                        Rectangle {
                            width: (parent.aN + parent.dN) > 0 ? ((parent.aN / (parent.aN + parent.dN)) * parent.width) : (parent.width * 0.5)
                            height: parent.height
                            radius: 2
                            color: "#4ade80"
                        }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Number(nothingBarRow.af.dec || 0) + "▼"
                        color: "#ff2a3c"
                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                        font.pixelSize: Math.max(9, Style.font.body - 1)
                        font.bold: true
                    }
                }

                // Delta Pill (+$0.93 emerald / 0.2% ▼ red / signal score)
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: String(nothingBarRow.af.delta || "") !== "" && nothingBarRow.af.kind !== "breadth"
                    width: deltaPillTxt.implicitWidth + 8
                    height: deltaPillTxt.implicitHeight + 3
                    radius: height / 2
                    color: nothingBarRow.af.tone === "gain" ? "#0c2216" : (nothingBarRow.af.tone === "loss" ? "#260b10" : "#18181b")
                    Text {
                        id: deltaPillTxt
                        anchors.centerIn: parent
                        text: String(nothingBarRow.af.delta || "")
                        color: nothingBarRow.af.tone === "gain" ? "#4ade80" : (nothingBarRow.af.tone === "loss" ? "#ff2a3c" : "#e4e4e7")
                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                        font.pixelSize: Math.max(8, Style.font.body - 2)
                        font.bold: true
                    }
                }
            }
        }
        onWheelMoved: function(delta) {
            root.rotIndex = delta > 0 ? (root.rotIndex - 1) : (root.rotIndex + 1)
            root.updateBarDisplay()
        }
        onPressed: function(buttonCode) {
            if (buttonCode === Qt.LeftButton) {
                notchCloseTimer.stop()
                root.notchSurfaceHovered = false
                root.notchPeekOpen = false
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
