// Container app. Safari only loads web extensions shipped inside an app, so
// this window exists to say where to switch the extension on.
// Plain AppKit: SwiftUI's @State needs macro plugins that ship only with Xcode.
import AppKit
import SafariServices

let extensionID = "com.ryanwisth.DarkMode.Extension"

final class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    let status = NSTextField(wrappingLabelWithString: "")

    func applicationDidFinishLaunching(_ notification: Notification) {
        let icon = NSImageView(image: NSApp.applicationIconImage)
        icon.translatesAutoresizingMaskIntoConstraints = false
        icon.widthAnchor.constraint(equalToConstant: 96).isActive = true
        icon.heightAnchor.constraint(equalToConstant: 96).isActive = true

        let title = NSTextField(labelWithString: "Dark Mode for Safari")
        title.font = .boldSystemFont(ofSize: 20)

        status.alignment = .center
        status.textColor = .secondaryLabelColor

        let note = NSTextField(wrappingLabelWithString:
            "This copy is built on this Mac and not signed by Apple, so Safari lists it only after "
            + "Settings → Developer → Allow unsigned extensions. Safari clears that setting every time it quits.")
        note.alignment = .center
        note.font = .systemFont(ofSize: NSFont.smallSystemFontSize)
        note.textColor = .tertiaryLabelColor

        let button = NSButton(title: "Open Safari Extensions Settings…", target: self, action: #selector(openSettings))
        button.keyEquivalent = "\r"

        let stack = NSStackView(views: [icon, title, status, note, button])
        stack.orientation = .vertical
        stack.alignment = .centerX
        stack.spacing = 12
        stack.edgeInsets = NSEdgeInsets(top: 28, left: 28, bottom: 28, right: 28)
        for label in [status, note] {
            label.preferredMaxLayoutWidth = 344
            label.widthAnchor.constraint(equalToConstant: 344).isActive = true
        }

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 400, height: 360),
                          styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "Dark Mode for Safari"
        window.contentView = stack
        window.center()
        window.makeKeyAndOrderFront(nil)
        refresh()
    }

    func applicationDidBecomeActive(_ notification: Notification) { refresh() }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    @objc func openSettings() {
        SFSafariApplication.showPreferencesForExtension(withIdentifier: extensionID) { _ in }
    }

    func refresh() {
        SFSafariExtensionManager.getStateOfSafariExtension(withIdentifier: extensionID) { state, _ in
            DispatchQueue.main.async {
                switch state?.isEnabled {
                case .some(true):
                    self.status.stringValue = "The extension is on. Pick a theme from the moon button in Safari's toolbar."
                case .some(false):
                    self.status.stringValue = "The extension is off. Turn on “Dark Mode” in Safari Settings → Extensions."
                case .none:
                    self.status.stringValue = "Turn on “Dark Mode” in Safari Settings → Extensions, then allow it on every website."
                }
            }
        }
    }
}

@main
enum Main {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }
}
