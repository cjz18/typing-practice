import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    Flickable {
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.height + 48
        Column {
            id: column
            x: 48
            y: 28
            width: Math.min(680, parent.width - 96)
            spacing: 18

            Row {
                width: parent.width
                Text {
                    text: "设置"
                    color: bridge.foreground
                    font.family: "Microsoft YaHei UI"
                    font.pixelSize: 28
                }
                Item { width: parent.width - 160; height: 1 }
                Button {
                    text: "完成"
                    font.family: "Microsoft YaHei UI"
                    onClicked: bridge.closeSettings()
                }
            }
            Text {
                text: "打字练习 1.0.0  ·  进度和日志只保存在这台电脑上"
                color: Qt.darker(bridge.foreground, 1.6)
                font.family: "Microsoft YaHei UI"
                font.pixelSize: 13
            }

            Text { text: "练习"; color: Qt.darker(bridge.foreground, 1.5); font.family: "Microsoft YaHei UI" }
            Rectangle {
                width: parent.width
                height: form1.height + 16
                radius: 12
                color: Qt.rgba(1, 1, 1, 0.06)
                Column {
                    id: form1
                    x: 16
                    y: 8
                    width: parent.width - 32
                    Switch {
                        text: "核对标点"
                        checked: bridge.punctOn
                        onToggled: bridge.setPunct(checked)
                        font.family: "Microsoft YaHei UI"
                    }
                    Switch {
                        text: "显示拼音"
                        enabled: bridge.chinese
                        checked: bridge.pinyinOn
                        onToggled: bridge.setPinyin(checked)
                        font.family: "Microsoft YaHei UI"
                    }
                }
            }

            Text { text: "动画"; color: Qt.darker(bridge.foreground, 1.5); font.family: "Microsoft YaHei UI" }
            Row {
                spacing: 8
                Repeater {
                    model: [30, 60, 120, 240]
                    delegate: Button {
                        text: modelData
                        highlighted: bridge.frameRate === modelData
                        onClicked: bridge.setFps(modelData)
                    }
                }
            }

            Text { text: "外观"; color: Qt.darker(bridge.foreground, 1.5); font.family: "Microsoft YaHei UI" }
            Row {
                spacing: 12
                Button { text: "背景 " + bridge.background; onClicked: bridge.pickColor("bg") }
                Button { text: "字体 " + bridge.foreground; onClicked: bridge.pickColor("fg") }
            }
            Button {
                text: "恢复默认"
                onClicked: bridge.restoreDefaults()
            }
        }
    }
}
