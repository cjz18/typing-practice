import QtQuick

// One lyric sentence, wrapped like a centered line of type and drawn glyph by glyph
// so the current sentence and the lines around it share the same breaks.
Item {
    id: root

    property string source: ""
    property bool frozen: false
    property color ink: "#c0caf5"
    property int pixelSize: 34
    property real rowSpacing: 44
    property real blend: 0
    property real soften: 0
    property bool armed: false
    property var colorFor: null
    readonly property int filled: units.count
    readonly property real textBaseline: metrics.ascent
    property real contentHeight: pixelSize
    property bool busy: false
    property bool pending: false
    property int layoutTries: 0

    signal relaid()

    width: parent ? parent.width * 0.86 : 0
    height: contentHeight
    anchors.horizontalCenter: parent.horizontalCenter
    transformOrigin: Item.Center

    function mix(a, b, t) {
        return Qt.rgba(
            a.r + (b.r - a.r) * t,
            a.g + (b.g - a.g) * t,
            a.b + (b.b - a.b) * t,
            1
        )
    }

    function glyphColor(state) {
        if (state === "plain" || blend >= 1)
            return ink
        var natural = colorFor ? colorFor(state) : ink
        if (state === "current" && soften > 0 && colorFor)
            natural = mix(natural, colorFor("pending"), soften)
        if (blend <= 0)
            return natural
        return mix(natural, ink, blend)
    }

    function rows() {
        var copy = []
        for (var i = 0; i < units.count; ++i) {
            var row = units.get(i)
            copy.push({ t: row.glyph, s: row.mark })
        }
        return copy
    }

    function setRows(rows) {
        frozen = true
        if (units.count === rows.length && rows.length > 0) {
            var geometry = false
            for (var i = 0; i < rows.length; ++i) {
                var have = units.get(i)
                if (have.glyph !== rows[i].t) {
                    units.setProperty(i, "glyph", rows[i].t)
                    geometry = true
                }
                if (have.mark !== rows[i].s)
                    units.setProperty(i, "mark", rows[i].s)
            }
            if (geometry)
                relayout()
            return
        }
        units.clear()
        for (var j = 0; j < rows.length; ++j)
            units.append({ glyph: rows[j].t, mark: rows[j].s, idx: j })
        relayout()
    }

    function clearRows() {
        frozen = true
        if (units.count === 0)
            return
        units.clear()
        contentHeight = pixelSize
    }

    function rebuildFromSource() {
        if (frozen)
            return
        units.clear()
        for (var i = 0; i < source.length; ++i)
            units.append({ glyph: source.charAt(i), mark: "plain", idx: i })
        relayout()
    }

    function requestLayout() {
        if (pending)
            return
        pending = true
        Qt.callLater(function () {
            pending = false
            relayout()
        })
    }

    function widthOf(item) {
        var drawn = item.glyphImplicit
        if (drawn > 0)
            return drawn
        var measured = metrics.advanceWidth(item.glyphText)
        return measured > 0 ? measured : 0
    }

    function heightOf(item) {
        if (item.textHeight > 0)
            return item.textHeight
        return metrics.height > 0 ? metrics.height : pixelSize
    }

    function canBreakAfter(ch) {
        if (!ch)
            return false
        if (ch === " " || ch === "\t")
            return true
        var code = ch.charCodeAt(0)
        if (code >= 0x2E80 && code <= 0x9FFF)
            return true
        if (code >= 0xF900 && code <= 0xFAFF)
            return true
        if (code >= 0xFF00 && code <= 0xFFEF)
            return true
        if (code >= 0x3000 && code <= 0x303F)
            return true
        return ".,!?;:)]}\"'，。！？；：、）》」』】、".indexOf(ch) >= 0
    }

    function relayout() {
        if (busy)
            return
        if (width < 40 || glyphs.count === 0) {
            contentHeight = pixelSize
            relaid()
            return
        }
        var items = []
        for (var n = 0; n < glyphs.count; ++n) {
            var found = glyphs.itemAt(n)
            if (!found) {
                if (layoutTries < 8) {
                    layoutTries += 1
                    requestLayout()
                }
                return
            }
            items.push(found)
        }
        layoutTries = 0
        busy = true

        var maxWidth = width
        var lines = []
        var line = []
        var lineWidth = 0
        var lastBreak = -1

        function commit(part) {
            if (part.length > 0)
                lines.push(part)
        }

        for (var i = 0; i < items.length; ++i) {
            var item = items[i]
            var itemWidth = widthOf(item)
            if (line.length > 0 && lineWidth + itemWidth > maxWidth + 0.5) {
                if (lastBreak >= 0) {
                    commit(line.slice(0, lastBreak + 1))
                    line = line.slice(lastBreak + 1)
                    lineWidth = 0
                    lastBreak = -1
                    for (var k = 0; k < line.length; ++k) {
                        lineWidth += widthOf(line[k])
                        if (canBreakAfter(line[k].glyphText))
                            lastBreak = k
                    }
                }
                if (line.length > 0 && lineWidth + itemWidth > maxWidth + 0.5) {
                    commit(line)
                    line = []
                    lineWidth = 0
                    lastBreak = -1
                }
            }
            line.push(item)
            lineWidth += itemWidth
            if (canBreakAfter(item.glyphText))
                lastBreak = line.length - 1
        }
        commit(line)

        var top = 0
        for (var r = 0; r < lines.length; ++r) {
            var row = lines[r]
            var rowWidth = 0
            var rowHeight = 0
            var widths = []
            for (var c = 0; c < row.length; ++c) {
                var cellWidth = widthOf(row[c])
                widths.push(cellWidth)
                rowWidth += cellWidth
                rowHeight = Math.max(rowHeight, heightOf(row[c]))
            }
            var x = Math.max(0, (maxWidth - rowWidth) / 2)
            for (var c = 0; c < row.length; ++c) {
                row[c].x = x
                row[c].y = top + rowHeight - heightOf(row[c])
                x += widths[c]
            }
            top += rowHeight
            if (r + 1 < lines.length)
                top += rowSpacing
        }
        contentHeight = Math.max(top, pixelSize)
        busy = false
        relaid()
    }

    function hotCell() {
        for (var i = 0; i < glyphs.count; ++i) {
            var item = glyphs.itemAt(i)
            if (item && item.hot)
                return item
        }
        return null
    }

    function pulseAt(index) {
        var item = glyphs.itemAt(index)
        if (item)
            item.playPulse()
    }

    function shakeHot() {
        var item = hotCell()
        if (item)
            item.playShake()
    }

    onSourceChanged: rebuildFromSource()
    onWidthChanged: requestLayout()
    onPixelSizeChanged: requestLayout()
    Component.onCompleted: rebuildFromSource()

    FontMetrics {
        id: metrics
        font.family: "Microsoft YaHei UI"
        font.pixelSize: root.pixelSize
    }

    ListModel { id: units }

    Repeater {
        id: glyphs
        model: units
        delegate: Item {
            id: cell
            property string glyphText: model.glyph
            property string stateName: model.mark
            property int unitIndex: model.idx
            property real glyphImplicit: glyph.implicitWidth
            property real textHeight: glyph.implicitHeight
            property bool hot: root.armed && (stateName === "current" || stateName === "error")
            property real emphasis: hot ? 1.045 : 1
            property real pulse: 1
            property real flash: 0
            property real breath: 0.8

            width: Math.max(glyphImplicit, 1)
            height: Math.max(glyph.implicitHeight, 1)
            scale: emphasis * pulse
            transformOrigin: Item.Center
            transform: Translate { id: nudge; x: 0 }

            Behavior on emphasis {
                enabled: root.armed
                NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
            }

            function playPulse() {
                pulseAnim.restart()
                flash = 1
                flashAnim.restart()
            }

            function playShake() {
                shakeAnim.restart()
            }

            SequentialAnimation {
                id: pulseAnim
                NumberAnimation {
                    target: cell
                    property: "pulse"
                    to: 1.06
                    duration: 80
                    easing.type: Easing.OutQuad
                }
                NumberAnimation {
                    target: cell
                    property: "pulse"
                    to: 1
                    duration: 170
                    easing.type: Easing.OutQuad
                }
            }
            NumberAnimation {
                id: flashAnim
                target: cell
                property: "flash"
                to: 0
                duration: 220
                easing.type: Easing.OutQuad
            }
            SequentialAnimation {
                running: cell.hot
                loops: Animation.Infinite
                NumberAnimation {
                    target: cell
                    property: "breath"
                    to: 1
                    duration: 900
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    target: cell
                    property: "breath"
                    to: 0.55
                    duration: 900
                    easing.type: Easing.InOutSine
                }
            }
            SequentialAnimation {
                id: shakeAnim
                NumberAnimation { target: nudge; property: "x"; to: 3.5; duration: 36; easing.type: Easing.OutQuad }
                NumberAnimation { target: nudge; property: "x"; to: -3; duration: 42; easing.type: Easing.InOutQuad }
                NumberAnimation { target: nudge; property: "x"; to: 2; duration: 36; easing.type: Easing.InOutQuad }
                NumberAnimation { target: nudge; property: "x"; to: 0; duration: 50; easing.type: Easing.OutQuad }
            }

            Text {
                id: glyph
                text: cell.glyphText
                font.family: "Microsoft YaHei UI"
                font.pixelSize: root.pixelSize
                renderType: Text.QtRendering
                color: {
                    var _watch = bridge.foreground + bridge.background + root.blend + root.soften + root.ink + cell.flash + cell.stateName
                    var _unused = _watch.length
                    var base = root.glyphColor(cell.stateName)
                    if (cell.flash <= 0)
                        return base
                    var lifted = Qt.rgba(
                        Math.min(1, base.r + 0.22),
                        Math.min(1, base.g + 0.22),
                        Math.min(1, base.b + 0.16),
                        1
                    )
                    return root.mix(base, lifted, cell.flash)
                }
                Behavior on color {
                    enabled: root.armed && root.blend === 0
                    ColorAnimation { duration: 150; easing.type: Easing.OutCubic }
                }
                onImplicitWidthChanged: {
                    if (!root.busy)
                        root.requestLayout()
                }
            }

            Rectangle {
                x: (cell.width - width) / 2
                y: root.textBaseline + 2
                width: Math.max(8, cell.glyphImplicit)
                height: 2
                radius: 1
                antialiasing: true
                color: cell.stateName === "error" ? "#f7768e" : bridge.foreground
                opacity: cell.hot ? cell.breath * (1 - root.soften * 0.85) : 0
            }
        }
    }
}
