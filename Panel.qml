import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "components"

Panel {
    id: root
    moduleName: "io.github.aomine-c2c.vfex-direct"
    manageIpc: false

    property var anchorItem: null
    property var hostWidget: null
    property var summaryData: ({ text: "VFEX --", total_value: 0, total_pnl: 0, total_pnl_pct: 0, items: [], watchlist: [] })
    property bool wideLayout: true
    property bool compactMode: !wideLayout

    // Single-Page Unified Workstation State (ZERO TABS)
    property string selectedSymbol: "INFR"
    property bool rightDockOpen: true
    property real rightDockWidth: 230
    property bool commandPaletteOpen: false

    // Collapsible Section States (Persisted)
    property bool secSummaryOpen: true
    property bool secAnalyticsOpen: true
    property bool secMarketsOpen: true
    property bool secResearchOpen: true
    property bool secNewsOpen: true
    property bool secAgentsOpen: true
    property bool secPlanningOpen: true
    property bool secTradingOpen: true
    property bool secAssistantOpen: true

    // Conversational Assistant (Section 10)
    property string assistantInput: ""
    property string assistantReply: "Ask anything about your VFEX/ZSE/C-TRADE portfolio, a specific counter, risk, or investment plan."
    property bool assistantBusy: assistProc.running

    // Status & CLI Feedback
    property string statusMessage: ""
    property bool statusError: false
    property bool cliBusy: cliProc.running

    TerminalTheme { id: theme }

    Component.onCompleted: loadLayoutPrefs()

    function scriptPath(name) {
        return Qt.resolvedUrl(name).toString().replace("file://", "")
    }

    function loadLayoutPrefs() {
        prefsLoadProc.command = ["python3", root.scriptPath("workspace_prefs.py")]
        prefsLoadProc.running = true
    }

    function saveLayoutPrefs() {
        var payload = JSON.stringify({
            compact_mode: root.compactMode,
            right_dock_open: root.rightDockOpen,
            right_dock_width: Math.round(root.rightDockWidth),
            collapsed: {
                summary: !root.secSummaryOpen,
                analytics: !root.secAnalyticsOpen,
                markets: !root.secMarketsOpen,
                research: !root.secResearchOpen,
                news: !root.secNewsOpen,
                agents: !root.secAgentsOpen,
                planning: !root.secPlanningOpen,
                trading: !root.secTradingOpen,
                assistant: !root.secAssistantOpen
            }
        })
        prefsSaveProc.command = ["python3", root.scriptPath("workspace_prefs.py"), "save", payload]
        prefsSaveProc.running = true
    }

    function runCli(args, successLabel) {
        if (cliProc.running) return
        cliProc.successLabel = successLabel || "Done"
        cliProc.lastErr = ""
        cliProc.lastOut = ""
        cliProc.command = ["python3", root.scriptPath("vfex.py")].concat(args)
        cliProc.running = true
    }

    function askAssistant(question) {
        if (assistProc.running || !question || !question.trim()) return
        assistProc.buf = ""
        assistProc.command = ["python3", root.scriptPath("intelligence.py"), question.trim()]
        assistProc.running = true
    }

    function selectStockInline(sym) {
        if (!sym) return
        root.selectedSymbol = String(sym).toUpperCase()
        root.secResearchOpen = true
        jumpToSection("research")
    }

    function jumpToSection(key) {
        root.compactMode = false
        var targetItem = secSummary
        if (key === "analytics") targetItem = secAnalytics
        else if (key === "markets") targetItem = secMarkets
        else if (key === "research") targetItem = secResearch
        else if (key === "newsroom") targetItem = secNews
        else if (key === "agents") targetItem = secAgents
        else if (key === "planning") targetItem = secPlanning
        else if (key === "trading") targetItem = secTrading
        else if (key === "assistant") targetItem = secAssistant
        if (targetItem && mainScroll) {
            mainScroll.contentY = Math.max(0, Math.min(mainScroll.contentHeight - mainScroll.height, targetItem.y - 6))
        }
    }

    function open() { root.controller.show() }
    function close() { root.controller.hide() }
    function switchPanel(direction) {
        if (root.bar && typeof root.bar.switchPanelFrom === "function")
            return root.bar.switchPanelFrom(root.hostWidget || root, direction)
        return false
    }

    Process {
        id: prefsLoadProc
        property string buf: ""
        stdout: SplitParser { splitMarker: ""; onRead: function(c) { prefsLoadProc.buf += c } }
        onExited: function(code) {
            if (code === 0 && prefsLoadProc.buf.trim() !== "") {
                try {
                    var p = JSON.parse(prefsLoadProc.buf)
                    if (p.right_dock_open !== undefined) root.rightDockOpen = p.right_dock_open
                    if (p.right_dock_width) root.rightDockWidth = Math.max(170, Math.min(360, Number(p.right_dock_width)))
                    var c = p.collapsed || ({})
                    if (c.summary !== undefined) root.secSummaryOpen = !c.summary
                    if (c.analytics !== undefined) root.secAnalyticsOpen = !c.analytics
                    if (c.markets !== undefined) root.secMarketsOpen = !c.markets
                    if (c.research !== undefined) root.secResearchOpen = !c.research
                    if (c.news !== undefined) root.secNewsOpen = !c.news
                    if (c.agents !== undefined) root.secAgentsOpen = !c.agents
                    if (c.planning !== undefined) root.secPlanningOpen = !c.planning
                    if (c.trading !== undefined) root.secTradingOpen = !c.trading
                    if (c.assistant !== undefined) root.secAssistantOpen = !c.assistant
                } catch (e) {}
            }
            prefsLoadProc.buf = ""
        }
    }

    Process { id: prefsSaveProc }

    Process {
        id: cliProc
        property string successLabel: ""
        property string lastOut: ""
        property string lastErr: ""
        stdout: SplitParser { onRead: function(line) { var t = line.trim(); if (t) cliProc.lastOut = t } }
        stderr: SplitParser { onRead: function(line) { var t = line.trim(); if (t) cliProc.lastErr = t } }
        onExited: function(exitCode) {
            if (exitCode === 0) {
                root.statusError = false
                root.statusMessage = cliProc.lastOut || cliProc.successLabel || "Completed"
                if (root.hostWidget && typeof root.hostWidget.refresh === "function") root.hostWidget.refresh()
            } else {
                root.statusError = true
                root.statusMessage = cliProc.lastErr || ("Command failed (code " + exitCode + ")")
            }
        }
    }

    Process {
        id: assistProc
        property string buf: ""
        stdout: SplitParser { splitMarker: ""; onRead: function(c) { assistProc.buf += c } }
        onExited: function(code) {
            if (code === 0 && assistProc.buf.trim() !== "") {
                try {
                    var r = JSON.parse(assistProc.buf)
                    var lines = []
                    var f = r.findings || []
                    for (var i = 0; i < Math.min(4, f.length); i++)
                        lines.push("[" + f[i].agent_name + " | " + f[i].stance + "] " + f[i].summary)
                    if ((r.disagreements || []).length > 0)
                        lines.push("⚠ DISAGREEMENT: " + r.disagreements[0].topic)
                    root.assistantReply = lines.join("\n") || "Analysis complete."
                } catch (e) { root.assistantReply = "Analysis completed." }
            } else {
                root.assistantReply = "Assistant encountered an error (code " + code + ")."
            }
            assistProc.buf = ""
        }
    }

    // Main Terminal Surface
    Rectangle {
        id: shell
        width: root.compactMode ? 380 : Math.min(1360, Math.max(900, (root.availableCardWidth > 0 ? root.availableCardWidth : 1280)))
        height: root.compactMode ? 290 : Math.min(880, Math.max(640, (root.availableCardHeight > 0 ? root.availableCardHeight : 820)))
        color: theme.bgBlack
        border.color: theme.borderDefault
        border.width: 1
        radius: theme.rSm
        clip: true
        focus: true

        Keys.onPressed: function(event) {
            if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_K) {
                root.commandPaletteOpen = !root.commandPaletteOpen
                event.accepted = true
            } else if (event.key === Qt.Key_Escape && root.commandPaletteOpen) {
                root.commandPaletteOpen = false
                event.accepted = true
            }
        }

        // COMPACT POPUP MODE
        CompactPopup {
            visible: root.compactMode
            anchors.fill: parent
            theme: theme
            summaryData: root.summaryData
            busy: root.cliBusy
            onOpenFullTerminal: function() { root.compactMode = false; root.saveLayoutPrefs() }
            onRefreshRequested: root.runCli(["fetch"], "Refreshed live market data")
        }

        // SINGLE-PAGE UNIFIED WORKSTATION (ZERO TABS)
        Column {
            visible: !root.compactMode
            anchors.fill: parent
            spacing: 0

            // SECTION 1: GLOBAL MARKET HEADER
            Rectangle {
                width: parent.width; height: 38
                color: theme.bgSurface; border.color: theme.borderSubtle; border.width: 1
                Row {
                    anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 10
                    Rectangle { width: 7; height: 7; radius: 3.5; anchors.verticalCenter: parent.verticalCenter; color: root.summaryData.market_status === "Open" ? theme.gain : theme.accent }
                    Text { text: "NOTHING // TERMINAL"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: "VFEX · ZSE · C-TRADE"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: "|  " + String(root.summaryData.market_status || "Closed").toUpperCase() + " (" + String(root.summaryData.last_updated || "--") + ")"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: "|  AGENTS 8/8"; color: theme.gain; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: "|  ALERTS " + (root.summaryData.triggered_alerts || []).length; color: (root.summaryData.triggered_alerts || []).length > 0 ? theme.accent : theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                    Item { width: Math.max(4, parent.width - 790); height: 1 }
                    Rectangle {
                        width: 116; height: 22; radius: theme.rSharp; anchors.verticalCenter: parent.verticalCenter
                        color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
                        Text { anchors.centerIn: parent; text: "SEARCH  CTRL+K"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 9 }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.commandPaletteOpen = true }
                    }
                    Rectangle {
                        width: 68; height: 22; radius: theme.rSharp; anchors.verticalCenter: parent.verticalCenter
                        color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                        Text { anchors.centerIn: parent; text: root.cliBusy ? "SYNC..." : "REFRESH"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.runCli(["fetch"], "Fetched live quotes") }
                    }
                    Rectangle {
                        width: 64; height: 22; radius: theme.rSharp; anchors.verticalCenter: parent.verticalCenter
                        color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                        Text { anchors.centerIn: parent; text: "COMPACT"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 9 }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.compactMode = true; root.saveLayoutPrefs() } }
                    }
                }
            }

            // CONTINUOUS WORKSTATION BODY + RESIZABLE RIGHT WATCHLIST DOCK
            Row {
                width: parent.width
                height: parent.height - 60

                Flickable {
                    id: mainScroll
                    width: parent.width - (root.rightDockOpen ? (root.rightDockWidth + 5) : 0)
                    height: parent.height
                    contentWidth: width
                    contentHeight: mainCol.implicitHeight + 28
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                    Column {
                        id: mainCol
                        width: parent.width - 20
                        x: 10; y: 10
                        spacing: 12

                        // SECTION 2: PORTFOLIO SUMMARY
                        Column {
                            id: secSummary
                            width: parent.width; spacing: 6
                            Text {
                                text: (root.secSummaryOpen ? "▾ " : "▸ ") + "02 // PORTFOLIO SUMMARY"
                                color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.secSummaryOpen = !root.secSummaryOpen; root.saveLayoutPrefs() } }
                            }
                            Grid {
                                visible: root.secSummaryOpen
                                width: parent.width; columns: width >= 900 ? 4 : 2; spacing: 8
                                property real cw: (width - (columns - 1) * spacing) / columns
                                Repeater {
                                    model: [
                                        { k: "TOTAL PORTFOLIO", v: theme.fmtMoney(root.summaryData.total_value, "USD", 2), c: theme.textPrimary },
                                        { k: "UNREALISED P&L", v: theme.fmtSignedMoney(root.summaryData.total_pnl, "USD", 2) + " (" + theme.fmtPct(root.summaryData.total_pnl_pct, 2) + ")", c: theme.toneColor(root.summaryData.total_pnl) },
                                        { k: "AVAILABLE CASH", v: "USD " + theme.fmtMoney(root.summaryData.wallet_cash_usd, "USD", 2) + " | ZWG " + theme.fmtMoney(root.summaryData.wallet_cash_zwg, "ZWG", 2), c: theme.textPrimary },
                                        { k: "REALISED & DIVIDENDS", v: "REAL " + theme.fmtSignedMoney(root.summaryData.realized_pnl, "USD", 2) + " | DIV " + theme.fmtMoney(root.summaryData.total_dividends, "USD", 2), c: theme.gain }
                                    ]
                                    delegate: Rectangle {
                                        width: parent.cw; height: 54; radius: theme.rSharp
                                        color: theme.bgPanel; border.color: theme.borderSubtle; border.width: 1
                                        Column {
                                            anchors.fill: parent; anchors.margins: 8; spacing: 3
                                            Text { text: modelData.k; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                                            Text { text: modelData.v; color: modelData.c; font.family: theme.fontMono; font.pixelSize: 13; font.bold: true; elide: Text.ElideRight; width: parent.width }
                                        }
                                    }
                                }
                            }
                        }

                        // SECTION 3: PORTFOLIO ANALYTICS
                        Column {
                            id: secAnalytics
                            width: parent.width; spacing: 6
                            Text {
                                text: (root.secAnalyticsOpen ? "▾ " : "▸ ") + "03 // PORTFOLIO ANALYTICS & HOLDINGS"
                                color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.secAnalyticsOpen = !root.secAnalyticsOpen; root.saveLayoutPrefs() } }
                            }
                            PortfolioScreen {
                                visible: root.secAnalyticsOpen
                                width: parent.width; height: 260
                                theme: theme; summaryData: root.summaryData
                                onOpenStock: root.selectStockInline
                            }
                        }

                        // SECTION 4: MARKET INTELLIGENCE & SCREENER
                        Column {
                            id: secMarkets
                            width: parent.width; spacing: 6
                            Text {
                                text: (root.secMarketsOpen ? "▾ " : "▸ ") + "04 // MARKET INTELLIGENCE & SCREENER (CLICK ANY COUNTER TO INSPECT INLINE)"
                                color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.secMarketsOpen = !root.secMarketsOpen; root.saveLayoutPrefs() } }
                            }
                            ScreenerScreen {
                                visible: root.secMarketsOpen
                                width: parent.width; height: 300
                                theme: theme; summaryData: root.summaryData
                                onOpenStock: root.selectStockInline
                            }
                        }

                        // SECTION 5: INVESTMENT RESEARCH (INLINE FOR SELECTED COUNTER)
                        Column {
                            id: secResearch
                            width: parent.width; spacing: 6
                            Text {
                                text: (root.secResearchOpen ? "▾ " : "▸ ") + "05 // INVESTMENT RESEARCH — " + root.selectedSymbol
                                color: theme.accent; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.secResearchOpen = !root.secResearchOpen; root.saveLayoutPrefs() } }
                            }
                            StockDetailScreen {
                                visible: root.secResearchOpen
                                width: parent.width; height: 520
                                theme: theme; summaryData: root.summaryData; symbol: root.selectedSymbol
                                onRunCli: root.runCli
                            }
                        }

                        // SECTION 6: LIVE NEWSROOM
                        Column {
                            id: secNews
                            width: parent.width; spacing: 6
                            Text {
                                text: (root.secNewsOpen ? "▾ " : "▸ ") + "06 // LIVE NEWSROOM & WHY THIS MATTERS TO MY PORTFOLIO"
                                color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.secNewsOpen = !root.secNewsOpen; root.saveLayoutPrefs() } }
                            }
                            NewsroomScreen {
                                visible: root.secNewsOpen
                                width: parent.width; height: 340
                                theme: theme; summaryData: root.summaryData
                                onOpenStock: root.selectStockInline
                                onRunCli: root.runCli
                            }
                        }

                        // SECTION 7: AI AGENT WORKSPACE
                        Column {
                            id: secAgents
                            width: parent.width; spacing: 6
                            Text {
                                text: (root.secAgentsOpen ? "▾ " : "▸ ") + "07 // AI AGENT WORKSPACE (8-AGENT DESK & MAHORAGA BRAIN)"
                                color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.secAgentsOpen = !root.secAgentsOpen; root.saveLayoutPrefs() } }
                            }
                            IntelligenceScreen {
                                visible: root.secAgentsOpen
                                width: parent.width; height: 340
                                theme: theme; summaryData: root.summaryData
                                onOpenStock: root.selectStockInline
                                onRunCli: root.runCli
                            }
                        }

                        // SECTION 8: INVESTMENT PLANNING
                        Column {
                            id: secPlanning
                            width: parent.width; spacing: 6
                            Text {
                                text: (root.secPlanningOpen ? "▾ " : "▸ ") + "08 // INVESTMENT PLANNING, SCENARIOS & CALENDAR"
                                color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.secPlanningOpen = !root.secPlanningOpen; root.saveLayoutPrefs() } }
                            }
                            PlannerScreen {
                                visible: root.secPlanningOpen
                                width: parent.width; height: 420
                                theme: theme; summaryData: root.summaryData
                                onRunCli: root.runCli
                            }
                        }

                        // SECTION 9: TRADING AND LEDGER
                        Column {
                            id: secTrading
                            width: parent.width; spacing: 6
                            Text {
                                text: (root.secTradingOpen ? "▾ " : "▸ ") + "09 // TRADING DESK & AUDIT LEDGER"
                                color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.secTradingOpen = !root.secTradingOpen; root.saveLayoutPrefs() } }
                            }
                            TradingScreen {
                                visible: root.secTradingOpen
                                width: parent.width; height: 360
                                theme: theme; summaryData: root.summaryData
                                onRunCli: root.runCli
                            }
                            LedgerScreen {
                                visible: root.secTradingOpen
                                width: parent.width; height: 300
                                theme: theme; summaryData: root.summaryData
                                onRunCli: root.runCli
                            }
                        }

                        // SECTION 10: CONVERSATIONAL INVESTMENT ASSISTANT
                        Column {
                            id: secAssistant
                            width: parent.width; spacing: 6
                            Text {
                                text: (root.secAssistantOpen ? "▾ " : "▸ ") + "10 // CONVERSATIONAL INVESTMENT ASSISTANT"
                                color: theme.accent; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.secAssistantOpen = !root.secAssistantOpen; root.saveLayoutPrefs() } }
                            }
                            Rectangle {
                                visible: root.secAssistantOpen
                                width: parent.width; height: Math.max(120, asstCol.implicitHeight + 20); radius: theme.rSharp
                                color: theme.bgPanel; border.color: theme.borderDefault; border.width: 1
                                Column {
                                    id: asstCol
                                    anchors.fill: parent; anchors.margins: 10; spacing: 8
                                    Row {
                                        width: parent.width; spacing: 6
                                        Rectangle {
                                            width: parent.width - 96; height: 28; radius: theme.rSharp; color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
                                            TextInput {
                                                anchors.fill: parent; anchors.margins: 6
                                                text: root.assistantInput
                                                color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11
                                                onTextChanged: root.assistantInput = text
                                                Keys.onReturnPressed: root.askAssistant(root.assistantInput)
                                                Text { visible: !parent.text; text: "Ask: 'Should I buy INFR?' or 'Audit my portfolio risk'..."; color: theme.textDim; font.family: theme.fontMono; font.pixelSize: 10 }
                                            }
                                        }
                                        Rectangle {
                                            width: 90; height: 28; radius: theme.rSharp; color: theme.accent
                                            Text { anchors.centerIn: parent; text: root.assistantBusy ? "THINKING..." : "ASK DESK"; color: "#FFFFFF"; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.askAssistant(root.assistantInput) }
                                        }
                                    }
                                    Text {
                                        width: parent.width; wrapMode: Text.WordWrap
                                        text: root.assistantReply
                                        color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10
                                    }
                                }
                            }
                        }

                        // SECTION 11: BYOK AI PROVIDERS & ISOLATED PAPER TRADING ARENA
                        Column {
                            id: secArena
                            width: parent.width; spacing: 6
                            Text {
                                text: "11 // BYOK AI PROVIDERS & 5-STRATEGY PAPER TRADING ARENA"
                                color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true
                            }
                            ArenaPanel {
                                width: parent.width
                                theme: theme
                            }
                        }
                    }
                }

                // Draggable Splitter for Right Watchlist Dock
                Rectangle {
                    visible: root.rightDockOpen
                    width: 5; height: parent.height
                    color: splitMa.containsMouse || splitMa.pressed ? theme.accent : theme.borderSubtle
                    MouseArea {
                        id: splitMa
                        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.SplitHCursor
                        property real startX: 0
                        property real startW: 230
                        onPressed: function(mouse) { startX = mouse.x; startW = root.rightDockWidth }
                        onPositionChanged: function(mouse) { if (pressed) root.rightDockWidth = Math.max(170, Math.min(360, startW - (mouse.x - startX))) }
                        onReleased: root.saveLayoutPrefs()
                    }
                }

                // Right Watchlist Tape Dock
                Rectangle {
                    visible: root.rightDockOpen
                    width: root.rightDockWidth; height: parent.height
                    color: theme.bgSurface; border.color: theme.borderSubtle; border.width: 1
                    Column {
                        anchors.fill: parent; anchors.margins: 8; spacing: 6
                        Row {
                            width: parent.width
                            Text { text: "WATCHLIST TAPE"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            Item { width: Math.max(4, parent.width - 120); height: 1 }
                            Text {
                                text: "HIDE"; color: theme.textDim; font.family: theme.fontMono; font.pixelSize: 9
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.rightDockOpen = false; root.saveLayoutPrefs() } }
                            }
                        }
                        Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }
                        ListView {
                            width: parent.width; height: parent.height - 28; clip: true; spacing: 3
                            model: root.summaryData.watchlist || []
                            delegate: Rectangle {
                                width: ListView.view.width; height: 34; radius: theme.rSharp
                                color: wMa.containsMouse ? theme.bgHover : theme.bgPanel
                                border.color: root.selectedSymbol === modelData.symbol ? theme.accent : theme.borderSubtle; border.width: 1
                                Row {
                                    anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8
                                    Column {
                                        anchors.verticalCenter: parent.verticalCenter
                                        Text { text: String(modelData.symbol || ""); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: true }
                                        Text { text: modelData.currency === "ZWG" ? "ZSE" : "VFEX"; color: theme.textDim; font.family: theme.fontMono; font.pixelSize: 8 }
                                    }
                                    Item { width: Math.max(4, parent.width - 130); height: 1 }
                                    Column {
                                        anchors.verticalCenter: parent.verticalCenter
                                        Text { horizontalAlignment: Text.AlignRight; text: theme.fmtMoney(modelData.price, modelData.currency, 4); color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 10 }
                                        Text { horizontalAlignment: Text.AlignRight; text: theme.fmtPct(modelData.change_pct, 2); color: theme.toneColor(modelData.change_pct); font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                                    }
                                }
                                MouseArea { id: wMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.selectStockInline(modelData.symbol) }
                            }
                        }
                    }
                }
            }

            // Bottom Status Bar
            Rectangle {
                width: parent.width; height: 22
                color: theme.bgSurface; border.color: theme.borderSubtle; border.width: 1
                Row {
                    anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 12
                    Text { text: "SINGLE-PAGE COMMAND CENTRE  |  ZERO TABS"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                    Text { visible: root.statusMessage !== ""; text: root.statusMessage; color: root.statusError ? theme.loss : theme.gain; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                    Item { width: Math.max(4, parent.width - 420); height: 1 }
                    Text {
                        visible: !root.rightDockOpen; text: "SHOW WATCHLIST"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.rightDockOpen = true; root.saveLayoutPrefs() } }
                    }
                }
            }
        }

        // GLOBAL COMMAND PALETTE (Ctrl+K — Scrolls to Section or Selects Counter Inline)
        CommandPalette {
            theme: theme
            summaryData: root.summaryData
            open: root.commandPaletteOpen
            onJumpSection: root.jumpToSection
            onOpenStock: root.selectStockInline
            onRunAction: function(act) {
                if (act === "refresh") root.runCli(["fetch"], "Refreshed live market data")
                else if (act === "toggle_dock") { root.rightDockOpen = !root.rightDockOpen; root.saveLayoutPrefs() }
                else if (act === "agent_train") root.runCli(["agent", "train", "--days", "365"], "Trained Mahoraga brain")
                else if (act === "sync_all") root.runCli(["account", "sync", "all"], "Synced all portals")
            }
            onCloseRequested: root.commandPaletteOpen = false
        }
    }
}
