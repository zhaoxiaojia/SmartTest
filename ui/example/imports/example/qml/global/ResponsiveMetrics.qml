pragma Singleton
import QtQml 2.15

QtObject {
    readonly property int compactBreakpoint: 720
    readonly property int wideBreakpoint: 1100
    readonly property int compact: 0
    readonly property int medium: 1
    readonly property int wide: 2

    function layoutForWidth(contentWidth) {
        if (contentWidth < compactBreakpoint)
            return compact
        if (contentWidth < wideBreakpoint)
            return medium
        return wide
    }

    function isCompact(contentWidth) { return layoutForWidth(contentWidth) === compact }
    function isMedium(contentWidth) { return layoutForWidth(contentWidth) === medium }
    function isWide(contentWidth) { return layoutForWidth(contentWidth) === wide }
    function safeContentWidth(contentWidth, margins) { return Math.max(0, contentWidth - (margins || 0)) }
    function safeContentHeight(contentHeight, margins) { return Math.max(0, contentHeight - (margins || 0)) }
    function columnsForWidth(contentWidth, wideColumns) {
        return isCompact(contentWidth) ? 1 : (isMedium(contentWidth) ? 2 : Math.max(3, wideColumns || 3))
    }
}
