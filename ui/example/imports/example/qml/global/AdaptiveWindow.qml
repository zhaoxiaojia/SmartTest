import QtQuick 2.15
import QtQuick.Window 2.15

QtObject {
    id: root
    property var target
    property real designWidth: 1000
    property real designHeight: 668
    property real preferredMinimumWidth: 668
    property real preferredMinimumHeight: 320
    property real availableRatio: 0.92
    property bool ready: false

    function validGeometry(geometry) {
        return geometry && geometry.width > 0 && geometry.height > 0
    }

    function screenGeometries() {
        var result = []
        var screens = Qt.application.screens || []
        for (var i = 0; i < screens.length; ++i) {
            var geometry = screens[i].availableGeometry
            if (validGeometry(geometry))
                result.push(Qt.rect(geometry.x, geometry.y, geometry.width, geometry.height))
        }
        return result
    }

    function selectGeometry(geometries, savedX, savedY, savedWidth, savedHeight, fallbackGeometry) {
        var hasSavedRect = savedX > -100000 && savedY > -100000 && savedWidth > 0 && savedHeight > 0
        if (hasSavedRect) {
            var centerX = savedX + savedWidth / 2
            var centerY = savedY + savedHeight / 2
            for (var i = 0; i < geometries.length; ++i) {
                var candidate = geometries[i]
                if (centerX >= candidate.x && centerX < candidate.x + candidate.width
                        && centerY >= candidate.y && centerY < candidate.y + candidate.height)
                    return candidate
            }
        }
        if (validGeometry(fallbackGeometry))
            return fallbackGeometry
        if (geometries.length > 0)
            return geometries[0]
        return Qt.rect(0, 0, Math.max(960, designWidth), Math.max(540, designHeight))
    }

    function currentGeometry() {
        var geometry = target && target.screen ? target.screen.availableGeometry : null
        return selectGeometry(screenGeometries(), -100000, -100000, 0, 0, geometry)
    }

    function boundedSize(requestedWidth, requestedHeight, geometry) {
        var bounds = validGeometry(geometry) ? geometry : currentGeometry()
        return Qt.size(Math.max(1, Math.min(requestedWidth, bounds.width * availableRatio)),
                       Math.max(1, Math.min(requestedHeight, bounds.height * availableRatio)))
    }

    function constrainToAvailableGeometry(geometry) {
        if (!target)
            return
        var bounds = validGeometry(geometry) ? geometry : currentGeometry()
        target.minimumWidth = Math.min(preferredMinimumWidth, bounds.width)
        target.minimumHeight = Math.min(preferredMinimumHeight, bounds.height)
        if (target.visibility !== Window.Maximized && target.visibility !== Window.FullScreen) {
            var size = boundedSize(target.width, target.height, bounds)
            target.width = size.width
            target.height = size.height
            target.x = Math.max(bounds.x, Math.min(target.x, bounds.x + bounds.width - target.width))
            target.y = Math.max(bounds.y, Math.min(target.y, bounds.y + bounds.height - target.height))
        }
        ready = true
    }

    function restoreGeometry(savedX, savedY, savedWidth, savedHeight) {
        if (!target)
            return
        var widthToRestore = savedWidth > 0 ? savedWidth : designWidth
        var heightToRestore = savedHeight > 0 ? savedHeight : designHeight
        var fallback = target.screen ? target.screen.availableGeometry : null
        var geometry = selectGeometry(screenGeometries(), savedX, savedY,
                                      widthToRestore, heightToRestore, fallback)
        target.width = widthToRestore
        target.height = heightToRestore
        if (savedX > -100000 && savedY > -100000) {
            target.x = savedX
            target.y = savedY
        }
        constrainToAvailableGeometry(geometry)
    }

}
