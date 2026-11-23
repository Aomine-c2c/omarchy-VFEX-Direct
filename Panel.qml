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

    // Navigation & Workspace State
    property string activeScreen: "overview"
    property string activeWorkspace: "portfolio_overview"
    property string selectedSymbol: "INFR"
    property bool navCollapsed: false
    property bool rightDockOpen: true
    property real rightDockWidth: 230
    property bool commandPaletteOpen: false

    // Status & Process Feedback
    property string statusMessage: ""
    property bool statusError: false
    property bool cliBusy: cliProc.running

    TerminalTheme { id: theme }

    function vfexPath() {
        return Qt.resolvedUrl("vfex.py").toString().replace("file://", "")
    }

    function runCli(args, successLabel) {
        if (cliProc.running) return
        cliProc.successLabel = successLabel || "Done"
        cliProc.lastErr = ""
        cliProc.lastOut = ""
        cliProc.command = ["python3", root.vfexPath()].concat(args)
        cliProc.running = true
    }

    function openStock(sym) {
        if (!sym) return
        root.selectedSymbol = String(sym).toUpperCase()
        root.activeScreen = "stock"
        root.compactMode = false
    }

    function applyWorkspace(wsKey) {
        root.activeWorkspace = wsKey
        root.compactMode = false
        if (wsKey === "portfolio_overview") { root.activeScreen = "overview"; root.rightDockOpen = true }
        else if (wsKey === "market_watch") { root.activeScreen = "screener"; root.rightDockOpen = true }
        else if (wsKey === "research_desk") { root.activeScreen = "stock"; root.rightDockOpen = true }
        else if (wsKey === "trading_desk") { root.activeScreen = "trading"; root.rightDockOpen = true }
        else if (wsKey === "intelligence_desk") { root.activeScreen = "intelligence"; root.rightDockOpen = false }
    }

    function open() { root.controller.show() }
    function close() { root.controller.hide() }
    function switchPanel(direction) {
        if (root.bar && typeof root.bar.switchPanelFrom === "function")
            return root.bar.switchPanelFrom(root.hostWidget || root, direction)
        return false
    }

    Process {
        id: cliProc
        property string successLabel: ""
        property string lastOut: ""
        property string lastErr: ""
        stdout: SplitParser {
            onRead: function(line) { var t = line.trim(); if (t) cliProc.lastOut = t }
        }
        stderr: SplitParser {
            onRead: function(line) { var t = line.trim(); if (t) cliProc.lastErr = t }
        }
        onExited: function(exitCode) {
            if (exitCode === 0) {
                root.statusError = false
                root.statusMessage = cliProc.lastOut || cliProc.successLabel || "Completed"
                if (root.hostWidget && typeof root.hostWidget.refresh === "function")
                    root.hostWidget.refresh()
            } else {
                root.statusError = true
                root.statusMessage = cliProc.lastErr || ("Command failed (code " + exitCode + ")")
            }
        }
    }

    // Panel Surface
    Rectangle {
        id: shell
        width: root.compactMode ? 380 : Math.min(1320, Math.max(920, (root.availableCardWidth > 0 ? root.availableCardWidth : 1240)))
        height: root.compactMode ? 290 : Math.min(860, Math.max(640, (root.availableCardHeight > 0 ? root.availableCardHeight : 780)))
        color: theme.bgBlack
        border.color: theme.borderDefault
        border.width: 1
        radius: theme.rSm
        clip: true
        focus: true

        // Global Keyboard Shortcuts
        Keys.onPressed: function(event) {
            if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_K) {
                root.commandPaletteOpen = !root.commandPaletteOpen
                event.accepted = true
            } else if (event.key === Qt.Key_Escape) {
                if (root.commandPaletteOpen) { root.commandPaletteOpen = false; event.accepted = true }
            } else if (!root.commandPaletteOpen && !(event.modifiers & Qt.ControlModifier)) {
                var map = {
                    49: "overview", 50: "portfolio", 51: "screener", 52: "stock",
                    53: "intelligence", 54: "newsroom", 55: "planner", 56: "trading", 57: "ledger"
                }
                if (map[event.key] && !root.compactMode) {
                    root.activeScreen = map[event.key]
                    event.accepted = true
                }
            }
        }

        // 1. COMPACT POPUP MODE
        CompactPopup {
            visible: root.compactMode
            anchors.fill: parent
            theme: theme
            summaryData: root.summaryData
            busy: root.cliBusy
            onOpenFullTerminal: function(screenKey) {
                root.compactMode = false
                if (screenKey) root.activeScreen = screenKey
            }
            onRefreshRequested: {
                if (root.hostWidget && typeof root.hostWidget.refresh === "function") root.hostWidget.refresh()
                else root.runCli(["fetch"], "Refreshed market data")
            }
        }

        // 2. FULL NOTHING INVESTMENT TERMINAL WORKSTATION
        Column {
            visible: !root.compactMode
            anchors.fill: parent
            spacing: 0

            // Top Terminal Chrome
            Rectangle {
                width: parent.width; height: 38
                color: theme.bgSurface
                border.color: theme.borderSubtle; border.width: 1
                Row {
                    anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 10

                    // Brand + Live Market Status LED
                    Row {
                        anchors.verticalCenter: parent.verticalCenter; spacing: 6
                        Rectangle {
                            width: 7; height: 7; radius: 3.5; anchors.verticalCenter: parent.verticalCenter
                            color: root.summaryData.market_status === "Open" ? theme.gain : theme.accent
                        }
                        Text {
                            text: "NOTHING // INVESTMENT TERMINAL"
                            color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 11; font.bold: true
                        }
                    }

                    Rectangle { width: 1; height: 18; color: theme.borderDefault; anchors.verticalCenter: parent.verticalCenter }

                    // 5 Saved Workspaces
                    Row {
                        anchors.verticalCenter: parent.verticalCenter; spacing: 4
                        Repeater {
                            model: [
                                { k: "portfolio_overview", t: "PORTFOLIO" },
                                { k: "market_watch", t: "MKT WATCH" },
                                { k: "research_desk", t: "RESEARCH" },
                                { k: "trading_desk", t: "TRADING" },
                                { k: "intelligence_desk", t: "INTEL DESK" }
                            ]
                            delegate: Rectangle {
                                width: wsTxt.implicitWidth + 12; height: 22; radius: theme.rSharp
                                color: root.activeWorkspace === modelData.k ? theme.bgActive : "transparent"
                                border.color: root.activeWorkspace === modelData.k ? theme.borderStrong : theme.borderSubtle; border.width: 1
                                Text { id: wsTxt; anchors.centerIn: parent; text: modelData.t; color: root.activeWorkspace === modelData.k ? theme.textPrimary : theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: root.activeWorkspace === modelData.k }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.applyWorkspace(modelData.k) }
                            }
                        }
                    }

                    Item { width: Math.max(4, parent.width - 780); height: 1 }

                    // Command Palette Trigger (Ctrl+K)
                    Rectangle {
                        width: 116; height: 22; radius: theme.rSharp; anchors.verticalCenter: parent.verticalCenter
                        color: theme.bgBlack; border.color: theme.borderDefault; border.width: 1
                        Text { anchors.centerIn: parent; text: "CMD  CTRL+K"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 9 }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.commandPaletteOpen = true }
                    }

                    // Refresh Button
                    Rectangle {
                        width: 68; height: 22; radius: theme.rSharp; anchors.verticalCenter: parent.verticalCenter
                        color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                        Text { anchors.centerIn: parent; text: root.cliBusy ? "SYNC..." : "REFRESH"; color: theme.textPrimary; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.runCli(["fetch"], "Fetched live VFEX/ZSE quotes") }
                    }

                    // Compact Mode Toggle
                    Rectangle {
                        width: 66; height: 22; radius: theme.rSharp; anchors.verticalCenter: parent.verticalCenter
                        color: theme.bgElevated; border.color: theme.borderDefault; border.width: 1
                        Text { anchors.centerIn: parent; text: "COMPACT"; color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 9 }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.compactMode = true }
                    }
                }
            }

            // Main 3-Pane Workstation Body (Left Nav Rail | Main Screen | Resizable Right Watchlist Dock)
            Row {
                width: parent.width
                height: parent.height - 60

                // Left Navigation Rail (9 Screens)
                Rectangle {
                    width: root.navCollapsed ? 42 : 148
                    height: parent.height
                    color: theme.bgSurface
                    border.color: theme.borderSubtle; border.width: 1

                    Column {
                        anchors.fill: parent; anchors.margins: 6; spacing: 3
                        Repeater {
                            model: [
                                { k: "overview", n: "1", t: "OVERVIEW" },
                                { k: "portfolio", n: "2", t: "PORTFOLIO" },
                                { k: "screener", n: "3", t: "SCREENER" },
                                { k: "stock", n: "4", t: "STOCK DETAIL" },
                                { k: "intelligence", n: "5", t: "INTELLIGENCE" },
                                { k: "newsroom", n: "6", t: "NEWSROOM" },
                                { k: "planner", n: "7", t: "PLANNER" },
                                { k: "trading", n: "8", t: "TRADING" },
                                { k: "ledger", n: "9", t: "LEDGER" }
                            ]
                            delegate: Rectangle {
                                width: parent.width; height: 28; radius: theme.rSharp
                                color: root.activeScreen === modelData.k ? theme.bgActive : (navMa.containsMouse ? theme.bgHover : "transparent")
                                border.color: root.activeScreen === modelData.k ? theme.accent : "transparent"; border.width: 1
                                Row {
                                    anchors.fill: parent; anchors.leftMargin: 8; spacing: 8
                                    Text { text: modelData.n; color: root.activeScreen === modelData.k ? theme.accent : theme.textDim; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                                    Text { visible: !root.navCollapsed; text: modelData.t; color: root.activeScreen === modelData.k ? theme.textPrimary : theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 10; font.bold: root.activeScreen === modelData.k; anchors.verticalCenter: parent.verticalCenter }
                                }
                                MouseArea { id: navMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.activeScreen = modelData.k }
                            }
                        }
                        Item { width: 1; height: Math.max(8, parent.height - 320) }
                        Rectangle {
                            width: parent.width; height: 24; radius: theme.rSharp; color: theme.bgElevated
                            Text { anchors.centerIn: parent; text: root.navCollapsed ? "»" : "« COLLAPSE"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9 }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.navCollapsed = !root.navCollapsed }
                        }
                    }
                }

                // Center Active Screen Container
                Item {
                    width: parent.width - (root.navCollapsed ? 42 : 148) - (root.rightDockOpen ? (root.rightDockWidth + 5) : 0)
                    height: parent.height

                    Item {
                        anchors.fill: parent; anchors.margins: 10

                        OverviewScreen { visible: root.activeScreen === "overview"; anchors.fill: parent; theme: theme; summaryData: root.summaryData; onOpenStock: root.openStock; onNavigateScreen: function(k) { root.activeScreen = k }; onRunCli: root.runCli }
                        PortfolioScreen { visible: root.activeScreen === "portfolio"; anchors.fill: parent; theme: theme; summaryData: root.summaryData; onOpenStock: root.openStock }
                        ScreenerScreen { visible: root.activeScreen === "screener"; anchors.fill: parent; theme: theme; summaryData: root.summaryData; onOpenStock: root.openStock }
                        StockDetailScreen { visible: root.activeScreen === "stock"; anchors.fill: parent; theme: theme; summaryData: root.summaryData; symbol: root.selectedSymbol; onRunCli: root.runCli }
                        IntelligenceScreen { visible: root.activeScreen === "intelligence"; anchors.fill: parent; theme: theme; summaryData: root.summaryData; onOpenStock: root.openStock; onRunCli: root.runCli }
                        NewsroomScreen { visible: root.activeScreen === "newsroom"; anchors.fill: parent; theme: theme; summaryData: root.summaryData; onOpenStock: root.openStock; onRunCli: root.runCli }
                        PlannerScreen { visible: root.activeScreen === "planner"; anchors.fill: parent; theme: theme; summaryData: root.summaryData; onRunCli: root.runCli }
                        TradingScreen { visible: root.activeScreen === "trading"; anchors.fill: parent; theme: theme; summaryData: root.summaryData; onRunCli: root.runCli }
                        LedgerScreen { visible: root.activeScreen === "ledger"; anchors.fill: parent; theme: theme; summaryData: root.summaryData; onRunCli: root.runCli }
                    }
                }

                // Draggable Splitter Handle for Right Dock
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
                        onPositionChanged: function(mouse) {
                            if (pressed) root.rightDockWidth = Math.max(170, Math.min(360, startW - (mouse.x - startX)))
                        }
                    }
                }

                // Right Watchlist & Live Tape Dock
                Rectangle {
                    visible: root.rightDockOpen
                    width: root.rightDockWidth
                    height: parent.height
                    color: theme.bgSurface
                    border.color: theme.borderSubtle; border.width: 1

                    Column {
                        anchors.fill: parent; anchors.margins: 8; spacing: 6
                        Row {
                            width: parent.width
                            Text { text: "WATCHLIST TAPE"; color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; font.bold: true }
                            Item { width: Math.max(4, parent.width - 120); height: 1 }
                            Text {
                                text: "HIDE"; color: theme.textDim; font.family: theme.fontMono; font.pixelSize: 9
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.rightDockOpen = false }
                            }
                        }
                        Rectangle { width: parent.width; height: 1; color: theme.borderSubtle }
                        ListView {
                            width: parent.width
                            height: parent.height - 28
                            clip: true; spacing: 3
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
                                MouseArea { id: wMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.openStock(modelData.symbol) }
                            }
                        }
                    }
                }
            }

            // Bottom Terminal Status Bar
            Rectangle {
                width: parent.width; height: 22
                color: theme.bgSurface
                border.color: theme.borderSubtle; border.width: 1
                Row {
                    anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 12
                    Text {
                        text: "MARKET: " + String(root.summaryData.market_status || "Closed").toUpperCase() + " (" + String(root.summaryData.market_countdown || "") + ")"
                        color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: "UPDATED: " + String(root.summaryData.last_updated || "--")
                        color: theme.textMuted; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        visible: root.statusMessage !== ""
                        text: root.statusMessage
                        color: root.statusError ? theme.loss : theme.gain
                        font.family: theme.fontMono; font.pixelSize: 9; font.bold: true; anchors.verticalCenter: parent.verticalCenter
                    }
                    Item { width: Math.max(4, parent.width - 540); height: 1 }
                    Text {
                        visible: !root.rightDockOpen
                        text: "SHOW WATCHLIST"
                        color: theme.textSecondary; font.family: theme.fontMono; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.rightDockOpen = true }
                    }
                }
            }
        }

        // 3. GLOBAL COMMAND PALETTE OVERLAY (Ctrl+K)
        CommandPalette {
            theme: theme
            summaryData: root.summaryData
            open: root.commandPaletteOpen
            onNavigateScreen: function(k) { root.activeScreen = k; root.compactMode = false }
            onSelectWorkspace: root.applyWorkspace
            onOpenStock: root.openStock
            onRunAction: function(act) {
                if (act === "refresh") root.runCli(["fetch"], "Refreshed market data")
                else if (act === "agent_step") root.runCli(["agent", "step"], "Ran Mahoraga step")
                else if (act === "agent_train") root.runCli(["agent", "train", "--days", "365"], "Trained Mahoraga brain")
                else if (act === "sync_all") root.runCli(["account", "sync", "all"], "Synced all portals")
            }
            onCloseRequested: root.commandPaletteOpen = false
        }
    }
}
