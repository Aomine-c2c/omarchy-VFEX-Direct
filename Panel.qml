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
    property bool watchAddOpen: false
    property string watchAddSym: ""
    property bool priceEditOpen: false
    property string priceEditSym: ""
    property string priceEditVal: ""
    property bool alertAddOpen: false
    property string alertAddSym: ""
    property string alertAddDir: "above"
    property string alertAddPrice: ""
    property bool stopEditOpen: false
    property string stopEditSym: ""
    property string stopEditPct: "10"
    property bool targetAddOpen: false
    property string targetAddSym: ""
    property string targetAddPct: "15"
    property bool divAddOpen: false
    property string divAddSym: ""
    property string divAddAmt: ""
    property string divAddDate: ""
    property string dcaBudgetText: "100"
    property string alertDirection: "above"
    property string statusMessage: ""
    property bool statusError: false
    property string lastManualError: ""
    property bool pendingClearInputs: false
    property bool calendarOpen: false
    property int calYear: (new Date()).getFullYear()
    property int calMonth: (new Date()).getMonth()
    property bool wideLayout: true
    property bool fullPageMode: true
    property bool accountDrawerOpen: false
    property string activeTab: "overview"
    property string signalFilter: "all"
    property string newsFilter: "all"
    property string buyHorizonTag: "auto"
    property string screenerFilter: "all"
    property string screenerViewMode: "heatmap"
    property string screenerSortKey: "signal"
    property bool screenerSortDesc: true
    property string screenerQuery: ""
    property string noteSymText: ""
    property string noteBodyText: ""
    property real projDcaMonthly: 50
    property int projCagrPct: 12
    property bool showMa20Overlay: true
    property bool showBeOverlay: true
    property bool showOptLimOverlay: true
    property int hoveredEquityIdx: -1
    property int hoveredProjIdx: -1
    property string toastMessage: ""
    property bool credsExpanded: false
    property string activeProvider: "ctrade"
    property string ctradeEmailText: ""
    property string ctradePassText: ""
    property string mfaOtpText: ""
    property string ctradeStatusMessage: ""
    property bool ctradeStatusError: false
    property var ctradeStatusData: root.summaryData.account || ({})
    property var donutCanvasRef: null
    property var equityCanvasRef: null
    property var btGaugeCanvasRef: null
    property var projCanvasRef: null
    property var agentEquityCanvasRef: null
    property string selectedContractId: ""
    property int hoveredAgentEqIdx: -1
    property string noteFilePath: ""
    property string noteRawText: ""
    property bool notePasteMode: false
    property var notePreviewData: null
    property string notePreviewErr: ""
    property string noteImportTag: "core"

    function activeProviderInfo() {
        var map = root.summaryData.accounts || ({})
        return map[root.activeProvider] || ({})
    }

    function connectedPortalsCount() {
        return Number(root.summaryData.connected_count || 0)
    }
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

    function fmtInt(v) {
        return String(Math.round(Number(v || 0))).replace(/\B(?=(\d{3})+(?!\d))/g, ",")
    }

    function fmtVol(v) {
        var n = Number(v || 0)
        if (n >= 1000000) return (n / 1000000).toFixed(2) + " Million"
        return fmtInt(n)
    }

    function fmtSourceLabel(s) {
        var txt = String(s || "")
        if (txt === "VFEX-D") return "VFEX Direct"
        if (txt === "ZSE-D") return "ZSE Direct"
        return txt
    }

    function fmtAgeLabel(s) {
        var txt = String(s || "").trim()
        if (!txt) return ""
        var m = txt.match(/^(\d+)([hdm])\s+ago$/i)
        if (!m) return txt
        var n = parseInt(m[1], 10)
        var unit = m[2].toLowerCase()
        var word = unit === "h" ? (n === 1 ? "hour" : "hours") : (unit === "d" ? (n === 1 ? "day" : "days") : (n === 1 ? "minute" : "minutes"))
        return n + " " + word + " ago"
    }

    function fmtCountdown(s) {
        var txt = String(s || "").trim()
        if (!txt) return ""
        return txt.replace(/(\d+)h\s*/gi, function(_, n) { return n + (Number(n) === 1 ? " hour " : " hours ") })
                  .replace(/(\d+)m\b/gi, function(_, n) { return Number(n) === 0 ? "" : (n + (Number(n) === 1 ? " minute" : " minutes")) })
                  .replace(/\s+/g, " ").trim()
    }

    function fmtReasonText(s) {
        return String(s || "")
            .replace(/\bDTR Vol\b/g, "Daily Turnover")
            .replace(/\bTop(\d+)\s+Cap\b/g, "Top $1 Market Cap")
            .replace(/\bOversold RSI\b/g, "Oversold Relative Strength Index")
            .replace(/\bOverbought RSI\b/g, "Overbought Relative Strength Index")
            .replace(/\bRSI\b/g, "Relative Strength Index")
            .replace(/\bSMA20\b/g, "20-Day Moving Average")
    }

    function activeQuote() {
        if (!root.chartSymbol) return null
        var lists = [root.summaryData.watchlist || [], root.summaryData.items || [], root.summaryData.screener || []]
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

    function runCliCommand(args, clearInputs) {
        if (manualProc.running || dcaProc.running) return
        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
        var cmd = ["python3", script]
        for (var i = 0; i < args.length; i++) cmd.push(String(args[i]))
        root.statusMessage = ""
        root.lastManualError = ""
        root.pendingClearInputs = Boolean(clearInputs)
        manualProc.command = cmd
        manualProc.running = true
    }

    function runDcaBudget(budgetRaw) {
        if (manualProc.running || dcaProc.running) return
        var prc = String(budgetRaw || "").replace(/^\s*\$?/, "").replace(/,/g, "").trim()
        if (!prc || Number(prc) <= 0) {
            root.statusError = true
            root.statusMessage = "Enter dollar budget"
            return
        }
        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
        root.statusMessage = ""
        root.dcaPlanData = null
        dcaProc.command = ["python3", script, "dca", prc, "--json"]
        dcaProc.running = true
    }

    function quickTrade(mode, sym) {
        if (mode === "alert") {
            root.alertAddSym = sym
            root.alertAddOpen = true
            root.statusMessage = ""
            return
        }
        if (mode === "stop") {
            root.stopEditSym = sym
            root.stopEditOpen = true
            root.statusMessage = ""
            return
        }
        root.manualMode = mode === "sell" ? "sell" : "buy"
        root.statusMessage = ""
        root.calendarOpen = false
        root.symText = sym
        if (root.sharesInputRef) root.sharesInputRef.forceActiveFocus()
    }

    function applySignal(sig) {
        if (!sig) return
        root.activeTab = "overview"
        root.chartSymbol = sig.symbol
        root.hoveredCandleIdx = -1
        root.manualMode = sig.action === "SELL" ? "sell" : "buy"
        if (sig.action !== "SELL")
            root.buyHorizonTag = sig.horizon === "CORE" ? "core" : (sig.horizon === "SWING" ? "swing" : "auto")
        root.statusMessage = ""
        root.dcaPlanData = null
        root.calendarOpen = false
        root.symText = sig.symbol
        if (Number(sig.recommended_shares || 0) > 0)
            root.sharesText = String(sig.recommended_shares)
        root.priceText = Number(sig.optimal_limit || sig.limit_price || sig.price || 0).toFixed(4)
        if (root.sharesInputRef) root.sharesInputRef.forceActiveFocus()
    }

    function activeCandles() {
        if (!root.chartSymbol) return []
        var lists = [root.summaryData.watchlist || [], root.summaryData.items || [], root.summaryData.screener || []]
        for (var li = 0; li < lists.length; li++) {
            var arr = lists[li]
            for (var i = 0; i < arr.length; i++) {
                if (arr[i].symbol === root.chartSymbol)
                    return arr[i].candles || []
            }
        }
        return []
    }

    function activeHolding() {
        if (!root.chartSymbol) return null
        var arr = root.summaryData.items || []
        for (var i = 0; i < arr.length; i++) {
            if (arr[i].symbol === root.chartSymbol) return arr[i]
        }
        return null
    }

    function effectiveTradingGoal() {
        return String(root.summaryData.trading_goal || (root.hostWidget && root.hostWidget.cfgTradingGoalKey) || "hybrid")
    }

    function tradingGoalLabel(g) {
        if (g === "long") return "◆ Long-Term"
        if (g === "short") return "⚡ Short-Term"
        return "◎ Hybrid"
    }

    function filteredSignals() {
        var sigs = root.summaryData.signals || []
        var flt = root.signalFilter || "all"
        if (flt === "all") return sigs
        var out = []
        for (var i = 0; i < sigs.length; i++) {
            var s = sigs[i]
            if (flt === "core" && s.horizon !== "CORE") continue
            if (flt === "swing" && s.horizon !== "SWING") continue
            if (flt === "buy" && s.action !== "BUY") continue
            if (flt === "sell" && s.action !== "SELL") continue
            if (flt === "strong" && Number(s.score || 0) < 40) continue
            out.push(s)
        }
        return out
    }

    function newsSentimentColor(sent) {
        if (sent === "Bullish") return "#a6e3a1"
        if (sent === "Caution") return "#f38ba8"
        return "#89b4fa"
    }

    function newsSentimentBg(sent) {
        if (sent === "Bullish") return "#1f3a27"
        if (sent === "Caution") return "#3d2229"
        return "#1e2e4a"
    }

    function filteredNews() {
        var rows = root.summaryData.news || []
        var flt = root.newsFilter || "all"
        if (flt === "all") return rows
        var out = []
        for (var i = 0; i < rows.length; i++) {
            var n = rows[i]
            if (flt === "tracked" && !n.tracked) continue
            if (flt === "bullish" && n.sentiment !== "Bullish") continue
            if (flt === "caution" && n.sentiment !== "Caution") continue
            if (flt === "official" && !n.official) continue
            out.push(n)
        }
        return out
    }

    function openNewsUrl(url) {
        if (url && String(url).length > 0) {
            Qt.openUrlExternally(String(url))
        }
    }

    function heatmapTileColor(chg) {
        if (chg === null || chg === undefined) return "#1e1e2e"
        var c = Number(chg)
        if (c >= 4.0) return "#1e462a"
        if (c >= 1.5) return "#1f3a27"
        if (c > 0.05) return "#1b2e24"
        if (c <= -4.0) return "#4a1f28"
        if (c <= -1.5) return "#3d1f26"
        if (c < -0.05) return "#2d1d24"
        return "#1e1e2e"
    }

    function isOwnedSymbol(sym) {
        var items = root.summaryData.items || []
        for (var i = 0; i < items.length; i++) if (items[i].symbol === sym) return true
        return false
    }

    function isWatchedSymbol(sym) {
        var wl = root.summaryData.watchlist || []
        for (var i = 0; i < wl.length; i++) if (wl[i].symbol === sym) return true
        return false
    }

    function filteredScreener() {
        var rows = root.summaryData.screener || []
        var q = (root.screenerQuery || "").trim().toUpperCase()
        var flt = root.screenerFilter || "all"
        var out = []
        for (var i = 0; i < rows.length; i++) {
            var r = rows[i]
            if (q && String(r.symbol).indexOf(q) === -1 && String(r.company_name || "").toUpperCase().indexOf(q) === -1) continue
            if (flt === "vfex" && r.currency !== "USD") continue
            if (flt === "zse" && r.currency !== "ZWG") continue
            if (flt === "signals" && !(Number(r.signal_score || 0) > 0)) continue
            if (flt === "gainers" && !(Number(r.change_pct || 0) > 0)) continue
            if (flt === "losers" && !(Number(r.change_pct || 0) < 0)) continue
            if (flt === "liquid" && !(Number(r.liquidity_score || 0) >= 50)) continue
            out.push(r)
        }
        var sk = root.screenerSortKey || "signal"
        var desc = root.screenerSortDesc ? -1 : 1
        out.sort(function(a, b) {
            if (sk === "symbol") return String(a.symbol).localeCompare(String(b.symbol)) * (-desc)
            if (sk === "price") return (Number(a.price || 0) - Number(b.price || 0)) * desc
            if (sk === "change") return (Number(a.change_pct || 0) - Number(b.change_pct || 0)) * desc
            if (sk === "liquidity") return (Number(a.liquidity_score || 0) - Number(b.liquidity_score || 0)) * desc
            if (sk === "spread") return (Number(a.spread_pct || 999) - Number(b.spread_pct || 999)) * (-desc)
            var diff = (Number(a.signal_score || 0) - Number(b.signal_score || 0)) * desc
            if (diff !== 0) return diff
            return (Number(a.liquidity_score || 0) - Number(b.liquidity_score || 0)) * (-1)
        })
        return out
    }

    function repaintCanvases() {
        if (root.candleCanvasRef) root.candleCanvasRef.requestPaint()
        if (root.donutCanvasRef) root.donutCanvasRef.requestPaint()
        if (root.equityCanvasRef) root.equityCanvasRef.requestPaint()
        if (root.btGaugeCanvasRef) root.btGaugeCanvasRef.requestPaint()
        if (root.projCanvasRef) root.projCanvasRef.requestPaint()
        if (root.agentEquityCanvasRef) root.agentEquityCanvasRef.requestPaint()
    }

    function runAgentCli(cliArgs) {
        if (manualProc.running) return
        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
        var cmd = ["python3", script, "agent"]
        for (var i = 0; i < cliArgs.length; i++) cmd.push(cliArgs[i])
        manualProc.command = cmd
        manualProc.running = true
    }

    onSummaryDataChanged: {
        if (!root.chartSymbol) {
            var items = root.summaryData.items || []
            var wl = root.summaryData.watchlist || []
            var sigs = root.summaryData.signals || []
            if (items.length > 0) root.chartSymbol = items[0].symbol
            else if (wl.length > 0) root.chartSymbol = wl[0].symbol
            else if (sigs.length > 0) root.chartSymbol = sigs[0].symbol
        }
        repaintCanvases()
    }
    onChartSymbolChanged: {
        if (root.candleCanvasRef) root.candleCanvasRef.requestPaint()
        if (root.chartSymbol) {
            root.noteSymText = root.chartSymbol
            root.noteBodyText = String(((root.summaryData.notes || ({}))[root.chartSymbol]) || "")
        }
    }
    onChartModeChanged: if (root.candleCanvasRef) root.candleCanvasRef.requestPaint()
    onHoveredCandleIdxChanged: if (root.candleCanvasRef) root.candleCanvasRef.requestPaint()
    onShowMa20OverlayChanged: if (root.candleCanvasRef) root.candleCanvasRef.requestPaint()
    onShowBeOverlayChanged: if (root.candleCanvasRef) root.candleCanvasRef.requestPaint()
    onShowOptLimOverlayChanged: if (root.candleCanvasRef) root.candleCanvasRef.requestPaint()
    onHoveredEquityIdxChanged: if (root.equityCanvasRef) root.equityCanvasRef.requestPaint()
    onProjDcaMonthlyChanged: if (root.projCanvasRef) root.projCanvasRef.requestPaint()
    onProjCagrPctChanged: if (root.projCanvasRef) root.projCanvasRef.requestPaint()
    onHoveredProjIdxChanged: if (root.projCanvasRef) root.projCanvasRef.requestPaint()
    onHoveredAgentEqIdxChanged: if (root.agentEquityCanvasRef) root.agentEquityCanvasRef.requestPaint()
    onActiveTabChanged: Qt.callLater(repaintCanvases)

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
        id: notePreviewProc
        property string lastErr: ""
        stdout: SplitParser {
            onRead: function(line) {
                try {
                    root.notePreviewData = JSON.parse(line)
                    root.notePreviewErr = ""
                } catch (e) {
                }
            }
        }
        stderr: SplitParser {
            onRead: function(line) {
                var t = line.trim()
                if (t) notePreviewProc.lastErr = t
            }
        }
        onExited: function(exitCode) {
            if (exitCode !== 0) {
                root.notePreviewData = null
                root.notePreviewErr = notePreviewProc.lastErr || ("Could not parse contract note (code " + exitCode + ")")
            }
            notePreviewProc.lastErr = ""
        }
    }

    Process {
        id: manualProc
        property string lastOut: ""
        stdout: SplitParser {
            onRead: function(line) {
                var t = line.trim()
                if (t) manualProc.lastOut = t
            }
        }
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
                if (manualProc.lastOut && manualProc.lastOut.indexOf("Imported") === 0) {
                    root.notePreviewData = null
                    root.notePreviewErr = ""
                    root.noteFilePath = ""
                    root.noteRawText = ""
                }
                root.pendingClearInputs = false
                root.calendarOpen = false
                root.statusError = false
                root.statusMessage = manualProc.lastOut || "Saved"
                if (manualProc.lastOut) root.toastMessage = manualProc.lastOut
                manualProc.lastOut = ""
                if (root.hostWidget && typeof root.hostWidget.refresh === "function")
                    root.hostWidget.refresh()
            } else {
                root.pendingClearInputs = false
                root.statusError = true
                root.statusMessage = root.lastManualError ? root.lastManualError : ("Failed (code " + exitCode + ")")
                manualProc.lastOut = ""
            }
        }
    }

    Process {
        id: ctradeProc
        property string secret: ""
        property string lastErr: ""
        property string lastOut: ""
        stdinEnabled: false
        stdout: SplitParser {
            onRead: function(line) {
                var t = line.trim()
                if (t) ctradeProc.lastOut = t
            }
        }
        stderr: SplitParser {
            onRead: function(line) {
                var t = line.trim()
                if (t) ctradeProc.lastErr = t
            }
        }
        onStarted: {
            if (stdinEnabled && secret.length > 0) {
                write(secret + "\n")
                secret = ""
                stdinEnabled = false
            }
        }
        onExited: function(exitCode) {
            ctradeProc.secret = ""
            ctradeProc.stdinEnabled = false
            if (exitCode === 0) {
                root.ctradePassText = ""
                root.mfaOtpText = ""
                root.ctradeStatusError = false
                root.ctradeStatusMessage = ctradeProc.lastOut || "C-TRADE synced"
                if (root.hostWidget && typeof root.hostWidget.refresh === "function")
                    root.hostWidget.refresh()
            } else {
                root.ctradeStatusError = true
                root.ctradeStatusMessage = ctradeProc.lastErr || ("Sync failed (code " + exitCode + ")")
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
        if (!sym) {
            root.statusError = true
            root.statusMessage = "Enter stock symbol"
            return
        }
        if (!sh || !prc) {
            root.statusError = true
            root.statusMessage = "Enter shares and price"
            return
        }
        var mode = root.manualMode === "sell" ? "sell" : "buy"
        var tradeCmd = [mode, sym, sh, prc]
        if (dt) { tradeCmd.push("--date"); tradeCmd.push(dt) }
        if (mode === "buy" && root.buyHorizonTag !== "auto") { tradeCmd.push("--tag"); tradeCmd.push(root.buyHorizonTag) }
        root.runCliCommand(tradeCmd, true)
    }

    KeyboardPanel {
        id: panel
        anchorItem: root.anchorItem
        owner: root.hostWidget || root
        bar: root.bar
        open: root.opened
        focusTarget: panel.loadedContent
        margin: root.fullPageMode ? Style.space(6) : Style.gapsOut
        gap: root.fullPageMode ? Style.space(4) : Style.gapsOut
        centerOnBar: root.fullPageMode
        contentWidth: root.fullPageMode
            ? (panel.availableCardWidth > 0 ? panel.availableCardWidth : panel.fittedContentWidth(Style.space(1280)))
            : panel.fittedContentWidth(Style.space(root.wideLayout ? 980 : 440))
        contentHeight: root.fullPageMode
            ? (panel.availableCardHeight > 0 ? panel.availableCardHeight : panel.fittedContentHeight(panel.loadedContentHeight))
            : panel.fittedContentHeight(panel.loadedContentHeight)

        content: PanelKeyCatcher {
            id: keyCatcher
            implicitHeight: contentColumn.implicitHeight
            anchors.fill: parent
            onCloseRequested: root.close()
            onTabRequested: function(direction) {
                root.switchPanel(direction)
            }

            Flickable {
                id: mainFlick
                anchors.fill: parent
                contentWidth: width
                contentHeight: contentColumn.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds

            Column {
                id: contentColumn
                width: mainFlick.width
                spacing: Style.space(8)

                // === WORKSTATION HEADER & LIVE MARKET TELEMETRY RIBBON ===
                Rectangle {
                    width: parent.width
                    height: hdrInnerCol.implicitHeight + Style.space(12)
                    radius: 8
                    color: "#181825"
                    border.color: "#313244"
                    border.width: 1

                    Column {
                        id: hdrInnerCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(6) }
                        spacing: Style.space(6)

                        Row {
                            width: parent.width
                            spacing: Style.space(8)

                            Rectangle {
                                id: brandMark
                                width: Style.space(22)
                                height: Style.space(22)
                                radius: 5
                                color: "#243b2c"
                                border.color: "#a6e3a1"
                                border.width: 1
                                anchors.verticalCenter: parent.verticalCenter
                                Text {
                                    anchors.centerIn: parent
                                    text: "◈"
                                    color: "#a6e3a1"
                                    font.pixelSize: Style.font.body
                                    font.bold: true
                                }
                            }

                            Column {
                                width: Math.max(Style.space(180), parent.width - brandMark.width - mktBadge.width - acctToggleBtn.width - refreshBtn.width - pageSizeToggleBtn.width - closePanelBtn.width - Style.space(44))
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 0
                                Text {
                                    text: "VFEX & ZSE Trading Terminal"
                                    color: "#cdd6f4"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.subtitle
                                    font.bold: true
                                    elide: Text.ElideRight
                                    width: parent.width
                                }
                                Text {
                                    text: {
                                        var upd = root.summaryData.last_updated || "--"
                                        var x = root.summaryData.portfolio_xirr_pct
                                        var xStr = (x !== null && x !== undefined) ? (" • Annualized Return " + (Number(x) >= 0 ? "+" : "") + Number(x).toFixed(0) + "%") : ""
                                        var cs = ""
                                        if (root.effectiveTradingGoal() === "hybrid" && (Number(root.summaryData.core_value || 0) > 0 || Number(root.summaryData.swing_value || 0) > 0)) {
                                            cs = " • Core Hold $" + Number(root.summaryData.core_value || 0).toFixed(0) + " / Swing Trade $" + Number(root.summaryData.swing_value || 0).toFixed(0)
                                        }
                                        return "Synced " + upd + xStr + cs
                                    }
                                    color: "#6c7086"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                    elide: Text.ElideRight
                                    width: parent.width
                                }
                            }

                            Rectangle {
                                id: mktBadge
                                anchors.verticalCenter: parent.verticalCenter
                                width: mktBadgeTxt.implicitWidth + Style.space(10)
                                height: mktBadgeTxt.implicitHeight + Style.space(5)
                                radius: 4
                                color: (root.summaryData.market_status === "Open") ? "#1f3a27" : "#1e1e2e"
                                border.color: (root.summaryData.market_status === "Open") ? "#a6e3a1" : "#45475a"
                                border.width: 1
                                Text {
                                    id: mktBadgeTxt
                                    anchors.centerIn: parent
                                    text: {
                                        var st = root.summaryData.market_status || "Closed"
                                        var cd = root.summaryData.market_countdown || ""
                                        return (st === "Open" ? "● Market Open" : "○ Market Closed") + (cd ? (" • " + root.fmtCountdown(cd)) : "")
                                    }
                                    color: (root.summaryData.market_status === "Open") ? "#a6e3a1" : "#a6adc8"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                    font.bold: true
                                }
                            }

                            Rectangle {
                                id: acctToggleBtn
                                anchors.verticalCenter: parent.verticalCenter
                                width: acctToggleTxt.implicitWidth + Style.space(10)
                                height: Style.space(22)
                                radius: 4
                                color: root.activeTab === "ledger" ? "#89b4fa" : "#313244"
                                border.color: root.connectedPortalsCount() > 0 ? "#a6e3a1" : "#45475a"
                                border.width: 1
                                Text {
                                    id: acctToggleTxt
                                    anchors.centerIn: parent
                                    text: root.connectedPortalsCount() > 0 ? ("⚙ " + root.connectedPortalsCount() + "/3 Portals Linked") : "⚙ Broker Portals"
                                    color: root.activeTab === "ledger" ? "#1e1e2e" : (root.connectedPortalsCount() > 0 ? "#a6e3a1" : "#cdd6f4")
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                    font.bold: true
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        root.activeTab = "ledger"
                                        root.accountDrawerOpen = true
                                    }
                                }
                            }

                            Rectangle {
                                id: refreshBtn
                                anchors.verticalCenter: parent.verticalCenter
                                readonly property bool busy: root.hostWidget && root.hostWidget.fetching === true
                                width: refTxt.implicitWidth + Style.space(10)
                                height: Style.space(22)
                                radius: 4
                                color: "#313244"
                                border.color: busy ? "#45475a" : "#89b4fa"
                                border.width: 1
                                Text {
                                    id: refTxt
                                    anchors.centerIn: parent
                                    text: parent.busy ? "↻ Refreshing..." : "↻ Refresh Market"
                                    color: parent.busy ? "#a6adc8" : "#89b4fa"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                    font.bold: true
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    enabled: !parent.busy
                                    onClicked: {
                                        if (root.hostWidget && typeof root.hostWidget.refresh === "function")
                                            root.hostWidget.refresh(true)
                                    }
                                }
                            }

                            Rectangle {
                                id: pageSizeToggleBtn
                                anchors.verticalCenter: parent.verticalCenter
                                width: pstTxt.implicitWidth + Style.space(10)
                                height: Style.space(22)
                                radius: 4
                                color: "#313244"
                                border.color: "#45475a"
                                border.width: 1
                                Text {
                                    id: pstTxt
                                    anchors.centerIn: parent
                                    text: root.fullPageMode ? "⊟ Compact Popup" : "⊞ Full Screen"
                                    color: "#cdd6f4"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                    font.bold: true
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        root.fullPageMode = !root.fullPageMode
                                        Qt.callLater(root.repaintCanvases)
                                    }
                                }
                            }

                            Rectangle {
                                id: closePanelBtn
                                anchors.verticalCenter: parent.verticalCenter
                                width: cpTxt.implicitWidth + Style.space(10)
                                height: Style.space(22)
                                radius: 4
                                color: "#2d1d24"
                                border.color: "#f38ba8"
                                border.width: 1
                                Text {
                                    id: cpTxt
                                    anchors.centerIn: parent
                                    text: "× Close"
                                    color: "#f38ba8"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                    font.bold: true
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.close()
                                }
                            }
                        }

                        // Dedicated Strategy Goal + Full Portal Status Row (prevents header title truncation)
                        Row {
                            width: parent.width
                            spacing: Style.space(6)

                            // 1-Click Adaptive Strategy Goal Pill
                            Rectangle {
                                id: strategyGoalPill
                                anchors.verticalCenter: parent.verticalCenter
                                width: goalPillTxt.implicitWidth + Style.space(12)
                                height: Style.space(20)
                                radius: 4
                                property string gKey: root.effectiveTradingGoal()
                                color: gKey === "long" ? "#1f3a27" : (gKey === "short" ? "#272138" : "#1e2e4a")
                                border.color: gKey === "long" ? "#a6e3a1" : (gKey === "short" ? "#cba6f7" : "#89b4fa")
                                border.width: 1
                                Text {
                                    id: goalPillTxt
                                    anchors.centerIn: parent
                                    text: root.tradingGoalLabel(parent.gKey)
                                    color: parent.gKey === "long" ? "#a6e3a1" : (parent.gKey === "short" ? "#cba6f7" : "#89b4fa")
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                    font.bold: true
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    enabled: !manualProc.running
                                    onClicked: {
                                        var g = parent.gKey
                                        var nxt = g === "hybrid" ? "long" : (g === "long" ? "short" : "hybrid")
                                        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                        if (nxt === "long") {
                                            root.screenerFilter = "vfex"; root.screenerSortKey = "signal"
                                        } else if (nxt === "short") {
                                            root.screenerFilter = "liquid"; root.screenerSortKey = "spread"
                                        } else {
                                            root.screenerFilter = "all"; root.screenerSortKey = "signal"
                                        }
                                        manualProc.command = ["python3", script, "goal", nxt]
                                        manualProc.running = true
                                    }
                                }
                            }

                            Row {
                                id: portalDotsRow
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: Style.space(4)
                                Repeater {
                                    model: [
                                        { key: "ctrade", label: "C-TRADE" },
                                        { key: "vfex_direct", label: "VFEX Direct" },
                                        { key: "zse_direct", label: "ZSE Direct" }
                                    ]
                                    delegate: Rectangle {
                                        property var pInfo: ((root.summaryData.accounts || ({}))[modelData.key]) || ({})
                                        width: pDotLbl.implicitWidth + 10
                                        height: Style.space(20)
                                        radius: 4
                                        color: Boolean(pInfo.connected) ? "#1f3a27" : (Boolean(pInfo.mfa_pending) ? "#2b261d" : "#1e1e2e")
                                        border.color: Boolean(pInfo.connected) ? "#a6e3a1" : (Boolean(pInfo.mfa_pending) ? "#f9e2af" : "#45475a")
                                        border.width: 1
                                        Text {
                                            id: pDotLbl
                                            anchors.centerIn: parent
                                            text: (Boolean(parent.pInfo.connected) ? "● " : "○ ") + modelData.label
                                            color: Boolean(parent.pInfo.connected) ? "#a6e3a1" : (Boolean(parent.pInfo.mfa_pending) ? "#f9e2af" : "#6c7086")
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                            font.bold: true
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                root.activeProvider = modelData.key
                                                root.activeTab = "ledger"
                                                root.accountDrawerOpen = true
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Compact Market Breadth Ribbon + Signal Win-Rate Strip
                        Row {
                            width: parent.width
                            visible: ((root.summaryData.breadth || ({})).total || 0) > 0
                            spacing: Style.space(8)
                            property var br: root.summaryData.breadth || ({ advancers: 0, unchanged: 1, decliners: 0, total: 1 })
                            property real totBr: Math.max(1, Number(br.total || 1))

                            Text {
                                width: Style.space(260)
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Breadth: " + (parent.br.advancers || 0) + " Up • " + (parent.br.unchanged || 0) + " Flat • " + (parent.br.decliners || 0) + " Down"
                                color: "#a6adc8"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                elide: Text.ElideRight
                            }

                            Row {
                                width: parent.width - Style.space(486)
                                height: 6
                                spacing: 2
                                anchors.verticalCenter: parent.verticalCenter
                                Rectangle { width: Math.max(2, (Number(parent.parent.br.advancers || 0) / parent.parent.totBr) * (parent.width - 4)); height: 6; radius: 3; color: "#a6e3a1" }
                                Rectangle { width: Math.max(2, (Number(parent.parent.br.unchanged || 0) / parent.parent.totBr) * (parent.width - 4)); height: 6; radius: 3; color: "#45475a" }
                                Rectangle { width: Math.max(2, (Number(parent.parent.br.decliners || 0) / parent.parent.totBr) * (parent.width - 4)); height: 6; radius: 3; color: "#f38ba8" }
                            }

                            Text {
                                width: Style.space(210)
                                horizontalAlignment: Text.AlignRight
                                anchors.verticalCenter: parent.verticalCenter
                                text: {
                                    var bt = root.summaryData.signal_backtest || ({})
                                    return "90-Day Win Rate " + Number(bt.win_rate_pct || 0).toFixed(0) + "% (" + (bt.total_logged || 0) + " signals)"
                                }
                                color: Number((root.summaryData.signal_backtest || ({})).avg_return_pct || 0) >= 0 ? "#a6e3a1" : "#f38ba8"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                font.bold: true
                            }
                        }

                        // Institutional Exchange Daily Regime Pulse (Index • Turnover • Foreign Net Flow)
                        Row {
                            width: parent.width
                            visible: Boolean(((root.summaryData.market_intel || ({})).vfex || ({})).index_value)
                            spacing: Style.space(8)
                            property var vx: ((root.summaryData.market_intel || ({})).vfex || ({}))
                            property var zs: ((root.summaryData.market_intel || ({})).zse || ({}))

                            Text {
                                width: parent.width * 0.58
                                text: {
                                    var ch = Number(parent.vx.index_chg_pct || 0)
                                    var fn = Number(parent.vx.foreign_net || 0)
                                    var fnTxt = fn === 0 ? "Foreign Net $0" : ("Foreign Net " + (fn > 0 ? "+" : "-") + "$" + root.fmtInt(Math.abs(fn)))
                                    return "VFEX Index " + Number(parent.vx.index_value || 0).toFixed(2) + " (" + (ch >= 0 ? "+" : "") + ch.toFixed(2) + "%) • Turnover $" + root.fmtInt(parent.vx.turnover || 0) + " (" + (parent.vx.num_trades || 0) + " trades) • " + fnTxt
                                }
                                color: Number(parent.vx.foreign_net || 0) < 0 ? "#f9e2af" : "#89dceb"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: 9
                                elide: Text.ElideRight
                            }

                            Text {
                                width: parent.width * 0.42 - Style.space(8)
                                horizontalAlignment: Text.AlignRight
                                visible: Boolean(parent.zs.turnover)
                                text: "ZSE Turnover ZiG " + (Number(parent.zs.turnover || 0) / 1000000).toFixed(2) + " Million (" + (parent.zs.num_trades || 0) + " trades)"
                                color: "#a6adc8"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: 9
                                elide: Text.ElideLeft
                            }
                        }

                        // Benchmark Sector Index & Market Capitalisation Pulse
                        Flow {
                            width: parent.width
                            spacing: Style.space(8)
                            visible: (((root.summaryData.market_intel || ({})).indices || []).length > 0) || Number((((root.summaryData.market_intel || ({})).vfex || ({})).total_market_cap) || 0) > 0
                            Repeater {
                                model: ((root.summaryData.market_intel || ({})).indices || []).slice(0, 4)
                                delegate: Text {
                                    text: modelData.name + ": " + Number(modelData.level || 0).toFixed(2) + (Number(modelData.one_month || 0) > 0 ? (" (1-Month " + Number(modelData.one_month).toFixed(2) + ")") : "")
                                    color: Number(modelData.change || 0) >= 0 ? "#89dceb" : "#f38ba8"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: 9
                                }
                            }
                            Text {
                                property real vmcap: Number((((root.summaryData.market_intel || ({})).vfex || ({})).total_market_cap) || 0)
                                visible: vmcap > 0
                                text: "VFEX Market Capitalisation: $" + (vmcap / 1000000000).toFixed(2) + " Billion"
                                color: "#a6e3a1"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: 9
                                font.bold: true
                            }
                        }
                    }
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

                // === SEGMENTED VECTOR TAB STRIP WITH COUNT BADGES ===
                Grid {
                    id: topTabBar
                    width: parent.width
                    columns: 5
                    columnSpacing: Style.space(5)
                    Repeater {
                        model: [
                            { key: "overview", icon: "▤", label: "Overview", badge: (root.summaryData.signals || []).length, badgeCol: "#a6e3a1" },
                            { key: "screener", icon: "⊞", label: "Market Screener", badge: (root.summaryData.screener || []).length, badgeCol: "#89b4fa" },
                            { key: "analytics", icon: "◔", label: "Analysis & 5-Year", badge: ((root.summaryData.signal_backtest || ({})).total_logged || 0), badgeCol: "#cba6f7" },
                            { key: "ledger", icon: "☰", label: root.wideLayout ? "Ledger & Portals" : "Ledger", badge: (root.summaryData.trades || []).length + (root.summaryData.triggered_alerts || []).length, badgeCol: (root.summaryData.triggered_alerts || []).length > 0 ? "#f9e2af" : "#89dceb" },
                            { key: "agent", icon: "🤖", label: root.wideLayout ? "Auto-Trader" : "Agent", badge: (((root.summaryData.paper_agent || ({})).positions || []).length), badgeCol: Number(((root.summaryData.paper_agent || ({})).net_pnl_usd || 0)) >= 0 ? "#a6e3a1" : "#f38ba8" }
                        ]
                        delegate: Rectangle {
                            width: (topTabBar.width - Style.space(5) * 4) / 5
                            height: Style.space(28)
                            radius: 6
                            color: root.activeTab === modelData.key ? "#242436" : "#181825"
                            border.color: root.activeTab === modelData.key ? "#89b4fa" : "#313244"
                            border.width: 1

                            Rectangle {
                                visible: root.activeTab === modelData.key
                                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 8; rightMargin: 8 }
                                height: 2
                                radius: 1
                                color: "#89b4fa"
                            }

                            Row {
                                anchors.centerIn: parent
                                spacing: Style.space(5)
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.icon
                                    color: root.activeTab === modelData.key ? "#89b4fa" : "#6c7086"
                                    font.pixelSize: Style.font.body
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.label
                                    color: root.activeTab === modelData.key ? "#cdd6f4" : "#a6adc8"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small || Style.font.body
                                    font.bold: root.activeTab === modelData.key
                                }
                                Rectangle {
                                    visible: Number(modelData.badge || 0) > 0
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: bNumTxt.implicitWidth + 8
                                    height: bNumTxt.implicitHeight + 2
                                    radius: 4
                                    color: "#313244"
                                    Text {
                                        id: bNumTxt
                                        anchors.centerIn: parent
                                        text: String(modelData.badge)
                                        color: modelData.badgeCol
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                        font.bold: true
                                    }
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.activeTab = modelData.key
                            }
                        }
                    }
                }

                // === TAB 1: RESPONSIVE 3-COLUMN FULL-PAGE WORKSTATION / 2-COLUMN POPUP ===
                Flow {
                    id: mainGrid
                    visible: root.activeTab === "overview"
                    width: parent.width
                    spacing: Style.space(10)

                    Column {
                        id: leftPaneCol
                        width: root.fullPageMode
                            ? Math.floor((mainGrid.width - Style.space(22)) * 0.33)
                            : (root.wideLayout ? Math.floor((mainGrid.width - Style.space(12)) * 0.54) : mainGrid.width)
                        spacing: Style.space(10)

                Rectangle {
                    id: portfolioCard
                    width: parent.width
                    visible: (root.summaryData.items || []).length > 0 || Number(root.summaryData.wallet_cash_usd || 0) > 0 || Number(root.summaryData.wallet_cash_zwg || 0) > 0
                    height: portfolioCol.implicitHeight + Style.space(16)
                    radius: 8
                    color: "#181825"
                    border.color: "#313244"
                    border.width: 1

                    Column {
                        id: portfolioCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                        spacing: Style.space(7)

                        Row {
                            width: parent.width
                            spacing: Style.space(10)

                            // Enlarged 92x92 Donut Chart with Center Overlay Label
                            Item {
                                width: Style.space(92)
                                height: Style.space(92)
                                anchors.verticalCenter: parent.verticalCenter

                                Canvas {
                                    id: allocDonutCanvas
                                    anchors.fill: parent
                                    onWidthChanged: requestPaint()
                                    Component.onCompleted: {
                                        root.donutCanvasRef = allocDonutCanvas
                                        requestPaint()
                                    }
                                    onPaint: {
                                        var ctx = getContext("2d")
                                        if (width <= 0 || height <= 0) return
                                        ctx.clearRect(0, 0, width, height)
                                        var arr = root.summaryData.items || []
                                        var cx = width / 2
                                        var cy = height / 2
                                        var rad = Math.min(cx, cy) - 7
                                        ctx.beginPath()
                                        ctx.arc(cx, cy, rad, 0, Math.PI * 2)
                                        ctx.strokeStyle = "#313244"
                                        ctx.lineWidth = 10
                                        ctx.stroke()
                                        if (arr.length === 0) return
                                        var tot = 0
                                        for (var i = 0; i < arr.length; i++) tot += Math.max(0, Number(arr[i].value || 0))
                                        if (tot <= 0) return
                                        var palette = ["#89b4fa", "#a6e3a1", "#f9e2af", "#cba6f7", "#fab387", "#94e2d5"]
                                        var ang = -Math.PI / 2
                                        for (var j = 0; j < arr.length; j++) {
                                            var v = Math.max(0, Number(arr[j].value || 0))
                                            if (v <= 0) continue
                                            var slice = (v / tot) * Math.PI * 2
                                            ctx.beginPath()
                                            ctx.arc(cx, cy, rad, ang, ang + slice - (arr.length > 1 ? 0.04 : 0))
                                            ctx.strokeStyle = palette[j % palette.length]
                                            ctx.lineWidth = 10
                                            ctx.stroke()
                                            ang += slice
                                        }
                                    }
                                }

                                Column {
                                    anchors.centerIn: parent
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: String((root.summaryData.items || []).length) + ((root.summaryData.items || []).length === 1 ? " holding" : " holdings")
                                        color: "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                        font.bold: true
                                    }
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: "$" + Number(root.summaryData.total_value || 0).toFixed(0)
                                        color: "#6c7086"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                    }
                                }
                            }

                            Column {
                                width: parent.width - Style.space(92) - Style.space(10)
                                spacing: Style.space(3)
                                anchors.verticalCenter: parent.verticalCenter

                                Row {
                                    width: parent.width
                                    Text {
                                        width: parent.width - pnlBadge.width
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "$" + Number(root.summaryData.total_value || 0).toFixed(2)
                                        color: "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: (Style.font.subtitle || 16) + 3
                                        font.bold: true
                                    }
                                    Rectangle {
                                        id: pnlBadge
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: pnlBadgeText.implicitWidth + Style.space(10)
                                        height: pnlBadgeText.implicitHeight + Style.space(5)
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

                                // 2x2 Key Performance & Cost Grid
                                Grid {
                                    width: parent.width
                                    columns: 2
                                    columnSpacing: Style.space(6)
                                    rowSpacing: 2
                                    Text {
                                        width: (parent.width - Style.space(6)) / 2
                                        text: "Cost: $" + Number(root.summaryData.total_cost || 0).toFixed(2)
                                        color: "#a6adc8"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                    }
                                    Text {
                                        width: (parent.width - Style.space(6)) / 2
                                        text: {
                                            var x = root.summaryData.portfolio_xirr_pct
                                            return "Annual Return: " + (x !== null && x !== undefined ? ((Number(x) >= 0 ? "+" : "") + Number(x).toFixed(1) + "%") : "--")
                                        }
                                        color: Number(root.summaryData.portfolio_xirr_pct || 0) >= 0 ? "#a6e3a1" : "#f38ba8"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                    }
                                    Text {
                                        width: (parent.width - Style.space(6)) / 2
                                        visible: Number(root.summaryData.total_dividends || 0) > 0 || Number(root.summaryData.realized_pnl || 0) !== 0
                                        text: "Dividends: $" + Number(root.summaryData.total_dividends || 0).toFixed(2) + " • Realized: " + (Number(root.summaryData.realized_pnl || 0) >= 0 ? "+" : "") + "$" + Number(root.summaryData.realized_pnl || 0).toFixed(2)
                                        color: "#89dceb"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        width: (parent.width - Style.space(6)) / 2
                                        visible: Number(root.summaryData.wallet_cash_usd || 0) > 0 || Number(root.summaryData.wallet_cash_zwg || 0) > 0
                                        text: {
                                            var u = Number(root.summaryData.wallet_cash_usd || 0)
                                            var z = Number(root.summaryData.wallet_cash_zwg || 0)
                                            var out = []
                                            if (u > 0) out.push("$" + u.toFixed(2))
                                            if (z > 0) out.push("ZiG " + z.toFixed(2))
                                            return "Cash: " + out.join(" ")
                                        }
                                        color: "#94e2d5"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                        elide: Text.ElideRight
                                    }
                                }

                                // Allocation Legend Bars vs Max Risk Cap
                                Repeater {
                                    model: (root.summaryData.items || []).slice(0, 4)
                                    delegate: Row {
                                        width: parent.width
                                        spacing: Style.space(4)
                                        property var palette: ["#89b4fa", "#a6e3a1", "#f9e2af", "#cba6f7"]
                                        property real wPct: Number(modelData.alloc_pct || 0)
                                        property real capPct: Number((root.summaryData.fee_config || ({})).max_stock_pct || 25)
                                        Text {
                                            width: Style.space(38)
                                            text: modelData.symbol
                                            color: parent.palette[index % parent.palette.length]
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }
                                        Item {
                                            width: parent.width - Style.space(84)
                                            height: Style.space(10)
                                            Rectangle {
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: parent.width
                                                height: 5
                                                radius: 2
                                                color: "#313244"
                                                Rectangle {
                                                    width: Math.min(parent.width, Math.max(2, Math.min(1, parent.parent.parent.wPct / 100.0) * parent.width))
                                                    height: parent.height
                                                    radius: 2
                                                    color: parent.parent.parent.wPct > parent.parent.parent.capPct ? "#f9e2af" : parent.parent.parent.palette[index % parent.parent.parent.palette.length]
                                                }
                                                Rectangle {
                                                    x: Math.min(parent.width - 2, (parent.parent.parent.capPct / 100.0) * parent.width)
                                                    y: -2; width: 1.5; height: 9; color: "#f38ba8"
                                                }
                                            }
                                        }
                                        Text {
                                            width: Style.space(38)
                                            horizontalAlignment: Text.AlignRight
                                            text: parent.wPct.toFixed(0) + "%"
                                            color: parent.wPct > parent.capPct ? "#f9e2af" : "#a6adc8"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            width: parent.width
                            visible: Boolean(root.summaryData.fee_config && Number(root.summaryData.fee_config.vfex_fee_pct || 0) > 0)
                            text: {
                                var fcfg = root.summaryData.fee_config || ({})
                                var np = Number(root.summaryData.net_total_pnl || 0)
                                var npct = Number(root.summaryData.net_total_pnl_pct || 0)
                                var sign = np >= 0 ? "+" : ""
                                var fLbl = fcfg.vfex_statutory ? "statutory fees (Morgan & Co)" : (Number(fcfg.vfex_fee_pct || 0).toFixed(1) + "%/side fees")
                                return "Net after " + fLbl + ": " + sign + "$" + np.toFixed(2) + " (" + sign + npct.toFixed(1) + "%)"
                            }
                            color: Number(root.summaryData.net_total_pnl || 0) >= 0 ? "#94e2d5" : "#f38ba8"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                        }

                        // 90px Interactive Hover Equity vs Cost Curve
                        Column {
                            width: parent.width
                            visible: (root.summaryData.equity_curve || []).length >= 2
                            spacing: 2

                            Row {
                                width: parent.width
                                Text {
                                    width: parent.width * 0.45
                                    text: "VALUE VERSUS COST"
                                    color: "#6c7086"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                    font.bold: true
                                }
                                Text {
                                    width: parent.width * 0.55
                                    horizontalAlignment: Text.AlignRight
                                    text: {
                                        var pts = root.summaryData.equity_curve || []
                                        if (pts.length === 0) return ""
                                        var idx = (root.hoveredEquityIdx >= 0 && root.hoveredEquityIdx < pts.length) ? root.hoveredEquityIdx : (pts.length - 1)
                                        var p = pts[idx]
                                        return p.date + " • $" + Number(p.value).toFixed(2) + " versus $" + Number(p.cost).toFixed(2)
                                    }
                                    color: "#cdd6f4"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                }
                            }

                            Canvas {
                                id: equityCanvas
                                width: parent.width
                                height: root.fullPageMode ? Style.space(128) : Style.space(86)
                                onWidthChanged: requestPaint()
                                Component.onCompleted: {
                                    root.equityCanvasRef = equityCanvas
                                    requestPaint()
                                }
                                onPaint: {
                                    var ctx = getContext("2d")
                                    if (width <= 0 || height <= 0) return
                                    ctx.clearRect(0, 0, width, height)
                                    var pts = root.summaryData.equity_curve || []
                                    if (!pts || pts.length < 2) return
                                    var minV = Number(pts[0].cost)
                                    var maxV = Number(pts[0].value)
                                    for (var i = 0; i < pts.length; i++) {
                                        minV = Math.min(minV, Number(pts[i].cost), Number(pts[i].value))
                                        maxV = Math.max(maxV, Number(pts[i].cost), Number(pts[i].value))
                                    }
                                    if (maxV === minV) { maxV += 1; minV = Math.max(0, minV - 1) }
                                    var span = maxV - minV || 1
                                    var pL = 38, pR = 6, pT = 6, pB = 6
                                    var pW = Math.max(10, width - pL - pR)
                                    var pH = Math.max(10, height - pT - pB)
                                    function xAt(idx) { return pL + (idx / (pts.length - 1)) * pW }
                                    function yAt(v) { return pT + pH - ((v - minV) / span) * pH }

                                    // Grid & Y labels
                                    ctx.font = "9px sans-serif"
                                    ctx.textBaseline = "middle"
                                    var lvls = [maxV, (maxV + minV) / 2, minV]
                                    for (var g = 0; g < lvls.length; g++) {
                                        var gy = yAt(lvls[g])
                                        ctx.save()
                                        ctx.strokeStyle = "#242436"
                                        ctx.lineWidth = 1
                                        ctx.beginPath()
                                        ctx.moveTo(pL, gy); ctx.lineTo(width - pR, gy); ctx.stroke()
                                        ctx.restore()
                                        ctx.fillStyle = "#6c7086"
                                        ctx.fillText("$" + lvls[g].toFixed(1), 0, gy)
                                    }

                                    // Cost basis dashed line
                                    ctx.save()
                                    ctx.strokeStyle = "#6c7086"
                                    ctx.lineWidth = 1.2
                                    ctx.setLineDash([3, 3])
                                    ctx.beginPath()
                                    for (var c = 0; c < pts.length; c++) {
                                        if (c === 0) ctx.moveTo(xAt(c), yAt(Number(pts[c].cost)))
                                        else ctx.lineTo(xAt(c), yAt(Number(pts[c].cost)))
                                    }
                                    ctx.stroke()
                                    ctx.restore()

                                    // Value curve + gradient fill
                                    var up = Number(pts[pts.length - 1].value) >= Number(pts[pts.length - 1].cost)
                                    var col = up ? "#a6e3a1" : "#f38ba8"
                                    var grad = ctx.createLinearGradient(0, pT, 0, pT + pH)
                                    grad.addColorStop(0, up ? "rgba(166, 227, 161, 0.30)" : "rgba(243, 139, 168, 0.30)")
                                    grad.addColorStop(1, "rgba(0, 0, 0, 0.0)")
                                    ctx.fillStyle = grad
                                    ctx.beginPath()
                                    ctx.moveTo(xAt(0), pT + pH)
                                    for (var k = 0; k < pts.length; k++) ctx.lineTo(xAt(k), yAt(Number(pts[k].value)))
                                    ctx.lineTo(xAt(pts.length - 1), pT + pH)
                                    ctx.closePath()
                                    ctx.fill()

                                    ctx.strokeStyle = col
                                    ctx.lineWidth = 2
                                    ctx.beginPath()
                                    for (var m = 0; m < pts.length; m++) {
                                        if (m === 0) ctx.moveTo(xAt(m), yAt(Number(pts[m].value)))
                                        else ctx.lineTo(xAt(m), yAt(Number(pts[m].value)))
                                    }
                                    ctx.stroke()

                                    // Hover crosshair dot
                                    if (root.hoveredEquityIdx >= 0 && root.hoveredEquityIdx < pts.length) {
                                        var hx = xAt(root.hoveredEquityIdx)
                                        var hy = yAt(Number(pts[root.hoveredEquityIdx].value))
                                        ctx.save()
                                        ctx.strokeStyle = "#89b4fa"
                                        ctx.lineWidth = 1
                                        ctx.setLineDash([2, 2])
                                        ctx.beginPath()
                                        ctx.moveTo(hx, pT); ctx.lineTo(hx, pT + pH); ctx.stroke()
                                        ctx.restore()
                                        ctx.fillStyle = col
                                        ctx.beginPath(); ctx.arc(hx, hy, 3.5, 0, Math.PI * 2); ctx.fill()
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onPositionChanged: function(mouse) {
                                        var pts = root.summaryData.equity_curve || []
                                        if (pts.length < 2) { root.hoveredEquityIdx = -1; return }
                                        var rel = (mouse.x - 38) / Math.max(10, width - 44)
                                        if (rel < 0 || rel > 1) { root.hoveredEquityIdx = -1; return }
                                        root.hoveredEquityIdx = Math.max(0, Math.min(pts.length - 1, Math.round(rel * (pts.length - 1))))
                                    }
                                    onExited: root.hoveredEquityIdx = -1
                                }
                            }
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

                        Rectangle { width: parent.width; height: 1; color: "#313244" }

                        Repeater {
                            model: root.summaryData.items || []
                            delegate: Column {
                                id: holdingItemCol
                                width: portfolioCol.width
                                spacing: Style.space(3)
                                property bool lotsExpanded: false
                                Rectangle {
                                    width: parent.width
                                    height: holdingRow.implicitHeight + Style.space(8)
                                    radius: 6
                                    color: holdingHover.containsMouse ? "#242436" : "#11111b"
                                    border.color: root.chartSymbol === modelData.symbol ? "#89b4fa" : "#242436"
                                    border.width: 1

                                    MouseArea {
                                        id: holdingHover
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            root.symText = modelData.symbol
                                            root.chartSymbol = modelData.symbol
                                            root.hoveredCandleIdx = -1
                                        }
                                    }

                                    Row {
                                        id: holdingRow
                                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 6; rightMargin: 6 }
                                        spacing: Style.space(4)
                                        Text {
                                            id: holdSymTxt
                                            width: parent.width * 0.14
                                            text: modelData.symbol
                                            color: modelData.currency === "ZWG" ? "#f9e2af" : "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small || Style.font.body
                                            font.bold: true
                                            elide: Text.ElideRight
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        // Clickable CORE / SWING Horizon Badge
                                        Rectangle {
                                            id: holdTagBadge
                                            anchors.verticalCenter: parent.verticalCenter
                                            width: holdTagTxt.implicitWidth + 8
                                            height: holdTagTxt.implicitHeight + 2
                                            radius: 3
                                            color: modelData.strategy_tag === "core" ? "#1f3a27" : "#272138"
                                            border.color: modelData.strategy_tag === "core" ? "#a6e3a1" : "#cba6f7"
                                            border.width: modelData.strategy_pinned ? 1 : 0
                                            Text {
                                                id: holdTagTxt
                                                anchors.centerIn: parent
                                                text: modelData.strategy_tag === "core" ? "CORE" : "SWING"
                                                color: modelData.strategy_tag === "core" ? "#a6e3a1" : "#cba6f7"
                                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                                font.pixelSize: 8
                                                font.bold: true
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                enabled: !manualProc.running
                                                onClicked: {
                                                    var nextTag = modelData.strategy_tag === "core" ? "swing" : "core"
                                                    var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                    manualProc.command = ["python3", script, "tag", "set", modelData.symbol, nextTag]
                                                    manualProc.running = true
                                                }
                                            }
                                        }
                                        Text {
                                            id: holdShTxt
                                            width: Math.min(parent.width * 0.24, Math.max(Style.space(58), implicitWidth + 4))
                                            text: Number(modelData.shares) + " shares"
                                            color: "#a6adc8"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                            elide: Text.ElideRight
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Text {
                                            id: holdPrcTxt
                                            width: Math.max(Style.space(56), implicitWidth + 4)
                                            text: "@ " + root.fmtPrice(modelData.price, modelData.currency)
                                            color: "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Text {
                                            width: Math.max(70, parent.width - holdSymTxt.width - holdTagBadge.width - holdShTxt.width - holdPrcTxt.width - Style.space(16))
                                            horizontalAlignment: Text.AlignRight
                                            text: {
                                                var pct = Number(modelData.pnl_pct || 0)
                                                var sign = pct >= 0 ? "+" : ""
                                                return root.fmtSignedMoney(modelData.pnl, modelData.currency) + " (" + sign + pct.toFixed(1) + "%)"
                                            }
                                            color: modelData.pnl >= 0 ? "#a6e3a1" : "#f38ba8"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                            font.bold: true
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                }

                                // Price Position Range Bar: Stop Floor <-> Cost Basis <-> Price <-> Adaptive Horizon Target
                                Row {
                                    width: portfolioCol.width
                                    spacing: Style.space(6)
                                    property real costP: Number(modelData.avg_cost || modelData.price || 0)
                                    property real curP: Number(modelData.price || 0)
                                    property real stopP: modelData.stop_price ? Number(modelData.stop_price) : (modelData.strategy_tag === "core" ? costP * 0.80 : costP * 0.92)
                                    property real baseTake: Number((root.summaryData.fee_config || ({})).profit_take_pct || 15)
                                    property real tgtMult: modelData.strategy_tag === "core" ? (1 + Math.max(50, baseTake * 3) / 100.0) : (1 + baseTake / 100.0)
                                    property real tgtP: costP * tgtMult
                                    property real loP: Math.min(stopP, costP, curP) * 0.98
                                    property real hiP: Math.max(tgtP, curP) * 1.02
                                    property real pSpan: Math.max(0.0001, hiP - loP)

                                    Text {
                                        id: beStopLbl
                                        width: Math.max(Style.space(116), implicitWidth + 2)
                                        text: modelData.stop_price ? ("Stop " + Number(modelData.stop_price).toFixed(3)) : ("Break-Even " + Number(modelData.breakeven_price || modelData.avg_cost || 0).toFixed(3))
                                        color: modelData.stop_price ? "#f9e2af" : "#6c7086"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                    }

                                    Item {
                                        width: Math.max(Style.space(40), parent.width - beStopLbl.width - tgtStopLbl.width - Style.space(12))
                                        height: Style.space(12)
                                        Rectangle {
                                            anchors.verticalCenter: parent.verticalCenter
                                            width: parent.width
                                            height: 4
                                            radius: 2
                                            color: "#313244"
                                            // Green zone from Cost to Price (or Red below Cost)
                                            Rectangle {
                                                property real xCost: Math.max(0, Math.min(1, (parent.parent.parent.costP - parent.parent.parent.loP) / parent.parent.parent.pSpan)) * parent.width
                                                property real xCur: Math.max(0, Math.min(1, (parent.parent.parent.curP - parent.parent.parent.loP) / parent.parent.parent.pSpan)) * parent.width
                                                x: Math.min(xCost, xCur)
                                                width: Math.max(2, Math.abs(xCur - xCost))
                                                height: parent.height
                                                radius: 2
                                                color: parent.parent.parent.curP >= parent.parent.parent.costP ? "#a6e3a1" : "#f38ba8"
                                            }
                                            // Stop Floor vertical tick
                                            Rectangle {
                                                x: Math.max(0, Math.min(parent.width - 2, ((parent.parent.parent.stopP - parent.parent.parent.loP) / parent.parent.parent.pSpan) * parent.width))
                                                y: -2; width: 2; height: 8; color: "#f9e2af"
                                            }
                                            // Cost Basis vertical tick
                                            Rectangle {
                                                x: Math.max(0, Math.min(parent.width - 2, ((parent.parent.parent.costP - parent.parent.parent.loP) / parent.parent.parent.pSpan) * parent.width))
                                                y: -2; width: 2; height: 8; color: "#cdd6f4"
                                            }
                                            // Current price glowing dot
                                            Rectangle {
                                                x: Math.max(0, Math.min(parent.width - 8, ((parent.parent.parent.curP - parent.parent.parent.loP) / parent.parent.parent.pSpan) * parent.width - 4))
                                                y: -2; width: 8; height: 8; radius: 4
                                                color: parent.parent.parent.curP >= parent.parent.parent.costP ? "#a6e3a1" : "#f38ba8"
                                                border.color: "#11111b"; border.width: 1
                                            }
                                        }
                                    }

                                    Text {
                                        id: tgtStopLbl
                                        width: Math.max(Style.space(102), implicitWidth + 2)
                                        horizontalAlignment: Text.AlignRight
                                        text: "Target Price " + Number(parent.tgtP).toFixed(3)
                                        color: "#89dceb"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
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
                                                var srcName = root.fmtSourceLabel(modelData.synced_source || modelData.source_tag || "SYNC")
                                                var srcTag = modelData.is_synced ? ("[" + srcName + "] ") : (modelData.synced_source ? ("[" + srcName + "] ") : "")
                                                var prefix = lc > 0 ? ((holdingItemCol.lotsExpanded ? "▾ " : "▸ ") + lc + (lc === 1 ? " lot" : " lots") + (modelData.synced_source ? (" • " + srcName) : "") + " • ") : srcTag
                                                var base = prefix + "Average " + root.fmtPrice(modelData.avg_cost || 0, modelData.currency) + " • Cost " + root.fmtShortMoney(modelData.cost !== undefined ? modelData.cost : (Number(modelData.shares || 0) * Number(modelData.avg_cost || 0)), modelData.currency)
                                                if (modelData.days_held !== null && modelData.days_held !== undefined) {
                                                    var dh = Number(modelData.days_held)
                                                    base += " • " + dh + (dh === 1 ? " day" : " days")
                                                }
                                                return base
                                            }
                                            color: (modelData.lots || []).length > 0 ? "#89b4fa" : "#a6adc8"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                            MouseArea {
                                                anchors.fill: parent
                                                enabled: (modelData.lots || []).length > 0
                                                cursorShape: (modelData.lots || []).length > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                onClicked: holdingItemCol.lotsExpanded = !holdingItemCol.lotsExpanded
                                            }
                                        }

                                        Row {
                                            id: quickBtnsRow
                                            spacing: Style.space(3)
                                            anchors.verticalCenter: parent.verticalCenter

                                            Rectangle {
                                                width: qbBuyTxt.implicitWidth + Style.space(6)
                                                height: qbBuyTxt.implicitHeight + 2
                                                radius: 3
                                                color: "#243b2c"
                                                border.color: "#45475a"
                                                border.width: 1
                                                Text {
                                                    id: qbBuyTxt
                                                    anchors.centerIn: parent
                                                    text: "Buy More"
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
                                                width: qbSellTxt.implicitWidth + Style.space(6)
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

                                            Rectangle {
                                                width: qbStopTxt.implicitWidth + Style.space(6)
                                                height: qbStopTxt.implicitHeight + 2
                                                radius: 3
                                                color: modelData.stop_pct ? "#2b261d" : "#313244"
                                                border.color: modelData.stop_pct ? "#f9e2af" : "#45475a"
                                                border.width: 1
                                                Text {
                                                    id: qbStopTxt
                                                    anchors.centerIn: parent
                                                    text: modelData.stop_pct ? ("Stop -" + Number(modelData.stop_pct).toFixed(0) + "%") : "Trailing Stop"
                                                    color: modelData.stop_pct ? "#f9e2af" : "#cdd6f4"
                                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                                    font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                                    font.bold: true
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: {
                                                        if (root.stopEditOpen && root.stopEditSym === modelData.symbol) {
                                                            root.stopEditOpen = false
                                                        } else {
                                                            root.stopEditSym = modelData.symbol
                                                            root.stopEditPct = String(modelData.stop_pct || 10)
                                                            root.stopEditOpen = true
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                Row {
                                    width: portfolioCol.width
                                    visible: modelData.stop_price !== null && modelData.stop_price !== undefined
                                    spacing: Style.space(6)
                                    Text {
                                        width: portfolioCol.width * 0.56
                                        text: "Stop " + root.fmtPrice(modelData.stop_price || 0, modelData.currency) + " (Peak " + root.fmtPrice(modelData.peak_price || 0, modelData.currency) + ")"
                                        color: "#f9e2af"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                        elide: Text.ElideRight
                                    }
                                    Rectangle {
                                        width: portfolioCol.width * 0.40
                                        height: 4
                                        radius: 2
                                        color: "#313244"
                                        anchors.verticalCenter: parent.verticalCenter
                                        Rectangle {
                                            width: Math.max(0, Math.min(1, Number(modelData.stop_distance_pct || 0) / Math.max(1, Number(modelData.stop_pct || 10)))) * parent.width
                                            height: parent.height
                                            radius: 2
                                            color: Number(modelData.stop_distance_pct || 0) <= 2 ? "#f38ba8" : "#a6e3a1"
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
                                            text: "  " + modelData.date + ": " + Number(modelData.shares) + " shares @ $" + Number(modelData.price).toFixed(4)
                                            color: "#a6adc8"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small || Style.font.body
                                        }
                                    }
                                }
                            }
                        }

                        // Inline Contextual Trailing Stop Editor inside Open Holdings
                        Rectangle {
                            width: portfolioCol.width
                            visible: root.stopEditOpen
                            height: stopEditRow.implicitHeight + Style.space(10)
                            radius: 6
                            color: "#11111b"
                            border.color: "#f9e2af"
                            border.width: 1
                            Row {
                                id: stopEditRow
                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: Style.space(6) }
                                spacing: Style.space(5)
                                Text {
                                    text: "Trailing Stop:"
                                    color: "#f9e2af"; font.pixelSize: Style.font.small ? Style.font.small - 1 : 10; font.bold: true
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Rectangle {
                                    width: parent.width * 0.24; height: Style.space(24); radius: 4; color: "#313244"; border.color: "#45475a"; border.width: 1
                                    TextInput {
                                        id: stopSymIn; anchors.fill: parent; anchors.margins: 4; color: "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small || Style.font.body
                                        text: root.stopEditSym; onTextChanged: if (root.stopEditSym !== text) root.stopEditSym = text
                                        Connections { target: root; function onStopEditSymChanged() { if (stopSymIn.text !== root.stopEditSym) stopSymIn.text = root.stopEditSym } }
                                        Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Symbol"; color: "#6c7086"; font: stopSymIn.font; visible: !stopSymIn.text && !stopSymIn.activeFocus }
                                    }
                                }
                                Rectangle {
                                    width: parent.width * 0.22; height: Style.space(24); radius: 4; color: "#313244"; border.color: "#45475a"; border.width: 1
                                    TextInput {
                                        id: stopPctIn; anchors.fill: parent; anchors.margins: 4; color: "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small || Style.font.body
                                        text: root.stopEditPct; onTextChanged: if (root.stopEditPct !== text) root.stopEditPct = text
                                        Connections { target: root; function onStopEditPctChanged() { if (stopPctIn.text !== root.stopEditPct) stopPctIn.text = root.stopEditPct } }
                                        Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Trail %"; color: "#6c7086"; font: stopPctIn.font; visible: !stopPctIn.text && !stopPctIn.activeFocus }
                                    }
                                }
                                Rectangle {
                                    width: stpSvTxt.implicitWidth + 14; height: Style.space(24); radius: 4; color: "#f9e2af"
                                    Text { id: stpSvTxt; anchors.centerIn: parent; text: "Set Stop"; color: "#1e1e2e"; font.pixelSize: 10; font.bold: true }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                        onClicked: {
                                            var sy = root.stopEditSym.trim().toUpperCase()
                                            var pc = root.stopEditPct.replace(/[^0-9.]/g, "").trim()
                                            if (sy && pc) {
                                                root.runCliCommand(["stop", "add", sy, pc], false)
                                                root.stopEditOpen = false
                                            }
                                        }
                                    }
                                }
                                Text {
                                    text: "×"; color: "#f38ba8"; font.pixelSize: Style.font.body; font.bold: true; anchors.verticalCenter: parent.verticalCenter
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.stopEditOpen = false }
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
                    visible: true
                    height: activeAlertsCol.implicitHeight + Style.space(16)
                    radius: 8
                    color: "#181825"
                    border.color: "#313244"
                    border.width: 1

                    Column {
                        id: activeAlertsCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                        spacing: Style.space(4)

                        Row {
                            width: parent.width
                            spacing: Style.space(6)
                            Text {
                                width: parent.width - addAlertTog.width - Style.space(6)
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Price Alerts (" + (root.summaryData.active_alerts || []).length + ")"
                                color: "#cdd6f4"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                font.bold: true
                            }
                            Rectangle {
                                id: addAlertTog
                                anchors.verticalCenter: parent.verticalCenter
                                width: addAlLbl.implicitWidth + 12; height: Style.space(20); radius: 4
                                color: root.alertAddOpen ? "#f9e2af" : "#2b261d"
                                border.color: "#f9e2af"; border.width: 1
                                Text {
                                    id: addAlLbl; anchors.centerIn: parent
                                    text: root.alertAddOpen ? "Close" : "+ Add Price Alert"
                                    color: root.alertAddOpen ? "#1e1e2e" : "#f9e2af"
                                    font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true
                                }
                                MouseArea {
                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (!root.alertAddSym && root.chartSymbol) root.alertAddSym = root.chartSymbol
                                        root.alertAddOpen = !root.alertAddOpen
                                    }
                                }
                            }
                        }

                        // Inline Price Alert Creation Row
                        Rectangle {
                            width: activeAlertsCol.width
                            visible: root.alertAddOpen
                            height: alFormCol.implicitHeight + Style.space(10)
                            radius: 6; color: "#11111b"; border.color: "#f9e2af"; border.width: 1
                            Column {
                                id: alFormCol
                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: Style.space(6) }
                                spacing: Style.space(4)
                                Row {
                                    width: parent.width; spacing: Style.space(4)
                                    Rectangle {
                                        width: parent.width * 0.25; height: Style.space(24); radius: 4; color: "#313244"; border.color: "#45475a"; border.width: 1
                                        TextInput {
                                            id: alSymIn; anchors.fill: parent; anchors.margins: 4; color: "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small || Style.font.body
                                            text: root.alertAddSym; onTextChanged: if (root.alertAddSym !== text) root.alertAddSym = text
                                            Connections { target: root; function onAlertAddSymChanged() { if (alSymIn.text !== root.alertAddSym) alSymIn.text = root.alertAddSym } }
                                            Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Symbol"; color: "#6c7086"; font: alSymIn.font; visible: !alSymIn.text && !alSymIn.activeFocus }
                                        }
                                    }
                                    Rectangle {
                                        width: parent.width * 0.23; height: Style.space(24); radius: 4; color: "#313244"; border.color: "#45475a"; border.width: 1
                                        Text { anchors.centerIn: parent; text: root.alertAddDir === "above" ? "Above" : "Below"; color: "#89b4fa"; font.pixelSize: Style.font.small || Style.font.body; font.bold: true }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.alertAddDir = root.alertAddDir === "above" ? "below" : "above" }
                                    }
                                    Rectangle {
                                        width: parent.width * 0.28; height: Style.space(24); radius: 4; color: "#313244"; border.color: "#45475a"; border.width: 1
                                        TextInput {
                                            id: alPrcIn; anchors.fill: parent; anchors.margins: 4; color: "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small || Style.font.body
                                            text: root.alertAddPrice; onTextChanged: if (root.alertAddPrice !== text) root.alertAddPrice = text
                                            Connections { target: root; function onAlertAddPriceChanged() { if (alPrcIn.text !== root.alertAddPrice) alPrcIn.text = root.alertAddPrice } }
                                            Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Price $"; color: "#6c7086"; font: alPrcIn.font; visible: !alPrcIn.text && !alPrcIn.activeFocus }
                                        }
                                    }
                                    Rectangle {
                                        width: parent.width * 0.24 - Style.space(12); height: Style.space(24); radius: 4; color: "#f9e2af"
                                        Text { anchors.centerIn: parent; text: "Set Alert"; color: "#1e1e2e"; font.pixelSize: 10; font.bold: true }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                            onClicked: {
                                                var sy = root.alertAddSym.trim().toUpperCase()
                                                var pr = root.alertAddPrice.replace(/^\s*\$?/, "").replace(/,/g, "").trim()
                                                if (sy && pr) {
                                                    root.runCliCommand(["alert", "add", sy, root.alertAddDir, pr], false)
                                                    root.alertAddPrice = ""
                                                    root.alertAddOpen = false
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            visible: (root.summaryData.active_alerts || []).length === 0 && !root.alertAddOpen
                            text: "No active price alerts configured."
                            color: "#6c7086"
                            font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
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

                // Full Screen Overview Left Bottom: Unused Portal Balances & Quick Picks
                Rectangle {
                    id: ovIdleCard
                    property var icpOv: (root.summaryData.idle_cash_plan || ({}))
                    property real depU: Number(icpOv.total_deployable_usd || 0)
                    property real depZ: Number(icpOv.total_deployable_zwg || 0)
                    width: parent.width
                    visible: root.fullPageMode && ((icpOv.accounts || []).length > 0 || depU > 0 || depZ > 0)
                    height: ovIdleCol.implicitHeight + Style.space(14)
                    radius: 8; color: "#181825"; border.color: (depU > 0 || depZ > 0) ? "#a6e3a1" : "#313244"; border.width: 1
                    Column {
                        id: ovIdleCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                        spacing: Style.space(5)
                        Row {
                            width: parent.width
                            Text {
                                width: parent.width * 0.60
                                text: "Unused Portal Balances & Quick Buys"
                                color: "#a6e3a1"; font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body; font.bold: true; elide: Text.ElideRight
                            }
                            Text {
                                width: parent.width * 0.40; horizontalAlignment: Text.AlignRight
                                text: "$" + ovIdleCard.depU.toFixed(2) + " USD • ZiG " + ovIdleCard.depZ.toFixed(2)
                                color: "#89dceb"; font.pixelSize: 9; font.bold: true; elide: Text.ElideLeft
                            }
                        }
                        Flow {
                            width: parent.width; spacing: 5
                            Repeater {
                                model: ovIdleCard.icpOv.accounts || []
                                delegate: Rectangle {
                                    width: ovAcTxt.implicitWidth + 10; height: Style.space(18); radius: 4; color: "#11111b"; border.color: "#313244"; border.width: 1
                                    Text {
                                        id: ovAcTxt; anchors.centerIn: parent
                                        text: modelData.title + ": $" + Number(modelData.deployable_usd || 0).toFixed(2) + " USD • ZiG " + Number(modelData.deployable_zwg || 0).toFixed(2)
                                        color: "#cdd6f4"; font.pixelSize: 8; font.bold: true
                                    }
                                }
                            }
                        }
                        Repeater {
                            model: (ovIdleCard.icpOv.usd_picks || []).slice(0, 2).concat((ovIdleCard.icpOv.zwg_picks || []).slice(0, 2))
                            delegate: Rectangle {
                                width: ovIdleCol.width; height: ovPkRow.implicitHeight + 6; radius: 4; color: "#11111b"
                                MouseArea {
                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        root.chartSymbol = modelData.symbol
                                        root.manualSymbol = modelData.symbol
                                        root.manualShares = String(modelData.max_shares || 1)
                                        root.manualPrice = String(modelData.exec_price || "")
                                        root.manualMode = "buy"
                                    }
                                }
                                Row {
                                    id: ovPkRow
                                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 5 }
                                    Text { width: parent.width * 0.20; text: modelData.symbol; color: "#a6e3a1"; font.pixelSize: 9; font.bold: true }
                                    Text { width: parent.width * 0.44; text: "Buy " + modelData.max_shares + " shares @ " + root.fmtPrice(modelData.exec_price, modelData.currency); color: "#cdd6f4"; font.pixelSize: 9; elide: Text.ElideRight }
                                    Text { width: parent.width * 0.36; horizontalAlignment: Text.AlignRight; text: root.fmtShortMoney(modelData.net_cost, modelData.currency) + " • Score " + modelData.score; color: "#cba6f7"; font.pixelSize: 9; font.bold: true }
                                }
                            }
                        }
                        Row {
                            width: parent.width
                            Text { width: parent.width * 0.65; text: "Click any pick above to pre-fill the Buy ticket →"; color: "#6c7086"; font.pixelSize: 8 }
                            Text {
                                width: parent.width * 0.35; horizontalAlignment: Text.AlignRight
                                text: "Full Planner →"; color: "#89b4fa"; font.pixelSize: 9; font.bold: true
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.activeTab = "analytics" }
                            }
                        }
                    }
                }

                Column {
                    id: centerPaneCol
                    parent: root.fullPageMode ? centerColHost : leftPaneCol
                    width: parent ? parent.width : leftPaneCol.width
                    spacing: Style.space(10)

                Rectangle {
                    id: signalsCard
                    width: parent.width
                    visible: true
                    height: signalsCol.implicitHeight + Style.space(16)
                    radius: 8
                    color: "#181825"
                    border.color: "#313244"
                    border.width: 1

                    Column {
                        id: signalsCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                        spacing: Style.space(6)

                        Row {
                            width: parent.width
                            spacing: Style.space(6)
                            Text {
                                width: parent.width - sigFilterRow.width - Style.space(6)
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Quant Trade Signals (" + (root.filteredSignals()).length + ")"
                                color: "#89b4fa"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                font.bold: true
                                elide: Text.ElideRight
                            }
                            Row {
                                id: sigFilterRow
                                spacing: Style.space(3)
                                anchors.verticalCenter: parent.verticalCenter
                                Repeater {
                                    model: [
                                        { key: "all", label: "All" },
                                        { key: "core", label: "CORE" },
                                        { key: "swing", label: "SWING" },
                                        { key: "buy", label: "BUY" },
                                        { key: "sell", label: "SELL" }
                                    ]
                                    delegate: Rectangle {
                                        width: sfLbl.implicitWidth + 10
                                        height: Style.space(18)
                                        radius: 4
                                        color: root.signalFilter === modelData.key ? "#89b4fa" : "#313244"
                                        Text {
                                            id: sfLbl
                                            anchors.centerIn: parent
                                            text: modelData.label
                                            color: root.signalFilter === modelData.key ? "#1e1e2e" : "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                            font.bold: true
                                        }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.signalFilter = modelData.key }
                                    }
                                }
                            }
                        }

                        Repeater {
                            model: root.filteredSignals().slice(0, 6)
                            delegate: Rectangle {
                                width: signalsCol.width
                                height: sigTicketRow.implicitHeight + Style.space(10)
                                radius: 6
                                color: sigHover.containsMouse ? "#242436" : "#11111b"
                                border.color: root.chartSymbol === modelData.symbol ? "#89b4fa" : (modelData.action === "SELL" ? "#4a242d" : "#243b2c")
                                border.width: 1

                                MouseArea {
                                    id: sigHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        root.chartSymbol = modelData.symbol
                                        root.hoveredCandleIdx = -1
                                    }
                                }

                                Row {
                                    id: sigTicketRow
                                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 6 }
                                    spacing: Style.space(8)

                                    // 36x36 Radial Conviction Gauge
                                    Item {
                                        width: Style.space(36)
                                        height: Style.space(36)
                                        anchors.verticalCenter: parent.verticalCenter

                                        Canvas {
                                            anchors.fill: parent
                                            property real scoreVal: Number(modelData.score || 0)
                                            property string actVal: String(modelData.action || "BUY")
                                            onScoreValChanged: requestPaint()
                                            onWidthChanged: requestPaint()
                                            Component.onCompleted: requestPaint()
                                            onPaint: {
                                                var ctx = getContext("2d")
                                                if (width <= 0 || height <= 0) return
                                                ctx.clearRect(0, 0, width, height)
                                                var cx = width / 2, cy = height / 2
                                                var r = Math.min(cx, cy) - 3
                                                ctx.beginPath()
                                                ctx.arc(cx, cy, r, 0, Math.PI * 2)
                                                ctx.strokeStyle = "#313244"
                                                ctx.lineWidth = 4
                                                ctx.stroke()

                                                var frac = Math.max(0.05, Math.min(1, scoreVal / 100.0))
                                                var col = actVal === "SELL" ? "#f38ba8" : (scoreVal >= 50 ? "#a6e3a1" : "#89b4fa")
                                                ctx.beginPath()
                                                ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + frac * Math.PI * 2)
                                                ctx.strokeStyle = col
                                                ctx.lineWidth = 4
                                                ctx.stroke()
                                            }
                                        }

                                        Text {
                                            anchors.centerIn: parent
                                            text: String(Math.round(Number(modelData.score || 0)))
                                            color: modelData.action === "SELL" ? "#f38ba8" : "#a6e3a1"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                            font.bold: true
                                        }
                                    }

                                    // Center Info + Bid/Ask Bar + Reasons + 5-dot Liquidity
                                    Column {
                                        width: parent.width - Style.space(36) - stageLimitBtn.width - Style.space(16)
                                        spacing: 2
                                        anchors.verticalCenter: parent.verticalCenter

                                        Row {
                                            width: parent.width
                                            spacing: Style.space(4)
                                            Rectangle {
                                                width: sigActTxt.implicitWidth + 8; height: sigActTxt.implicitHeight + 2; radius: 3
                                                color: modelData.action === "SELL" ? "#3d2229" : "#243b2c"
                                                anchors.verticalCenter: parent.verticalCenter
                                                Text { id: sigActTxt; anchors.centerIn: parent; text: modelData.action; color: modelData.action === "SELL" ? "#f38ba8" : "#a6e3a1"; font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                            }
                                            Rectangle {
                                                visible: Boolean(modelData.horizon)
                                                width: sigHzTxt.implicitWidth + 6; height: sigHzTxt.implicitHeight + 2; radius: 3
                                                color: modelData.horizon === "CORE" ? "#1f3a27" : "#272138"
                                                anchors.verticalCenter: parent.verticalCenter
                                                Text { id: sigHzTxt; anchors.centerIn: parent; text: String(modelData.horizon || "SWING"); color: modelData.horizon === "CORE" ? "#a6e3a1" : "#cba6f7"; font.pixelSize: 8; font.bold: true }
                                            }
                                            Text {
                                                text: modelData.symbol
                                                color: modelData.currency === "ZWG" ? "#f9e2af" : "#cdd6f4"
                                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                                font.pixelSize: Style.font.body
                                                font.bold: true
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                            Text {
                                                text: root.fmtPrice(modelData.price, modelData.currency)
                                                color: "#a6adc8"
                                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                                font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                            Rectangle {
                                                visible: Boolean(modelData.wide_spread)
                                                width: wspTxt.implicitWidth + 6; height: wspTxt.implicitHeight + 2; radius: 3; color: "#2b261d"
                                                anchors.verticalCenter: parent.verticalCenter
                                                Text { id: wspTxt; anchors.centerIn: parent; text: "⚠" + Number(modelData.spread_pct || 0).toFixed(0) + "%"; color: "#f9e2af"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9 }
                                            }
                                            Rectangle {
                                                visible: Boolean(modelData.news_catalyst)
                                                width: sigNewsTxt.implicitWidth + 8; height: sigNewsTxt.implicitHeight + 2; radius: 3
                                                color: modelData.news_catalyst ? root.newsSentimentBg(modelData.news_catalyst.sentiment) : "#1e2e4a"
                                                anchors.verticalCenter: parent.verticalCenter
                                                Text {
                                                    id: sigNewsTxt
                                                    anchors.centerIn: parent
                                                    text: modelData.news_catalyst ? ("📰 " + modelData.news_catalyst.category) : ""
                                                    color: modelData.news_catalyst ? root.newsSentimentColor(modelData.news_catalyst.sentiment) : "#89b4fa"
                                                    font.pixelSize: 8
                                                    font.bold: true
                                                }
                                                MouseArea {
                                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                    onClicked: { root.newsFilter = "all"; root.activeTab = "analytics" }
                                                }
                                            }
                                            Rectangle {
                                                visible: Number(modelData.dtr_turnover || 0) > 0
                                                width: sigDtrTxt.implicitWidth + 6; height: sigDtrTxt.implicitHeight + 2; radius: 3; color: "#1b2e33"
                                                anchors.verticalCenter: parent.verticalCenter
                                                Text { id: sigDtrTxt; anchors.centerIn: parent; text: "📊 Daily Turnover"; color: "#89dceb"; font.pixelSize: 8; font.bold: true }
                                            }
                                            Rectangle {
                                                visible: Number(modelData.blue_chip_rank || 0) > 0
                                                width: sigBcTxt.implicitWidth + 6; height: sigBcTxt.implicitHeight + 2; radius: 3; color: "#272138"
                                                anchors.verticalCenter: parent.verticalCenter
                                                Text { id: sigBcTxt; anchors.centerIn: parent; text: "Top #" + (modelData.blue_chip_rank || "") + " Market Cap"; color: "#cba6f7"; font.pixelSize: 8; font.bold: true }
                                            }
                                        }

                                        Text {
                                            width: parent.width
                                            text: root.fmtReasonText((modelData.reasons || []).join(" • "))
                                            color: "#a6adc8"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                            elide: Text.ElideRight
                                        }

                                        Row {
                                            width: parent.width
                                            spacing: Style.space(6)
                                            // 5-dot Liquidity Meter
                                            Row {
                                                spacing: 2
                                                anchors.verticalCenter: parent.verticalCenter
                                                property int liqLevel: Math.round(Number(modelData.liquidity_score || 0) / 20)
                                                Text { text: "Liquidity"; color: "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; anchors.verticalCenter: parent.verticalCenter }
                                                Repeater {
                                                    model: 5
                                                    delegate: Rectangle {
                                                        width: 5; height: 5; radius: 2.5
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        color: index < parent.liqLevel ? "#89dceb" : "#313244"
                                                    }
                                                }
                                            }
                                            // Bid/Ask mini tug bar
                                            Rectangle {
                                                width: Style.space(48); height: 4; radius: 2; color: "#3d2229"
                                                anchors.verticalCenter: parent.verticalCenter
                                                visible: Number(modelData.bid_volume || 0) > 0 || Number(modelData.ask_volume || 0) > 0
                                                Rectangle {
                                                    property real bv: Number(modelData.bid_volume || 0)
                                                    property real av: Number(modelData.ask_volume || 0)
                                                    width: (bv + av) > 0 ? (bv / (bv + av)) * parent.width : parent.width * 0.5
                                                    height: parent.height; radius: 2; color: "#a6e3a1"
                                                }
                                            }
                                            Text {
                                                visible: modelData.rsi14 !== null && modelData.rsi14 !== undefined
                                                text: "Relative Strength " + Number(modelData.rsi14 || 0).toFixed(0)
                                                color: Number(modelData.rsi14 || 50) <= 35 ? "#a6e3a1" : (Number(modelData.rsi14 || 50) >= 68 ? "#f38ba8" : "#6c7086")
                                                font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                            }
                                        }
                                    }

                                    // One-click Stage Limit button
                                    Rectangle {
                                        id: stageLimitBtn
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: stgCol.implicitWidth + Style.space(10)
                                        height: stgCol.implicitHeight + Style.space(6)
                                        radius: 5
                                        color: modelData.action === "SELL" ? "#3d2229" : "#243b2c"
                                        border.color: modelData.action === "SELL" ? "#f38ba8" : "#a6e3a1"
                                        border.width: 1
                                        Column {
                                            id: stgCol
                                            anchors.centerIn: parent
                                            spacing: 1
                                            Text {
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                text: "Stage Limit Order"
                                                color: modelData.action === "SELL" ? "#f38ba8" : "#a6e3a1"
                                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                                font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                                font.bold: true
                                            }
                                            Text {
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                text: root.fmtPrice(modelData.optimal_limit || modelData.limit_price || modelData.price, modelData.currency) + (Number(modelData.recommended_shares || 0) > 0 ? (" ×" + modelData.recommended_shares) : "")
                                                color: "#cdd6f4"
                                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                                font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                            }
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: root.applySignal(modelData)
                                        }
                                    }
                                }
                            }
                        }

                        // Calm Tracked State Card + Quick-Watch Discovery Chips from Screener
                        Rectangle {
                            width: signalsCol.width
                            visible: root.filteredSignals().length === 0
                            height: calmCol.implicitHeight + Style.space(12)
                            radius: 6
                            color: "#11111b"
                            border.color: "#313244"
                            border.width: 1

                            Column {
                                id: calmCol
                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(6) }
                                spacing: Style.space(5)

                                Row {
                                    width: parent.width
                                    spacing: Style.space(6)
                                    Text {
                                        width: parent.width - browseScrBtn.width - Style.space(6)
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: root.summaryData.tracked_only === false
                                            ? "✓ No active signals matching filter."
                                            : ("✓ All " + (root.summaryData.tracked_count || 0) + " tracked stocks calm right now.")
                                        color: "#a6e3a1"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small || Style.font.body
                                        font.bold: true
                                        wrapMode: Text.WordWrap
                                    }
                                    Rectangle {
                                        id: browseScrBtn
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: bScrTxt.implicitWidth + 12
                                        height: Style.space(20)
                                        radius: 4
                                        color: "#1e2e4a"
                                        border.color: "#89b4fa"
                                        border.width: 1
                                        Text { id: bScrTxt; anchors.centerIn: parent; text: "Market Screener →"; color: "#89b4fa"; font.pixelSize: 9; font.bold: true }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                            onClicked: { root.activeTab = "screener"; root.screenerFilter = "signals" }
                                        }
                                    }
                                }

                                Text {
                                    width: parent.width
                                    visible: (root.summaryData.market_top_signals || []).length > 0 && root.summaryData.tracked_only !== false
                                    text: "Top Market Setups (Add to Watchlist):"
                                    color: "#6c7086"
                                    font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                }

                                Flow {
                                    width: parent.width
                                    spacing: Style.space(4)
                                    visible: (root.summaryData.market_top_signals || []).length > 0 && root.summaryData.tracked_only !== false
                                    Repeater {
                                        model: root.summaryData.market_top_signals || []
                                        delegate: Rectangle {
                                            width: discChipTxt.implicitWidth + 12
                                            height: Style.space(20)
                                            radius: 4
                                            color: "#181825"
                                            border.color: "#45475a"
                                            border.width: 1
                                            Text {
                                                id: discChipTxt
                                                anchors.centerIn: parent
                                                text: "+ Watchlist " + modelData.symbol + " (" + modelData.signal_score + ")"
                                                color: "#89b4fa"
                                                font.pixelSize: 9
                                                font.bold: true
                                            }
                                            MouseArea {
                                                anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                                onClicked: {
                                                    var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                    manualProc.command = ["python3", script, "watch", "add", modelData.symbol]
                                                    manualProc.running = true
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Live VFEX/ZSE News Catalysts Hero Card (Top 3 prioritized)
                Rectangle {
                    id: overviewNewsCard
                    width: parent.width
                    visible: root.summaryData.news_enabled !== false && (root.summaryData.news_top || []).length > 0
                    height: overviewNewsCol.implicitHeight + Style.space(14)
                    radius: 8
                    color: "#181825"
                    border.color: "#313244"
                    border.width: 1

                    Column {
                        id: overviewNewsCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                        spacing: Style.space(5)

                        Row {
                            width: parent.width
                            spacing: Style.space(6)
                            Text {
                                width: parent.width - allNewsLink.width - Style.space(6)
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Live News Catalysts (" + ((root.summaryData.news_summary || ({})).total || (root.summaryData.news_top || []).length) + ")"
                                color: "#cba6f7"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                font.bold: true
                                elide: Text.ElideRight
                            }
                            Text {
                                id: allNewsLink
                                anchors.verticalCenter: parent.verticalCenter
                                text: "All News →"
                                color: "#89b4fa"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                font.bold: true
                                MouseArea {
                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                    onClicked: { root.newsFilter = "all"; root.activeTab = "analytics" }
                                }
                            }
                        }

                        Repeater {
                            model: (root.summaryData.news_top || []).slice(0, 3)
                            delegate: Rectangle {
                                width: overviewNewsCol.width
                                height: ovNewsItemCol.implicitHeight + Style.space(10)
                                radius: 6
                                color: ovNewsHover.containsMouse ? "#242436" : "#11111b"
                                border.color: modelData.sentiment === "Bullish" ? "#243b2c" : (modelData.sentiment === "Caution" ? "#4a242d" : "#242436")
                                border.width: 1

                                MouseArea {
                                    id: ovNewsHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.openNewsUrl(modelData.url)
                                }

                                Column {
                                    id: ovNewsItemCol
                                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(6) }
                                    spacing: 3

                                    Row {
                                        width: parent.width
                                        spacing: Style.space(4)
                                        Rectangle {
                                            width: ovSentLbl.implicitWidth + 8; height: ovSentLbl.implicitHeight + 2; radius: 3
                                            color: root.newsSentimentBg(modelData.sentiment)
                                            anchors.verticalCenter: parent.verticalCenter
                                            Text {
                                                id: ovSentLbl
                                                anchors.centerIn: parent
                                                text: modelData.sentiment + " • " + modelData.category
                                                color: root.newsSentimentColor(modelData.sentiment)
                                                font.pixelSize: 8
                                                font.bold: true
                                            }
                                        }
                                        Repeater {
                                            model: (modelData.symbols || []).slice(0, 2)
                                            delegate: Row {
                                                spacing: 2
                                                anchors.verticalCenter: parent.verticalCenter
                                                Rectangle {
                                                    width: ovSymLbl.implicitWidth + 8; height: ovSymLbl.implicitHeight + 2; radius: 3
                                                    color: root.isWatchedSymbol(modelData) || root.isOwnedSymbol(modelData) ? "#1e2e4a" : "#242436"
                                                    Text {
                                                        id: ovSymLbl
                                                        anchors.centerIn: parent
                                                        text: modelData
                                                        color: root.isWatchedSymbol(modelData) || root.isOwnedSymbol(modelData) ? "#89b4fa" : "#cdd6f4"
                                                        font.pixelSize: 8
                                                        font.bold: true
                                                    }
                                                    MouseArea {
                                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                        onClicked: { root.chartSymbol = modelData; root.hoveredCandleIdx = -1 }
                                                    }
                                                }
                                                Rectangle {
                                                    visible: !root.isWatchedSymbol(modelData) && !root.isOwnedSymbol(modelData)
                                                    width: ovWatchPlus.implicitWidth + 6; height: ovWatchPlus.implicitHeight + 2; radius: 3
                                                    color: "#1b2e24"
                                                    Text { id: ovWatchPlus; anchors.centerIn: parent; text: "+ Watchlist"; color: "#a6e3a1"; font.pixelSize: 8; font.bold: true }
                                                    MouseArea {
                                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                                        onClicked: {
                                                            var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                            manualProc.command = ["python3", script, "watch", "add", modelData]
                                                            manualProc.running = true
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                        Text {
                                            text: (modelData.source || "") + (modelData.age_label ? (" • " + root.fmtAgeLabel(modelData.age_label)) : "")
                                            color: "#6c7086"
                                            font.pixelSize: 8
                                            anchors.verticalCenter: parent.verticalCenter
                                            elide: Text.ElideRight
                                        }
                                    }

                                    Text {
                                        width: parent.width
                                        text: modelData.title || ""
                                        color: "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                        wrapMode: Text.WordWrap
                                        maximumLineCount: 2
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }
                }

                // Compact Overview $100 Agent Status Pill
                Rectangle {
                    id: ovAgentBanner
                    width: parent.width
                    visible: Boolean(root.summaryData.paper_agent)
                    height: ovAgentRow.implicitHeight + Style.space(10)
                    radius: 8
                    color: "#181825"
                    border.color: "#313244"
                    border.width: 1
                    property var pa: root.summaryData.paper_agent || ({})

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.activeTab = "agent"
                    }

                    Row {
                        id: ovAgentRow
                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: Style.space(8) }
                        spacing: Style.space(6)

                        Text {
                            width: parent.width - ovAgentGoTxt.width - Style.space(6)
                            anchors.verticalCenter: parent.verticalCenter
                            text: {
                                var p = ovAgentBanner.pa
                                var eq = Number(p.equity_usd || 100)
                                var pct = Number(p.net_pnl_pct || 0)
                                var sg = pct >= 0 ? "+" : ""
                                var oc = (p.positions || []).length
                                var lc = (p.lessons || []).length
                                return "🤖 $100 Agent: $" + eq.toFixed(2) + " (" + sg + pct.toFixed(2) + "%) • " + oc + (oc === 1 ? " open position" : " open positions") + " • " + lc + (lc === 1 ? " lesson learned" : " lessons learned")
                            }
                            color: Number(ovAgentBanner.pa.net_pnl_pct || 0) >= 0 ? "#a6e3a1" : "#f38ba8"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                            font.bold: true
                            elide: Text.ElideRight
                        }

                        Text {
                            id: ovAgentGoTxt
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Open Auto-Trader →"
                            color: "#89b4fa"
                            font.pixelSize: 9
                            font.bold: true
                        }
                    }
                }

                // Full Screen Overview Center Bottom: Live Indices, Institutional Flows & Grokking Status
                Rectangle {
                    id: ovMktPulseCard
                    property var miOv: (root.summaryData.market_intel || ({}))
                    property var gkOv: ((ovAgentBanner.pa.brain || ({})).grok || ({}))
                    property var gmOv: (gkOv.metrics || ({}))
                    width: parent.width
                    visible: root.fullPageMode
                    height: ovMktPulseCol.implicitHeight + Style.space(14)
                    radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                    Column {
                        id: ovMktPulseCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                        spacing: Style.space(5)
                        Row {
                            width: parent.width
                            Text { width: parent.width * 0.62; text: "Market Indices, Flows & Grokking Brain"; color: "#89dceb"; font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.body; font.bold: true; elide: Text.ElideRight }
                            Text {
                                width: parent.width * 0.38; horizontalAlignment: Text.AlignRight
                                text: "All Indices →"; color: "#89b4fa"; font.pixelSize: 9; font.bold: true
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.activeTab = "analytics" }
                            }
                        }
                        Repeater {
                            model: (ovMktPulseCard.miOv.indices || []).slice(0, 4)
                            delegate: Row {
                                width: ovMktPulseCol.width
                                Text { width: ovMktPulseCol.width * 0.48; text: modelData.name; color: "#cdd6f4"; font.pixelSize: 9; elide: Text.ElideRight }
                                Text { width: ovMktPulseCol.width * 0.28; horizontalAlignment: Text.AlignRight; text: Number(modelData.level || 0).toFixed(2); color: "#89dceb"; font.pixelSize: 9; font.bold: true }
                                Text {
                                    width: ovMktPulseCol.width * 0.24; horizontalAlignment: Text.AlignRight
                                    text: (Number(modelData.change_pct || 0) >= 0 ? "+" : "") + Number(modelData.change_pct || 0).toFixed(2) + "%"
                                    color: Number(modelData.change_pct || 0) >= 0 ? "#a6e3a1" : "#f38ba8"; font.pixelSize: 9; font.bold: true
                                }
                            }
                        }
                        Rectangle {
                            width: parent.width; height: ovGkLine.implicitHeight + 8; radius: 4; color: "#11111b"
                            border.color: String(ovMktPulseCard.gkOv.status || "") === "Grokked (Active)" ? "#a6e3a1" : "#313244"; border.width: 1
                            Text {
                                id: ovGkLine
                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 5 }
                                elide: Text.ElideRight; font.pixelSize: 8; color: "#cdd6f4"
                                text: "☸ Grokking: " + String(ovMktPulseCard.gkOv.status || "Accumulating History")
                                    + (Number(ovMktPulseCard.gmOv.episodes_total || 0) >= 18
                                        ? (" • Train " + Number(ovMktPulseCard.gmOv.train_acc_pct || 0).toFixed(0) + "% / Validation " + Number(ovMktPulseCard.gmOv.val_acc_pct || 0).toFixed(0) + "% (" + Number(ovMktPulseCard.gmOv.episodes_total || 0) + " episodes)")
                                        : (" • " + Number(ovMktPulseCard.gmOv.episodes_total || 0) + "/18 episodes"))
                            }
                        }
                    }
                }
                }
                    }

                    Column {
                        id: centerColHost
                        visible: root.fullPageMode
                        width: Math.floor((mainGrid.width - Style.space(22)) * 0.35)
                        spacing: Style.space(10)
                    }

                    Column {
                        id: rightPaneCol
                        width: root.fullPageMode
                            ? Math.floor((mainGrid.width - Style.space(22)) * 0.32)
                            : (root.wideLayout ? Math.floor((mainGrid.width - Style.space(12)) * 0.46) : mainGrid.width)
                        spacing: Style.space(10)

                Rectangle {
                    id: watchlistCard
                    width: parent.width
                    visible: true
                    height: watchlistCol.implicitHeight + Style.space(16)
                    radius: 8
                    color: "#181825"
                    border.color: "#313244"
                    border.width: 1

                    Column {
                        id: watchlistCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                        spacing: Style.space(6)

                        Row {
                            width: parent.width
                            spacing: Style.space(4)
                            Text {
                                width: parent.width - wlActionBtns.width - Style.space(4)
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Watchlist & Order Depth (" + (root.summaryData.watchlist || []).length + ")"
                                color: "#cdd6f4"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                font.bold: true
                                elide: Text.ElideRight
                            }
                            Row {
                                id: wlActionBtns
                                spacing: Style.space(4)
                                anchors.verticalCenter: parent.verticalCenter
                                Rectangle {
                                    width: wlPrcBtnTxt.implicitWidth + 10; height: Style.space(20); radius: 4
                                    color: root.priceEditOpen ? "#89dceb" : "#313244"
                                    border.color: "#89dceb"; border.width: 1
                                    Text { id: wlPrcBtnTxt; anchors.centerIn: parent; text: root.priceEditOpen ? "Close" : "Update Price"; color: root.priceEditOpen ? "#1e1e2e" : "#89dceb"; font.pixelSize: 9; font.bold: true }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (!root.priceEditSym && root.chartSymbol) root.priceEditSym = root.chartSymbol
                                            root.priceEditOpen = !root.priceEditOpen
                                            if (root.priceEditOpen) root.watchAddOpen = false
                                        }
                                    }
                                }
                                Rectangle {
                                    width: wlAddBtnTxt.implicitWidth + 10; height: Style.space(20); radius: 4
                                    color: root.watchAddOpen ? "#89b4fa" : "#1e2e4a"
                                    border.color: "#89b4fa"; border.width: 1
                                    Text { id: wlAddBtnTxt; anchors.centerIn: parent; text: root.watchAddOpen ? "Close" : "+ Add Stock"; color: root.watchAddOpen ? "#1e1e2e" : "#89b4fa"; font.pixelSize: 9; font.bold: true }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            root.watchAddOpen = !root.watchAddOpen
                                            if (root.watchAddOpen) root.priceEditOpen = false
                                        }
                                    }
                                }
                            }
                        }

                        // Collapsible Add to Watchlist Bar
                        Rectangle {
                            width: watchlistCol.width; visible: root.watchAddOpen
                            height: wlAddFormRow.implicitHeight + Style.space(10); radius: 6; color: "#11111b"; border.color: "#89b4fa"; border.width: 1
                            Row {
                                id: wlAddFormRow
                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: Style.space(6) }
                                spacing: Style.space(5)
                                Rectangle {
                                    width: parent.width * 0.64; height: Style.space(24); radius: 4; color: "#313244"; border.color: "#45475a"; border.width: 1
                                    TextInput {
                                        id: wlAddSymIn; anchors.fill: parent; anchors.margins: 4; color: "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small || Style.font.body
                                        text: root.watchAddSym; onTextChanged: if (root.watchAddSym !== text) root.watchAddSym = text
                                        Connections { target: root; function onWatchAddSymChanged() { if (wlAddSymIn.text !== root.watchAddSym) wlAddSymIn.text = root.watchAddSym } }
                                        Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Enter stock symbol (for example INFR or SIM)"; color: "#6c7086"; font: wlAddSymIn.font; visible: !wlAddSymIn.text && !wlAddSymIn.activeFocus }
                                    }
                                }
                                Rectangle {
                                    width: parent.width * 0.36 - Style.space(5); height: Style.space(24); radius: 4; color: "#89b4fa"
                                    Text { anchors.centerIn: parent; text: "Add to Watchlist"; color: "#1e1e2e"; font.pixelSize: 10; font.bold: true }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                        onClicked: {
                                            var sy = root.watchAddSym.trim().toUpperCase()
                                            if (sy) {
                                                root.runCliCommand(["watch", "add", sy], false)
                                                root.watchAddSym = ""
                                                root.watchAddOpen = false
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Collapsible Manual Price Override Bar
                        Rectangle {
                            width: watchlistCol.width; visible: root.priceEditOpen
                            height: wlPrcFormRow.implicitHeight + Style.space(10); radius: 6; color: "#11111b"; border.color: "#89dceb"; border.width: 1
                            Row {
                                id: wlPrcFormRow
                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: Style.space(6) }
                                spacing: Style.space(5)
                                Rectangle {
                                    width: parent.width * 0.32; height: Style.space(24); radius: 4; color: "#313244"; border.color: "#45475a"; border.width: 1
                                    TextInput {
                                        id: peSymIn; anchors.fill: parent; anchors.margins: 4; color: "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small || Style.font.body
                                        text: root.priceEditSym; onTextChanged: if (root.priceEditSym !== text) root.priceEditSym = text
                                        Connections { target: root; function onPriceEditSymChanged() { if (peSymIn.text !== root.priceEditSym) peSymIn.text = root.priceEditSym } }
                                        Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Symbol"; color: "#6c7086"; font: peSymIn.font; visible: !peSymIn.text && !peSymIn.activeFocus }
                                    }
                                }
                                Rectangle {
                                    width: parent.width * 0.34; height: Style.space(24); radius: 4; color: "#313244"; border.color: "#45475a"; border.width: 1
                                    TextInput {
                                        id: peValIn; anchors.fill: parent; anchors.margins: 4; color: "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small || Style.font.body
                                        text: root.priceEditVal; onTextChanged: if (root.priceEditVal !== text) root.priceEditVal = text
                                        Connections { target: root; function onPriceEditValChanged() { if (peValIn.text !== root.priceEditVal) peValIn.text = root.priceEditVal } }
                                        Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "New Price $"; color: "#6c7086"; font: peValIn.font; visible: !peValIn.text && !peValIn.activeFocus }
                                    }
                                }
                                Rectangle {
                                    width: parent.width * 0.34 - Style.space(10); height: Style.space(24); radius: 4; color: "#89dceb"
                                    Text { anchors.centerIn: parent; text: "Save Price"; color: "#1e1e2e"; font.pixelSize: 10; font.bold: true }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                        onClicked: {
                                            var sy = root.priceEditSym.trim().toUpperCase()
                                            var pr = root.priceEditVal.replace(/^\s*\$?/, "").replace(/,/g, "").trim()
                                            if (sy && pr) {
                                                root.runCliCommand(["price", sy, pr], false)
                                                root.priceEditVal = ""
                                                root.priceEditOpen = false
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            visible: (root.summaryData.watchlist || []).length === 0 && !root.watchAddOpen
                            text: "Watchlist is empty — click '+ Add Stock' above to track counters."
                            color: "#6c7086"
                            font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                        }

                        Repeater {
                            model: root.summaryData.watchlist || []
                            delegate: Rectangle {
                                width: watchlistCol.width
                                height: watchInnerCol.implicitHeight + Style.space(8)
                                radius: 6
                                color: root.chartSymbol === modelData.symbol ? "#242436" : (watchHover.containsMouse ? "#1e1e2e" : "#11111b")
                                border.color: root.chartSymbol === modelData.symbol ? "#89b4fa" : "#242436"
                                border.width: 1

                                Rectangle {
                                    visible: root.chartSymbol === modelData.symbol
                                    width: 3
                                    height: parent.height - 6
                                    anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 1 }
                                    radius: 1.5
                                    color: "#89b4fa"
                                }

                                MouseArea {
                                    id: watchHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        root.symText = modelData.symbol
                                        root.chartSymbol = modelData.symbol
                                        root.hoveredCandleIdx = -1
                                    }
                                }

                                Column {
                                    id: watchInnerCol
                                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 8; rightMargin: 6 }
                                    spacing: 3

                                    Row {
                                        id: watchRow
                                        width: parent.width
                                        spacing: Style.space(4)
                                        Text {
                                            width: watchInnerCol.width * 0.20
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: modelData.symbol + (((root.summaryData.notes || ({}))[modelData.symbol]) ? " ✎" : "")
                                            color: modelData.currency === "ZWG" ? "#f9e2af" : "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small || Style.font.body
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }
                                        Canvas {
                                            id: sparkline
                                            width: Math.max(Style.space(62), watchInnerCol.width * 0.20)
                                            height: Style.space(22)
                                            anchors.verticalCenter: parent.verticalCenter
                                            property var pts: modelData.history || []
                                            onPtsChanged: requestPaint()
                                            onWidthChanged: requestPaint()
                                            Component.onCompleted: requestPaint()
                                            onPaint: {
                                                var ctx = getContext("2d")
                                                if (width <= 0 || height <= 0) return
                                                ctx.clearRect(0, 0, width, height)
                                                var pts = sparkline.pts
                                                if (!pts || pts.length === 0) return
                                                if (pts.length === 1) {
                                                    ctx.save()
                                                    ctx.strokeStyle = "#45475a"
                                                    ctx.lineWidth = 1
                                                    ctx.setLineDash([2, 2])
                                                    ctx.beginPath()
                                                    ctx.moveTo(2, height / 2); ctx.lineTo(width - 4, height / 2); ctx.stroke()
                                                    ctx.fillStyle = "#89b4fa"
                                                    ctx.beginPath(); ctx.arc(width - 4, height / 2, 2.2, 0, Math.PI * 2); ctx.fill()
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
                                                grad.addColorStop(0, up ? "rgba(166, 227, 161, 0.32)" : "rgba(243, 139, 168, 0.32)")
                                                grad.addColorStop(1, "rgba(0, 0, 0, 0.0)")
                                                ctx.fillStyle = grad
                                                ctx.beginPath()
                                                ctx.moveTo(coords[0].x, height)
                                                for (var j = 0; j < coords.length; j++) ctx.lineTo(coords[j].x, coords[j].y)
                                                ctx.lineTo(coords[coords.length - 1].x, height)
                                                ctx.closePath()
                                                ctx.fill()

                                                ctx.strokeStyle = strokeCol
                                                ctx.lineWidth = 1.6
                                                ctx.beginPath()
                                                for (var k = 0; k < coords.length; k++) {
                                                    if (k === 0) ctx.moveTo(coords[k].x, coords[k].y)
                                                    else ctx.lineTo(coords[k].x, coords[k].y)
                                                }
                                                ctx.stroke()

                                                var last = coords[coords.length - 1]
                                                ctx.fillStyle = strokeCol
                                                ctx.beginPath(); ctx.arc(last.x, last.y, 2.5, 0, Math.PI * 2); ctx.fill()
                                            }
                                        }
                                        Item {
                                            width: watchInnerCol.width * 0.19
                                            height: Style.space(20)
                                            anchors.verticalCenter: parent.verticalCenter
                                            Rectangle {
                                                visible: modelData.change_pct !== null && modelData.change_pct !== undefined
                                                anchors.centerIn: parent
                                                width: chgText.implicitWidth + 6
                                                height: chgText.implicitHeight + 3
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
                                                    font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                                    font.bold: true
                                                }
                                            }
                                        }
                                        Text {
                                            width: watchInnerCol.width * 0.22
                                            anchors.verticalCenter: parent.verticalCenter
                                            horizontalAlignment: Text.AlignRight
                                            elide: Text.ElideLeft
                                            text: modelData.price !== null && modelData.price !== undefined ? root.fmtPrice(modelData.price, modelData.currency) : "N/A"
                                            color: "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small || Style.font.body
                                        }
                                        Row {
                                            anchors.verticalCenter: parent.verticalCenter
                                            spacing: 3
                                            Text {
                                                text: "🔔"
                                                color: "#f9e2af"
                                                font.pixelSize: Style.font.small ? Style.font.small - 1 : 10
                                                MouseArea {
                                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                    onClicked: root.quickTrade("alert", modelData.symbol)
                                                }
                                            }
                                            Text {
                                                text: "+"
                                                color: "#a6e3a1"
                                                font.pixelSize: Style.font.body
                                                font.bold: true
                                                MouseArea {
                                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                    onClicked: root.quickTrade("buy", modelData.symbol)
                                                }
                                            }
                                            Text {
                                                text: "×"
                                                color: "#f38ba8"
                                                font.pixelSize: Style.font.body
                                                font.bold: true
                                                MouseArea {
                                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                                    onClicked: {
                                                        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                        manualProc.command = ["python3", script, "watch", "remove", modelData.symbol]
                                                        manualProc.running = true
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    // Bid/Ask Tug-of-War Bar + Spread % Pill
                                    Row {
                                        width: parent.width
                                        visible: Number(modelData.best_bid || 0) > 0 || Number(modelData.best_ask || 0) > 0
                                        spacing: Style.space(4)

                                        Text {
                                            width: parent.width * 0.34
                                            visible: Number(modelData.best_bid || 0) > 0
                                            text: "Bid " + root.fmtPrice(modelData.best_bid, modelData.currency) + " × " + root.fmtVol(modelData.bid_volume || 0)
                                            color: "#a6e3a1"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                            elide: Text.ElideRight
                                        }

                                        Rectangle {
                                            width: parent.width * 0.18
                                            height: 5
                                            radius: 2
                                            color: "#3d2229"
                                            anchors.verticalCenter: parent.verticalCenter
                                            Rectangle {
                                                width: {
                                                    var bv = Number(modelData.bid_volume || 0)
                                                    var av = Number(modelData.ask_volume || 0)
                                                    var tot = bv + av
                                                    return tot > 0 ? (bv / tot) * parent.width : parent.width * 0.5
                                                }
                                                height: parent.height
                                                radius: 2
                                                color: "#a6e3a1"
                                            }
                                        }

                                        Text {
                                            width: parent.width * 0.14
                                            horizontalAlignment: Text.AlignHCenter
                                            text: (modelData.spread_pct !== null && modelData.spread_pct !== undefined) ? (Number(modelData.spread_pct).toFixed(1) + "%") : ""
                                            color: modelData.wide_spread ? "#f9e2af" : "#6c7086"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                            font.bold: Boolean(modelData.wide_spread)
                                        }

                                        Text {
                                            width: parent.width * 0.34 - Style.space(12)
                                            visible: Number(modelData.best_ask || 0) > 0
                                            horizontalAlignment: Text.AlignRight
                                            text: "Ask " + root.fmtPrice(modelData.best_ask, modelData.currency) + " × " + root.fmtVol(modelData.ask_volume || 0)
                                            color: "#f38ba8"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                            elide: Text.ElideRight
                                        }
                                    }

                                    // Inline Watchlist News Catalyst Strip
                                    Rectangle {
                                        width: parent.width
                                        visible: Boolean(modelData.news_catalyst)
                                        height: wlNewsRow.implicitHeight + 4
                                        radius: 4
                                        color: modelData.news_catalyst ? root.newsSentimentBg(modelData.news_catalyst.sentiment) : "#181825"
                                        Row {
                                            id: wlNewsRow
                                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 5; rightMargin: 5 }
                                            spacing: 4
                                            Text {
                                                id: wlNewsCatTxt
                                                text: modelData.news_catalyst ? ("📰 " + modelData.news_catalyst.category) : ""
                                                color: modelData.news_catalyst ? root.newsSentimentColor(modelData.news_catalyst.sentiment) : "#89b4fa"
                                                font.pixelSize: 8
                                                font.bold: true
                                            }
                                            Text {
                                                width: Math.max(40, parent.width - wlNewsCatTxt.implicitWidth - 6)
                                                text: modelData.news_catalyst ? String(modelData.news_catalyst.title || "") : ""
                                                color: "#cdd6f4"
                                                font.pixelSize: 8
                                                elide: Text.ElideRight
                                            }
                                        }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                            onClicked: { root.newsFilter = "tracked"; root.activeTab = "analytics" }
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
                                width: parent.width - chartCloseBtn.width - Style.space(6)
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.chartSymbol + " • 30-Day Price Chart"
                                color: "#cdd6f4"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.body
                                font.bold: true
                                elide: Text.ElideRight
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

                        Flow {
                            id: chartToggleRow
                            width: parent.width
                            spacing: 4
                            Repeater {
                                model: [
                                    { key: "candles", label: "Candlesticks" },
                                    { key: "line", label: "Area Chart" }
                                ]
                                delegate: Rectangle {
                                    width: cModeLbl.implicitWidth + 10
                                    height: Style.space(18)
                                    radius: 4
                                    color: root.chartMode === modelData.key ? "#89b4fa" : "#313244"
                                    Text {
                                        id: cModeLbl
                                        anchors.centerIn: parent
                                        text: modelData.label
                                        color: root.chartMode === modelData.key ? "#1e1e2e" : "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                        font.bold: root.chartMode === modelData.key
                                    }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.chartMode = modelData.key }
                                }
                            }
                            Rectangle {
                                width: maTogLbl.implicitWidth + 10; height: Style.space(18); radius: 4
                                color: root.showMa20Overlay ? "#1e2e4a" : "#313244"
                                border.color: root.showMa20Overlay ? "#89b4fa" : "transparent"; border.width: 1
                                Text { id: maTogLbl; anchors.centerIn: parent; text: "Moving Average"; color: root.showMa20Overlay ? "#89b4fa" : "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.showMa20Overlay = !root.showMa20Overlay }
                            }
                            Rectangle {
                                width: beTogLbl.implicitWidth + 10; height: Style.space(18); radius: 4
                                color: root.showBeOverlay ? "#2b261d" : "#313244"
                                border.color: root.showBeOverlay ? "#f9e2af" : "transparent"; border.width: 1
                                Text { id: beTogLbl; anchors.centerIn: parent; text: "Break-Even"; color: root.showBeOverlay ? "#f9e2af" : "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.showBeOverlay = !root.showBeOverlay }
                            }
                            Rectangle {
                                width: olTogLbl.implicitWidth + 10; height: Style.space(18); radius: 4
                                color: root.showOptLimOverlay ? "#1b2e33" : "#313244"
                                border.color: root.showOptLimOverlay ? "#89dceb" : "transparent"; border.width: 1
                                Text { id: olTogLbl; anchors.centerIn: parent; text: "Optimal Limit"; color: root.showOptLimOverlay ? "#89dceb" : "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.showOptLimOverlay = !root.showOptLimOverlay }
                            }
                        }

                        // Quick Symbol Switcher Strip (Holdings + Watchlist)
                        Flow {
                            width: parent.width
                            spacing: Style.space(3)
                            Repeater {
                                model: {
                                    var seen = {}
                                    var out = []
                                    var items = root.summaryData.items || []
                                    var wl = root.summaryData.watchlist || []
                                    for (var i = 0; i < items.length; i++) {
                                        if (!seen[items[i].symbol]) { seen[items[i].symbol] = true; out.push(items[i].symbol) }
                                    }
                                    for (var j = 0; j < wl.length; j++) {
                                        if (!seen[wl[j].symbol]) { seen[wl[j].symbol] = true; out.push(wl[j].symbol) }
                                    }
                                    if (root.chartSymbol && !seen[root.chartSymbol]) out.unshift(root.chartSymbol)
                                    return out.slice(0, 7)
                                }
                                delegate: Rectangle {
                                    width: qsLbl.implicitWidth + 10
                                    height: Style.space(16)
                                    radius: 3
                                    color: root.chartSymbol === modelData ? "#89b4fa" : "#11111b"
                                    border.color: root.chartSymbol === modelData ? "#89b4fa" : "#313244"
                                    border.width: 1
                                    Text {
                                        id: qsLbl
                                        anchors.centerIn: parent
                                        text: modelData
                                        color: root.chartSymbol === modelData ? "#1e1e2e" : "#a6adc8"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                        font.bold: root.chartSymbol === modelData
                                    }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        onClicked: { root.chartSymbol = modelData; root.hoveredCandleIdx = -1 }
                                    }
                                }
                            }
                        }

                        // Interactive Price Canvas with Bid/Ask Corridor + Floating Crosshair HUD
                        Item {
                            width: parent.width
                            height: root.fullPageMode ? Style.space(210) : Style.space(162)

                            Canvas {
                                id: candleCanvas
                                anchors.fill: parent
                                onWidthChanged: requestPaint()
                                Component.onCompleted: {
                                    root.candleCanvasRef = candleCanvas
                                    candleCanvas.requestPaint()
                                }
                                onPaint: {
                                    var ctx = getContext("2d")
                                    if (width <= 0 || height <= 0) return
                                    ctx.clearRect(0, 0, width, height)
                                    var cs = root.activeCandles()
                                    if (!cs || cs.length === 0) return

                                    var padLeft = 46
                                    var padRight = 10
                                    var padTop = 22
                                    var padBottom = 8
                                    var plotW = Math.max(10, width - padLeft - padRight)
                                    var plotH = Math.max(10, height - padTop - padBottom)

                                    var aq = root.activeQuote()
                                    var ah = root.activeHolding()
                                    var minV = Number(cs[0].low)
                                    var maxV = Number(cs[0].high)
                                    for (var i = 0; i < cs.length; i++) {
                                        if (Number(cs[i].low) < minV) minV = Number(cs[i].low)
                                        if (Number(cs[i].high) > maxV) maxV = Number(cs[i].high)
                                    }
                                    if (aq && Number(aq.best_bid || 0) > 0 && Number(aq.best_ask || 0) > 0) {
                                        minV = Math.min(minV, Number(aq.best_bid))
                                        maxV = Math.max(maxV, Number(aq.best_ask))
                                    }
                                    if (maxV === minV) {
                                        var pad = Math.max(0.001, maxV * 0.02)
                                        maxV += pad
                                        minV = Math.max(0, minV - pad)
                                    }
                                    var span = maxV - minV || 1
                                    function yFor(v) { return padTop + plotH - ((v - minV) / span) * plotH }

                                    // Bid-Ask Spread Corridor
                                    if (aq && Number(aq.best_bid || 0) > 0 && Number(aq.best_ask || 0) > Number(aq.best_bid || 0)) {
                                        var yAsk = yFor(Number(aq.best_ask))
                                        var yBid = yFor(Number(aq.best_bid))
                                        ctx.fillStyle = "rgba(137, 220, 235, 0.07)"
                                        ctx.fillRect(padLeft, yAsk, plotW, Math.max(2, yBid - yAsk))
                                    }

                                    // Gridlines + Price labels
                                    ctx.font = "9px sans-serif"
                                    ctx.textBaseline = "middle"
                                    var levels = [maxV, (maxV + minV) / 2, minV]
                                    for (var g = 0; g < levels.length; g++) {
                                        var gy = yFor(levels[g])
                                        ctx.save()
                                        ctx.strokeStyle = "#242436"
                                        ctx.lineWidth = 1
                                        ctx.setLineDash([2, 3])
                                        ctx.beginPath()
                                        ctx.moveTo(padLeft, gy); ctx.lineTo(width - padRight, gy); ctx.stroke()
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
                                        grad.addColorStop(0, up ? "rgba(166, 227, 161, 0.28)" : "rgba(243, 139, 168, 0.28)")
                                        grad.addColorStop(1, "rgba(0, 0, 0, 0.0)")
                                        ctx.fillStyle = grad
                                        ctx.beginPath()
                                        ctx.moveTo(pts[0].x, padTop + plotH)
                                        for (var j = 0; j < pts.length; j++) ctx.lineTo(pts[j].x, pts[j].y)
                                        ctx.lineTo(pts[pts.length - 1].x, padTop + plotH)
                                        ctx.closePath(); ctx.fill()

                                        ctx.strokeStyle = strokeCol
                                        ctx.lineWidth = 2
                                        ctx.beginPath()
                                        for (var k = 0; k < pts.length; k++) {
                                            if (k === 0) ctx.moveTo(pts[k].x, pts[k].y)
                                            else ctx.lineTo(pts[k].x, pts[k].y)
                                        }
                                        ctx.stroke()

                                        var hi = (root.hoveredCandleIdx >= 0 && root.hoveredCandleIdx < n) ? root.hoveredCandleIdx : (n - 1)
                                        ctx.fillStyle = strokeCol
                                        ctx.beginPath(); ctx.arc(pts[hi].x, pts[hi].y, 3.2, 0, Math.PI * 2); ctx.fill()
                                    } else {
                                        // Candlestick mode
                                        var bodyW = Math.max(4, Math.min(n <= 6 ? 11 : 14, slotW * 0.36))
                                        for (var c = 0; c < n; c++) {
                                            var cd = cs[c]
                                            var cx = padLeft + slotW * (c + 0.5)
                                            if (c === root.hoveredCandleIdx) {
                                                ctx.fillStyle = "#242436"
                                                ctx.fillRect(padLeft + slotW * c, padTop, slotW, plotH)
                                            }
                                            var o = Number(cd.open), h = Number(cd.high), l = Number(cd.low), cl = Number(cd.close)
                                            var col = cl >= o ? "#a6e3a1" : "#f38ba8"
                                            ctx.strokeStyle = col; ctx.lineWidth = 1.5
                                            ctx.beginPath(); ctx.moveTo(cx, yFor(h)); ctx.lineTo(cx, yFor(l)); ctx.stroke()
                                            var yo = yFor(o), yc = yFor(cl)
                                            ctx.fillStyle = col
                                            ctx.fillRect(cx - bodyW / 2, Math.min(yo, yc), bodyW, Math.max(2, Math.abs(yc - yo)))
                                        }
                                    }

                                    // 20D Moving Average overlay (#89b4fa)
                                    var maSer = (aq && aq.ma20_series) ? aq.ma20_series : []
                                    if (root.showMa20Overlay && maSer.length >= 2 && maSer.length === n) {
                                        ctx.strokeStyle = "#89b4fa"
                                        ctx.lineWidth = 1.4
                                        ctx.beginPath()
                                        for (var mi = 0; mi < maSer.length; mi++) {
                                            var mx = root.chartMode === "line" && n > 1 ? (padLeft + (mi / (n - 1)) * plotW) : (padLeft + slotW * (mi + 0.5))
                                            var my = yFor(Number(maSer[mi]))
                                            if (mi === 0) ctx.moveTo(mx, my); else ctx.lineTo(mx, my)
                                        }
                                        ctx.stroke()
                                    }

                                    // Held Cost / Breakeven dashed horizontal line (#f9e2af)
                                    var refCost = ah ? Number(ah.breakeven_price || ah.avg_cost || 0) : 0
                                    if (root.showBeOverlay && refCost >= minV && refCost <= maxV && refCost > 0) {
                                        var cy = yFor(refCost)
                                        ctx.save(); ctx.strokeStyle = "#f9e2af"; ctx.lineWidth = 1.2; ctx.setLineDash([4, 3])
                                        ctx.beginPath(); ctx.moveTo(padLeft, cy); ctx.lineTo(width - padRight, cy); ctx.stroke()
                                        ctx.restore()
                                    }

                                    // Smart Optimal Limit dashed horizontal line (#89dceb)
                                    var optL = aq ? Number(aq.optimal_limit || 0) : 0
                                    if (root.showOptLimOverlay && optL >= minV && optL <= maxV && optL > 0) {
                                        var oy = yFor(optL)
                                        ctx.save(); ctx.strokeStyle = "#89dceb"; ctx.lineWidth = 1.1; ctx.setLineDash([2, 3])
                                        ctx.beginPath(); ctx.moveTo(padLeft, oy); ctx.lineTo(width - padRight, oy); ctx.stroke()
                                        ctx.restore()
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onPositionChanged: function(mouse) {
                                        var cs = root.activeCandles()
                                        if (!cs || cs.length === 0) { root.hoveredCandleIdx = -1; return }
                                        var rel = (mouse.x - 46) / Math.max(10, width - 56)
                                        if (rel < 0 || rel > 1) { root.hoveredCandleIdx = -1; return }
                                        root.hoveredCandleIdx = Math.max(0, Math.min(cs.length - 1, Math.floor(rel * cs.length)))
                                    }
                                    onExited: root.hoveredCandleIdx = -1
                                }
                            }

                            // Floating OHLC Crosshair HUD inside Top-Left of Canvas
                            Rectangle {
                                anchors { left: parent.left; top: parent.top; leftMargin: 46 }
                                width: hudTxt.implicitWidth + 10
                                height: hudTxt.implicitHeight + 4
                                radius: 4
                                color: "#cc11111b"
                                border.color: "#313244"
                                border.width: 1
                                property var curCandle: {
                                    var cs = root.activeCandles()
                                    if (!cs || cs.length === 0) return null
                                    var idx = (root.hoveredCandleIdx >= 0 && root.hoveredCandleIdx < cs.length) ? root.hoveredCandleIdx : (cs.length - 1)
                                    return cs[idx]
                                }
                                Text {
                                    id: hudTxt
                                    anchors.centerIn: parent
                                    text: {
                                        if (!parent.curCandle) return "No candlestick history yet"
                                        var c = parent.curCandle
                                        var pf = root.moneyPrefix(root.activeCurrency())
                                        return c.date + " • Open " + pf + Number(c.open).toFixed(4) + "  High " + pf + Number(c.high).toFixed(4) + "  Low " + pf + Number(c.low).toFixed(4) + "  Close " + pf + Number(c.close).toFixed(4)
                                    }
                                    color: parent.curCandle ? (Number(parent.curCandle.close) >= Number(parent.curCandle.open) ? "#a6e3a1" : "#f38ba8") : "#a6adc8"
                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                    font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                }
                            }
                        }

                        // Visual RSI-14 Gradient Spectrum + Z-Score Mean-Reversion Slider
                        Row {
                            width: parent.width
                            spacing: Style.space(8)
                            property var aq: root.activeQuote() || ({})
                            property real rsiVal: Number(aq.rsi14 !== null && aq.rsi14 !== undefined ? aq.rsi14 : 50)
                            property bool hasRsi: aq.rsi14 !== null && aq.rsi14 !== undefined
                            property real zVal: Number(aq.z_score !== null && aq.z_score !== undefined ? aq.z_score : 0)
                            property bool hasZ: aq.z_score !== null && aq.z_score !== undefined

                            // RSI-14 Gauge
                            Column {
                                width: (parent.width - Style.space(8)) / 2
                                spacing: 2
                                Row {
                                    width: parent.width
                                    Text { width: parent.width * 0.62; text: "Relative Strength (14-Day)"; color: "#a6adc8"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                    Text {
                                        width: parent.width * 0.38; horizontalAlignment: Text.AlignRight
                                        text: parent.parent.parent.hasRsi ? (parent.parent.parent.rsiVal.toFixed(0) + (parent.parent.parent.rsiVal <= 30 ? " Oversold" : (parent.parent.parent.rsiVal >= 70 ? " Overbought" : " Neutral"))) : "--"
                                        color: !parent.parent.parent.hasRsi ? "#6c7086" : (parent.parent.parent.rsiVal <= 30 ? "#a6e3a1" : (parent.parent.parent.rsiVal >= 70 ? "#f38ba8" : "#cdd6f4"))
                                        font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true
                                    }
                                }
                                Item {
                                    width: parent.width; height: 8
                                    Row {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width; height: 5; spacing: 1
                                        Rectangle { width: parent.width * 0.30; height: 5; radius: 2; color: "#243b2c" }
                                        Rectangle { width: parent.width * 0.40 - 2; height: 5; radius: 2; color: "#313244" }
                                        Rectangle { width: parent.width * 0.30; height: 5; radius: 2; color: "#3d2229" }
                                    }
                                    Rectangle {
                                        visible: parent.parent.parent.hasRsi
                                        x: Math.max(0, Math.min(parent.width - 6, (parent.parent.parent.rsiVal / 100.0) * parent.width - 3))
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 6; height: 8; radius: 3; color: "#cdd6f4"; border.color: "#11111b"; border.width: 1
                                    }
                                }
                            }

                            // Z-Score Gauge (-2σ .. 0 .. +2σ)
                            Column {
                                width: (parent.width - Style.space(8)) / 2
                                spacing: 2
                                Row {
                                    width: parent.width
                                    Text { width: parent.width * 0.62; text: "Price Z-Score (20-Day)"; color: "#a6adc8"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                    Text {
                                        width: parent.width * 0.38; horizontalAlignment: Text.AlignRight
                                        text: parent.parent.parent.hasZ ? ((parent.parent.parent.zVal >= 0 ? "+" : "") + parent.parent.parent.zVal.toFixed(1) + " std dev") : "--"
                                        color: !parent.parent.parent.hasZ ? "#6c7086" : (parent.parent.parent.zVal <= -1.0 ? "#a6e3a1" : (parent.parent.parent.zVal >= 1.5 ? "#f38ba8" : "#89b4fa"))
                                        font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true
                                    }
                                }
                                Item {
                                    width: parent.width; height: 8
                                    Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width; height: 5; radius: 2; color: "#313244"
                                        Rectangle { x: parent.width / 2 - 1; y: -1; width: 2; height: 7; color: "#6c7086" }
                                        Rectangle {
                                            visible: parent.parent.parent.parent.hasZ
                                            property real norm: Math.max(-2, Math.min(2, parent.parent.parent.parent.zVal)) / 4.0 + 0.5
                                            x: Math.max(0, Math.min(parent.width - 6, norm * parent.width - 3))
                                            y: -1.5; width: 6; height: 8; radius: 3
                                            color: parent.parent.parent.parent.zVal <= -1.0 ? "#a6e3a1" : (parent.parent.parent.parent.zVal >= 1.5 ? "#f38ba8" : "#89b4fa")
                                            border.color: "#11111b"; border.width: 1
                                        }
                                    }
                                }
                            }
                        }

                        // Compact Quant Execution Pill Row (OptLim, Liquidity, BE)
                        Row {
                            width: parent.width
                            spacing: Style.space(6)
                            property var aq: root.activeQuote() || ({})
                            property var ah: root.activeHolding()
                            Text {
                                width: parent.width * 0.38
                                text: parent.aq.optimal_limit ? ("Optimal Limit: " + root.fmtPrice(parent.aq.optimal_limit, root.activeCurrency())) : "Optimal Limit: --"
                                color: "#89dceb"
                                font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                font.bold: true
                                elide: Text.ElideRight
                            }
                            Text {
                                width: parent.width * 0.30
                                horizontalAlignment: Text.AlignHCenter
                                text: (parent.aq.liquidity_score !== undefined && parent.aq.liquidity_score !== null) ? ("Liquidity: " + parent.aq.liquidity_score + "/100") : "Liquidity: --"
                                color: "#a6adc8"
                                font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                            }
                            Text {
                                width: parent.width * 0.32 - Style.space(12)
                                horizontalAlignment: Text.AlignRight
                                text: parent.ah ? ("Breakeven: " + root.fmtPrice(parent.ah.breakeven_price || parent.ah.avg_cost || 0, root.activeCurrency())) : ((parent.aq.spread_pct !== null && parent.aq.spread_pct !== undefined) ? ("Spread: " + Number(parent.aq.spread_pct).toFixed(1) + "%") : "")
                                color: "#f9e2af"
                                font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                elide: Text.ElideRight
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

                        Text {
                            text: "Trade Order Ticket"
                            color: "#cdd6f4"
                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                            font.pixelSize: Style.font.body
                            font.bold: true
                        }

                        Row {
                            width: parent.width
                            spacing: Style.space(6)
                            Repeater {
                                model: [
                                    { key: "buy", label: "Buy Shares", activeBg: "#a6e3a1", idleBg: "#1b2e24", idleFg: "#a6e3a1" },
                                    { key: "sell", label: "Sell Shares", activeBg: "#f38ba8", idleBg: "#2d1d24", idleFg: "#f38ba8" }
                                ]
                                delegate: Rectangle {
                                    width: (manualCol.width - Style.space(6)) / 2
                                    height: modeLabel.implicitHeight + Style.space(6)
                                    radius: 4
                                    color: root.manualMode === modelData.key ? modelData.activeBg : modelData.idleBg
                                    border.color: root.manualMode === modelData.key ? modelData.activeBg : "#45475a"
                                    border.width: 1
                                    Text {
                                        id: modeLabel
                                        anchors.centerIn: parent
                                        text: modelData.label
                                        color: root.manualMode === modelData.key ? "#1e1e2e" : modelData.idleFg
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.small || Style.font.body
                                        font.bold: true
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

                        // Quick Optimal Limit + $25 / $50 / $100 Sizing Chips
                        Flow {
                            width: parent.width
                            spacing: Style.space(4)
                            property var symQ: {
                                var s = root.symText.trim().toUpperCase() || root.chartSymbol
                                if (!s) return null
                                var lists = [root.summaryData.signals || [], root.summaryData.watchlist || [], root.summaryData.screener || [], root.summaryData.items || []]
                                for (var li = 0; li < lists.length; li++) {
                                    for (var i = 0; i < lists[li].length; i++) if (lists[li][i].symbol === s) return lists[li][i]
                                }
                                return null
                            }

                            Rectangle {
                                visible: Boolean(parent.symQ && (parent.symQ.optimal_limit || parent.symQ.limit_price || parent.symQ.price))
                                width: optChipTxt.implicitWidth + 10; height: Style.space(18); radius: 4; color: "#1b2e33"; border.color: "#89dceb"; border.width: 1
                                Text {
                                    id: optChipTxt; anchors.centerIn: parent
                                    text: "Optimal Limit $" + Number((parent.parent.symQ && (parent.parent.symQ.optimal_limit || parent.parent.symQ.limit_price || parent.parent.symQ.price)) || 0).toFixed(4)
                                    color: "#89dceb"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true
                                }
                                MouseArea {
                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        var q = parent.parent.symQ
                                        if (q) {
                                            if (!root.symText) root.symText = q.symbol
                                            root.priceText = Number(q.optimal_limit || q.limit_price || q.price || 0).toFixed(4)
                                        }
                                    }
                                }
                            }

                            Repeater {
                                model: [25, 50, 100]
                                delegate: Rectangle {
                                    width: szChipTxt.implicitWidth + 10; height: Style.space(18); radius: 4; color: "#313244"
                                    Text { id: szChipTxt; anchors.centerIn: parent; text: "$" + modelData; color: "#cdd6f4"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            var p = Number(root.priceText.replace(/[^0-9.]/g, ""))
                                            if (!(p > 0) && parent.parent.symQ) {
                                                p = Number(parent.parent.symQ.optimal_limit || parent.parent.symQ.price || 0)
                                                if (p > 0) root.priceText = p.toFixed(4)
                                            }
                                            if (p > 0) root.sharesText = String(Math.max(1, Math.floor(modelData / p)))
                                        }
                                    }
                                }
                            }
                        }

                        // Buy Strategy Horizon Selector (Automatic / Core Hold / Swing Trade) + 1-Click Guardrails
                        Flow {
                            width: parent.width
                            visible: root.manualMode === "buy"
                            spacing: Style.space(4)

                            Text { text: "Strategy:"; color: "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; height: Style.space(18); verticalAlignment: Text.AlignVCenter }

                            Repeater {
                                model: [
                                    { key: "auto", label: "Automatic", col: "#89b4fa" },
                                    { key: "core", label: "Core Hold", col: "#a6e3a1" },
                                    { key: "swing", label: "Swing Trade", col: "#cba6f7" }
                                ]
                                delegate: Rectangle {
                                    width: bhTxt.implicitWidth + 10; height: Style.space(18); radius: 4
                                    color: root.buyHorizonTag === modelData.key ? modelData.col : "#313244"
                                    Text { id: bhTxt; anchors.centerIn: parent; text: modelData.label; color: root.buyHorizonTag === modelData.key ? "#1e1e2e" : "#cdd6f4"; font.pixelSize: 9; font.bold: true }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.buyHorizonTag = modelData.key }
                                }
                            }

                            // 1-Click Guardrail Helper matching active horizon
                            Rectangle {
                                property string effTag: root.buyHorizonTag !== "auto" ? root.buyHorizonTag : (root.effectiveTradingGoal() === "long" ? "core" : "swing")
                                visible: root.symText.trim().length > 0
                                width: grdTxt.implicitWidth + 10; height: Style.space(18); radius: 4
                                color: effTag === "swing" ? "#2b261d" : "#1f3a27"
                                border.color: effTag === "swing" ? "#f9e2af" : "#a6e3a1"; border.width: 1
                                Text {
                                    id: grdTxt; anchors.centerIn: parent
                                    text: parent.effTag === "swing" ? "🛡 7% Trailing Stop" : "🎯 25% Profit Target"
                                    color: parent.effTag === "swing" ? "#f9e2af" : "#a6e3a1"
                                    font.pixelSize: 9; font.bold: true
                                }
                                MouseArea {
                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                    onClicked: {
                                        var sy = root.symText.trim().toUpperCase(); if (!sy) return
                                        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                        if (parent.effTag === "swing") {
                                            manualProc.command = ["python3", script, "stop", "add", sy, "7"]
                                        } else {
                                            manualProc.command = ["python3", script, "target", "set", sy, "25"]
                                        }
                                        manualProc.running = true
                                    }
                                }
                            }
                        }

                    Row {
                        width: parent.width
                        spacing: Style.space(6)

                        Rectangle {
                            width: parent.width * 0.25
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
                                KeyNavigation.tab: sharesInput
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
                            width: parent.width * 0.27
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
                                KeyNavigation.tab: symbolInput
                                KeyNavigation.backtab: sharesInput
                                onAccepted: root.submitManualEntry()
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
                            width: parent.width * 0.26 - Style.space(18)
                            height: Style.space(26)
                            radius: 4
                            color: (manualProc.running || dcaProc.running) ? "#45475a" : (root.manualMode === "sell" ? "#f38ba8" : "#a6e3a1")

                            Text {
                                anchors.centerIn: parent
                                text: (manualProc.running || dcaProc.running) ? "Saving..." : (root.manualMode === "sell" ? "Save Sell" : "Save Buy")
                                color: "#1e1e2e"
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.small || Style.font.body
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

                    // Live Pre-Trade Risk Impact Bar (Est $, Statutory/Custom Fee Receipt, Post-Trade Weight vs Max Cap %)
                    Rectangle {
                        id: preImpRect
                        width: parent.width
                        property real shNum: Number(root.sharesText.replace(/[^0-9.]/g, "")) || 0
                        property real prcNum: Number(root.priceText.replace(/[^0-9.]/g, "")) || 0
                        property real estTotal: shNum * prcNum
                        property real capPct: Number((root.summaryData.fee_config || ({})).max_stock_pct || 25)
                        property real postWeightPct: {
                            if (root.manualMode !== "buy" || estTotal <= 0) return 0
                            var s = root.symText.trim().toUpperCase()
                            var totV = Number(root.summaryData.total_value || 0)
                            var curSymV = 0
                            var items = root.summaryData.items || []
                            for (var i = 0; i < items.length; i++) if (items[i].symbol === s) curSymV = Number(items[i].value || 0)
                            var newTot = Math.max(estTotal, totV + estTotal)
                            return newTot > 0 ? ((curSymV + estTotal) / newTot * 100.0) : 0
                        }
                        visible: (root.manualMode === "buy" || root.manualMode === "sell") && estTotal > 0
                        height: preImpCol.implicitHeight + Style.space(8)
                        radius: 5
                        color: "#11111b"
                        border.color: (root.manualMode === "buy" && postWeightPct > capPct) ? "#f9e2af" : "#313244"
                        border.width: 1

                        Column {
                            id: preImpCol
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: Style.space(6) }
                            spacing: 3
                            property bool isBuy: root.manualMode === "buy"
                            property bool isZse: root.symText.trim().toUpperCase().slice(-3) === ".ZW"
                            property string curPref: isZse ? "ZiG " : "$"
                            property real brk: Math.round(preImpRect.estTotal * (isZse ? 0.0092 : 0.0059) * 100) / 100
                            property real vat: Math.round(brk * 0.15 * 100) / 100
                            property real plt: Math.round(preImpRect.estTotal * (isZse ? 0.00095 : 0.0012) * 100) / 100
                            property real secz: Math.round(preImpRect.estTotal * (isZse ? 0.0016 : 0.0012) * 100) / 100
                            property real stmp: isBuy ? (Math.round(preImpRect.estTotal * (isZse ? 0.0025 : 0.0024) * 100) / 100) : 0.0
                            property real cgt: (!isBuy && isZse) ? (Math.round(preImpRect.estTotal * 0.015 * 100) / 100) : 0.0
                            property real estFees: {
                                var fcfg = root.summaryData.fee_config || ({})
                                var useStat = preImpCol.isZse ? Boolean(fcfg.zse_statutory !== false) : Boolean(fcfg.vfex_statutory !== false)
                                if (useStat) {
                                    var b = (preImpRect.estTotal >= 1.0 && preImpCol.brk === 0) ? 0.01 : preImpCol.brk
                                    var v = (b >= 0.04 && preImpCol.vat === 0) ? 0.01 : preImpCol.vat
                                    var p = (!preImpCol.isZse && preImpRect.estTotal >= 5.0 && preImpCol.plt === 0) ? 0.01 : preImpCol.plt
                                    var s = (!preImpCol.isZse && preImpRect.estTotal >= 5.0 && preImpCol.secz === 0) ? 0.01 : preImpCol.secz
                                    var d = (preImpCol.isBuy && !preImpCol.isZse && preImpRect.estTotal >= 5.0 && preImpCol.stmp === 0) ? 0.01 : preImpCol.stmp
                                    return Math.round((b + v + p + s + d + preImpCol.cgt) * 100) / 100
                                }
                                var fp = preImpCol.isZse ? Number(fcfg.zse_fee_pct || 0) : Number(fcfg.vfex_fee_pct || 0)
                                return Math.round(preImpRect.estTotal * (fp / 100.0) * 100) / 100
                            }
                            property real netTotal: preImpCol.isBuy ? (preImpRect.estTotal + preImpCol.estFees) : Math.max(0, preImpRect.estTotal - preImpCol.estFees)

                            Row {
                                width: parent.width
                                Text {
                                    width: parent.width * 0.58
                                    text: "Gross " + preImpCol.curPref + preImpRect.estTotal.toFixed(2) + (preImpCol.estFees > 0 ? (" + " + preImpCol.estFees.toFixed(2) + " fee = Net " + preImpCol.curPref + preImpCol.netTotal.toFixed(2)) : "")
                                    color: "#cdd6f4"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true; elide: Text.ElideRight
                                }
                                Text {
                                    width: parent.width * 0.42; horizontalAlignment: Text.AlignRight
                                    visible: root.manualMode === "buy"
                                    text: "Weight: " + preImpRect.postWeightPct.toFixed(0) + "% (Cap " + preImpRect.capPct.toFixed(0) + "%)"
                                    color: preImpRect.postWeightPct > preImpRect.capPct ? "#f9e2af" : "#a6e3a1"
                                    font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true
                                }
                            }
                            Text {
                                width: parent.width
                                visible: preImpCol.estFees > 0 && preImpRect.estTotal > 0
                                text: "Receipt: Brokerage " + preImpCol.brk.toFixed(2) + " • VAT " + preImpCol.vat.toFixed(2) + " • Platform/SECZ " + (preImpCol.plt + preImpCol.secz).toFixed(2) + (preImpCol.stmp > 0 ? (" • Stamp Duty " + preImpCol.stmp.toFixed(2)) : "") + (preImpCol.cgt > 0 ? (" • CGT " + preImpCol.cgt.toFixed(2)) : "")
                                color: "#a6adc8"; font.pixelSize: 8; elide: Text.ElideRight
                            }
                            Item {
                                width: parent.width; height: 5; visible: root.manualMode === "buy"
                                Rectangle {
                                    anchors.fill: parent; radius: 2.5; color: "#313244"
                                    Rectangle {
                                        width: Math.min(1, preImpRect.postWeightPct / 100.0) * parent.width
                                        height: parent.height; radius: 2.5
                                        color: preImpRect.postWeightPct > preImpRect.capPct ? "#f9e2af" : "#a6e3a1"
                                    }
                                    Rectangle {
                                        x: Math.min(parent.width - 2, (preImpRect.capPct / 100.0) * parent.width)
                                        y: -1; width: 1.5; height: 7; color: "#f38ba8"
                                    }
                                }
                            }
                        }
                    }

                    Row {
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
                                    text: "Trade Date (blank = Today)"
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
                            width: calBtnTxt.implicitWidth + Style.space(14)
                            height: Style.space(26)
                            radius: 4
                            color: root.calendarOpen ? "#89b4fa" : "#313244"
                            border.color: root.calendarOpen ? "#89b4fa" : "#45475a"
                            border.width: 1
                            Text {
                                id: calBtnTxt
                                anchors.centerIn: parent
                                text: root.calendarOpen ? "Calendar ▴" : "Calendar ▾"
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
                        visible: root.calendarOpen
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
                    }
                }
                    }
                }

                // === TAB 2: DUAL-VIEW MARKET SCREENER (HEATMAP + FULL SORTABLE TABLE) ===
                Column {
                    id: screenerTabCol
                    visible: root.activeTab === "screener"
                    width: parent.width
                    spacing: Style.space(8)

                    Rectangle {
                        width: parent.width
                        height: scrCtrlCol.implicitHeight + Style.space(12)
                        radius: 8
                        color: "#181825"
                        border.color: "#313244"
                        border.width: 1

                        Column {
                            id: scrCtrlCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(6) }
                            spacing: Style.space(6)

                            Row {
                                width: parent.width
                                spacing: Style.space(6)

                                Rectangle {
                                    width: parent.width * 0.36
                                    height: Style.space(26)
                                    radius: 4
                                    color: "#313244"
                                    border.color: scrSearchInput.activeFocus ? "#89b4fa" : "#45475a"
                                    border.width: 1
                                    TextInput {
                                        id: scrSearchInput
                                        anchors.fill: parent; anchors.margins: Style.space(5)
                                        color: "#cdd6f4"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.body
                                        verticalAlignment: TextInput.AlignVCenter; clip: true
                                        Component.onCompleted: text = root.screenerQuery
                                        onTextChanged: if (root.screenerQuery !== text) root.screenerQuery = text
                                        Connections { target: root; function onScreenerQueryChanged() { if (scrSearchInput.text !== root.screenerQuery) scrSearchInput.text = root.screenerQuery } }
                                        Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Search 56 VFEX + ZSE..."; color: "#6c7086"; font: scrSearchInput.font; visible: !scrSearchInput.text && !scrSearchInput.activeFocus }
                                    }
                                }

                                Row {
                                    id: viewSwitchRow
                                    spacing: 3
                                    anchors.verticalCenter: parent.verticalCenter
                                    Repeater {
                                        model: [
                                            { key: "heatmap", label: "⊞ Heatmap" },
                                            { key: "table", label: "☰ Table" }
                                        ]
                                        delegate: Rectangle {
                                            width: vmTxt.implicitWidth + 12; height: Style.space(24); radius: 4
                                            color: root.screenerViewMode === modelData.key ? "#a6e3a1" : "#313244"
                                            Text { id: vmTxt; anchors.centerIn: parent; text: modelData.label; color: root.screenerViewMode === modelData.key ? "#1e1e2e" : "#cdd6f4"; font.pixelSize: Style.font.small ? Style.font.small - 1 : 10; font.bold: true }
                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.screenerViewMode = modelData.key }
                                        }
                                    }
                                }

                                Flow {
                                    width: parent.width - parent.width * 0.36 - viewSwitchRow.width - Style.space(12)
                                    spacing: Style.space(3)
                                    anchors.verticalCenter: parent.verticalCenter
                                    Repeater {
                                        model: [
                                            { key: "all", label: "All" },
                                            { key: "vfex", label: "VFEX" },
                                            { key: "zse", label: "ZSE" },
                                            { key: "signals", label: "Signals" },
                                            { key: "gainers", label: "Gainers" },
                                            { key: "losers", label: "Losers" },
                                            { key: "liquid", label: "Liquidity" }
                                        ]
                                        delegate: Rectangle {
                                            width: fltLbl.implicitWidth + Style.space(8); height: Style.space(20); radius: 4
                                            color: root.screenerFilter === modelData.key ? "#89b4fa" : "#313244"
                                            Text { id: fltLbl; anchors.centerIn: parent; text: modelData.label; color: root.screenerFilter === modelData.key ? "#1e1e2e" : "#cdd6f4"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: root.screenerFilter === modelData.key }
                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.screenerFilter = modelData.key }
                                        }
                                    }
                                }
                            }

                            Flow {
                                width: parent.width
                                spacing: Style.space(4)
                                Text { text: "Sort:"; color: "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; height: Style.space(18); verticalAlignment: Text.AlignVCenter }
                                Repeater {
                                    model: [
                                        { key: "signal", label: "Signal" },
                                        { key: "change", label: "Day Change %" },
                                        { key: "liquidity", label: "Liquidity" },
                                        { key: "spread", label: "Tightest Spread" },
                                        { key: "price", label: "Price" },
                                        { key: "symbol", label: "Alphabetical" }
                                    ]
                                    delegate: Rectangle {
                                        width: srtLbl.implicitWidth + 10; height: Style.space(18); radius: 3
                                        color: root.screenerSortKey === modelData.key ? "#242436" : "transparent"
                                        border.color: root.screenerSortKey === modelData.key ? "#89b4fa" : "#313244"; border.width: 1
                                        Text {
                                            id: srtLbl; anchors.centerIn: parent
                                            text: modelData.label + (root.screenerSortKey === modelData.key ? (root.screenerSortDesc ? " ↓" : " ↑") : "")
                                            color: root.screenerSortKey === modelData.key ? "#89b4fa" : "#a6adc8"
                                            font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                        }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                if (root.screenerSortKey === modelData.key) root.screenerSortDesc = !root.screenerSortDesc
                                                else { root.screenerSortKey = modelData.key; root.screenerSortDesc = true }
                                            }
                                        }
                                    }
                                }
                                Text {
                                    text: (root.filteredScreener()).length + " counters • ★ Signal • ● Owned • ◎ Watchlist"
                                    color: "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                    height: Style.space(18); verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }

                    Rectangle {
                        width: parent.width
                        height: root.fullPageMode
                            ? Math.max(Style.space(520), panel.availableCardHeight - Style.space(220))
                            : (root.wideLayout ? Style.space(430) : Style.space(340))
                        radius: 8
                        color: "#181825"
                        border.color: "#313244"
                        border.width: 1
                        clip: true

                        Flickable {
                            anchors { fill: parent; margins: Style.space(6) }
                            contentWidth: width
                            contentHeight: root.screenerViewMode === "heatmap" ? hmGrid.implicitHeight : scrTableCol.implicitHeight
                            clip: true

                            Grid {
                                id: hmGrid
                                visible: root.screenerViewMode === "heatmap"
                                width: parent.width
                                columns: root.fullPageMode ? 8 : (root.wideLayout ? 6 : 3)
                                columnSpacing: Style.space(5)
                                rowSpacing: Style.space(5)

                                Repeater {
                                    model: root.filteredScreener()
                                    delegate: Rectangle {
                                        width: (hmGrid.width - Style.space(5) * (hmGrid.columns - 1)) / hmGrid.columns
                                        height: Style.space(66)
                                        radius: 6
                                        color: root.heatmapTileColor(modelData.change_pct)
                                        border.color: hmMouse.containsMouse ? "#89b4fa" : (Number(modelData.signal_score || 0) >= 35 ? "#a6e3a1" : "#313244")
                                        border.width: Number(modelData.signal_score || 0) >= 35 ? 1.5 : 1

                                        MouseArea {
                                            id: hmMouse
                                            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                root.activeTab = "overview"
                                                root.chartSymbol = modelData.symbol
                                                root.symText = modelData.symbol
                                                root.priceText = Number(modelData.optimal_limit || modelData.price || 0).toFixed(4)
                                                if (Number(modelData.recommended_shares || 0) > 0) root.sharesText = String(modelData.recommended_shares)
                                                root.manualMode = modelData.signal_action === "SELL" ? "sell" : "buy"
                                            }
                                        }

                                        Column {
                                            anchors { fill: parent; margins: 5 }
                                            spacing: 1
                                            Row {
                                                width: parent.width
                                                Text {
                                                    width: parent.width - watchPillCorner.width - 2
                                                    text: modelData.symbol + (Number(modelData.signal_score || 0) > 0 ? "★" : "") + (root.isOwnedSymbol(modelData.symbol) ? "●" : "")
                                                    color: modelData.currency === "ZWG" ? "#f9e2af" : "#cdd6f4"
                                                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                                    font.pixelSize: Style.font.small || Style.font.body
                                                    font.bold: true
                                                    elide: Text.ElideRight
                                                    anchors.verticalCenter: parent.verticalCenter
                                                }
                                                Rectangle {
                                                    id: watchPillCorner
                                                    width: cornerTags.implicitWidth + 6
                                                    height: cornerTags.implicitHeight + 2
                                                    radius: 3
                                                    color: root.isWatchedSymbol(modelData.symbol) ? "#1e2e4a" : "#242436"
                                                    border.color: root.isWatchedSymbol(modelData.symbol) ? "#89b4fa" : "#45475a"
                                                    border.width: 1
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    Text {
                                                        id: cornerTags
                                                        anchors.centerIn: parent
                                                        text: root.isWatchedSymbol(modelData.symbol) ? "◎" : "+"
                                                        color: root.isWatchedSymbol(modelData.symbol) ? "#89b4fa" : "#a6adc8"
                                                        font.pixelSize: 9
                                                        font.bold: true
                                                    }
                                                    MouseArea {
                                                        anchors.fill: parent
                                                        cursorShape: Qt.PointingHandCursor
                                                        enabled: !manualProc.running
                                                        onClicked: {
                                                            var act = root.isWatchedSymbol(modelData.symbol) ? "remove" : "add"
                                                            var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                            manualProc.command = ["python3", script, "watch", act, modelData.symbol]
                                                            manualProc.running = true
                                                        }
                                                    }
                                                }
                                            }
                                            Text {
                                                text: {
                                                    var c = modelData.change_pct
                                                    if (c === null || c === undefined) return "0.0%"
                                                    return (Number(c) >= 0 ? "+" : "") + Number(c).toFixed(1) + "%"
                                                }
                                                color: Number(modelData.change_pct || 0) > 0 ? "#a6e3a1" : (Number(modelData.change_pct || 0) < 0 ? "#f38ba8" : "#a6adc8")
                                                font.pixelSize: Style.font.body
                                                font.bold: true
                                            }
                                            Text {
                                                width: parent.width
                                                text: root.fmtPrice(modelData.price, modelData.currency)
                                                color: "#a6adc8"
                                                font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                                elide: Text.ElideRight
                                            }
                                            Row {
                                                width: parent.width
                                                spacing: 2
                                                property int liqN: Math.round(Number(modelData.liquidity_score || 0) / 25)
                                                Repeater {
                                                    model: 4
                                                    delegate: Rectangle {
                                                        width: (parent.width - 6) / 4; height: 2.5; radius: 1
                                                        color: index < parent.liqN ? "#89dceb" : "#313244"
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            Column {
                                id: scrTableCol
                                visible: root.screenerViewMode === "table"
                                width: parent.width
                                spacing: Style.space(4)

                                Row {
                                    width: parent.width
                                    Text { width: parent.width * 0.16; text: "Ticker"; color: "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                    Text { width: parent.width * 0.13; text: "Price"; color: "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                    Text { width: parent.width * 0.10; text: "Day Change"; color: "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                    Text { width: parent.width * 0.21; text: "Bid / Ask Depth"; color: "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                    Text { width: parent.width * 0.09; text: "Liquidity"; color: "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                    Text { width: parent.width * 0.09; text: "Strength"; color: "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                    Text { width: parent.width * 0.11; text: "Signal"; color: "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                    Text { width: parent.width * 0.11; horizontalAlignment: Text.AlignRight; text: "Watchlist"; color: "#6c7086"; font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true }
                                }

                                Repeater {
                                    model: root.filteredScreener()
                                    delegate: Rectangle {
                                        width: scrTableCol.width
                                        height: scrRowInner.implicitHeight + Style.space(6)
                                        radius: 4
                                        color: scrHover.containsMouse ? "#242436" : "#11111b"
                                        MouseArea {
                                            id: scrHover
                                            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                root.activeTab = "overview"
                                                root.chartSymbol = modelData.symbol
                                                root.symText = modelData.symbol
                                                root.priceText = Number(modelData.optimal_limit || modelData.price || 0).toFixed(4)
                                                if (Number(modelData.recommended_shares || 0) > 0) root.sharesText = String(modelData.recommended_shares)
                                                root.manualMode = modelData.signal_action === "SELL" ? "sell" : "buy"
                                            }
                                        }
                                        Row {
                                            id: scrRowInner
                                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 4; rightMargin: 4 }
                                            Column {
                                                width: parent.width * 0.16
                                                anchors.verticalCenter: parent.verticalCenter
                                                Text { text: modelData.symbol; color: modelData.currency === "ZWG" ? "#f9e2af" : "#cdd6f4"; font.pixelSize: Style.font.small ? Style.font.small - 1 : 10; font.bold: true; elide: Text.ElideRight; width: parent.width }
                                                Text {
                                                    property string st: String(modelData.security_type || "EQUITY")
                                                    text: (modelData.currency === "ZWG" ? "ZSE" : "VFEX") + (st && st !== "EQUITY" ? (" • " + st) : "")
                                                    color: st !== "EQUITY" ? "#89dceb" : "#6c7086"
                                                    font.pixelSize: 8
                                                    width: parent.width
                                                    elide: Text.ElideRight
                                                }
                                            }
                                            Column {
                                                width: parent.width * 0.13
                                                anchors.verticalCenter: parent.verticalCenter
                                                Text { text: root.fmtPrice(modelData.price, modelData.currency); color: "#cdd6f4"; font.pixelSize: Style.font.small ? Style.font.small - 1 : 10; width: parent.width; elide: Text.ElideRight }
                                                Text { visible: Boolean(modelData.optimal_limit); text: "Limit " + root.fmtPrice(modelData.optimal_limit, modelData.currency); color: "#89dceb"; font.pixelSize: 8; width: parent.width; elide: Text.ElideRight }
                                            }
                                            Text {
                                                width: parent.width * 0.10; anchors.verticalCenter: parent.verticalCenter
                                                text: (modelData.change_pct !== null && modelData.change_pct !== undefined) ? ((Number(modelData.change_pct) >= 0 ? "+" : "") + Number(modelData.change_pct).toFixed(1) + "%") : "--"
                                                color: Number(modelData.change_pct || 0) > 0 ? "#a6e3a1" : (Number(modelData.change_pct || 0) < 0 ? "#f38ba8" : "#6c7086")
                                                font.pixelSize: Style.font.small ? Style.font.small - 1 : 10; font.bold: true
                                            }
                                            Column {
                                                width: parent.width * 0.21; anchors.verticalCenter: parent.verticalCenter; spacing: 2
                                                Rectangle {
                                                    width: parent.width * 0.90; height: 5; radius: 2; color: "#3d2229"
                                                    Rectangle {
                                                        property real bv: Number(modelData.bid_volume || 0); property real av: Number(modelData.ask_volume || 0)
                                                        width: (bv + av) > 0 ? (bv / (bv + av)) * parent.width : parent.width * 0.5
                                                        height: parent.height; radius: 2; color: "#a6e3a1"
                                                    }
                                                }
                                                Text { text: "Bid:" + root.fmtVol(modelData.bid_volume || 0) + " Ask:" + root.fmtVol(modelData.ask_volume || 0); color: "#a6adc8"; font.pixelSize: 8; width: parent.width; elide: Text.ElideRight }
                                            }
                                            Row {
                                                width: parent.width * 0.09; anchors.verticalCenter: parent.verticalCenter; spacing: 1
                                                property int lv: Math.round(Number(modelData.liquidity_score || 0) / 25)
                                                Repeater { model: 4; delegate: Rectangle { width: 4; height: 4; radius: 2; color: index < parent.lv ? "#89dceb" : "#313244" } }
                                            }
                                            Text {
                                                width: parent.width * 0.09; anchors.verticalCenter: parent.verticalCenter
                                                text: modelData.rsi14 !== null && modelData.rsi14 !== undefined ? Number(modelData.rsi14).toFixed(0) : "--"
                                                color: Number(modelData.rsi14 || 50) <= 35 ? "#a6e3a1" : (Number(modelData.rsi14 || 50) >= 68 ? "#f38ba8" : "#a6adc8")
                                                font.pixelSize: Style.font.small ? Style.font.small - 2 : 9
                                            }
                                            Text {
                                                width: parent.width * 0.11; anchors.verticalCenter: parent.verticalCenter
                                                text: Number(modelData.signal_score || 0) > 0 ? (modelData.signal_action + " " + modelData.signal_score) : (modelData.spread_pct !== null && modelData.spread_pct !== undefined ? (Number(modelData.spread_pct).toFixed(0) + "% spread") : "--")
                                                color: Number(modelData.signal_score || 0) > 0 ? (modelData.signal_action === "SELL" ? "#f38ba8" : "#a6e3a1") : (modelData.wide_spread ? "#f9e2af" : "#6c7086")
                                                font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: Number(modelData.signal_score || 0) > 0; elide: Text.ElideRight
                                            }
                                            Text {
                                                width: parent.width * 0.11; horizontalAlignment: Text.AlignRight; anchors.verticalCenter: parent.verticalCenter
                                                text: root.isWatchedSymbol(modelData.symbol) ? "★ Watching" : "+ Watchlist"
                                                color: root.isWatchedSymbol(modelData.symbol) ? "#a6e3a1" : "#89b4fa"
                                                font.pixelSize: Style.font.small ? Style.font.small - 2 : 9; font.bold: true; elide: Text.ElideLeft
                                                MouseArea {
                                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                                    onClicked: {
                                                        var act = root.isWatchedSymbol(modelData.symbol) ? "remove" : "add"
                                                        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                        manualProc.command = ["python3", script, "watch", act, modelData.symbol]
                                                        manualProc.running = true
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

                // === TAB 3: QUANT & 5Y COMPOUNDING WORKSTATION ===
                Column {
                    id: analyticsTabCol
                    visible: root.activeTab === "analytics"
                    width: parent.width
                    spacing: Style.space(8)

                    Grid {
                        width: parent.width
                        columns: root.wideLayout ? 2 : 1
                        columnSpacing: Style.space(8)
                        rowSpacing: Style.space(8)

                        // LEFT CARD: 90D Signal Track Record with Radial Win-Rate Gauge & Win/Loss Horizontal Bars
                        Rectangle {
                            width: root.wideLayout ? (analyticsTabCol.width - Style.space(8)) / 2 : analyticsTabCol.width
                            height: btCol.implicitHeight + Style.space(16)
                            radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1

                            Column {
                                id: btCol
                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                                spacing: Style.space(6)
                                property var bt: root.summaryData.signal_backtest || ({})

                                Text { text: "90-Day Signal Track Record"; color: "#89b4fa"; font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.body; font.bold: true }

                                Row {
                                    width: parent.width
                                    spacing: Style.space(10)

                                    Item {
                                        width: Style.space(78); height: Style.space(78)
                                        Canvas {
                                            id: btGaugeCanvas
                                            anchors.fill: parent
                                            onWidthChanged: requestPaint()
                                            Component.onCompleted: { root.btGaugeCanvasRef = btGaugeCanvas; requestPaint() }
                                            onPaint: {
                                                var ctx = getContext("2d")
                                                if (width <= 0 || height <= 0) return
                                                ctx.clearRect(0, 0, width, height)
                                                var bt = root.summaryData.signal_backtest || ({})
                                                var wr = Math.max(0, Math.min(100, Number(bt.win_rate_pct || 0)))
                                                var cx = width / 2, cy = height / 2, r = Math.min(cx, cy) - 6
                                                ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.strokeStyle = "#313244"; ctx.lineWidth = 8; ctx.stroke()
                                                if (wr > 0) {
                                                    ctx.beginPath(); ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + (wr / 100.0) * Math.PI * 2)
                                                    ctx.strokeStyle = wr >= 55 ? "#a6e3a1" : (wr >= 40 ? "#89b4fa" : "#f9e2af")
                                                    ctx.lineWidth = 8; ctx.stroke()
                                                }
                                            }
                                        }
                                        Column {
                                            anchors.centerIn: parent
                                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: Number(btCol.bt.win_rate_pct || 0).toFixed(0) + "%"; color: "#cdd6f4"; font.pixelSize: Style.font.body; font.bold: true }
                                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "WIN"; color: "#6c7086"; font.pixelSize: 8; font.bold: true }
                                        }
                                    }

                                    Column {
                                        width: parent.width - Style.space(88); spacing: 4; anchors.verticalCenter: parent.verticalCenter
                                        Text { text: "Signals Tracked: " + (btCol.bt.total_logged || 0) + " (" + (btCol.bt.wins || 0) + " wins)"; color: "#cdd6f4"; font.pixelSize: Style.font.small || Style.font.body }
                                        Text {
                                            text: "Average Forward Return: " + (Number(btCol.bt.avg_return_pct || 0) >= 0 ? "+" : "") + Number(btCol.bt.avg_return_pct || 0).toFixed(2) + "%"
                                            color: Number(btCol.bt.avg_return_pct || 0) >= 0 ? "#a6e3a1" : "#f38ba8"
                                            font.pixelSize: Style.font.small || Style.font.body; font.bold: true
                                        }
                                        Row {
                                            width: parent.width; spacing: 4
                                            Rectangle {
                                                width: (parent.width - 4) / 2; height: Style.space(18); radius: 4; color: "#1f3a27"
                                                Text { anchors.centerIn: parent; text: "CORE: " + Number(btCol.bt.core_win_rate_pct || 0).toFixed(0) + "% (" + (btCol.bt.core_count || 0) + ")"; color: "#a6e3a1"; font.pixelSize: 9; font.bold: true }
                                            }
                                            Rectangle {
                                                width: (parent.width - 4) / 2; height: Style.space(18); radius: 4; color: "#272138"
                                                Text { anchors.centerIn: parent; text: "SWING: " + Number(btCol.bt.swing_win_rate_pct || 0).toFixed(0) + "% (" + (btCol.bt.swing_count || 0) + ")"; color: "#cba6f7"; font.pixelSize: 9; font.bold: true }
                                            }
                                        }
                                        Row {
                                            width: parent.width; spacing: 4
                                            visible: Boolean(btCol.bt.best)
                                            Rectangle {
                                                width: (parent.width - 4) / 2; height: Style.space(28); radius: 4; color: "#1b2e24"
                                                Column { anchors.centerIn: parent
                                                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Best: " + (btCol.bt.best ? btCol.bt.best.symbol : ""); color: "#a6e3a1"; font.pixelSize: 9; font.bold: true }
                                                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: btCol.bt.best ? ((Number(btCol.bt.best.return_pct) >= 0 ? "+" : "") + Number(btCol.bt.best.return_pct).toFixed(1) + "%") : ""; color: "#cdd6f4"; font.pixelSize: 9 }
                                                }
                                            }
                                            Rectangle {
                                                width: (parent.width - 4) / 2; height: Style.space(28); radius: 4; color: "#2d1d24"
                                                Column { anchors.centerIn: parent
                                                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Worst: " + (btCol.bt.worst ? btCol.bt.worst.symbol : ""); color: "#f38ba8"; font.pixelSize: 9; font.bold: true }
                                                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: btCol.bt.worst ? ((Number(btCol.bt.worst.return_pct) >= 0 ? "+" : "") + Number(btCol.bt.worst.return_pct).toFixed(1) + "%") : ""; color: "#cdd6f4"; font.pixelSize: 9 }
                                                }
                                            }
                                        }
                                    }
                                }

                                Repeater {
                                    model: ((root.summaryData.signal_backtest || ({})).entries || []).slice(0, 6)
                                    delegate: Row {
                                        width: btCol.width; spacing: Style.space(4)
                                        property real retV: Number(modelData.return_pct || 0)
                                        Text { width: btCol.width * 0.20; text: modelData.date.slice(5); color: "#6c7086"; font.pixelSize: 9 }
                                        Text { width: btCol.width * 0.24; text: (modelData.horizon === "CORE" ? "◆" : "⚡") + " " + modelData.action + " " + modelData.symbol; color: modelData.horizon === "CORE" ? "#a6e3a1" : "#cba6f7"; font.pixelSize: 9; font.bold: true; elide: Text.ElideRight }
                                        Item {
                                            width: btCol.width * 0.36; height: 10
                                            Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 5; radius: 2; color: "#313244"
                                                Rectangle { x: parent.width / 2 - 0.5; y: -1; width: 1; height: 7; color: "#6c7086" }
                                                Rectangle {
                                                    property real normW: Math.min(0.5, Math.abs(parent.parent.parent.retV) / 30.0) * parent.width
                                                    x: parent.parent.parent.retV >= 0 ? (parent.width / 2) : (parent.width / 2 - normW)
                                                    width: Math.max(2, normW); height: parent.height; radius: 2
                                                    color: parent.parent.parent.retV >= 0 ? "#a6e3a1" : "#f38ba8"
                                                }
                                            }
                                        }
                                        Text {
                                            width: btCol.width * 0.20 - Style.space(12); horizontalAlignment: Text.AlignRight
                                            text: (retV >= 0 ? "+" : "") + retV.toFixed(1) + "%"
                                            color: retV >= 0 ? "#a6e3a1" : "#f38ba8"; font.pixelSize: 9; font.bold: true
                                        }
                                    }
                                }
                            }
                        }

                        // RIGHT CARD: Interactive 5-Year Multi-Curve Compounding Canvas
                        Rectangle {
                            width: root.wideLayout ? (analyticsTabCol.width - Style.space(8)) / 2 : analyticsTabCol.width
                            height: wealthCol.implicitHeight + Style.space(16)
                            radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1

                            Column {
                                id: wealthCol
                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                                spacing: Style.space(5)

                                Row {
                                    width: parent.width
                                    Text { width: parent.width - cagrRow.width; anchors.verticalCenter: parent.verticalCenter; text: "5-Year Wealth Projection"; color: "#a6e3a1"; font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.body; font.bold: true }
                                    Row {
                                        id: cagrRow; spacing: 3
                                        Repeater {
                                            model: [8, 12, 18]
                                            delegate: Rectangle {
                                                width: Style.space(30); height: Style.space(18); radius: 4
                                                color: root.projCagrPct === modelData ? "#a6e3a1" : "#313244"
                                                Text { anchors.centerIn: parent; text: modelData + "%"; color: root.projCagrPct === modelData ? "#1e1e2e" : "#cdd6f4"; font.pixelSize: 9; font.bold: true }
                                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.projCagrPct = modelData }
                                            }
                                        }
                                    }
                                }

                                Row {
                                    width: parent.width; spacing: Style.space(4)
                                    Text { text: "Monthly Investment:"; color: "#a6adc8"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                                    Repeater {
                                        model: [0, 25, 50, 100, 250]
                                        delegate: Rectangle {
                                            width: Style.space(34); height: Style.space(18); radius: 4
                                            color: root.projDcaMonthly === modelData ? "#89b4fa" : "#313244"
                                            Text { anchors.centerIn: parent; text: "$" + modelData; color: root.projDcaMonthly === modelData ? "#1e1e2e" : "#cdd6f4"; font.pixelSize: 9; font.bold: root.projDcaMonthly === modelData }
                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.projDcaMonthly = modelData }
                                        }
                                    }
                                }

                                Canvas {
                                    id: projCanvas
                                    width: parent.width
                                    height: root.fullPageMode ? Style.space(185) : Style.space(116)
                                    onWidthChanged: requestPaint()
                                    Component.onCompleted: { root.projCanvasRef = projCanvas; requestPaint() }
                                    onPaint: {
                                        var ctx = getContext("2d")
                                        if (width <= 0 || height <= 0) return
                                        ctx.clearRect(0, 0, width, height)
                                        var startEq = Number(root.summaryData.total_value || 0) + Number(root.summaryData.wallet_cash_usd || 0)
                                        var rM = (root.projCagrPct / 100.0) / 12.0
                                        var dca = Number(root.projDcaMonthly || 0)
                                        var ptsTotal = [], ptsBase = [], ptsCash = []
                                        var maxV = Math.max(10, startEq)
                                        for (var yr = 0; yr <= 5; yr++) {
                                            var m = yr * 12
                                            var fvStart = startEq * Math.pow(1 + rM, m)
                                            var fvDca = m > 0 ? dca * ((Math.pow(1 + rM, m) - 1) / rM) : 0
                                            var totV = fvStart + fvDca
                                            var cashV = startEq + dca * m
                                            ptsTotal.push(totV); ptsBase.push(fvStart); ptsCash.push(cashV)
                                            if (totV > maxV) maxV = totV
                                        }
                                        var pL = 42, pR = 8, pT = 8, pB = 14
                                        var pW = Math.max(10, width - pL - pR), pH = Math.max(10, height - pT - pB)
                                        function xAt(i) { return pL + (i / 5.0) * pW }
                                        function yAt(v) { return pT + pH - (v / maxV) * pH }

                                        ctx.font = "9px sans-serif"; ctx.textBaseline = "middle"
                                        for (var g = 0; g <= 2; g++) {
                                            var gv = maxV * (1 - g * 0.5)
                                            var gy = yAt(gv)
                                            ctx.strokeStyle = "#242436"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(pL, gy); ctx.lineTo(width - pR, gy); ctx.stroke()
                                            ctx.fillStyle = "#6c7086"; ctx.fillText("$" + Math.round(gv), 0, gy)
                                        }
                                        for (var yr2 = 0; yr2 <= 5; yr2++) {
                                            ctx.fillStyle = "#6c7086"; ctx.fillText("Year " + yr2, xAt(yr2) - 14, height - 6)
                                        }

                                        ctx.save(); ctx.strokeStyle = "#6c7086"; ctx.lineWidth = 1.2; ctx.setLineDash([3, 3])
                                        ctx.beginPath()
                                        for (var c = 0; c <= 5; c++) { if (c === 0) ctx.moveTo(xAt(c), yAt(ptsCash[c])); else ctx.lineTo(xAt(c), yAt(ptsCash[c])) }
                                        ctx.stroke(); ctx.restore()

                                        ctx.strokeStyle = "#89b4fa"; ctx.lineWidth = 1.5; ctx.beginPath()
                                        for (var b = 0; b <= 5; b++) { if (b === 0) ctx.moveTo(xAt(b), yAt(ptsBase[b])); else ctx.lineTo(xAt(b), yAt(ptsBase[b])) }
                                        ctx.stroke()

                                        var grad = ctx.createLinearGradient(0, pT, 0, pT + pH)
                                        grad.addColorStop(0, "rgba(166, 227, 161, 0.25)"); grad.addColorStop(1, "rgba(0,0,0,0)")
                                        ctx.fillStyle = grad; ctx.beginPath(); ctx.moveTo(xAt(0), pT + pH)
                                        for (var t = 0; t <= 5; t++) ctx.lineTo(xAt(t), yAt(ptsTotal[t]))
                                        ctx.lineTo(xAt(5), pT + pH); ctx.closePath(); ctx.fill()

                                        ctx.strokeStyle = "#a6e3a1"; ctx.lineWidth = 2; ctx.beginPath()
                                        for (var t2 = 0; t2 <= 5; t2++) { if (t2 === 0) ctx.moveTo(xAt(t2), yAt(ptsTotal[t2])); else ctx.lineTo(xAt(t2), yAt(ptsTotal[t2])) }
                                        ctx.stroke()
                                        for (var d = 0; d <= 5; d++) {
                                            ctx.fillStyle = (d === root.hoveredProjIdx) ? "#f9e2af" : "#a6e3a1"
                                            ctx.beginPath(); ctx.arc(xAt(d), yAt(ptsTotal[d]), d === root.hoveredProjIdx ? 4 : 2.5, 0, Math.PI * 2); ctx.fill()
                                        }
                                    }
                                    MouseArea {
                                        anchors.fill: parent; hoverEnabled: true
                                        onPositionChanged: function(mouse) {
                                            var rel = (mouse.x - 42) / Math.max(10, width - 50)
                                            if (rel < 0 || rel > 1) { root.hoveredProjIdx = -1; return }
                                            root.hoveredProjIdx = Math.max(0, Math.min(5, Math.round(rel * 5)))
                                        }
                                        onExited: root.hoveredProjIdx = -1
                                    }
                                }

                                Row {
                                    width: parent.width; spacing: Style.space(4)
                                    Repeater {
                                        model: [1, 3, 5]
                                        delegate: Rectangle {
                                            width: (parent.width - Style.space(8)) / 3; height: Style.space(32); radius: 5; color: "#11111b"
                                            property real startEq: Number(root.summaryData.total_value || 0) + Number(root.summaryData.wallet_cash_usd || 0)
                                            property real rM: (root.projCagrPct / 100.0) / 12.0
                                            property real months: modelData * 12
                                            property real fvTot: startEq * Math.pow(1 + rM, months) + root.projDcaMonthly * ((Math.pow(1 + rM, months) - 1) / rM)
                                            border.color: root.hoveredProjIdx === modelData ? "#a6e3a1" : "#313244"; border.width: 1
                                            Column { anchors.centerIn: parent
                                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData + " Year"; color: "#6c7086"; font.pixelSize: 9 }
                                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "$" + fvTot.toFixed(0); color: "#a6e3a1"; font.pixelSize: Style.font.small || Style.font.body; font.bold: true }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        width: parent.width
                        height: rebCol.implicitHeight + Style.space(14)
                        radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                        Column {
                            id: rebCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                            spacing: Style.space(5)
                            Row {
                                width: parent.width
                                Text { width: parent.width - tgtAddBtn.width - Style.space(6); anchors.verticalCenter: parent.verticalCenter; text: "Target Portfolio Allocation Versus Maximum Limit (" + Number((root.summaryData.fee_config || ({})).max_stock_pct || 25).toFixed(0) + "%)"; color: "#cdd6f4"; font.pixelSize: Style.font.body; font.bold: true; elide: Text.ElideRight }
                                Rectangle {
                                    id: tgtAddBtn; anchors.verticalCenter: parent.verticalCenter
                                    width: tgtAddBtnTxt.implicitWidth + 12; height: Style.space(20); radius: 4
                                    color: root.targetAddOpen ? "#89b4fa" : "#1e2e4a"; border.color: "#89b4fa"; border.width: 1
                                    Text { id: tgtAddBtnTxt; anchors.centerIn: parent; text: root.targetAddOpen ? "Close" : "+ Set Target Weight"; color: root.targetAddOpen ? "#1e1e2e" : "#89b4fa"; font.pixelSize: 9; font.bold: true }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.targetAddOpen = !root.targetAddOpen }
                                }
                            }
                            Rectangle {
                                width: rebCol.width; visible: root.targetAddOpen
                                height: tgtFormRow.implicitHeight + Style.space(10); radius: 6; color: "#11111b"; border.color: "#89b4fa"; border.width: 1
                                Row {
                                    id: tgtFormRow
                                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: Style.space(6) }
                                    spacing: Style.space(5)
                                    Rectangle {
                                        width: parent.width * 0.34; height: Style.space(24); radius: 4; color: "#313244"; border.color: "#45475a"; border.width: 1
                                        TextInput {
                                            id: tgtSymIn; anchors.fill: parent; anchors.margins: 4; color: "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small || Style.font.body
                                            text: root.targetAddSym; onTextChanged: if (root.targetAddSym !== text) root.targetAddSym = text
                                            Connections { target: root; function onTargetAddSymChanged() { if (tgtSymIn.text !== root.targetAddSym) tgtSymIn.text = root.targetAddSym } }
                                            Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Symbol"; color: "#6c7086"; font: tgtSymIn.font; visible: !tgtSymIn.text && !tgtSymIn.activeFocus }
                                        }
                                    }
                                    Rectangle {
                                        width: parent.width * 0.32; height: Style.space(24); radius: 4; color: "#313244"; border.color: "#45475a"; border.width: 1
                                        TextInput {
                                            id: tgtPctIn; anchors.fill: parent; anchors.margins: 4; color: "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small || Style.font.body
                                            text: root.targetAddPct; onTextChanged: if (root.targetAddPct !== text) root.targetAddPct = text
                                            Connections { target: root; function onTargetAddPctChanged() { if (tgtPctIn.text !== root.targetAddPct) tgtPctIn.text = root.targetAddPct } }
                                            Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Target Weight %"; color: "#6c7086"; font: tgtPctIn.font; visible: !tgtPctIn.text && !tgtPctIn.activeFocus }
                                        }
                                    }
                                    Rectangle {
                                        width: parent.width * 0.34 - Style.space(10); height: Style.space(24); radius: 4; color: "#89b4fa"
                                        Text { anchors.centerIn: parent; text: "Save Target"; color: "#1e1e2e"; font.pixelSize: 10; font.bold: true }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                            onClicked: {
                                                var sy = root.targetAddSym.trim().toUpperCase()
                                                var pc = root.targetAddPct.replace(/[^0-9.]/g, "").trim()
                                                if (sy && pc) {
                                                    root.runCliCommand(["target", "set", sy, pc], false)
                                                    root.targetAddSym = ""
                                                    root.targetAddOpen = false
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            Text {
                                visible: Object.keys(root.summaryData.targets || ({})).length === 0
                                text: "No target weights configured yet — click '+ Set Target Weight' above."
                                color: "#6c7086"; font.pixelSize: Style.font.small || Style.font.body; wrapMode: Text.WordWrap; width: parent.width
                            }
                            Repeater {
                                model: Object.keys(root.summaryData.targets || ({}))
                                delegate: Row {
                                    width: rebCol.width; spacing: Style.space(6)
                                    property real tgtPct: Number((root.summaryData.targets || ({}))[modelData] || 0)
                                    property real capPct: Number((root.summaryData.fee_config || ({})).max_stock_pct || 25)
                                    property real curPct: {
                                        var items = root.summaryData.items || []
                                        for (var i = 0; i < items.length; i++) if (items[i].symbol === modelData) return Number(items[i].alloc_pct || 0)
                                        return 0
                                    }
                                    property real needUsd: Math.max(0, (tgtPct - curPct) / 100.0 * Math.max(10, Number(root.summaryData.total_value || 0)))
                                    Text { width: rebCol.width * 0.14; text: modelData; color: "#cdd6f4"; font.pixelSize: Style.font.small || Style.font.body; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                                    Item {
                                        width: rebCol.width * 0.50; height: 10; anchors.verticalCenter: parent.verticalCenter
                                        Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 6; radius: 3; color: "#313244"
                                            Rectangle { width: Math.min(1, parent.parent.parent.curPct / 100.0) * parent.width; height: parent.height; radius: 3; color: parent.parent.parent.curPct >= parent.parent.parent.tgtPct ? "#a6e3a1" : "#89b4fa" }
                                            Rectangle { x: Math.min(parent.width - 2, (parent.parent.parent.tgtPct / 100.0) * parent.width); y: -2; width: 2; height: 10; color: "#f9e2af" }
                                            Rectangle { x: Math.min(parent.width - 2, (parent.parent.parent.capPct / 100.0) * parent.width); y: -2; width: 1.5; height: 10; color: "#f38ba8" }
                                        }
                                    }
                                    Text { width: rebCol.width * 0.20; text: curPct.toFixed(0) + "% / " + tgtPct.toFixed(0) + "%"; color: "#a6adc8"; font.pixelSize: Style.font.small ? Style.font.small - 1 : 10; anchors.verticalCenter: parent.verticalCenter }
                                    Rectangle {
                                        width: rebCol.width * 0.16 - Style.space(18); height: Style.space(20); radius: 4
                                        color: needUsd >= 1 ? "#243b2c" : "#313244"
                                        Text { anchors.centerIn: parent; text: needUsd >= 1 ? ("Buy $" + needUsd.toFixed(0)) : "× Delete"; color: needUsd >= 1 ? "#a6e3a1" : "#f38ba8"; font.pixelSize: 9; font.bold: true }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                            onClicked: {
                                                if (needUsd >= 1) {
                                                    root.activeTab = "overview"; root.quickTrade("buy", modelData)
                                                } else {
                                                    var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                    manualProc.command = ["python3", script, "target", "remove", modelData]; manualProc.running = true
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Unused Portal Balances Deployment Advisor
                    Rectangle {
                        id: idleCashCard
                        property var icp: (root.summaryData.idle_cash_plan || ({}))
                        property real depUsd: Number(icp.total_deployable_usd || 0)
                        property real depZwg: Number(icp.total_deployable_zwg || 0)
                        width: parent.width
                        visible: (icp.accounts || []).length > 0 || depUsd > 0 || depZwg > 0
                        height: idleCashCol.implicitHeight + Style.space(14)
                        radius: 8; color: "#181825"; border.color: (depUsd > 0 || depZwg > 0) ? "#a6e3a1" : "#313244"; border.width: 1
                        Column {
                            id: idleCashCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                            spacing: Style.space(5)
                            Row {
                                width: parent.width
                                Text {
                                    width: parent.width * 0.56
                                    text: "Unused Portal Balances Deployment"
                                    color: "#a6e3a1"; font.pixelSize: Style.font.body; font.bold: true; elide: Text.ElideRight
                                }
                                Text {
                                    width: parent.width * 0.44; horizontalAlignment: Text.AlignRight
                                    text: "Deployable: $" + idleCashCard.depUsd.toFixed(2) + " USD • ZiG " + idleCashCard.depZwg.toFixed(2)
                                    color: "#89dceb"; font.pixelSize: 9; font.bold: true; elide: Text.ElideLeft
                                }
                            }
                            Flow {
                                width: parent.width; spacing: 6
                                Repeater {
                                    model: idleCashCard.icp.accounts || []
                                    delegate: Rectangle {
                                        width: acChipTxt.implicitWidth + 12; height: Style.space(18); radius: 4
                                        color: "#11111b"; border.color: (Number(modelData.deployable_usd || 0) > 0 || Number(modelData.deployable_zwg || 0) > 0) ? "#89b4fa" : "#313244"; border.width: 1
                                        Text {
                                            id: acChipTxt; anchors.centerIn: parent
                                            text: modelData.title + ": $" + Number(modelData.deployable_usd || 0).toFixed(2) + " USD • ZiG " + Number(modelData.deployable_zwg || 0).toFixed(2) + ((Number(modelData.held_usd || 0) > 0 || Number(modelData.held_zwg || 0) > 0) ? " (held deducted)" : "")
                                            color: "#cdd6f4"; font.pixelSize: 8; font.bold: true
                                        }
                                    }
                                }
                            }
                            Text {
                                visible: (idleCashCard.icp.usd_picks || []).length === 0 && (idleCashCard.icp.zwg_picks || []).length === 0
                                width: parent.width; wrapMode: Text.WordWrap
                                text: (idleCashCard.depUsd <= 0 && idleCashCard.depZwg <= 0)
                                    ? "All connected portal cash is deployed or $0.00. Sync portals in Tab 4 after a deposit or order expiry to refresh unused balances."
                                    : ("Idle balances cannot yet cover 1 whole share + broker fees"
                                        + (idleCashCard.icp.usd_gap_for_one !== null && idleCashCard.icp.usd_gap_for_one !== undefined ? (" • USD Top-Up Needed: +$" + Number(idleCashCard.icp.usd_gap_for_one).toFixed(2)) : "")
                                        + (idleCashCard.icp.zwg_gap_for_one !== null && idleCashCard.icp.zwg_gap_for_one !== undefined ? (" • ZiG Top-Up Needed: +ZiG " + Number(idleCashCard.icp.zwg_gap_for_one).toFixed(2)) : ""))
                                color: "#a6adc8"; font.pixelSize: 9
                            }
                            Repeater {
                                model: (idleCashCard.icp.usd_picks || []).slice(0, 3).concat((idleCashCard.icp.zwg_picks || []).slice(0, 3))
                                delegate: Row {
                                    width: idleCashCol.width
                                    Text { width: idleCashCol.width * 0.14; text: modelData.symbol; color: "#a6e3a1"; font.pixelSize: 9; font.bold: true }
                                    Text { width: idleCashCol.width * 0.34; text: "Buy " + modelData.max_shares + " shares @ " + root.fmtPrice(modelData.exec_price, modelData.currency); color: "#cdd6f4"; font.pixelSize: 9; elide: Text.ElideRight }
                                    Text { width: idleCashCol.width * 0.30; text: "Cost " + root.fmtShortMoney(modelData.net_cost, modelData.currency) + " (incl. fees)"; color: "#89dceb"; font.pixelSize: 9; elide: Text.ElideRight }
                                    Text { width: idleCashCol.width * 0.22; horizontalAlignment: Text.AlignRight; text: "Score " + modelData.score + " • " + Number(modelData.win_prob_pct || 50).toFixed(0) + "% win"; color: "#cba6f7"; font.pixelSize: 9; font.bold: true }
                                }
                            }
                        }
                    }

                    // Dedicated Dollar-Cost Averaging Investment Planner
                    Rectangle {
                        width: parent.width
                        height: dcaTabCol.implicitHeight + Style.space(14)
                        radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                        Column {
                            id: dcaTabCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                            spacing: Style.space(5)
                            Row {
                                width: parent.width; spacing: Style.space(6)
                                Text { width: parent.width - dcaBudgetRow.width - Style.space(6); anchors.verticalCenter: parent.verticalCenter; text: "Dollar-Cost Averaging Investment Planner"; color: "#cba6f7"; font.pixelSize: Style.font.body; font.bold: true; elide: Text.ElideRight }
                                Row {
                                    id: dcaBudgetRow; spacing: Style.space(4); anchors.verticalCenter: parent.verticalCenter
                                    Rectangle {
                                        visible: Number((root.summaryData.idle_cash_plan || ({})).total_deployable_usd || 0) > 0
                                        width: dcaIdleTxt.implicitWidth + 10; height: Style.space(22); radius: 4; color: "#243b2c"; border.color: "#a6e3a1"; border.width: 1
                                        Text {
                                            id: dcaIdleTxt; anchors.centerIn: parent
                                            text: "Use Unused ($" + Number((root.summaryData.idle_cash_plan || ({})).total_deployable_usd || 0).toFixed(2) + ")"
                                            color: "#a6e3a1"; font.pixelSize: 9; font.bold: true
                                        }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !dcaProc.running
                                            onClicked: {
                                                var uAmt = Number((root.summaryData.idle_cash_plan || ({})).total_deployable_usd || 0).toFixed(2)
                                                root.dcaBudgetText = uAmt
                                                root.runDcaBudget(uAmt)
                                            }
                                        }
                                    }
                                    Rectangle {
                                        width: Style.space(90); height: Style.space(22); radius: 4; color: "#313244"; border.color: "#45475a"; border.width: 1
                                        TextInput {
                                            id: dcaBudIn; anchors.fill: parent; anchors.margins: 4; color: "#cdd6f4"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family; font.pixelSize: Style.font.small || Style.font.body
                                            text: root.dcaBudgetText; onTextChanged: if (root.dcaBudgetText !== text) root.dcaBudgetText = text
                                            onAccepted: root.runDcaBudget(root.dcaBudgetText)
                                            Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Budget $"; color: "#6c7086"; font: dcaBudIn.font; visible: !dcaBudIn.text && !dcaBudIn.activeFocus }
                                        }
                                    }
                                    Rectangle {
                                        width: dcaRunTxt.implicitWidth + 14; height: Style.space(22); radius: 4; color: dcaProc.running ? "#45475a" : "#cba6f7"
                                        Text { id: dcaRunTxt; anchors.centerIn: parent; text: dcaProc.running ? "Planning..." : "Generate Plan"; color: "#1e1e2e"; font.pixelSize: 10; font.bold: true }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !dcaProc.running; onClicked: root.runDcaBudget(root.dcaBudgetText) }
                                    }
                                }
                            }
                            Text {
                                visible: root.dcaPlanData === null || (root.dcaPlanData.plan || []).length === 0
                                text: "Enter your investment budget above to allocate shares toward under-weight positions or watchlist picks."
                                color: "#6c7086"; font.pixelSize: Style.font.small || Style.font.body; wrapMode: Text.WordWrap; width: parent.width
                            }
                            Repeater {
                                model: root.dcaPlanData ? (root.dcaPlanData.plan || []) : []
                                delegate: Row {
                                    width: dcaTabCol.width
                                    Text { width: dcaTabCol.width * 0.20; text: modelData.symbol; color: "#cdd6f4"; font.pixelSize: Style.font.small || Style.font.body; font.bold: true }
                                    Text { width: dcaTabCol.width * 0.30; text: Number(modelData.current_pct || 0).toFixed(0) + "% → " + Number(modelData.target_pct || 0).toFixed(0) + "%"; color: "#a6adc8"; font.pixelSize: Style.font.small || Style.font.body }
                                    Text { width: dcaTabCol.width * 0.25; horizontalAlignment: Text.AlignRight; text: "$" + Number(modelData.alloc_usd || 0).toFixed(2); color: "#a6e3a1"; font.pixelSize: Style.font.small || Style.font.body }
                                    Text { width: dcaTabCol.width * 0.25; horizontalAlignment: Text.AlignRight; text: Number(modelData.shares || 0).toFixed(2) + " shares"; color: "#cdd6f4"; font.pixelSize: Style.font.small || Style.font.body }
                                }
                            }
                        }
                    }

                    // Market Indices, Unit Trusts & Institutional Foreign Flows
                    Grid {
                        width: parent.width
                        columns: root.wideLayout ? 2 : 1
                        columnSpacing: Style.space(8)
                        rowSpacing: Style.space(8)
                        visible: (((root.summaryData.market_intel || ({})).indices || []).length > 0) || (Object.keys((root.summaryData.market_intel || ({})).foreign_counters || ({})).length > 0)

                        Rectangle {
                            width: root.wideLayout ? (analyticsTabCol.width - Style.space(8)) / 2 : analyticsTabCol.width
                            height: idxCol.implicitHeight + Style.space(14)
                            radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                            Column {
                                id: idxCol
                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                                spacing: Style.space(4)
                                Text { text: "Live Market Indices & Unit Trusts"; color: "#89dceb"; font.pixelSize: Style.font.body; font.bold: true }
                                Repeater {
                                    model: ((root.summaryData.market_intel || ({})).indices || []).slice(0, 8)
                                    delegate: Row {
                                        width: idxCol.width
                                        Text { width: idxCol.width * 0.36; text: modelData.name; color: "#cdd6f4"; font.pixelSize: 9; font.bold: true; elide: Text.ElideRight }
                                        Text { width: idxCol.width * 0.18; horizontalAlignment: Text.AlignRight; text: Number(modelData.level || 0).toFixed(2); color: "#89b4fa"; font.pixelSize: 9 }
                                        Text { width: idxCol.width * 0.46; horizontalAlignment: Text.AlignRight; text: "1-Month " + Number(modelData.one_month || 0).toFixed(0) + " • 52-Week High " + Number(modelData.high_52w || 0).toFixed(0); color: "#a6adc8"; font.pixelSize: 8; elide: Text.ElideRight }
                                    }
                                }
                                Text {
                                    visible: ((root.summaryData.market_intel || ({})).unit_trusts || []).length > 0
                                    text: "Unit Trusts (" + ((root.summaryData.market_intel || ({})).unit_trusts || []).length + ")"
                                    color: "#cba6f7"; font.pixelSize: 9; font.bold: true
                                }
                                Repeater {
                                    model: ((root.summaryData.market_intel || ({})).unit_trusts || []).slice(0, 5)
                                    delegate: Row {
                                        width: idxCol.width
                                        Text { width: idxCol.width * 0.65; text: modelData.name || modelData.symbol; color: "#cdd6f4"; font.pixelSize: 9; elide: Text.ElideRight }
                                        Text { width: idxCol.width * 0.35; horizontalAlignment: Text.AlignRight; text: root.fmtShortMoney(modelData.price, modelData.currency) + " (" + modelData.currency + ")"; color: "#a6e3a1"; font.pixelSize: 9 }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            width: root.wideLayout ? (analyticsTabCol.width - Style.space(8)) / 2 : analyticsTabCol.width
                            height: ffCol.implicitHeight + Style.space(14)
                            radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                            Column {
                                id: ffCol
                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                                spacing: Style.space(4)
                                Text { text: "Exchange Foreign Flow Leaders & Movers"; color: "#f9e2af"; font.pixelSize: Style.font.body; font.bold: true }
                                property var fKeys: Object.keys((root.summaryData.market_intel || ({})).foreign_counters || ({}))
                                Text {
                                    visible: ffCol.fKeys.length === 0
                                    text: "No counter-level foreign purchases or sales reported in the latest Daily Trade Report."
                                    color: "#6c7086"; font.pixelSize: 9; wrapMode: Text.WordWrap; width: parent.width
                                }
                                Repeater {
                                    model: ffCol.fKeys.slice(0, 6)
                                    delegate: Row {
                                        width: ffCol.width
                                        property var fObj: ((root.summaryData.market_intel || ({})).foreign_counters || ({}))[modelData] || ({})
                                        property real fNet: Number(fObj.net_val || 0)
                                        Text { width: ffCol.width * 0.28; text: modelData; color: fObj.currency === "ZWG" ? "#f9e2af" : "#cdd6f4"; font.pixelSize: 9; font.bold: true }
                                        Text { width: ffCol.width * 0.36; text: fNet >= 0 ? "Foreign Inflow" : "Foreign Outflow"; color: fNet >= 0 ? "#a6e3a1" : "#f38ba8"; font.pixelSize: 9 }
                                        Text { width: ffCol.width * 0.36; horizontalAlignment: Text.AlignRight; text: root.fmtSignedMoney(fNet, fObj.currency || "USD"); color: fNet >= 0 ? "#a6e3a1" : "#f38ba8"; font.pixelSize: 9; font.bold: true }
                                    }
                                }
                                Repeater {
                                    model: (((root.summaryData.market_intel || ({})).vfex || ({})).movers || []).slice(0, 3)
                                    delegate: Row {
                                        width: ffCol.width
                                        Text { width: ffCol.width * 0.65; text: "Mover: " + (modelData.counter || ""); color: "#a6adc8"; font.pixelSize: 8; elide: Text.ElideRight }
                                        Text { width: ffCol.width * 0.35; horizontalAlignment: Text.AlignRight; text: (Number(modelData.percentageChange || 0) >= 0 ? "+" : "") + Number(modelData.percentageChange || 0).toFixed(2) + "%"; color: Number(modelData.percentageChange || 0) >= 0 ? "#a6e3a1" : "#f38ba8"; font.pixelSize: 8; font.bold: true }
                                    }
                                }
                            }
                        }
                    }

                    // Full Filterable VFEX & ZSE News Catalysts Feed
                    Rectangle {
                        id: tab3NewsCard
                        width: parent.width
                        height: tab3NewsCol.implicitHeight + Style.space(16)
                        radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1

                        Column {
                            id: tab3NewsCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                            spacing: Style.space(6)
                            property var nsum: root.summaryData.news_summary || ({})

                            Row {
                                width: parent.width
                                spacing: Style.space(6)
                                Column {
                                    width: parent.width - t3NewsCtrls.width - Style.space(6)
                                    anchors.verticalCenter: parent.verticalCenter
                                    Text {
                                        text: "Live VFEX & ZSE News Catalysts (" + root.filteredNews().length + ")"
                                        color: "#cba6f7"
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.body
                                        font.bold: true
                                    }
                                    Text {
                                        text: "Tracked: " + (tab3NewsCol.nsum.tracked || 0) + " • Bullish: " + (tab3NewsCol.nsum.bullish || 0) + " • Caution: " + (tab3NewsCol.nsum.caution || 0) + " • Official Disclosures: " + (tab3NewsCol.nsum.official || 0)
                                        color: "#6c7086"
                                        font.pixelSize: 9
                                    }
                                }
                                Row {
                                    id: t3NewsCtrls
                                    spacing: 4
                                    anchors.verticalCenter: parent.verticalCenter
                                    Repeater {
                                        model: [
                                            { key: "all", label: "All" },
                                            { key: "tracked", label: "Tracked" },
                                            { key: "bullish", label: "Bullish" },
                                            { key: "caution", label: "Caution" },
                                            { key: "official", label: "Official" }
                                        ]
                                        delegate: Rectangle {
                                            width: nfltLbl.implicitWidth + 10; height: Style.space(18); radius: 4
                                            color: root.newsFilter === modelData.key ? "#cba6f7" : "#313244"
                                            Text {
                                                id: nfltLbl
                                                anchors.centerIn: parent
                                                text: modelData.label
                                                color: root.newsFilter === modelData.key ? "#1e1e2e" : "#cdd6f4"
                                                font.pixelSize: 9
                                                font.bold: true
                                            }
                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.newsFilter = modelData.key }
                                        }
                                    }
                                    Rectangle {
                                        width: nRefLbl.implicitWidth + 10; height: Style.space(18); radius: 4
                                        color: "#1e2e4a"; border.color: "#89b4fa"; border.width: 1
                                        Text { id: nRefLbl; anchors.centerIn: parent; text: manualProc.running ? "Refreshing..." : "⟳ Refresh News"; color: "#89b4fa"; font.pixelSize: 9; font.bold: true }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                            onClicked: {
                                                var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                manualProc.command = ["python3", script, "news", "--fetch", "--summary"]
                                                manualProc.running = true
                                            }
                                        }
                                    }
                                }
                            }

                            Text {
                                visible: root.summaryData.news_enabled === false
                                text: "Live news catalyst watching is disabled in Plugin Settings (enable newsEnabled to watch VFEX/ZSE headlines)."
                                color: "#6c7086"
                                font.pixelSize: Style.font.small || Style.font.body
                                wrapMode: Text.WordWrap
                                width: parent.width
                            }

                            Text {
                                visible: root.summaryData.news_enabled !== false && root.filteredNews().length === 0
                                text: "No headlines match this filter right now — try switching filter or clicking Fetch."
                                color: "#6c7086"
                                font.pixelSize: Style.font.small || Style.font.body
                                wrapMode: Text.WordWrap
                                width: parent.width
                            }

                            Repeater {
                                model: root.filteredNews().slice(0, 18)
                                delegate: Rectangle {
                                    width: tab3NewsCol.width
                                    height: t3nItemCol.implicitHeight + Style.space(10)
                                    radius: 6
                                    color: t3nHover.containsMouse ? "#242436" : "#11111b"
                                    border.color: modelData.sentiment === "Bullish" ? "#243b2c" : (modelData.sentiment === "Caution" ? "#4a242d" : "#242436")
                                    border.width: 1

                                    Rectangle {
                                        width: 3; height: parent.height - 8; radius: 1.5
                                        anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 2 }
                                        color: root.newsSentimentColor(modelData.sentiment)
                                    }

                                    MouseArea {
                                        id: t3nHover
                                        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        onClicked: root.openNewsUrl(modelData.url)
                                    }

                                    Column {
                                        id: t3nItemCol
                                        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: Style.space(10); rightMargin: Style.space(8); topMargin: Style.space(6) }
                                        spacing: 3

                                        Row {
                                            width: parent.width
                                            spacing: Style.space(4)
                                            Rectangle {
                                                width: t3nCatLbl.implicitWidth + 8; height: t3nCatLbl.implicitHeight + 2; radius: 3
                                                color: root.newsSentimentBg(modelData.sentiment)
                                                anchors.verticalCenter: parent.verticalCenter
                                                Text {
                                                    id: t3nCatLbl
                                                    anchors.centerIn: parent
                                                    text: modelData.sentiment + " • " + modelData.category
                                                    color: root.newsSentimentColor(modelData.sentiment)
                                                    font.pixelSize: 8; font.bold: true
                                                }
                                            }
                                            Rectangle {
                                                visible: Boolean(modelData.tracked)
                                                width: t3TrkLbl.implicitWidth + 6; height: t3TrkLbl.implicitHeight + 2; radius: 3
                                                color: "#1e2e4a"
                                                anchors.verticalCenter: parent.verticalCenter
                                                Text { id: t3TrkLbl; anchors.centerIn: parent; text: "★ TRACKED"; color: "#89b4fa"; font.pixelSize: 8; font.bold: true }
                                            }
                                            Repeater {
                                                model: (modelData.symbols || []).slice(0, 3)
                                                delegate: Row {
                                                    spacing: 2
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    Rectangle {
                                                        width: t3SymLbl.implicitWidth + 8; height: t3SymLbl.implicitHeight + 2; radius: 3
                                                        color: "#242436"
                                                        Text { id: t3SymLbl; anchors.centerIn: parent; text: modelData; color: "#cdd6f4"; font.pixelSize: 8; font.bold: true }
                                                        MouseArea {
                                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                            onClicked: { root.chartSymbol = modelData; root.hoveredCandleIdx = -1; root.activeTab = "overview" }
                                                        }
                                                    }
                                                    Rectangle {
                                                        visible: !root.isWatchedSymbol(modelData) && !root.isOwnedSymbol(modelData)
                                                        width: t3WPlus.implicitWidth + 6; height: t3WPlus.implicitHeight + 2; radius: 3
                                                        color: "#1b2e24"
                                                        Text { id: t3WPlus; anchors.centerIn: parent; text: "+ Watchlist"; color: "#a6e3a1"; font.pixelSize: 8; font.bold: true }
                                                        MouseArea {
                                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                                            onClicked: {
                                                                var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                                manualProc.command = ["python3", script, "watch", "add", modelData]
                                                                manualProc.running = true
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                            Text {
                                                text: (modelData.source || "") + " • " + (modelData.date || "") + (modelData.age_label ? (" (" + root.fmtAgeLabel(modelData.age_label) + ")") : "")
                                                color: "#6c7086"
                                                font.pixelSize: 8
                                                anchors.verticalCenter: parent.verticalCenter
                                                elide: Text.ElideRight
                                            }
                                        }

                                        Row {
                                            width: parent.width
                                            spacing: Style.space(6)
                                            Text {
                                                width: parent.width - openArtBtn.width - Style.space(6)
                                                text: modelData.title || ""
                                                color: "#cdd6f4"
                                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                                font.pixelSize: Style.font.small || Style.font.body
                                                wrapMode: Text.WordWrap
                                            }
                                            Text {
                                                id: openArtBtn
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: "Open ↗"
                                                color: "#89b4fa"
                                                font.pixelSize: 9
                                                font.bold: true
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // === TAB 4: UNIFIED 3-PORTAL GRID & COMPLETE WORKSTATION LEDGER ===
                Column {
                    id: ledgerTabCol
                    visible: root.activeTab === "ledger"
                    width: parent.width
                    spacing: Style.space(8)

                    // 3-Column Broker Portals Status Cards
                    Grid {
                        width: parent.width
                        columns: root.wideLayout ? 3 : 1
                        columnSpacing: Style.space(8)
                        rowSpacing: Style.space(8)
                        Repeater {
                            model: [
                                { key: "ctrade", label: "C-TRADE (VFEX + ZSE)", cur: "USD" },
                                { key: "vfex_direct", label: "VFEX Direct", cur: "USD" },
                                { key: "zse_direct", label: "ZSE Direct", cur: "ZWG" }
                            ]
                            delegate: Rectangle {
                                id: pCardRoot
                                property var pInfo: ((root.summaryData.accounts || ({}))[modelData.key]) || ({})
                                property bool isSel: root.activeProvider === modelData.key
                                width: root.wideLayout ? (ledgerTabCol.width - Style.space(16)) / 3 : ledgerTabCol.width
                                height: pCardCol.implicitHeight + Style.space(12)
                                radius: 8
                                color: isSel ? "#242436" : "#181825"
                                border.color: Boolean(pInfo.connected) ? "#a6e3a1" : (Boolean(pInfo.mfa_pending) ? "#f9e2af" : (isSel ? "#89b4fa" : "#313244"))
                                border.width: 1

                                MouseArea {
                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                    onClicked: { root.activeProvider = modelData.key; root.ctradeStatusMessage = "" }
                                }

                                Column {
                                    id: pCardCol
                                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(6) }
                                    spacing: 3
                                    Row {
                                        width: parent.width
                                        Text { width: parent.width - stPill.width; text: modelData.label; color: "#cdd6f4"; font.pixelSize: Style.font.small || Style.font.body; font.bold: true; elide: Text.ElideRight; anchors.verticalCenter: parent.verticalCenter }
                                        Rectangle {
                                            id: stPill; width: stPillTxt.implicitWidth + 8; height: stPillTxt.implicitHeight + 3; radius: 3
                                            color: Boolean(pCardRoot.pInfo.connected) ? "#1f3a27" : (Boolean(pCardRoot.pInfo.mfa_pending) ? "#2b261d" : "#313244")
                                            Text {
                                                id: stPillTxt; anchors.centerIn: parent
                                                text: Boolean(pCardRoot.pInfo.connected) ? "● Synced" : (Boolean(pCardRoot.pInfo.mfa_pending) ? "◔ OTP" : "Offline")
                                                color: Boolean(pCardRoot.pInfo.connected) ? "#a6e3a1" : (Boolean(pCardRoot.pInfo.mfa_pending) ? "#f9e2af" : "#6c7086")
                                                font.pixelSize: 8; font.bold: true
                                            }
                                        }
                                    }
                                    Text {
                                        width: parent.width
                                        text: Boolean(pCardRoot.pInfo.connected) ? ((pCardRoot.pInfo.email_masked || "") + (pCardRoot.pInfo.cds_number ? (" • CDS " + pCardRoot.pInfo.cds_number) : "")) : "Click to configure 0600 login"
                                        color: "#a6adc8"; font.pixelSize: 9; elide: Text.ElideRight
                                    }
                                    Row {
                                        width: parent.width; spacing: 4
                                        Text {
                                            width: parent.width - pActChip.width - 4
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: {
                                                var a = pCardRoot.pInfo
                                                var cv = modelData.cur === "ZWG" ? Number(a.cash_zwg || 0) : Number(a.cash_usd || 0)
                                                return Boolean(a.connected) ? ("Holdings: " + (a.holdings_count || 0) + (cv > 0 ? (" • " + root.fmtShortMoney(cv, modelData.cur)) : "")) : "Local secrets only"
                                            }
                                            color: "#89dceb"; font.pixelSize: 9; elide: Text.ElideRight
                                        }
                                        Rectangle {
                                            id: pActChip; width: pActTxt.implicitWidth + 10; height: Style.space(18); radius: 3; color: "#313244"
                                            Text { id: pActTxt; anchors.centerIn: parent; text: Boolean(pCardRoot.pInfo.connected) ? "Sync" : "Login"; color: "#89b4fa"; font.pixelSize: 9; font.bold: true }
                                            MouseArea {
                                                anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !ctradeProc.running
                                                onClicked: {
                                                    root.activeProvider = modelData.key
                                                    if (Boolean(pCardRoot.pInfo.connected)) {
                                                        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                        ctradeProc.stdinEnabled = false; ctradeProc.lastErr = ""; ctradeProc.lastOut = ""
                                                        ctradeProc.command = ["python3", script, "account", "sync", "--provider", modelData.key]
                                                        ctradeProc.running = true
                                                    } else {
                                                        root.credsExpanded = true
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Collapsible Credential & OTP Drawer
                    Rectangle {
                        id: accountSyncCard
                        width: parent.width
                        height: accountSyncCol.implicitHeight + Style.space(12)
                        radius: 8; color: "#181825"
                        border.color: Boolean(root.activeProviderInfo().mfa_pending) ? "#f9e2af" : "#313244"; border.width: 1

                        Column {
                            id: accountSyncCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(6) }
                            spacing: Style.space(6)

                            Row {
                                width: parent.width; spacing: Style.space(6)
                                Text {
                                    width: parent.width - credTogBtn.width - (syncAllHdrBtn.visible ? syncAllHdrBtn.width + Style.space(6) : 0) - Style.space(6)
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "Portal Credentials (" + root.activeProvider.toUpperCase() + ")"
                                    color: "#cdd6f4"; font.pixelSize: Style.font.small || Style.font.body; font.bold: true
                                }
                                Rectangle {
                                    id: syncAllHdrBtn; visible: root.connectedPortalsCount() > 0
                                    width: sAllTxt.implicitWidth + 12; height: Style.space(22); radius: 4; color: "#1f3a27"; border.color: "#a6e3a1"; border.width: 1
                                    Text { id: sAllTxt; anchors.centerIn: parent; text: "↻ Sync All (" + root.connectedPortalsCount() + ")"; color: "#a6e3a1"; font.pixelSize: 9; font.bold: true }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !ctradeProc.running
                                        onClicked: {
                                            var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                            ctradeProc.stdinEnabled = false; ctradeProc.lastErr = ""; ctradeProc.lastOut = ""
                                            ctradeProc.command = ["python3", script, "account", "sync", "--provider", "all"]; ctradeProc.running = true
                                        }
                                    }
                                }
                                Rectangle {
                                    id: credTogBtn
                                    width: cTogTxt.implicitWidth + 12; height: Style.space(22); radius: 4; color: "#313244"
                                    Text { id: cTogTxt; anchors.centerIn: parent; text: (root.credsExpanded || Boolean(root.activeProviderInfo().mfa_pending) || !Boolean(root.activeProviderInfo().connected)) ? "Hide Form ▴" : "Edit Login ▾"; color: "#cdd6f4"; font.pixelSize: 9; font.bold: true }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.credsExpanded = !root.credsExpanded }
                                }
                            }

                            Column {
                                width: parent.width; spacing: Style.space(5)
                                visible: root.credsExpanded || Boolean(root.activeProviderInfo().mfa_pending) || !Boolean(root.activeProviderInfo().connected)

                                Row {
                                    width: parent.width; spacing: Style.space(6)
                                    Rectangle {
                                        width: (parent.width - Style.space(6)) / 2; height: Style.space(26); radius: 4; color: "#313244"; border.color: ctradeEmailInput.activeFocus ? "#89b4fa" : "#45475a"; border.width: 1
                                        TextInput {
                                            id: ctradeEmailInput; anchors.fill: parent; anchors.margins: Style.space(5); color: "#cdd6f4"; font.pixelSize: Style.font.body; verticalAlignment: TextInput.AlignVCenter; clip: true
                                            Component.onCompleted: text = root.ctradeEmailText
                                            onTextChanged: if (root.ctradeEmailText !== text) root.ctradeEmailText = text
                                            Connections { target: root; function onCtradeEmailTextChanged() { if (ctradeEmailInput.text !== root.ctradeEmailText) ctradeEmailInput.text = root.ctradeEmailText } }
                                            Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Portal Email"; color: "#6c7086"; font: ctradeEmailInput.font; visible: !ctradeEmailInput.text && !ctradeEmailInput.activeFocus }
                                        }
                                    }
                                    Rectangle {
                                        width: (parent.width - Style.space(6)) / 2; height: Style.space(26); radius: 4; color: "#313244"; border.color: ctradePassInput.activeFocus ? "#89b4fa" : "#45475a"; border.width: 1
                                        TextInput {
                                            id: ctradePassInput; anchors.fill: parent; anchors.margins: Style.space(5); color: "#cdd6f4"; font.pixelSize: Style.font.body; verticalAlignment: TextInput.AlignVCenter; echoMode: TextInput.Password; clip: true
                                            Component.onCompleted: text = root.ctradePassText
                                            onTextChanged: if (root.ctradePassText !== text) root.ctradePassText = text
                                            Connections { target: root; function onCtradePassTextChanged() { if (ctradePassInput.text !== root.ctradePassText) ctradePassInput.text = root.ctradePassText } }
                                            Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Password (0600 local)"; color: "#6c7086"; font: ctradePassInput.font; visible: !ctradePassInput.text && !ctradePassInput.activeFocus }
                                        }
                                    }
                                }

                                Row {
                                    width: parent.width; visible: Boolean(root.activeProviderInfo().mfa_pending); spacing: Style.space(6)
                                    Rectangle {
                                        width: parent.width * 0.68; height: Style.space(26); radius: 4; color: "#313244"; border.color: mfaOtpInput.activeFocus ? "#f9e2af" : "#45475a"; border.width: 1
                                        TextInput {
                                            id: mfaOtpInput; anchors.fill: parent; anchors.margins: Style.space(5); color: "#cdd6f4"; font.pixelSize: Style.font.body; verticalAlignment: TextInput.AlignVCenter; clip: true
                                            Component.onCompleted: text = root.mfaOtpText
                                            onTextChanged: if (root.mfaOtpText !== text) root.mfaOtpText = text
                                            Connections { target: root; function onMfaOtpTextChanged() { if (mfaOtpInput.text !== root.mfaOtpText) mfaOtpInput.text = root.mfaOtpText } }
                                            Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Enter 6-digit OTP code"; color: "#f9e2af"; font: mfaOtpInput.font; visible: !mfaOtpInput.text && !mfaOtpInput.activeFocus }
                                        }
                                    }
                                    Rectangle {
                                        width: parent.width * 0.32 - Style.space(6); height: Style.space(26); radius: 4; color: ctradeProc.running ? "#45475a" : "#f9e2af"
                                        Text { anchors.centerIn: parent; text: ctradeProc.running ? "..." : "Verify OTP"; color: "#1e1e2e"; font.pixelSize: Style.font.small || Style.font.body; font.bold: true }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !ctradeProc.running
                                            onClicked: {
                                                var code = root.mfaOtpText.trim()
                                                if (!code) { root.ctradeStatusError = true; root.ctradeStatusMessage = "Enter 6-digit OTP code"; return }
                                                var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                ctradeProc.stdinEnabled = false; ctradeProc.lastErr = ""; ctradeProc.lastOut = ""
                                                ctradeProc.command = ["python3", script, "account", "verify-mfa", "--provider", root.activeProvider, "--code", code]
                                                ctradeProc.running = true
                                            }
                                        }
                                    }
                                }

                                Row {
                                    width: parent.width; spacing: Style.space(6)
                                    Rectangle {
                                        property bool hasDisc: Boolean(root.activeProviderInfo().connected) || Boolean(root.activeProviderInfo().mfa_pending)
                                        width: hasDisc ? parent.width * 0.70 : parent.width
                                        height: Style.space(24); radius: 4; color: ctradeProc.running ? "#45475a" : "#89b4fa"
                                        Text { anchors.centerIn: parent; text: ctradeProc.running ? "Working..." : "Connect & Sync " + root.activeProvider.toUpperCase(); color: "#1e1e2e"; font.pixelSize: Style.font.small || Style.font.body; font.bold: true }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !ctradeProc.running
                                            onClicked: {
                                                var em = root.ctradeEmailText.trim(), pw = root.ctradePassText
                                                var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                ctradeProc.lastErr = ""; ctradeProc.lastOut = ""
                                                if (em && pw) {
                                                    ctradeProc.secret = pw; ctradeProc.stdinEnabled = true
                                                    ctradeProc.command = ["python3", script, "account", "login", "--provider", root.activeProvider, "--email", em, "--password-stdin"]
                                                    ctradeProc.running = true
                                                } else if (Boolean(root.activeProviderInfo().connected)) {
                                                    ctradeProc.stdinEnabled = false
                                                    ctradeProc.command = ["python3", script, "account", "sync", "--provider", root.activeProvider]
                                                    ctradeProc.running = true
                                                } else {
                                                    root.ctradeStatusError = true; root.ctradeStatusMessage = "Enter email and password"
                                                }
                                            }
                                        }
                                    }
                                    Rectangle {
                                        visible: Boolean(root.activeProviderInfo().connected) || Boolean(root.activeProviderInfo().mfa_pending)
                                        width: parent.width * 0.30 - Style.space(6); height: Style.space(24); radius: 4; color: "#3d2229"; border.color: "#f38ba8"; border.width: 1
                                        Text { anchors.centerIn: parent; text: "Disconnect"; color: "#f38ba8"; font.pixelSize: Style.font.small ? Style.font.small - 1 : 10; font.bold: true }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !ctradeProc.running
                                            onClicked: {
                                                var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                ctradeProc.stdinEnabled = false; ctradeProc.lastErr = ""; ctradeProc.lastOut = ""
                                                ctradeProc.command = ["python3", script, "account", "logout", "--provider", root.activeProvider]; ctradeProc.running = true
                                            }
                                        }
                                    }
                                }
                            }

                            Text {
                                width: parent.width; visible: root.ctradeStatusMessage.length > 0
                                text: root.ctradeStatusMessage; color: root.ctradeStatusError ? "#f38ba8" : "#a6e3a1"
                                font.pixelSize: Style.font.small ? Style.font.small - 1 : 10; wrapMode: Text.WordWrap
                            }
                        }
                    }

                    // Morgan & Co / VFEX / ZSE PDF & Text Contract Note Importer
                    Rectangle {
                        id: noteImportCard
                        width: parent.width
                        height: noteImpCol.implicitHeight + Style.space(12)
                        radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1

                        Column {
                            id: noteImpCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                            spacing: Style.space(5)

                            Row {
                                width: parent.width; spacing: Style.space(6)
                                Column {
                                    width: parent.width - noteModeTog.width - Style.space(6)
                                    anchors.verticalCenter: parent.verticalCenter
                                    Text { text: "Contract Note PDF / Text Importer (Morgan & Co • pdftotext)"; color: "#89dceb"; font.pixelSize: Style.font.body; font.bold: true }
                                    Text { text: "Parse exact Brokerage, VAT, Platform, SECZ, Stamp & CGT straight into your FIFO ledger with duplicate protection"; color: "#6c7086"; font.pixelSize: 9; elide: Text.ElideRight; width: parent.width }
                                }
                                Row {
                                    id: noteModeTog; spacing: 3; anchors.verticalCenter: parent.verticalCenter
                                    Repeater {
                                        model: [
                                            { paste: false, label: "PDF File" },
                                            { paste: true, label: "Paste Text" }
                                        ]
                                        delegate: Rectangle {
                                            width: nmtLbl.implicitWidth + 10; height: Style.space(20); radius: 4
                                            color: root.notePasteMode === modelData.paste ? "#89dceb" : "#313244"
                                            Text { id: nmtLbl; anchors.centerIn: parent; text: modelData.label; color: root.notePasteMode === modelData.paste ? "#1e1e2e" : "#cdd6f4"; font.pixelSize: 9; font.bold: true }
                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.notePasteMode = modelData.paste; root.notePreviewData = null; root.notePreviewErr = "" } }
                                        }
                                    }
                                }
                            }

                            // Recent Downloads PDF quick-pick chips
                            Flow {
                                width: parent.width; spacing: 4
                                visible: !root.notePasteMode && (root.summaryData.local_pdfs || []).length > 0
                                Text { text: "~/Downloads PDFs:"; color: "#6c7086"; font.pixelSize: 9 }
                                Repeater {
                                    model: (root.summaryData.local_pdfs || []).slice(0, 4)
                                    delegate: Rectangle {
                                        width: dlPdfTxt.implicitWidth + 10; height: Style.space(18); radius: 4
                                        color: root.noteFilePath === modelData.path ? "#1e2e4a" : "#11111b"
                                        border.color: root.noteFilePath === modelData.path ? "#89b4fa" : "#313244"; border.width: 1
                                        Text { id: dlPdfTxt; anchors.centerIn: parent; text: String(modelData.name || "").slice(0, 28); color: "#89b4fa"; font.pixelSize: 8; font.bold: true }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                root.noteFilePath = modelData.path
                                                var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                notePreviewProc.lastErr = ""
                                                notePreviewProc.command = ["python3", script, "import-note", modelData.path, "--preview", "--json"]
                                                notePreviewProc.running = true
                                            }
                                        }
                                    }
                                }
                            }

                            Row {
                                width: parent.width; spacing: Style.space(6)
                                Rectangle {
                                    width: parent.width - previewNoteBtn.width - Style.space(6)
                                    height: root.notePasteMode ? Style.space(48) : Style.space(26)
                                    radius: 4; color: "#313244"
                                    border.color: (notePathInput.activeFocus || noteTextArea.activeFocus) ? "#89dceb" : "#45475a"; border.width: 1

                                    TextInput {
                                        id: notePathInput
                                        visible: !root.notePasteMode
                                        anchors.fill: parent; anchors.margins: Style.space(5); color: "#cdd6f4"; font.pixelSize: Style.font.small || Style.font.body; verticalAlignment: TextInput.AlignVCenter; clip: true
                                        Component.onCompleted: text = root.noteFilePath
                                        onTextChanged: if (root.noteFilePath !== text) root.noteFilePath = text
                                        Connections { target: root; function onNoteFilePathChanged() { if (notePathInput.text !== root.noteFilePath) notePathInput.text = root.noteFilePath } }
                                        Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Path to Morgan & Co .pdf / .txt (e.g. ~/Downloads/contract.pdf)"; color: "#6c7086"; font: notePathInput.font; visible: !notePathInput.text && !notePathInput.activeFocus }
                                    }

                                    TextEdit {
                                        id: noteTextArea
                                        visible: root.notePasteMode
                                        anchors.fill: parent; anchors.margins: Style.space(5); color: "#cdd6f4"; font.pixelSize: 9; wrapMode: TextEdit.Wrap; clip: true
                                        Component.onCompleted: text = root.noteRawText
                                        onTextChanged: if (root.noteRawText !== text) root.noteRawText = text
                                        Connections { target: root; function onNoteRawTextChanged() { if (noteTextArea.text !== root.noteRawText) noteTextArea.text = root.noteRawText } }
                                        Text { anchors.fill: parent; text: "Paste Morgan & Co contract note text here..."; color: "#6c7086"; font: noteTextArea.font; visible: !noteTextArea.text && !noteTextArea.activeFocus }
                                    }
                                }

                                Rectangle {
                                    id: previewNoteBtn
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: pvBtnTxt.implicitWidth + 14; height: Style.space(26); radius: 4; color: notePreviewProc.running ? "#45475a" : "#1e2e4a"; border.color: "#89b4fa"; border.width: 1
                                    Text { id: pvBtnTxt; anchors.centerIn: parent; text: notePreviewProc.running ? "Parsing..." : "Preview Note"; color: "#89b4fa"; font.pixelSize: 9; font.bold: true }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !notePreviewProc.running
                                        onClicked: {
                                            var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                            notePreviewProc.lastErr = ""
                                            if (root.notePasteMode) {
                                                var txt = root.noteRawText.trim()
                                                if (!txt) { root.notePreviewErr = "Paste contract note text first."; return }
                                                notePreviewProc.command = ["python3", script, "import-note", "--text", txt, "--preview", "--json"]
                                            } else {
                                                var fp = root.noteFilePath.trim()
                                                if (!fp) { root.notePreviewErr = "Enter a PDF or text file path first."; return }
                                                notePreviewProc.command = ["python3", script, "import-note", fp, "--preview", "--json"]
                                            }
                                            notePreviewProc.running = true
                                        }
                                    }
                                }
                            }

                            Text {
                                width: parent.width
                                visible: root.notePreviewErr.length > 0
                                text: "⚠ " + root.notePreviewErr
                                color: "#f38ba8"; font.pixelSize: 9; wrapMode: Text.WordWrap
                            }

                            // Parsed Contract Note Preview + Commit Controls
                            Rectangle {
                                width: parent.width
                                visible: Boolean(root.notePreviewData && root.notePreviewData.ok)
                                height: npvCol.implicitHeight + Style.space(10)
                                radius: 6; color: "#11111b"
                                border.color: Boolean((root.notePreviewData || ({})).duplicate) ? "#f9e2af" : "#a6e3a1"; border.width: 1

                                Column {
                                    id: npvCol
                                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(5) }
                                    spacing: 4
                                    property var pv: root.notePreviewData || ({})
                                    property var pcn: pv.contract_note || ({})

                                    Row {
                                        width: parent.width; spacing: 6
                                        Text {
                                            width: parent.width - npvBtnsRow.width - 6
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: (npvCol.pv.broker || "Note") + ": " + (npvCol.pv.side || "BUY") + " " + Number(npvCol.pv.shares || 0) + " " + (npvCol.pv.symbol || "") + " @ " + root.fmtPrice(npvCol.pv.price, npvCol.pv.currency) + " (" + (npvCol.pv.date || "") + ")" + (npvCol.pv.duplicate ? "  [⚠ ALREADY IN LEDGER]" : "")
                                            color: npvCol.pv.duplicate ? "#f9e2af" : "#a6e3a1"
                                            font.pixelSize: 9; font.bold: true; wrapMode: Text.WordWrap
                                        }
                                        Row {
                                            id: npvBtnsRow; spacing: 4; anchors.verticalCenter: parent.verticalCenter
                                            Repeater {
                                                model: ["core", "swing"]
                                                delegate: Rectangle {
                                                    width: tgLbl.implicitWidth + 8; height: Style.space(20); radius: 3
                                                    color: root.noteImportTag === modelData ? (modelData === "core" ? "#1f3a27" : "#272138") : "#313244"
                                                    Text { id: tgLbl; anchors.centerIn: parent; text: modelData.toUpperCase(); color: modelData === "core" ? "#a6e3a1" : "#cba6f7"; font.pixelSize: 8; font.bold: true }
                                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.noteImportTag = modelData }
                                                }
                                            }
                                            Rectangle {
                                                width: impGoTxt.implicitWidth + 12; height: Style.space(20); radius: 4
                                                color: manualProc.running ? "#45475a" : (npvCol.pv.duplicate ? "#2b261d" : "#a6e3a1")
                                                Text { id: impGoTxt; anchors.centerIn: parent; text: npvCol.pv.duplicate ? "Re-Import" : "Import Trade"; color: npvCol.pv.duplicate ? "#f9e2af" : "#1e1e2e"; font.pixelSize: 9; font.bold: true }
                                                MouseArea {
                                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                                    onClicked: {
                                                        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                        var cmd = ["python3", script, "import-note"]
                                                        if (root.notePasteMode) {
                                                            cmd.push("--text"); cmd.push(root.noteRawText.trim())
                                                        } else {
                                                            cmd.push(root.noteFilePath.trim())
                                                        }
                                                        cmd.push("--tag"); cmd.push(root.noteImportTag)
                                                        if (npvCol.pv.duplicate) cmd.push("--allow-duplicate")
                                                        root.lastManualError = ""
                                                        manualProc.lastOut = ""
                                                        manualProc.command = cmd
                                                        manualProc.running = true
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    Text {
                                        width: parent.width
                                        text: "Gross " + root.fmtShortMoney(npvCol.pv.gross, npvCol.pv.currency) + "  •  Brokerage " + root.fmtShortMoney(npvCol.pcn.brokerage, npvCol.pv.currency) + "  •  VAT " + root.fmtShortMoney(npvCol.pcn.vat, npvCol.pv.currency) + "  •  Platform/SECZ " + root.fmtShortMoney(Number(npvCol.pcn.platform_levy || 0) + Number(npvCol.pcn.secz_levy || 0), npvCol.pv.currency) + "  •  Stamp Duty " + root.fmtShortMoney(npvCol.pcn.stamp_duty, npvCol.pv.currency) + "  •  Total Charges " + root.fmtShortMoney(npvCol.pv.total_charges, npvCol.pv.currency) + "  →  Net " + root.fmtShortMoney(npvCol.pv.net_settlement, npvCol.pv.currency)
                                        color: "#a6adc8"; font.pixelSize: 8; wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }
                    }

                    // 2-Column Complete Workstation Ledger: Trades + Dividends | Protections + Notes
                    Flow {
                        width: parent.width; spacing: Style.space(8)

                        // LEFT COLUMN (58%): Portal Cash & Orders + Trade History Ledger + Dividends History
                        Column {
                            width: root.wideLayout ? (ledgerTabCol.width - Style.space(8)) * 0.58 : ledgerTabCol.width
                            spacing: Style.space(8)

                            Rectangle {
                                width: parent.width
                                visible: ((root.summaryData.portal_orders || []).length > 0) || ((root.summaryData.portal_transactions || []).length > 0) || Number(root.summaryData.wallet_cash_usd || 0) > 0 || Number(root.summaryData.wallet_cash_zwg || 0) > 0
                                height: portalSyncCol.implicitHeight + Style.space(14)
                                radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                                Column {
                                    id: portalSyncCol
                                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                                    spacing: Style.space(4)
                                    property var icp4: (root.summaryData.idle_cash_plan || ({}))
                                    Row {
                                        width: parent.width
                                        Text { width: parent.width * 0.55; text: "Synced Portal Cash, Orders & History"; color: "#89dceb"; font.pixelSize: Style.font.body; font.bold: true }
                                        Text {
                                            width: parent.width * 0.45; horizontalAlignment: Text.AlignRight
                                            text: "Idle Cash: $" + Number(portalSyncCol.icp4.total_deployable_usd || root.summaryData.wallet_cash_usd || 0).toFixed(2) + " USD • ZiG " + Number(portalSyncCol.icp4.total_deployable_zwg || root.summaryData.wallet_cash_zwg || 0).toFixed(2)
                                            color: "#a6e3a1"; font.pixelSize: 9; font.bold: true; elide: Text.ElideLeft
                                        }
                                    }
                                    Text { visible: (root.summaryData.portal_orders || []).length > 0; text: "Open Working Orders (" + (root.summaryData.portal_orders || []).length + ")"; color: "#f9e2af"; font.pixelSize: 9; font.bold: true }
                                    Repeater {
                                        model: (root.summaryData.portal_orders || []).slice(0, 6)
                                        delegate: Row {
                                            width: portalSyncCol.width
                                            Text { width: portalSyncCol.width * 0.25; text: modelData.side + " " + modelData.symbol; color: modelData.side === "SELL" ? "#f38ba8" : "#a6e3a1"; font.pixelSize: 9; font.bold: true }
                                            Text { width: portalSyncCol.width * 0.45; text: Number(modelData.shares || 0) + " shares @ " + root.fmtPrice(modelData.price, modelData.currency); color: "#cdd6f4"; font.pixelSize: 9 }
                                            Text { width: portalSyncCol.width * 0.30; horizontalAlignment: Text.AlignRight; text: modelData.status || "Active"; color: "#f9e2af"; font.pixelSize: 9 }
                                        }
                                    }
                                    Text { visible: (root.summaryData.portal_transactions || []).length > 0; text: "Portal Statements (" + (root.summaryData.portal_transactions || []).length + ")"; color: "#cba6f7"; font.pixelSize: 9; font.bold: true }
                                    Repeater {
                                        model: (root.summaryData.portal_transactions || []).slice(0, 8)
                                        delegate: Rectangle {
                                            width: portalSyncCol.width; height: ptxRow.implicitHeight + 6; radius: 4; color: "#11111b"
                                            Row {
                                                id: ptxRow
                                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 4 }
                                                spacing: 4
                                                Text { width: parent.width * 0.15; text: modelData.date || "--"; color: "#6c7086"; font.pixelSize: 8; anchors.verticalCenter: parent.verticalCenter }
                                                Text { width: parent.width * 0.36; text: (modelData.symbol ? (modelData.symbol + " • ") : "") + (modelData.description || modelData.type); color: "#cdd6f4"; font.pixelSize: 8; elide: Text.ElideRight; anchors.verticalCenter: parent.verticalCenter }
                                                Text { width: parent.width * 0.21; horizontalAlignment: Text.AlignRight; text: root.fmtShortMoney(modelData.amount, modelData.currency); color: "#89b4fa"; font.pixelSize: 8; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                                                Rectangle {
                                                    width: parent.width * 0.28 - 12; height: Style.space(18); radius: 3
                                                    color: modelData.already_imported ? "#1f3a27" : ((modelData.trade_side === "BUY" || modelData.trade_side === "SELL" || modelData.trade_side === "DIV") ? "#1e2e4a" : "transparent")
                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: modelData.already_imported ? "Imported" : (modelData.trade_side === "BUY" ? "Import Buy" : (modelData.trade_side === "SELL" ? "Import Sell" : (modelData.trade_side === "DIV" ? "Import Dividend" : "")))
                                                        color: modelData.already_imported ? "#a6e3a1" : "#89b4fa"; font.pixelSize: 8; font.bold: true
                                                    }
                                                    MouseArea {
                                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                        enabled: !manualProc.running && !modelData.already_imported && (modelData.trade_side === "BUY" || modelData.trade_side === "SELL" || modelData.trade_side === "DIV")
                                                        onClicked: {
                                                            if (modelData.trade_side === "BUY" || modelData.trade_side === "SELL") {
                                                                var act = modelData.trade_side === "SELL" ? "sell" : "buy"
                                                                var args = [act, modelData.symbol, String(modelData.shares || 0), String(modelData.price || 0)]
                                                                if (modelData.date) { args.push("--date"); args.push(modelData.date) }
                                                                root.runCliCommand(args, false)
                                                            } else if (modelData.trade_side === "DIV" && modelData.symbol) {
                                                                var dargs = ["dividend", "add", modelData.symbol, String(modelData.amount || 0)]
                                                                if (modelData.date) { dargs.push("--date"); dargs.push(modelData.date) }
                                                                root.runCliCommand(dargs, false)
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                width: parent.width; height: ledgerCol.implicitHeight + Style.space(14); radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                                Column {
                                    id: ledgerCol
                                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                                    spacing: Style.space(5)

                                    Row {
                                        width: parent.width
                                        Text { width: parent.width * 0.52; text: "Trade History Ledger (" + ((root.summaryData.trades || []).length) + ")"; color: "#cdd6f4"; font.pixelSize: Style.font.body; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                                        Row {
                                            width: parent.width * 0.48; spacing: Style.space(4); layoutDirection: Qt.RightToLeft
                                            Rectangle {
                                                width: expCsvTxt.implicitWidth + 10; height: Style.space(20); radius: 4; color: "#313244"
                                                Text { id: expCsvTxt; anchors.centerIn: parent; text: "Export CSV"; color: "#89b4fa"; font.pixelSize: 9; font.bold: true }
                                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                                    onClicked: {
                                                        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                        manualProc.command = ["python3", script, "export", "--format", "csv", "--out", Quickshell.env("HOME") + "/vfex-report.csv"]; manualProc.running = true
                                                    }
                                                }
                                            }
                                            Rectangle {
                                                width: expMdTxt.implicitWidth + 10; height: Style.space(20); radius: 4; color: "#313244"
                                                Text { id: expMdTxt; anchors.centerIn: parent; text: "Export Markdown"; color: "#a6e3a1"; font.pixelSize: 9; font.bold: true }
                                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                                    onClicked: {
                                                        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                        manualProc.command = ["python3", script, "export", "--format", "md", "--out", Quickshell.env("HOME") + "/vfex-report.md"]; manualProc.running = true
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    Text {
                                        width: parent.width; visible: root.toastMessage.length > 0
                                        text: "✓ " + root.toastMessage; color: "#a6e3a1"; font.pixelSize: 9; elide: Text.ElideRight
                                    }
                                    Text { visible: (root.summaryData.trades || []).length === 0; text: "No trades recorded yet."; color: "#6c7086"; font.pixelSize: Style.font.small || Style.font.body }

                                    Repeater {
                                        model: (root.summaryData.trades || []).slice(0, 12)
                                        delegate: Rectangle {
                                            width: ledgerCol.width; height: trRowInner.implicitHeight + 6; radius: 4; color: "#11111b"
                                            Row {
                                                id: trRowInner; anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 5; rightMargin: 5 }
                                                Text { width: parent.width * 0.20; text: modelData.date; color: "#6c7086"; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                                                Rectangle {
                                                    width: trActTxt.implicitWidth + 8; height: trActTxt.implicitHeight + 2; radius: 3; anchors.verticalCenter: parent.verticalCenter
                                                    color: modelData.action === "SELL" ? "#3d2229" : "#243b2c"
                                                    Text { id: trActTxt; anchors.centerIn: parent; text: modelData.action; color: modelData.action === "SELL" ? "#f38ba8" : "#a6e3a1"; font.pixelSize: 8; font.bold: true }
                                                }
                                                Item { width: 4; height: 1 }
                                                Text { width: parent.width * 0.14; text: modelData.symbol; color: "#cdd6f4"; font.pixelSize: 9; font.bold: true; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight }
                                                Text { width: parent.width * 0.28; text: Number(modelData.shares) + "×" + root.fmtPrice(modelData.price, modelData.currency); color: "#a6adc8"; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                                                Text { width: parent.width * 0.20; horizontalAlignment: Text.AlignRight; text: root.fmtShortMoney(Number(modelData.shares || 0) * Number(modelData.price || 0), modelData.currency) + (modelData.contract_note ? (" (+" + root.fmtShortMoney(modelData.contract_note.total_charges, modelData.currency) + ")") : ""); color: modelData.contract_note ? "#89dceb" : "#cdd6f4"; font.pixelSize: 9; font.bold: true; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideLeft }
                                                Text {
                                                    width: Math.max(14, parent.width * 0.08 - 4); horizontalAlignment: Text.AlignRight; text: "×"; color: "#f38ba8"; font.pixelSize: Style.font.body; font.bold: true
                                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                                        onClicked: {
                                                            var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                            manualProc.command = ["python3", script, "trade", "delete", String(modelData.index)]; manualProc.running = true
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // Dividends Card with inline Record Dividend form
                            Rectangle {
                                width: parent.width; height: divHistCol.implicitHeight + Style.space(12); radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                                Column {
                                    id: divHistCol
                                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                                    spacing: Style.space(4)
                                    Row {
                                        width: parent.width
                                        Text { width: parent.width - addDivTog.width - 6; anchors.verticalCenter: parent.verticalCenter; text: "Dividends History (" + (root.summaryData.dividends || []).length + ")"; color: "#94e2d5"; font.pixelSize: Style.font.small || Style.font.body; font.bold: true }
                                        Rectangle {
                                            id: addDivTog; anchors.verticalCenter: parent.verticalCenter
                                            width: addDivLbl.implicitWidth + 12; height: Style.space(20); radius: 4
                                            color: root.divAddOpen ? "#94e2d5" : "#1b2e33"; border.color: "#94e2d5"; border.width: 1
                                            Text { id: addDivLbl; anchors.centerIn: parent; text: root.divAddOpen ? "Close" : "+ Record Dividend"; color: root.divAddOpen ? "#1e1e2e" : "#94e2d5"; font.pixelSize: 9; font.bold: true }
                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.divAddOpen = !root.divAddOpen }
                                        }
                                    }
                                    Rectangle {
                                        width: divHistCol.width; visible: root.divAddOpen
                                        height: divFormRow.implicitHeight + Style.space(10); radius: 6; color: "#11111b"; border.color: "#94e2d5"; border.width: 1
                                        Row {
                                            id: divFormRow
                                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: Style.space(6) }
                                            spacing: Style.space(4)
                                            Rectangle {
                                                width: parent.width * 0.24; height: Style.space(24); radius: 4; color: "#313244"; border.color: "#45475a"; border.width: 1
                                                TextInput {
                                                    id: dvSymIn; anchors.fill: parent; anchors.margins: 4; color: "#cdd6f4"; font.pixelSize: Style.font.small || Style.font.body
                                                    text: root.divAddSym; onTextChanged: if (root.divAddSym !== text) root.divAddSym = text
                                                    Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Symbol"; color: "#6c7086"; font: dvSymIn.font; visible: !dvSymIn.text && !dvSymIn.activeFocus }
                                                }
                                            }
                                            Rectangle {
                                                width: parent.width * 0.24; height: Style.space(24); radius: 4; color: "#313244"; border.color: "#45475a"; border.width: 1
                                                TextInput {
                                                    id: dvAmtIn; anchors.fill: parent; anchors.margins: 4; color: "#cdd6f4"; font.pixelSize: Style.font.small || Style.font.body
                                                    text: root.divAddAmt; onTextChanged: if (root.divAddAmt !== text) root.divAddAmt = text
                                                    Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Amount $"; color: "#6c7086"; font: dvAmtIn.font; visible: !dvAmtIn.text && !dvAmtIn.activeFocus }
                                                }
                                            }
                                            Rectangle {
                                                width: parent.width * 0.26; height: Style.space(24); radius: 4; color: "#313244"; border.color: "#45475a"; border.width: 1
                                                TextInput {
                                                    id: dvDtIn; anchors.fill: parent; anchors.margins: 4; color: "#cdd6f4"; font.pixelSize: Style.font.small || Style.font.body
                                                    text: root.divAddDate; onTextChanged: if (root.divAddDate !== text) root.divAddDate = text
                                                    Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Date (Optional)"; color: "#6c7086"; font: dvDtIn.font; visible: !dvDtIn.text && !dvDtIn.activeFocus }
                                                }
                                            }
                                            Rectangle {
                                                width: parent.width * 0.26 - Style.space(12); height: Style.space(24); radius: 4; color: "#94e2d5"
                                                Text { anchors.centerIn: parent; text: "Save"; color: "#1e1e2e"; font.pixelSize: 10; font.bold: true }
                                                MouseArea {
                                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                                    onClicked: {
                                                        var sy = root.divAddSym.trim().toUpperCase()
                                                        var am = root.divAddAmt.replace(/^\s*\$?/, "").replace(/,/g, "").trim()
                                                        var dt = root.divAddDate.trim()
                                                        if (sy && am) {
                                                            var args = ["dividend", "add", sy, am]
                                                            if (dt) { args.push("--date"); args.push(dt) }
                                                            root.runCliCommand(args, false)
                                                            root.divAddSym = ""; root.divAddAmt = ""; root.divAddDate = ""; root.divAddOpen = false
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    Text { visible: (root.summaryData.dividends || []).length === 0 && !root.divAddOpen; text: "No dividends recorded yet."; color: "#6c7086"; font.pixelSize: 9 }
                                    Repeater {
                                        model: (root.summaryData.dividends || []).slice(0, 6)
                                        delegate: Row {
                                            width: divHistCol.width
                                            Text { width: divHistCol.width * 0.30; text: modelData.date || "--"; color: "#6c7086"; font.pixelSize: 9 }
                                            Text { width: divHistCol.width * 0.35; text: modelData.symbol; color: "#cdd6f4"; font.pixelSize: 9; font.bold: true }
                                            Text { width: divHistCol.width * 0.35; horizontalAlignment: Text.AlignRight; text: "+$" + Number(modelData.amount || 0).toFixed(2); color: "#a6e3a1"; font.pixelSize: 9; font.bold: true }
                                        }
                                    }
                                }
                            }
                        }

                        // RIGHT COLUMN (42%): Trailing Stops & Alerts Manager + Investment Thesis Notes
                        Column {
                            width: root.wideLayout ? (ledgerTabCol.width - Style.space(8)) * 0.42 : ledgerTabCol.width
                            spacing: Style.space(8)

                            Rectangle {
                                width: parent.width; height: protCol.implicitHeight + Style.space(12); radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                                Column {
                                    id: protCol
                                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                                    spacing: Style.space(4)
                                    Text { text: "Stops & Alerts (" + ((root.summaryData.trailing_stops || []).length + (root.summaryData.active_alerts || []).length) + ")"; color: "#f9e2af"; font.pixelSize: Style.font.small || Style.font.body; font.bold: true }
                                    Text { visible: (root.summaryData.trailing_stops || []).length === 0 && (root.summaryData.active_alerts || []).length === 0; text: "No active stops or price alerts."; color: "#6c7086"; font.pixelSize: 9 }
                                    Repeater {
                                        model: root.summaryData.trailing_stops || []
                                        delegate: Row {
                                            width: protCol.width
                                            Text { width: protCol.width * 0.85; text: "🛡 " + modelData.symbol + " -" + Number(modelData.trail_pct || 0).toFixed(1) + "% (Peak " + Number(modelData.peak_price || 0).toFixed(4) + ")"; color: "#f9e2af"; font.pixelSize: 9; elide: Text.ElideRight }
                                            Text { width: protCol.width * 0.15; horizontalAlignment: Text.AlignRight; text: "×"; color: "#f38ba8"; font.pixelSize: Style.font.body; font.bold: true
                                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                                    onClicked: {
                                                        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                        manualProc.command = ["python3", script, "stop", "remove", modelData.symbol]; manualProc.running = true
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    Repeater {
                                        model: root.summaryData.active_alerts || []
                                        delegate: Row {
                                            width: protCol.width
                                            Text { width: protCol.width * 0.85; text: "🔔 " + modelData.text; color: "#a6adc8"; font.pixelSize: 9; elide: Text.ElideRight }
                                            Text { width: protCol.width * 0.15; horizontalAlignment: Text.AlignRight; text: "×"; color: "#f38ba8"; font.pixelSize: Style.font.body; font.bold: true
                                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                                    onClicked: {
                                                        var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                        manualProc.command = ["python3", script, "alert", "remove", String(modelData.index)]; manualProc.running = true
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // Investment Thesis Notes Card
                            Rectangle {
                                width: parent.width; height: notesCol.implicitHeight + Style.space(14); radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                                Column {
                                    id: notesCol
                                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                                    spacing: Style.space(5)
                                    Text { text: "Investment Thesis Notes"; color: "#cdd6f4"; font.pixelSize: Style.font.small || Style.font.body; font.bold: true }
                                    Row {
                                        width: parent.width; spacing: Style.space(4)
                                        Rectangle {
                                            width: parent.width * 0.25; height: Style.space(24); radius: 4; color: "#313244"; border.color: noteSymInput.activeFocus ? "#89b4fa" : "#45475a"; border.width: 1
                                            TextInput {
                                                id: noteSymInput; anchors.fill: parent; anchors.margins: Style.space(4); color: "#cdd6f4"; font.pixelSize: Style.font.small || Style.font.body; verticalAlignment: TextInput.AlignVCenter; clip: true
                                                Component.onCompleted: text = root.noteSymText
                                                onTextChanged: if (root.noteSymText !== text) root.noteSymText = text
                                                Connections { target: root; function onNoteSymTextChanged() { if (noteSymInput.text !== root.noteSymText) noteSymInput.text = root.noteSymText } }
                                                Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Symbol"; color: "#6c7086"; font: noteSymInput.font; visible: !noteSymInput.text && !noteSymInput.activeFocus }
                                            }
                                        }
                                        Rectangle {
                                            width: parent.width * 0.55 - Style.space(8); height: Style.space(24); radius: 4; color: "#313244"; border.color: noteBodyInput.activeFocus ? "#89b4fa" : "#45475a"; border.width: 1
                                            TextInput {
                                                id: noteBodyInput; anchors.fill: parent; anchors.margins: Style.space(4); color: "#cdd6f4"; font.pixelSize: Style.font.small || Style.font.body; verticalAlignment: TextInput.AlignVCenter; clip: true
                                                Component.onCompleted: text = root.noteBodyText
                                                onTextChanged: if (root.noteBodyText !== text) root.noteBodyText = text
                                                Connections { target: root; function onNoteBodyTextChanged() { if (noteBodyInput.text !== root.noteBodyText) noteBodyInput.text = root.noteBodyText } }
                                                Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Thesis..."; color: "#6c7086"; font: noteBodyInput.font; visible: !noteBodyInput.text && !noteBodyInput.activeFocus }
                                            }
                                        }
                                        Rectangle {
                                            width: parent.width * 0.20; height: Style.space(24); radius: 4; color: "#a6e3a1"
                                            Text { anchors.centerIn: parent; text: "Save"; color: "#1e1e2e"; font.pixelSize: 9; font.bold: true }
                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                                onClicked: {
                                                    var sy = root.noteSymText.trim().toUpperCase(); if (!sy) return
                                                    var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                    manualProc.command = ["python3", script, "note", "set", sy, root.noteBodyText.trim()]; manualProc.running = true
                                                }
                                            }
                                        }
                                    }
                                    Repeater {
                                        model: Object.keys(root.summaryData.notes || ({}))
                                        delegate: Rectangle {
                                            width: notesCol.width; height: noteCardRow.implicitHeight + 6; radius: 4; color: "#11111b"
                                            Row {
                                                id: noteCardRow; anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 4 }
                                                Text {
                                                    width: parent.width * 0.88
                                                    text: modelData + ": " + ((root.summaryData.notes || ({}))[modelData] || "")
                                                    color: "#a6adc8"; font.pixelSize: 9; wrapMode: Text.WordWrap
                                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.activeTab = "overview"; root.chartSymbol = modelData } }
                                                }
                                                Text {
                                                    width: parent.width * 0.12; horizontalAlignment: Text.AlignRight; text: "×"; color: "#f38ba8"; font.pixelSize: Style.font.body; font.bold: true
                                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running
                                                        onClicked: {
                                                            var script = Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
                                                            manualProc.command = ["python3", script, "note", "clear", modelData]; manualProc.running = true
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

                // === TAB 5: SELF-LEARNING $100 PAPER-TRADING AGENT ===
                Column {
                    id: agentTabCol
                    visible: root.activeTab === "agent"
                    width: parent.width
                    spacing: Style.space(8)
                    property var pa: root.summaryData.paper_agent || ({})
                    property var paWeights: (pa.weights || ({}))
                    property var paBrain: (pa.brain || ({}))

                    // 1. Agent Hero KPIs & Controls Card
                    Rectangle {
                        width: parent.width
                        height: agHeroCol.implicitHeight + Style.space(16)
                        radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1

                        Column {
                            id: agHeroCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                            spacing: Style.space(6)

                            Row {
                                width: parent.width
                                spacing: Style.space(6)

                                Column {
                                    width: parent.width - agCtrlsRow.width - Style.space(6)
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 2
                                    Row {
                                        spacing: Style.space(6)
                                        Text {
                                            text: "🤖 $100 Self-Learning Paper Agent"
                                            color: "#cba6f7"
                                            font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                            font.pixelSize: Style.font.body
                                            font.bold: true
                                        }
                                        Rectangle {
                                            width: agStTxt.implicitWidth + 10; height: agStTxt.implicitHeight + 3; radius: 4
                                            color: agentTabCol.pa.enabled !== false ? "#1f3a27" : "#3d2229"
                                            anchors.verticalCenter: parent.verticalCenter
                                            Text {
                                                id: agStTxt; anchors.centerIn: parent
                                                text: agentTabCol.pa.enabled !== false ? "● AUTONOMOUS" : "⏸ PAUSED"
                                                color: agentTabCol.pa.enabled !== false ? "#a6e3a1" : "#f38ba8"
                                                font.pixelSize: 8; font.bold: true
                                            }
                                        }
                                        Rectangle {
                                            property var rg: (agentTabCol.pa.regime || ({}))
                                            property string rlbl: String(rg.label || "Neutral")
                                            width: rgTxt.implicitWidth + 10; height: rgTxt.implicitHeight + 3; radius: 4
                                            color: rlbl === "Risk-On" ? "#1f3a27" : (rlbl === "Risk-Off" ? "#3d2229" : "#1e2e4a")
                                            anchors.verticalCenter: parent.verticalCenter
                                            Text {
                                                id: rgTxt; anchors.centerIn: parent
                                                text: parent.rlbl + " • " + Number(parent.rg.cash_floor_pct || 25).toFixed(0) + "% cash"
                                                color: parent.rlbl === "Risk-On" ? "#a6e3a1" : (parent.rlbl === "Risk-Off" ? "#f38ba8" : "#89b4fa")
                                                font.pixelSize: 8; font.bold: true
                                            }
                                        }
                                    }
                                    Text {
                                        text: "All-Market (VFEX USD $80 + ZSE ZWG $20 @ " + Number(agentTabCol.pa.zwg_rate || 26.5).toFixed(1) + ") • Minimum holds (3-Day Swing / 14-Day Core) • Contract note fees"
                                        color: "#6c7086"; font.pixelSize: 9; elide: Text.ElideRight; width: parent.width
                                    }
                                }

                                Row {
                                    id: agCtrlsRow
                                    spacing: 4
                                    anchors.verticalCenter: parent.verticalCenter
                                    Rectangle {
                                        width: stpLbl.implicitWidth + 10; height: Style.space(22); radius: 4; color: "#243b2c"; border.color: "#a6e3a1"; border.width: 1
                                        Text { id: stpLbl; anchors.centerIn: parent; text: manualProc.running ? "…" : "⚡ Step"; color: "#a6e3a1"; font.pixelSize: 9; font.bold: true }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running; onClicked: root.runAgentCli(["step"]) }
                                    }
                                    Rectangle {
                                        width: trnLbl.implicitWidth + 10; height: Style.space(22); radius: 4; color: "#272138"; border.color: "#cba6f7"; border.width: 1
                                        Text { id: trnLbl; anchors.centerIn: parent; text: "☸ Train"; color: "#cba6f7"; font.pixelSize: 9; font.bold: true }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running; onClicked: root.runAgentCli(["train", "--days", "180"]) }
                                    }
                                    Rectangle {
                                        width: rplLbl.implicitWidth + 10; height: Style.space(22); radius: 4; color: "#1e2e4a"; border.color: "#89b4fa"; border.width: 1
                                        Text { id: rplLbl; anchors.centerIn: parent; text: "▶ Replay"; color: "#89b4fa"; font.pixelSize: 9; font.bold: true }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running; onClicked: root.runAgentCli(["replay", "--days", "30"]) }
                                    }
                                    Rectangle {
                                        width: prsLbl.implicitWidth + 10; height: Style.space(22); radius: 4; color: "#313244"
                                        Text { id: prsLbl; anchors.centerIn: parent; text: agentTabCol.pa.enabled !== false ? "⏸ Pause" : "▶ Resume"; color: "#f9e2af"; font.pixelSize: 9; font.bold: true }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running; onClicked: root.runAgentCli([agentTabCol.pa.enabled !== false ? "pause" : "resume"]) }
                                    }
                                    Rectangle {
                                        width: rstLbl.implicitWidth + 10; height: Style.space(22); radius: 4; color: "#3d2229"
                                        Text { id: rstLbl; anchors.centerIn: parent; text: "↺ $100"; color: "#f38ba8"; font.pixelSize: 9; font.bold: true }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !manualProc.running; onClicked: { root.selectedContractId = ""; root.runAgentCli(["reset", "--capital", "100"]) } }
                                    }
                                }
                            }

                            // 5 KPI Metrics Row
                            Grid {
                                width: parent.width
                                columns: root.wideLayout ? 5 : 2
                                columnSpacing: Style.space(6)
                                rowSpacing: Style.space(6)
                                Repeater {
                                    model: {
                                        var p = agentTabCol.pa
                                        var eq = Number(p.equity_usd || 100)
                                        var pct = Number(p.net_pnl_pct || 0)
                                        var pnl = Number(p.net_pnl_usd || 0)
                                        var psg = pnl >= 0 ? "+" : "-"
                                        return [
                                            { k: "Net Equity", v: "$" + eq.toFixed(2), sub: "Start $" + Number(p.starting_capital_usd || 100).toFixed(0), col: "#cdd6f4" },
                                            { k: "Net Return", v: psg + "$" + Math.abs(pnl).toFixed(2) + " (" + (pct >= 0 ? "+" : "") + pct.toFixed(2) + "%)", sub: (p.positions || []).length + " open positions", col: pnl >= 0 ? "#a6e3a1" : "#f38ba8" },
                                            { k: "Cash Pools", v: "$" + Number(p.cash_usd || 0).toFixed(2) + " USD", sub: "ZiG " + Number(p.cash_zwg || 0).toFixed(2) + " ZSE", col: "#89dceb" },
                                            { k: "Total Fees Paid", v: "$" + Number(p.total_fees_usd || 0).toFixed(2), sub: (p.trades || []).length + " contract fills", col: "#f9e2af" },
                                            { k: "Mahoraga Brain", v: Number(p.win_rate_pct || 0).toFixed(0) + "% Win Rate", sub: (p.wins || 0) + " Wins / " + (p.losses || 0) + " Losses • " + Number((agentTabCol.paBrain || ({})).adaptations_spun || 0) + " adaptations", col: "#cba6f7" }
                                        ]
                                    }
                                    delegate: Rectangle {
                                        width: root.wideLayout ? (agHeroCol.width - Style.space(24)) / 5 : (agHeroCol.width - Style.space(6)) / 2
                                        height: Style.space(42); radius: 6; color: "#11111b"; border.color: "#242436"; border.width: 1
                                        Column {
                                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: Style.space(6) }
                                            spacing: 1
                                            Text { text: modelData.k; color: "#6c7086"; font.pixelSize: 9; elide: Text.ElideRight; width: parent.width }
                                            Text { text: modelData.v; color: modelData.col; font.pixelSize: Style.font.small || Style.font.body; font.bold: true; elide: Text.ElideRight; width: parent.width }
                                            Text { text: modelData.sub; color: "#a6adc8"; font.pixelSize: 8; elide: Text.ElideRight; width: parent.width }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // 2. Agent Equity Curve Over Time vs $100 Benchmark Canvas
                    Rectangle {
                        width: parent.width
                        height: agChartCol.implicitHeight + Style.space(14)
                        radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1

                        Column {
                            id: agChartCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(8) }
                            spacing: Style.space(4)
                            property var eqPts: agentTabCol.pa.equity_history || []

                            Row {
                                width: parent.width
                                Text {
                                    width: parent.width * 0.50
                                    text: "Performance Over Time (Versus $100 Benchmark)"
                                    color: "#89b4fa"; font.pixelSize: Style.font.body; font.bold: true
                                }
                                Text {
                                    width: parent.width * 0.50; horizontalAlignment: Text.AlignRight
                                    text: {
                                        var pts = agChartCol.eqPts
                                        if (root.hoveredAgentEqIdx >= 0 && root.hoveredAgentEqIdx < pts.length) {
                                            var h = pts[root.hoveredAgentEqIdx]
                                            return h.date + " • Equity $" + Number(h.equity_usd).toFixed(2) + " • Invested $" + Number(h.invested_usd).toFixed(2) + " • Fees $" + Number(h.fees_paid_usd).toFixed(2)
                                        }
                                        return pts.length > 0 ? ("Latest " + pts[pts.length - 1].date + ": $" + Number(pts[pts.length - 1].equity_usd).toFixed(2)) : "Run Step or Replay"
                                    }
                                    color: "#a6adc8"; font.pixelSize: 9; elide: Text.ElideLeft
                                }
                            }

                            Canvas {
                                id: agentEquityCanvas
                                width: parent.width
                                height: root.fullPageMode ? Style.space(165) : Style.space(104)
                                onWidthChanged: requestPaint()
                                Component.onCompleted: { root.agentEquityCanvasRef = agentEquityCanvas; requestPaint() }
                                onPaint: {
                                    var ctx = getContext("2d")
                                    if (width <= 0 || height <= 0) return
                                    ctx.clearRect(0, 0, width, height)
                                    var pts = agChartCol.eqPts
                                    var startCap = Number(agentTabCol.pa.starting_capital_usd || 100)
                                    if (!pts || pts.length === 0) return
                                    var plotPts = pts.length === 1 ? [pts[0], pts[0]] : pts
                                    var mn = startCap, mx = startCap
                                    for (var i = 0; i < plotPts.length; i++) {
                                        var v = Number(plotPts[i].equity_usd || startCap)
                                        if (v < mn) mn = v
                                        if (v > mx) mx = v
                                    }
                                    var pad = Math.max(1.5, (mx - mn) * 0.25)
                                    mn = Math.max(0, mn - pad); mx = mx + pad
                                    var span = Math.max(1, mx - mn)
                                    var pL = 42, pR = 10, pT = 8, pB = 14
                                    var pW = Math.max(10, width - pL - pR), pH = Math.max(10, height - pT - pB)
                                    function xAt(idx) { return pL + (idx / Math.max(1, plotPts.length - 1)) * pW }
                                    function yAt(val) { return pT + pH - ((val - mn) / span) * pH }

                                    ctx.font = "9px sans-serif"; ctx.textBaseline = "middle"
                                    for (var g = 0; g <= 2; g++) {
                                        var gv = mn + span * (1 - g * 0.5)
                                        var gy = yAt(gv)
                                        ctx.strokeStyle = "#242436"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(pL, gy); ctx.lineTo(width - pR, gy); ctx.stroke()
                                        ctx.fillStyle = "#6c7086"; ctx.fillText("$" + gv.toFixed(1), 0, gy)
                                    }

                                    // $100 dashed baseline
                                    var baseY = yAt(startCap)
                                    ctx.save(); ctx.strokeStyle = "#6c7086"; ctx.lineWidth = 1.2; ctx.setLineDash([4, 3])
                                    ctx.beginPath(); ctx.moveTo(pL, baseY); ctx.lineTo(width - pR, baseY); ctx.stroke(); ctx.restore()

                                    var lastEq = Number(plotPts[plotPts.length - 1].equity_usd || startCap)
                                    var col = lastEq >= startCap ? "#a6e3a1" : "#f38ba8"
                                    var grad = ctx.createLinearGradient(0, pT, 0, pT + pH)
                                    grad.addColorStop(0, lastEq >= startCap ? "rgba(166, 227, 161, 0.28)" : "rgba(243, 139, 168, 0.28)")
                                    grad.addColorStop(1, "rgba(0,0,0,0)")
                                    ctx.fillStyle = grad; ctx.beginPath(); ctx.moveTo(xAt(0), pT + pH)
                                    for (var j = 0; j < plotPts.length; j++) ctx.lineTo(xAt(j), yAt(Number(plotPts[j].equity_usd || startCap)))
                                    ctx.lineTo(xAt(plotPts.length - 1), pT + pH); ctx.closePath(); ctx.fill()

                                    ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.beginPath()
                                    for (var k = 0; k < plotPts.length; k++) {
                                        var xk = xAt(k), yk = yAt(Number(plotPts[k].equity_usd || startCap))
                                        if (k === 0) ctx.moveTo(xk, yk); else ctx.lineTo(xk, yk)
                                    }
                                    ctx.stroke()

                                    for (var d = 0; d < plotPts.length; d++) {
                                        var isH = (pts.length > 1 && d === root.hoveredAgentEqIdx)
                                        ctx.fillStyle = isH ? "#f9e2af" : col
                                        ctx.beginPath(); ctx.arc(xAt(d), yAt(Number(plotPts[d].equity_usd || startCap)), isH ? 4 : 2.5, 0, Math.PI * 2); ctx.fill()
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent; hoverEnabled: true
                                    onPositionChanged: function(mouse) {
                                        var pts = agChartCol.eqPts
                                        if (!pts || pts.length <= 1) { root.hoveredAgentEqIdx = pts.length - 1; return }
                                        var rel = (mouse.x - 42) / Math.max(10, width - 52)
                                        if (rel < 0 || rel > 1) { root.hoveredAgentEqIdx = -1; return }
                                        root.hoveredAgentEqIdx = Math.max(0, Math.min(pts.length - 1, Math.round(rel * (pts.length - 1))))
                                    }
                                    onExited: root.hoveredAgentEqIdx = -1
                                }
                            }
                        }
                    }

                    // 3. Two-Column Details: Positions + Brain Left | Lessons + Itemized Contract Notes Right
                    Grid {
                        width: parent.width
                        columns: root.wideLayout ? 2 : 1
                        columnSpacing: Style.space(8)
                        rowSpacing: Style.space(8)

                        // LEFT COLUMN: Open Positions + Adaptive Weights
                        Column {
                            width: root.wideLayout ? (agentTabCol.width - Style.space(8)) / 2 : agentTabCol.width
                            spacing: Style.space(8)

                            Rectangle {
                                width: parent.width
                                height: agPosCol.implicitHeight + Style.space(14)
                                radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                                Column {
                                    id: agPosCol
                                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                                    spacing: Style.space(5)
                                    Text { text: "Open Paper Positions (" + (agentTabCol.pa.positions || []).length + ")"; color: "#a6e3a1"; font.pixelSize: Style.font.body; font.bold: true }
                                    Text {
                                        visible: (agentTabCol.pa.positions || []).length === 0
                                        text: "No open paper positions right now — cash is waiting cleanly for high-conviction net-of-fee setups."
                                        color: "#6c7086"; font.pixelSize: 10; wrapMode: Text.WordWrap; width: parent.width
                                    }
                                    Repeater {
                                        model: agentTabCol.pa.positions || []
                                        delegate: Rectangle {
                                            width: agPosCol.width; height: agPosRowCol.implicitHeight + 8; radius: 6; color: "#11111b"; border.color: "#242436"; border.width: 1
                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.chartSymbol = modelData.symbol; root.activeTab = "overview" } }
                                            Column {
                                                id: agPosRowCol
                                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 5 }
                                                spacing: 2
                                                Row {
                                                    width: parent.width; spacing: 4
                                                    Rectangle {
                                                        width: posHzTxt.implicitWidth + 6; height: posHzTxt.implicitHeight + 2; radius: 3
                                                        color: modelData.horizon === "CORE" ? "#1f3a27" : "#272138"
                                                        Text { id: posHzTxt; anchors.centerIn: parent; text: modelData.horizon; color: modelData.horizon === "CORE" ? "#a6e3a1" : "#cba6f7"; font.pixelSize: 8; font.bold: true }
                                                    }
                                                    Text { text: modelData.symbol; color: modelData.currency === "ZWG" ? "#f9e2af" : "#cdd6f4"; font.pixelSize: Style.font.body; font.bold: true }
                                                    Text { text: modelData.shares + " shares @ " + root.fmtPrice(modelData.entry_price, modelData.currency) + " → " + root.fmtPrice(modelData.current_price, modelData.currency); color: "#a6adc8"; font.pixelSize: 9 }
                                                }
                                                Row {
                                                    width: parent.width
                                                    Text {
                                                        width: parent.width * 0.58
                                                        text: "Held " + modelData.hold_days + " of " + modelData.min_hold_days + " days minimum • " + (modelData.playbook || "Signal") + (modelData.win_prob_pct ? (" (" + Number(modelData.win_prob_pct).toFixed(0) + "% probability)") : "")
                                                        color: "#89b4fa"; font.pixelSize: 9; elide: Text.ElideRight
                                                    }
                                                    Text {
                                                        width: parent.width * 0.42; horizontalAlignment: Text.AlignRight
                                                        text: "Net " + (Number(modelData.net_pnl_usd) >= 0 ? "+" : "-") + "$" + Math.abs(Number(modelData.net_pnl_usd)).toFixed(2) + " (" + (Number(modelData.net_pnl_pct) >= 0 ? "+" : "") + Number(modelData.net_pnl_pct).toFixed(1) + "%)"
                                                        color: Number(modelData.net_pnl_usd) >= 0 ? "#a6e3a1" : "#f38ba8"
                                                        font.pixelSize: 9; font.bold: true
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // Evolved Next-Buy Radar, Pending GTD Limits & Shielded Traps
                            Rectangle {
                                width: parent.width
                                visible: (agentTabCol.pa.radar || []).length > 0 || (agentTabCol.pa.shielded || []).length > 0 || (agentTabCol.pa.pending_orders || []).length > 0
                                height: agRadCol.implicitHeight + Style.space(14)
                                radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                                Column {
                                    id: agRadCol
                                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                                    spacing: Style.space(4)
                                    Column {
                                        width: parent.width
                                        visible: (agentTabCol.pa.pending_orders || []).length > 0
                                        spacing: 3
                                        Text { text: "⧖ Resting Smart Limit Orders (" + (agentTabCol.pa.pending_orders || []).length + ")"; color: "#f9e2af"; font.pixelSize: 9; font.bold: true }
                                        Repeater {
                                            model: agentTabCol.pa.pending_orders || []
                                            delegate: Rectangle {
                                                width: agRadCol.width; height: pndTxt.implicitHeight + 6; radius: 4; color: "#1e1a12"; border.color: "#f9e2af"; border.width: 1
                                                Text {
                                                    id: pndTxt
                                                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 5 }
                                                    text: modelData.symbol + " • Limit Price " + root.fmtPrice(modelData.limit_price, modelData.currency) + " (" + (modelData.playbook || "") + ") • Expires " + (modelData.expires_at || "")
                                                    color: "#f9e2af"; font.pixelSize: 8; elide: Text.ElideRight
                                                }
                                            }
                                        }
                                    }
                                    Row {
                                        width: parent.width
                                        Text { width: parent.width * 0.65; text: "◎ Mahoraga Next-Buy Radar"; color: "#89dceb"; font.pixelSize: Style.font.body; font.bold: true }
                                        Text { width: parent.width * 0.35; horizontalAlignment: Text.AlignRight; text: (agentTabCol.pa.radar || []).length + " live setups"; color: "#6c7086"; font.pixelSize: 9 }
                                    }
                                    Repeater {
                                        model: (agentTabCol.pa.radar || []).slice(0, 4)
                                        delegate: Rectangle {
                                            width: agRadCol.width; height: radRowCol.implicitHeight + 6; radius: 4; color: "#11111b"; border.color: "#242436"; border.width: 1
                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.chartSymbol = modelData.symbol; root.activeTab = "overview" } }
                                            Column {
                                                id: radRowCol
                                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 4 }
                                                spacing: 1
                                                Row {
                                                    width: parent.width; spacing: 4
                                                    Text { text: modelData.symbol; color: modelData.currency === "ZWG" ? "#f9e2af" : "#cdd6f4"; font.pixelSize: 10; font.bold: true }
                                                    Text { text: (modelData.playbook || "") + (modelData.stage_limit ? " [Limit]" : ""); color: modelData.stage_limit ? "#f9e2af" : "#89b4fa"; font.pixelSize: 8; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                                                    Text {
                                                        width: Math.max(40, parent.width - 150)
                                                        horizontalAlignment: Text.AlignRight
                                                        text: Number(modelData.win_prob_pct || 0).toFixed(0) + "% probability (" + (Number(modelData.ucb_edge_pct || modelData.expected_net_pct || 0) >= 0 ? "+" : "") + Number(modelData.ucb_edge_pct || modelData.expected_net_pct || 0).toFixed(1) + "% edge)"
                                                        color: Number(modelData.ucb_edge_pct || modelData.expected_net_pct || 0) >= 0 ? "#a6e3a1" : "#f9e2af"
                                                        font.pixelSize: 8; font.bold: true; elide: Text.ElideLeft
                                                    }
                                                }
                                                Text {
                                                    text: "Score " + modelData.score + " • " + root.fmtReasonText((modelData.reasons || []).slice(0, 2).join(" • "))
                                                    color: "#6c7086"; font.pixelSize: 8; elide: Text.ElideRight; width: parent.width
                                                }
                                            }
                                        }
                                    }
                                    Flow {
                                        width: parent.width; spacing: 4
                                        visible: (agentTabCol.pa.shielded || []).length > 0
                                        Text { text: "Shielded:"; color: "#f38ba8"; font.pixelSize: 8; font.bold: true }
                                        Repeater {
                                            model: (agentTabCol.pa.shielded || []).slice(0, 4)
                                            delegate: Rectangle {
                                                width: shldTxt.implicitWidth + 8; height: Style.space(15); radius: 3; color: "#2b1d24"; border.color: "#f38ba8"; border.width: 1
                                                Text { id: shldTxt; anchors.centerIn: parent; text: "🛡 " + modelData.symbol + ": " + modelData.block_reason; color: "#f38ba8"; font.pixelSize: 8 }
                                            }
                                        }
                                    }
                                }
                            }

                            // Adaptive Brain Weights & Cooldowns
                            Rectangle {
                                width: parent.width
                                height: agBrainCol.implicitHeight + Style.space(14)
                                radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                                Column {
                                    id: agBrainCol
                                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                                    spacing: Style.space(5)
                                    Row {
                                        width: parent.width
                                        Text { width: parent.width * 0.46; text: "☸ Mahoraga Adaptation Brain"; color: "#cba6f7"; font.pixelSize: Style.font.body; font.bold: true; elide: Text.ElideRight }
                                        Text {
                                            width: parent.width * 0.54; horizontalAlignment: Text.AlignRight
                                            text: (agentTabCol.paBrain.adaptations_spun || 0) + " wheel spins • Minimum Score " + (agentTabCol.paWeights.min_entry_score || 22)
                                            color: "#f9e2af"; font.pixelSize: 9; font.bold: true; elide: Text.ElideRight
                                        }
                                    }
                                    Text {
                                        width: parent.width
                                        property var po: (agentTabCol.paBrain.payoffs || ({}))
                                        text: "Shadow Trades: " + (agentTabCol.paBrain.shadows_resolved || 0) + "/" + (agentTabCol.paBrain.shadows_total || 0) + " • Payoff Odds: Win +" + Number(po.avg_win_pct || 8.5).toFixed(1) + "% / Loss -" + Number(po.avg_loss_pct || 5.0).toFixed(1) + "%"
                                        color: "#89dceb"; font.pixelSize: 9; elide: Text.ElideRight
                                    }
                                    // 4 Strategy Playbooks Performance Grid
                                    Grid {
                                        width: parent.width
                                        columns: 2
                                        columnSpacing: 6
                                        rowSpacing: 4
                                        Repeater {
                                            model: agentTabCol.paBrain.playbooks || []
                                            delegate: Rectangle {
                                                width: (agBrainCol.width - 6) / 2
                                                height: pbCol.implicitHeight + 6; radius: 4; color: "#11111b"; border.color: "#242436"; border.width: 1
                                                Column {
                                                    id: pbCol
                                                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 4 }
                                                    spacing: 1
                                                    Row {
                                                        width: parent.width
                                                        Text { width: parent.width * 0.68; text: modelData.name; color: "#cdd6f4"; font.pixelSize: 8; font.bold: true; elide: Text.ElideRight }
                                                        Text { width: parent.width * 0.32; horizontalAlignment: Text.AlignRight; text: Number(modelData.mult || 1.0).toFixed(2) + "×"; color: Number(modelData.mult || 1.0) >= 1.0 ? "#a6e3a1" : "#f38ba8"; font.pixelSize: 8; font.bold: true }
                                                    }
                                                    Text {
                                                        text: (modelData.wins || 0) + " Wins / " + (modelData.losses || 0) + " Losses" + (modelData.avg_net_pct !== null && modelData.avg_net_pct !== undefined ? (" • Average " + (Number(modelData.avg_net_pct) >= 0 ? "+" : "") + Number(modelData.avg_net_pct).toFixed(1) + "%") : " • Untested")
                                                        color: "#a6adc8"; font.pixelSize: 8; elide: Text.ElideRight; width: parent.width
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    // Evolved Regime Immunity Shields
                                    Flow {
                                        width: parent.width; spacing: 4
                                        visible: (agentTabCol.paBrain.immunities || []).length > 0
                                        Text { text: "Immunities:"; color: "#cba6f7"; font.pixelSize: 9; font.bold: true }
                                        Repeater {
                                            model: agentTabCol.paBrain.immunities || []
                                            delegate: Rectangle {
                                                width: immChipTxt.implicitWidth + 10; height: Style.space(16); radius: 3
                                                color: modelData.active ? "#272138" : "#1e1e2e"
                                                border.color: modelData.active ? "#cba6f7" : "#45475a"; border.width: 1
                                                Text {
                                                    id: immChipTxt; anchors.centerIn: parent
                                                    text: (modelData.active ? "🛡 " : "○ ") + modelData.label + " (" + (modelData.loss_count || 0) + ")"
                                                    color: modelData.active ? "#cba6f7" : "#6c7086"; font.pixelSize: 8; font.bold: Boolean(modelData.active)
                                                }
                                            }
                                        }
                                    }
                                    Text {
                                        width: parent.width
                                        property var ep: (agentTabCol.paBrain.exit_policy || ({}))
                                        text: "Exit Policy: Caution Tier " + Number(ep.caution_exit_strictness || 0) + " • Take +" + Number(ep.swing_take_pct || 4.5).toFixed(1) + "% / ZSE +" + Number(ep.zse_take_pct || 6.5).toFixed(1) + "% • Stop " + Number(ep.hard_stop_pct || -8.0).toFixed(1) + "%"
                                        color: "#94e2d5"; font.pixelSize: 8; elide: Text.ElideRight
                                    }
                                    Rectangle {
                                        id: gkBox
                                        property var gk: (agentTabCol.paBrain.grok || ({}))
                                        property var gm: (gk.metrics || ({}))
                                        property string gkSt: String(gk.status || "Accumulating History")
                                        width: parent.width
                                        height: gkCol.implicitHeight + 10
                                        radius: 5
                                        color: "#11111b"
                                        border.color: gkBox.gkSt === "Grokked (Active)" ? "#a6e3a1" : (gkBox.gkSt === "Memorizing (Gated)" ? "#f9e2af" : "#313244")
                                        border.width: 1
                                        Column {
                                            id: gkCol
                                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 6 }
                                            spacing: 2
                                            Row {
                                                width: parent.width
                                                Text { width: parent.width * 0.56; text: "Grokking Generalization Engine"; color: "#cba6f7"; font.pixelSize: 8; font.bold: true; elide: Text.ElideRight }
                                                Text {
                                                    width: parent.width * 0.44; horizontalAlignment: Text.AlignRight
                                                    text: gkBox.gkSt
                                                    color: gkBox.gkSt === "Grokked (Active)" ? "#a6e3a1" : (gkBox.gkSt === "Memorizing (Gated)" ? "#f9e2af" : "#9399b2")
                                                    font.pixelSize: 8; font.bold: true; elide: Text.ElideLeft
                                                }
                                            }
                                            Text {
                                                visible: Number(gkBox.gm.episodes_total || 0) < Number(gkBox.gm.min_episodes || 18)
                                                width: parent.width; elide: Text.ElideRight
                                                text: "Dataset: " + Number(gkBox.gm.episodes_total || 0) + "/" + Number(gkBox.gm.min_episodes || 18) + " chronological episodes needed for 70/30 out-of-sample split"
                                                color: "#a6adc8"; font.pixelSize: 8
                                            }
                                            Text {
                                                visible: Number(gkBox.gm.episodes_total || 0) >= Number(gkBox.gm.min_episodes || 18)
                                                width: parent.width; elide: Text.ElideRight
                                                text: "Train Accuracy: " + Number(gkBox.gm.train_acc_pct || 0).toFixed(1) + "% (" + Number(gkBox.gm.train_count || 0) + ") • Validation Accuracy: " + Number(gkBox.gm.val_acc_pct || 0).toFixed(1) + "% (" + Number(gkBox.gm.val_count || 0) + ")"
                                                color: "#cdd6f4"; font.pixelSize: 8
                                            }
                                            Text {
                                                visible: Number(gkBox.gm.episodes_total || 0) >= Number(gkBox.gm.min_episodes || 18)
                                                width: parent.width; elide: Text.ElideRight
                                                text: "Epoch " + Number(gkBox.gm.best_epoch || 0) + "/" + Number(gkBox.gm.epochs_run || 0) + " • Weight L2 Norm: " + Number(gkBox.gm.weight_l2_norm || 0).toFixed(2) + " • Validation Loss " + Number(gkBox.gm.grok_val_loss || 0).toFixed(3) + " vs Linear " + Number(gkBox.gm.linear_val_loss || 0).toFixed(3)
                                                color: "#89dceb"; font.pixelSize: 8
                                            }
                                        }
                                    }
                                    Repeater {
                                        model: [
                                            { label: "Dip Depth", val: Number(agentTabCol.paWeights.dip_mult || 1.0), col: "#89b4fa" },
                                            { label: "Relative Strength Oversold", val: Number(agentTabCol.paWeights.rsi_mult || 1.0), col: "#a6e3a1" },
                                            { label: "Order-Book Imbalance", val: Number(agentTabCol.paWeights.book_mult || 1.0), col: "#89dceb" },
                                            { label: "News Catalyst", val: Number(agentTabCol.paWeights.news_mult || 1.0), col: "#cba6f7" },
                                            { label: "Daily Turnover", val: Number(agentTabCol.paWeights.volume_mult || 1.0), col: "#94e2d5" },
                                            { label: "Spread Guard", val: Number(agentTabCol.paWeights.wide_spread_penalty || 1.0), col: "#f9e2af" },
                                            { label: "ZSE Fee Hurdle", val: Number(agentTabCol.paWeights.zse_hurdle_mult || 1.0), col: "#f38ba8" }
                                        ]
                                        delegate: Row {
                                            width: agBrainCol.width; spacing: 6
                                            Text { width: agBrainCol.width * 0.34; text: modelData.label; color: "#a6adc8"; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                                            Rectangle {
                                                width: agBrainCol.width * 0.48; height: 6; radius: 3; color: "#313244"; anchors.verticalCenter: parent.verticalCenter
                                                Rectangle { width: Math.min(1, Math.max(0.1, modelData.val / 2.0)) * parent.width; height: parent.height; radius: 3; color: modelData.col }
                                            }
                                            Text { width: agBrainCol.width * 0.18 - 12; horizontalAlignment: Text.AlignRight; text: modelData.val.toFixed(2) + "×"; color: "#cdd6f4"; font.pixelSize: 9; font.bold: true }
                                        }
                                    }
                                    Flow {
                                        width: parent.width; spacing: 4
                                        visible: (agentTabCol.pa.cooldowns || []).length > 0
                                        Text { text: "Loss Cooldowns:"; color: "#f38ba8"; font.pixelSize: 9; font.bold: true }
                                        Repeater {
                                            model: agentTabCol.pa.cooldowns || []
                                            delegate: Rectangle {
                                                width: cdChipTxt.implicitWidth + 10; height: Style.space(16); radius: 3; color: "#3d2229"
                                                Text { id: cdChipTxt; anchors.centerIn: parent; text: modelData.symbol + " (" + modelData.until + ")"; color: "#f38ba8"; font.pixelSize: 8; font.bold: true }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // RIGHT COLUMN: Lessons Learned + Filled Contract Notes
                        Column {
                            width: root.wideLayout ? (agentTabCol.width - Style.space(8)) / 2 : agentTabCol.width
                            spacing: Style.space(8)

                            // Lessons Learned Journal
                            Rectangle {
                                width: parent.width
                                height: agLessCol.implicitHeight + Style.space(14)
                                radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                                Column {
                                    id: agLessCol
                                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                                    spacing: Style.space(5)
                                    Text { text: "Lessons Learned (" + (agentTabCol.pa.lessons || []).length + ")"; color: "#cba6f7"; font.pixelSize: Style.font.body; font.bold: true }
                                    Text {
                                        visible: (agentTabCol.pa.lessons || []).length === 0
                                        text: "Lessons appear automatically once trades close — diagnosing wins, fee drag, and mistakes to adapt rules."
                                        color: "#6c7086"; font.pixelSize: 9; wrapMode: Text.WordWrap; width: parent.width
                                    }
                                    Repeater {
                                        model: (agentTabCol.pa.lessons || []).slice(0, 6)
                                        delegate: Rectangle {
                                            width: agLessCol.width; height: agLsInner.implicitHeight + 8; radius: 5
                                            color: "#11111b"
                                            border.color: modelData.type === "WIN" ? "#243b2c" : (modelData.type === "TRAIN" ? "#1e2e4a" : "#4a242d"); border.width: 1
                                            Column {
                                                id: agLsInner
                                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 5 }
                                                spacing: 2
                                                Row {
                                                    width: parent.width; spacing: 4
                                                    Rectangle {
                                                        id: lsTagRect
                                                        width: lsTag.implicitWidth + 6; height: lsTag.implicitHeight + 2; radius: 3
                                                        color: modelData.type === "WIN" ? "#1f3a27" : (modelData.type === "TRAIN" ? "#1e2e4a" : "#3d2229")
                                                        Text { id: lsTag; anchors.centerIn: parent; text: modelData.type; color: modelData.type === "WIN" ? "#a6e3a1" : (modelData.type === "TRAIN" ? "#89b4fa" : "#f38ba8"); font.pixelSize: 8; font.bold: true }
                                                    }
                                                    Text { text: modelData.date + " • " + modelData.summary; color: "#cdd6f4"; font.pixelSize: 9; font.bold: true; elide: Text.ElideRight; width: Math.max(40, parent.width - lsTagRect.width - 8) }
                                                }
                                                Text { text: "↳ " + (modelData.adjustment || ""); color: "#a6adc8"; font.pixelSize: 8; wrapMode: Text.WordWrap; width: parent.width }
                                            }
                                        }
                                    }
                                }
                            }

                            // Itemized Contract Notes Ledger
                            Rectangle {
                                width: parent.width
                                height: agTrdCol.implicitHeight + Style.space(14)
                                radius: 8; color: "#181825"; border.color: "#313244"; border.width: 1
                                Column {
                                    id: agTrdCol
                                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
                                    spacing: Style.space(5)
                                    Row {
                                        width: parent.width
                                        Text { width: parent.width * 0.65; text: "Paper Fills & Contract Notes (" + (agentTabCol.pa.trades || []).length + ")"; color: "#89dceb"; font.pixelSize: Style.font.body; font.bold: true }
                                        Text { width: parent.width * 0.35; horizontalAlignment: Text.AlignRight; text: "Click row for receipt"; color: "#6c7086"; font.pixelSize: 9 }
                                    }
                                    Text {
                                        visible: (agentTabCol.pa.trades || []).length === 0
                                        text: "No paper fills yet — click ⚡ Step or ▶ Replay above."
                                        color: "#6c7086"; font.pixelSize: 9
                                    }
                                    Repeater {
                                        model: (agentTabCol.pa.trades || []).slice(0, 12)
                                        delegate: Rectangle {
                                            id: trdDelRoot
                                            width: agTrdCol.width
                                            height: trdItemCol.implicitHeight + 8
                                            radius: 5; color: root.selectedContractId === modelData.id ? "#1e1e2e" : "#11111b"
                                            border.color: root.selectedContractId === modelData.id ? "#89b4fa" : "#242436"; border.width: 1
                                            property var cn: modelData.contract_note || ({})
                                            property bool expanded: root.selectedContractId === modelData.id

                                            MouseArea {
                                                anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                onClicked: root.selectedContractId = (root.selectedContractId === modelData.id ? "" : modelData.id)
                                            }

                                            Column {
                                                id: trdItemCol
                                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 5 }
                                                spacing: 3

                                                Row {
                                                    width: parent.width; spacing: 4
                                                    Rectangle {
                                                        id: tdSdBadge
                                                        width: tdSdTxt.implicitWidth + 6; height: tdSdTxt.implicitHeight + 2; radius: 3
                                                        color: modelData.side === "BUY" ? "#1f3a27" : "#3d2229"
                                                        Text { id: tdSdTxt; anchors.centerIn: parent; text: modelData.side; color: modelData.side === "BUY" ? "#a6e3a1" : "#f38ba8"; font.pixelSize: 8; font.bold: true }
                                                    }
                                                    Text { id: tdSymTxt; text: modelData.date.slice(5) + " " + modelData.symbol; color: "#cdd6f4"; font.pixelSize: 9; font.bold: true }
                                                    Text { id: tdPxTxt; text: modelData.shares + " shares @ " + root.fmtPrice(modelData.price, modelData.currency); color: "#a6adc8"; font.pixelSize: 9 }
                                                    Text {
                                                        width: Math.max(40, parent.width - tdSdBadge.width - tdSymTxt.implicitWidth - tdPxTxt.implicitWidth - 14); horizontalAlignment: Text.AlignRight
                                                        text: modelData.realized_net_pnl_usd !== null && modelData.realized_net_pnl_usd !== undefined
                                                            ? ((Number(modelData.realized_net_pnl_usd) >= 0 ? "+" : "-") + "$" + Math.abs(Number(modelData.realized_net_pnl_usd)).toFixed(2) + " net")
                                                            : ("Fee " + Number((modelData.contract_note || ({})).total_fee_pct || 0).toFixed(2) + "%")
                                                        color: modelData.realized_net_pnl_usd !== null && modelData.realized_net_pnl_usd !== undefined
                                                            ? (Number(modelData.realized_net_pnl_usd) >= 0 ? "#a6e3a1" : "#f38ba8")
                                                            : "#f9e2af"
                                                        font.pixelSize: 9; font.bold: true; elide: Text.ElideLeft
                                                    }
                                                }

                                                // Expandable Itemized Morgan & Co / ZSE Contract Note Receipt
                                                Rectangle {
                                                    width: parent.width
                                                    visible: Boolean(trdDelRoot.expanded)
                                                    height: cnBoxCol.implicitHeight + 8
                                                    radius: 4; color: "#181825"; border.color: "#313244"; border.width: 1
                                                    Column {
                                                        id: cnBoxCol
                                                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 4 }
                                                        spacing: 2
                                                        property var c: (modelData.contract_note || ({}))
                                                        Text { text: (cnBoxCol.c.exchange || "VFEX") + " Contract Note (" + (modelData.reasons || []).join(" • ") + ")"; color: "#89b4fa"; font.pixelSize: 8; font.bold: true; elide: Text.ElideRight; width: parent.width }
                                                        Text { text: "Gross Consideration: " + root.fmtShortMoney(cnBoxCol.c.gross, cnBoxCol.c.currency); color: "#cdd6f4"; font.pixelSize: 8 }
                                                        Text { text: "Brokerage (" + Number(cnBoxCol.c.brokerage_pct || 0).toFixed(2) + "%): " + root.fmtShortMoney(cnBoxCol.c.brokerage, cnBoxCol.c.currency) + "  •  VAT (15%): " + root.fmtShortMoney(cnBoxCol.c.vat, cnBoxCol.c.currency); color: "#a6adc8"; font.pixelSize: 8 }
                                                        Text { text: "Platform (" + Number(cnBoxCol.c.platform_levy_pct || 0).toFixed(2) + "%): " + root.fmtShortMoney(cnBoxCol.c.platform_levy, cnBoxCol.c.currency) + "  •  SECZ (" + Number(cnBoxCol.c.secz_levy_pct || 0).toFixed(2) + "%): " + root.fmtShortMoney(cnBoxCol.c.secz_levy, cnBoxCol.c.currency); color: "#a6adc8"; font.pixelSize: 8 }
                                                        Text { text: "Stamp Duty (" + Number(cnBoxCol.c.stamp_duty_pct || 0).toFixed(2) + "%): " + root.fmtShortMoney(cnBoxCol.c.stamp_duty, cnBoxCol.c.currency) + "  •  CGT (" + Number(cnBoxCol.c.cgt_pct || 0).toFixed(2) + "%): " + root.fmtShortMoney(cnBoxCol.c.cgt, cnBoxCol.c.currency); color: "#a6adc8"; font.pixelSize: 8 }
                                                        Text { text: "Total Charges: " + root.fmtShortMoney(cnBoxCol.c.total_charges, cnBoxCol.c.currency) + " (" + Number(cnBoxCol.c.total_fee_pct || 0).toFixed(2) + "%)  |  Net Settlement: " + root.fmtShortMoney(cnBoxCol.c.net_settlement, cnBoxCol.c.currency); color: "#f9e2af"; font.pixelSize: 8; font.bold: true; wrapMode: Text.WordWrap; width: parent.width }
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
            }
        }
    }
}
