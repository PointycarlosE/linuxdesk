import QtQuick
import Quickshell.Io
import qs.Commons

Item {
    id: root
    property var pluginApi: null

    property bool active: false
    property bool loading: false

    function toggle() {
        if (loading) return
        loading = true
        if (active) {
            stopProcess.running = true
        } else {
            startProcess.running = true
        }
    }

    Process {
        id: startProcess
        command: ["linuxdesk-switch", "on"]
        stdout: StdioCollector {}
        stderr: StdioCollector {}
        onExited: function(exitCode) {
            root.loading = false
            if (exitCode === 0) {
                root.active = true
            }
        }
    }

    Process {
        id: stopProcess
        command: ["linuxdesk-switch", "off"]
        stdout: StdioCollector {}
        stderr: StdioCollector {}
        onExited: function(exitCode) {
            root.loading = false
            root.active = false
        }
    }
}
