.pragma library

function fittedSize(designWidth, designHeight, availableWidth, availableHeight) {
    var safeWidth = availableWidth > 0 ? availableWidth : Math.max(960, designWidth)
    var safeHeight = availableHeight > 0 ? availableHeight : Math.max(540, designHeight)
    return Qt.size(Math.min(designWidth, safeWidth * 0.92),
                   Math.min(designHeight, safeHeight * 0.92))
}
