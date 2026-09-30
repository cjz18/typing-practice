import QtQuick
import Qt5Compat.GraphicalEffects

Item {
    id: root
    property string name: ""
    property color tint: bridge.foreground
    property int box: 18
    width: box
    height: box

    Image {
        id: src
        anchors.fill: parent
        source: bridge.iconUrl(root.name)
        sourceSize.width: root.box
        sourceSize.height: root.box
        visible: false
        fillMode: Image.PreserveAspectFit
    }

    ColorOverlay {
        anchors.fill: src
        source: src
        color: root.tint
    }
}
