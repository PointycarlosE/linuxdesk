import QtQuick
import Quickshell
import qs.Commons
import qs.Modules.Bar.Extras
import qs.Services.UI
import qs.Widgets

Item {
    id: root
    property var pluginApi: null
    property ShellScreen screen
    property string widgetId: ""
    property string section: ""
    property int sectionWidgetIndex: -1
    property int sectionWidgetsCount: 0

    implicitWidth: pill.width
    implicitHeight: pill.height

    readonly property var main: pluginApi?.mainInstance

    BarPill {
        id: pill
        screen: root.screen
        oppositeDirection: BarService.getPillDirection(root)
        icon: main?.loading ? "loader" : (main?.active ? "monitor-smartphone" : "monitor-x")
        tooltipText: main?.active ? "LinuxDesk ativo — clique para desligar" : "LinuxDesk — clique para ligar"
        autoHide: false
        onClicked: {
            main?.toggle()
        }
    }
}
