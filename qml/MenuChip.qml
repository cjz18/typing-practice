import QtQuick
import QtQuick.Controls

Button {
    id: chip
    property string label: ""
    property string iconName: ""
    property bool selected: false
    padding: 10
    leftPadding: 12
    rightPadding: 14
    font.family: "Microsoft YaHei UI"
    font.pixelSize: 15

    contentItem: Row {
        spacing: 6
        Icon {
            name: chip.iconName
            box: 16
            tint: chip.selected ? "#1a1b26" : bridge.foreground
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text: chip.label
            color: chip.selected ? "#1a1b26" : bridge.foreground
            font.family: "Microsoft YaHei UI"
            font.pixelSize: 15
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    background: Rectangle {
        radius: 8
        color: chip.selected ? "#7aa2f7" : Qt.rgba(1, 1, 1, 0.08)
    }
}
