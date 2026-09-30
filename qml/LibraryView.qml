import QtQuick
import QtQuick.Controls

Item {
    Column {
        anchors.fill: parent
        anchors.margins: 36
        spacing: 8
        Row {
            width: parent.width
            Text {
                text: "资料库"
                color: bridge.foreground
                font.family: "Microsoft YaHei UI"
                font.pixelSize: 28
            }
            Item { width: parent.width - 220; height: 1 }
            Button {
                text: "继续练习"
                font.family: "Microsoft YaHei UI"
                onClicked: bridge.showPractice()
            }
        }
        Text {
            text: "把 txt 拖进窗口，或点「加入」"
            color: Qt.darker(bridge.foreground, 1.6)
            font.family: "Microsoft YaHei UI"
            font.pixelSize: 14
        }
        Text {
            text: bridge.noteText
            color: bridge.foreground
            font.family: "Microsoft YaHei UI"
            font.pixelSize: 14
        }
        Flickable {
            width: parent.width
            height: parent.height - 120
            contentHeight: grid.height
            clip: true
            Grid {
                id: grid
                width: parent.width
                columns: Math.max(1, Math.floor(width / 180))
                columnSpacing: 28
                rowSpacing: 24
                Repeater {
                    model: bridge.libraryRows
                    delegate: Column {
                        width: 150
                        spacing: 8
                        Rectangle {
                            width: 132
                            height: 180
                            radius: 8
                            color: modelData.color
                            Text {
                                anchors.centerIn: parent
                                width: 100
                                text: modelData.title
                                wrapMode: Text.Wrap
                                horizontalAlignment: Text.AlignHCenter
                                color: "#f7f4ef"
                                font.family: "Microsoft YaHei UI"
                                font.pixelSize: 18
                            }
                            Rectangle {
                                visible: modelData.ratio > 0
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                anchors.margins: 12
                                height: 3
                                radius: 1
                                color: Qt.rgba(0, 0, 0, 0.25)
                                Rectangle {
                                    width: parent.width * modelData.ratio
                                    height: parent.height
                                    color: "#f7f4ef"
                                }
                            }
                            MouseArea {
                                anchors.fill: parent
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                onClicked: function (mouse) {
                                    if (mouse.button === Qt.RightButton)
                                        removeMenu.popup()
                                    else
                                        bridge.openBook(modelData.id)
                                }
                            }
                            Menu {
                                id: removeMenu
                                MenuItem {
                                    text: "从资料库移除"
                                    onTriggered: bridge.removeBook(modelData.id)
                                }
                            }
                        }
                        Text {
                            width: parent.width
                            text: modelData.title
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            color: bridge.foreground
                            font.family: "Microsoft YaHei UI"
                            font.pixelSize: 14
                        }
                        Text {
                            width: parent.width
                            text: modelData.caption
                            horizontalAlignment: Text.AlignHCenter
                            color: Qt.darker(bridge.foreground, 1.6)
                            font.family: "Microsoft YaHei UI"
                            font.pixelSize: 12
                        }
                    }
                }
            }
        }
    }
}
