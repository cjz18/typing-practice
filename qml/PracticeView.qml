import QtQuick

Item {
    id: stage

    property real shift: 0
    readonly property int gap: 124
    readonly property int big: 34
    readonly property int footer: 88
    readonly property color bgColor: Qt.color(bridge.background)

    function lyricCenter() {
        return (height - footer) / 2
    }

    function scaleAt(slot) {
        var distance = Math.min(2, Math.abs(slot - shift))
        return 1 - distance * 0.2
    }

    function fadeAt(slot) {
        var distance = Math.min(2, Math.abs(slot - shift))
        return 1 - distance * 0.16
    }

    function smooth(edge0, edge1, value) {
        var t = Math.max(0, Math.min(1, (value - edge0) / (edge1 - edge0)))
        return t * t * (3 - 2 * t)
    }

    function edgeFade(item) {
        var center = item.y + item.height / 2
        var distance = Math.abs(center - lyricCenter())
        var clearUntil = gap * 1.55
        var goneBy = gap * 3.6
        return 1 - smooth(clearUntil, goneBy, distance)
    }

    function place(line, slot) {
        var mid = lyricCenter()
        line.y = mid + (slot - shift) * gap - line.height / 2
        line.scale = scaleAt(slot)
        var base = line.text === "" && slot !== 0 ? 0 : fadeAt(slot)
        line.opacity = base * edgeFade(line)
    }

    Connections {
        target: bridge
        function onScroll() {
            glide.restart()
        }
        function onShiftReset() {
            stage.shift = 0
        }
    }

    NumberAnimation {
        id: glide
        target: stage
        property: "shift"
        from: 0
        to: 1
        duration: 520
        easing.type: Easing.InOutQuad
        onFinished: bridge.finishScroll()
    }

    LyricText {
        id: beforeLine
        text: bridge.beforeLine
        color: Qt.darker(bridge.foreground, 1.7)
    }
    LyricText {
        id: prevLine
        text: bridge.prevLine
        color: Qt.darker(bridge.foreground, 1.45)
    }
    LyricText {
        id: leavingLine
        text: bridge.currentLine
        color: bridge.foreground
        visible: stage.shift > 0
    }
    Text {
        id: liveLine
        width: parent.width * 0.86
        anchors.horizontalCenter: parent.horizontalCenter
        visible: stage.shift === 0
        text: bridge.currentHtml
        textFormat: Text.RichText
        wrapMode: Text.Wrap
        horizontalAlignment: Text.AlignHCenter
        font.family: "Microsoft YaHei UI"
        font.pixelSize: stage.big
        color: bridge.foreground
    }
    LyricText {
        id: nextLine
        text: bridge.nextLine
        color: Qt.darker(bridge.foreground, 1.45)
    }
    LyricText {
        id: afterLine
        text: bridge.afterLine
        color: Qt.darker(bridge.foreground, 1.7)
    }

    Text {
        id: hint
        anchors.horizontalCenter: parent.horizontalCenter
        y: liveLine.y + liveLine.height + 8
        visible: stage.shift === 0 && (bridge.errorText !== "" || bridge.pinyinTyped !== "" || bridge.pinyinRest !== "")
        text: bridge.errorText !== "" ? bridge.errorText : (bridge.pinyinTyped + bridge.pinyinRest)
        color: bridge.errorText !== "" ? "#f7768e" : Qt.darker(bridge.foreground, 1.5)
        font.family: bridge.errorText !== "" ? "Microsoft YaHei UI" : bridge.pinyinFont
        font.pixelSize: 18
    }

    onWidthChanged: layout()
    onHeightChanged: layout()
    onShiftChanged: layout()
    Connections {
        target: bridge
        function onUpdated() { stage.layout() }
    }

    function ink(state) {
        if (state === "error")
            return "#f7768e"
        var fg = Qt.color(bridge.foreground)
        var bg = Qt.color(bridge.background)
        var amount = state === "current" ? 0 : (state === "done" ? 0.28 : 0.62)
        return Qt.rgba(
            fg.r + (bg.r - fg.r) * amount,
            fg.g + (bg.g - fg.g) * amount,
            fg.b + (bg.b - fg.b) * amount,
            1
        )
    }

    function layout() {
        place(beforeLine, -2)
        place(prevLine, -1)
        place(leavingLine, 0)
        place(nextLine, 1)
        place(afterLine, 2)
        liveLine.y = lyricCenter() - liveLine.height / 2
        liveLine.scale = 1
        liveLine.opacity = stage.shift === 0 ? edgeFade(liveLine) : 0
        hint.opacity = liveLine.opacity
    }

    Component.onCompleted: layout()

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
