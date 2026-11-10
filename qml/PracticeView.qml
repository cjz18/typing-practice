import QtQuick

Item {
    id: stage
    objectName: "practiceStage"

    property real shift: 0
    property bool rolling: false
    property bool layingOut: false
    property real glideStart: 0
    readonly property int gap: 140
    readonly property int big: 34
    readonly property int footer: 88
    readonly property int frameStep: Math.max(1, Math.round(1000 / Math.max(1, bridge.frameRate)))
    readonly property color bgColor: Qt.color(bridge.background)

    function lyricCenter() {
        return (height - footer) / 2
    }

    function scaleFor(distance) {
        if (distance <= 0)
            return 1
        if (distance >= 3)
            return 0.48
        if (distance >= 2)
            return 0.6 + (0.48 - 0.6) * (distance - 2)
        if (distance >= 1)
            return 0.78 + (0.6 - 0.78) * (distance - 1)
        return 1 + (0.78 - 1) * distance
    }

    function fadeFor(distance) {
        if (distance <= 0)
            return 1
        if (distance >= 3)
            return 0
        if (distance >= 2)
            return 0.4 * (3 - distance)
        if (distance >= 1)
            return 0.72 + (0.4 - 0.72) * (distance - 1)
        return 1 + (0.72 - 1) * distance
    }

    function smooth(edge0, edge1, value) {
        var span = edge1 - edge0
        if (span <= 0)
            return value >= edge1 ? 1 : 0
        var t = Math.max(0, Math.min(1, (value - edge0) / span))
        return t * t * (3 - 2 * t)
    }

    function edgeFade(item) {
        var center = item.y + item.height / 2
        var distance = Math.abs(center - lyricCenter())
        return 1 - smooth(gap * 1.45, gap * 3.35, distance)
    }

    function mixColors(a, b, t) {
        return Qt.rgba(
            a.r + (b.r - a.r) * t,
            a.g + (b.g - a.g) * t,
            a.b + (b.b - a.b) * t,
            1
        )
    }

    function mixAmount(amount) {
        var fg = Qt.color(bridge.foreground)
        var bg = Qt.color(bridge.background)
        return Qt.rgba(
            fg.r + (bg.r - fg.r) * amount,
            fg.g + (bg.g - fg.g) * amount,
            fg.b + (bg.b - fg.b) * amount,
            1
        )
    }

    // Typed stays readable, untyped falls back toward the background, current stays the chosen color.
    function ink(state) {
        if (state === "error")
            return "#f7768e"
        if (state === "current")
            return Qt.color(bridge.foreground)
        var amount = 0.62
        if (state === "done")
            amount = 0.28
        else if (state === "skip")
            amount = 0.82
        return mixAmount(amount)
    }

    function contextAmount(distance) {
        if (distance <= 1)
            return 0.62
        if (distance >= 3)
            return 0.86
        if (distance >= 2)
            return 0.74 + (0.86 - 0.74) * (distance - 2)
        return 0.62 + (0.74 - 0.62) * (distance - 1)
    }

    function contextColor(distance) {
        return mixAmount(contextAmount(distance))
    }

    function place(line, slot, tint) {
        var distance = Math.abs(slot - shift)
        var mid = lyricCenter()
        line.y = mid + (slot - shift) * gap - line.height / 2
        line.scale = scaleFor(distance)
        if (tint !== undefined)
            line.ink = tint
        var hidden = line.filled === 0 && slot !== 0
        var base = hidden ? 0 : fadeFor(distance)
        line.opacity = base * edgeFade(line)
    }

    function syncLive() {
        var rows = bridge.chars
        var copy = []
        for (var i = 0; i < rows.length; ++i)
            copy.push({ t: rows[i].t, s: rows[i].s })
        liveLine.setRows(copy)
    }

    function stopGlide(arrived) {
        var wasRolling = rolling
        glideTimer.stop()
        rolling = false
        shift = 0
        leavingLine.clearRows()
        if (arrived && wasRolling) {
            liveLine.soften = 1
            softenAnim.restart()
        }
        layout()
    }

    function beginGlide() {
        rolling = true
        leavingLine.setRows(liveLine.rows())
        glideStart = Date.now()
        glideTimer.interval = frameStep
        glideTimer.restart()
        layout()
    }

    function stepGlide() {
        if (glideTimer.interval !== frameStep)
            glideTimer.interval = frameStep
        var elapsed = Date.now() - glideStart
        var t = Math.min(1, elapsed / 520)
        var eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2
        shift = eased
        if (t >= 1) {
            glideTimer.stop()
            bridge.finishScroll()
        }
    }

    function placeHint() {
        var caption = hint.text
        if (rolling || shift !== 0 || caption === "") {
            hint.opacity = 0
            return
        }
        var cell = liveLine.hotCell()
        if (!cell) {
            hint.opacity = 0
            return
        }
        var point = liveLine.mapToItem(stage, cell.x + cell.width / 2, cell.y + liveLine.textBaseline + 10)
        var hintWidth = hint.implicitWidth
        var x = point.x - hintWidth / 2
        if (x < 16)
            x = 16
        if (x + hintWidth > width - 16)
            x = Math.max(16, width - 16 - hintWidth)
        hint.x = x
        hint.y = point.y + 9
        hint.opacity = liveLine.opacity
    }

    function layout() {
        if (layingOut || !liveLine || !tailLine)
            return
        layingOut = true
        var leaveDistance = Math.abs(shift)
        if (leaveDistance >= 1) {
            leavingLine.blend = 1
            leavingLine.ink = contextColor(leaveDistance)
        } else {
            leavingLine.blend = leaveDistance
            leavingLine.ink = contextColor(1)
        }

        var nextDistance = Math.abs(1 - shift)
        var nextTint = contextColor(nextDistance)
        if (rolling && nextDistance < 1)
            nextTint = mixColors(ink("pending"), contextColor(1), nextDistance)

        place(beforeLine, -2, contextColor(Math.abs(-2 - shift)))
        place(prevLine, -1, contextColor(Math.abs(-1 - shift)))
        place(leavingLine, 0)
        place(liveLine, 0)
        place(nextLine, 1, nextTint)
        place(afterLine, 2, contextColor(Math.abs(2 - shift)))
        place(tailLine, 3, contextColor(Math.abs(3 - shift)))

        var liveDistance = Math.abs(shift)
        if (rolling) {
            leavingLine.opacity = leavingLine.filled > 0 ? fadeFor(leaveDistance) * edgeFade(leavingLine) : 0
            liveLine.opacity = 0
        } else {
            leavingLine.opacity = 0
            liveLine.opacity = fadeFor(liveDistance) * edgeFade(liveLine)
        }
        placeHint()
        layingOut = false
    }

    Connections {
        target: bridge
        function onScroll() { stage.beginGlide() }
        function onShiftReset() { stage.stopGlide(false) }
        function onUpdated() {
            var arrived = stage.rolling && !bridge.scrollingNow
            stage.syncLive()
            if (arrived)
                stage.stopGlide(true)
            else
                stage.layout()
        }
        function onConfirmed(index) {
            liveLine.soften = 0
            liveLine.pulseAt(index)
        }
        function onMistyped() {
            liveLine.soften = 0
            liveLine.shakeHot()
        }
    }

    NumberAnimation {
        id: softenAnim
        target: liveLine
        property: "soften"
        to: 0
        duration: 220
        easing.type: Easing.OutCubic
    }

    Timer {
        id: glideTimer
        repeat: true
        interval: stage.frameStep
        onTriggered: stage.stepGlide()
    }

    LyricLine {
        id: beforeLine
        source: bridge.beforeLine
        pixelSize: stage.big
        colorFor: stage.ink
        onRelaid: stage.layout()
    }
    LyricLine {
        id: prevLine
        source: bridge.prevLine
        pixelSize: stage.big
        colorFor: stage.ink
        onRelaid: stage.layout()
    }
    LyricLine {
        id: leavingLine
        frozen: true
        pixelSize: stage.big
        colorFor: stage.ink
        onRelaid: stage.layout()
    }
    LyricLine {
        id: liveLine
        objectName: "liveLine"
        frozen: true
        armed: true
        pixelSize: stage.big
        colorFor: stage.ink
        onRelaid: stage.layout()
    }
    LyricLine {
        id: nextLine
        source: bridge.nextLine
        pixelSize: stage.big
        colorFor: stage.ink
        onRelaid: stage.layout()
    }
    LyricLine {
        id: afterLine
        source: bridge.afterLine
        pixelSize: stage.big
        colorFor: stage.ink
        onRelaid: stage.layout()
    }
    LyricLine {
        id: tailLine
        source: bridge.tailLine
        pixelSize: stage.big
        colorFor: stage.ink
        onRelaid: stage.layout()
    }

    Text {
        id: hint
        objectName: "hintLabel"
        z: 4
        text: bridge.errorText !== "" ? bridge.errorText : (bridge.pinyinTyped + bridge.pinyinRest)
        color: bridge.errorText !== "" ? "#f7768e" : Qt.darker(bridge.foreground, 1.45)
        font.family: bridge.errorText !== "" ? "Microsoft YaHei UI" : bridge.pinyinFont
        font.pixelSize: 18
        onTextChanged: stage.placeHint()
        onImplicitWidthChanged: stage.placeHint()
    }

    onWidthChanged: layout()
    onHeightChanged: layout()
    onShiftChanged: layout()

    Component.onCompleted: {
        syncLive()
        layout()
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 48
        z: 2
        gradient: Gradient {
            GradientStop { position: 0.0; color: bridge.background }
            GradientStop { position: 0.55; color: Qt.rgba(bgColor.r, bgColor.g, bgColor.b, 0.35) }
            GradientStop { position: 1.0; color: Qt.rgba(bgColor.r, bgColor.g, bgColor.b, 0) }
        }
    }
    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.bottomMargin: footer
        height: 48
        z: 2
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(bgColor.r, bgColor.g, bgColor.b, 0) }
            GradientStop { position: 0.45; color: Qt.rgba(bgColor.r, bgColor.g, bgColor.b, 0.35) }
            GradientStop { position: 1.0; color: bridge.background }
        }
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 36
        z: 3
        text: bridge.statsText
        color: Qt.darker(bridge.foreground, 1.7)
        font.family: "Microsoft YaHei UI"
        font.pixelSize: 14
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 8
        z: 3
        text: bridge.noteText !== "" ? bridge.noteText : "请使用英文输入法"
        color: bridge.noteText !== "" ? bridge.foreground : Qt.darker(bridge.foreground, 1.9)
        font.family: "Microsoft YaHei UI"
        font.pixelSize: 13
    }
}
