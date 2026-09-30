import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window
    width: 980
    height: 760
    minimumWidth: 760
    minimumHeight: 680
    visible: true
    title: "打字练习"
    color: bridge.background

    header: Rectangle {
        color: bridge.background
        height: 48
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 24
            anchors.rightMargin: 24
            ToolButton {
                implicitWidth: 96
                implicitHeight: 36
                text: "资料库"
                font.family: "Microsoft YaHei UI"
                font.pixelSize: 15
                contentItem: Row {
                    spacing: 6
                    Icon { name: "books"; tint: bridge.foreground; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: "资料库"
                        color: bridge.foreground
                        font.family: "Microsoft YaHei UI"
                        font.pixelSize: 15
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                background: Rectangle { color: "transparent" }
                onClicked: bridge.showLibrary()
            }
            Item { Layout.fillWidth: true }
            Text {
                text: bridge.pageName === "practice" ? bridge.placeText : ""
                color: Qt.rgba(0, 0, 0, 0.45)
                font.family: "Microsoft YaHei UI"
                font.pixelSize: 14
            }
            ToolButton {
                implicitWidth: 72
                implicitHeight: 36
                visible: bridge.pageName === "library"
                text: "加入"
                font.family: "Microsoft YaHei UI"
                contentItem: Row {
                    spacing: 6
                    Icon { name: "plus"; tint: bridge.foreground; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: "加入"
                        color: bridge.foreground
                        font.family: "Microsoft YaHei UI"
                        font.pixelSize: 15
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                background: Rectangle { color: "transparent" }
                onClicked: bridge.pickFiles()
            }
            ToolButton {
                implicitWidth: 36
                implicitHeight: 36
                background: Rectangle { color: "transparent" }
                contentItem: Icon { name: "dots-three"; tint: bridge.foreground; anchors.centerIn: parent }
                onClicked: bridge.toggleMenu()
            }
        }
    }

    Column {
        visible: bridge.menuOpen && bridge.pageName === "practice"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 24
        spacing: 8
        z: 2
        Row {
            spacing: 8
            MenuChip { label: "英文"; iconName: "text-aa"; selected: bridge.modeName === "en"; onClicked: bridge.useMode("en") }
            MenuChip { label: "中文拼音"; iconName: "translate"; selected: bridge.modeName === "zh"; onClicked: bridge.useMode("zh") }
            MenuChip { label: "换一篇"; iconName: "arrow-clockwise"; onClicked: bridge.nextPiece() }
            MenuChip { label: "重来"; iconName: "arrow-counter-clockwise"; onClicked: bridge.restart() }
            MenuChip { label: "资料库"; iconName: "books"; onClicked: bridge.showLibrary() }
            MenuChip { label: "粘贴文本"; iconName: "clipboard-text"; onClicked: bridge.paste() }
            MenuChip { label: "设置"; iconName: "gear"; onClicked: bridge.showSettings() }
        }
    }

    PracticeView { anchors.fill: parent; visible: bridge.pageName === "practice" }
    LibraryView { anchors.fill: parent; visible: bridge.pageName === "library" }
    SettingsView { anchors.fill: parent; visible: bridge.pageName === "settings" }

    DropArea {
        anchors.fill: parent
        keys: ["text/uri-list"]
        onEntered: function (drag) {
            drag.accept(Qt.CopyAction)
        }
        onDropped: function (drop) {
            drop.accept(Qt.CopyAction)
            if (!drop.hasUrls)
                return
            var paths = []
            for (var i = 0; i < drop.urls.length; i++)
                paths.push(drop.urls[i] + "")
            Qt.callLater(function () { bridge.addPaths(paths) })
        }
    }
}
