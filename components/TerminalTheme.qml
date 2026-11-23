import QtQuick

QtObject {
    // NOTHING Investment Terminal — Deep Black & Charcoal Design System
    readonly property color bgBlack: "#000000"
    readonly property color bgSurface: "#09090B"
    readonly property color bgPanel: "#0E0E12"
    readonly property color bgElevated: "#141419"
    readonly property color bgHover: "#1B1B22"
    readonly property color bgActive: "#1E1E26"

    readonly property color borderSubtle: "#1C1C22"
    readonly property color borderDefault: "#272730"
    readonly property color borderStrong: "#3A3A47"

    readonly property color textPrimary: "#F2F2F5"
    readonly property color textSecondary: "#A1A1AA"
    readonly property color textMuted: "#6C6C78"
    readonly property color textDim: "#4A4A55"

    // Restrained financial market indicators (no neon/SaaS saturation)
    readonly property color gain: "#2EBD85"
    readonly property color gainBg: "#0B2018"
    readonly property color loss: "#D93848"
    readonly property color lossBg: "#230C10"
    readonly property color warn: "#E5A93B"
    readonly property color warnBg: "#241B0B"
    readonly property color accent: "#E62E3D"
    readonly property color accentBg: "#240A0E"
    readonly property color info: "#7AA2F7"
    readonly property color infoBg: "#0F1829"

    readonly property string fontMono: "JetBrains Mono, Fira Code, Cascadia Code, monospace"
    readonly property string fontSans: "Inter, Space Grotesk, sans-serif"

    readonly property int rSharp: 2
    readonly property int rSm: 3

    function fmtMoney(val, currency, decimals) {
        var n = Number(val || 0)
        var d = (decimals !== undefined && decimals !== null) ? decimals : 2
        var cur = String(currency || "USD").toUpperCase()
        var pref = cur === "ZWG" ? "ZiG " : "$"
        var sign = n < 0 ? "-" : ""
        return sign + pref + Math.abs(n).toFixed(d)
    }

    function fmtSignedMoney(val, currency, decimals) {
        var n = Number(val || 0)
        var d = (decimals !== undefined && decimals !== null) ? decimals : 2
        var cur = String(currency || "USD").toUpperCase()
        var pref = cur === "ZWG" ? "ZiG " : "$"
        var sign = n > 0 ? "+" : (n < 0 ? "-" : "")
        return sign + pref + Math.abs(n).toFixed(d)
    }

    function fmtPct(val, decimals) {
        var n = Number(val || 0)
        var d = (decimals !== undefined && decimals !== null) ? decimals : 2
        var sign = n > 0 ? "+" : ""
        return sign + n.toFixed(d) + "%"
    }

    function toneColor(val) {
        var n = Number(val || 0)
        if (n > 0.0001) return gain
        if (n < -0.0001) return loss
        return textSecondary
    }

    function exchangeLabel(item) {
        if (!item) return "VFEX"
        var cur = String(item.currency || "USD").toUpperCase()
        if (cur === "ZWG") return "ZSE"
        var prov = String(item.provider || "").toLowerCase()
        if (prov.indexOf("ctrade") >= 0) return "C-TRADE"
        return "VFEX"
    }
}
