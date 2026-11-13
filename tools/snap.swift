// Test harness: load a page in the system WebKit (the engine Safari uses),
// inject the extension's content scripts with a fake `browser` API, and save
// a PNG. Optionally run a JS expression afterwards and print its result.
//
// Build: swiftc -O tools/snap.swift -o build/snap
// Use:   build/snap <url|file> <out.png> [--settings JSON] [--dark] [--width N] [--height N]
//                    [--wait SECONDS] [--eval JS] [--scroll PX] [--no-inject] [--popup]
import AppKit
import WebKit

var args = Array(CommandLine.arguments.dropFirst())
func opt(_ name: String) -> String? {
    guard let i = args.firstIndex(of: name), i + 1 < args.count else { return nil }
    let v = args[i + 1]; args.removeSubrange(i...(i + 1)); return v
}
func flag(_ name: String) -> Bool {
    guard let i = args.firstIndex(of: name) else { return false }
    args.remove(at: i); return true
}

let settingsJSON = opt("--settings") ?? "{}"
let width = Double(opt("--width") ?? "1200")!
let height = Double(opt("--height") ?? "800")!
let wait = Double(opt("--wait") ?? "2.0")!
let evalJS = opt("--eval")
let scroll = opt("--scroll")
let dark = flag("--dark")
let noInject = flag("--no-inject")
let popup = flag("--popup")
guard args.count == 2 else {
    FileHandle.standardError.write("usage: snap <url|file> <out.png> [options]\n".data(using: .utf8)!)
    exit(2)
}
let target = args[0], outPath = args[1]
let extDir = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
    .appendingPathComponent("extension")

func read(_ name: String) -> String { (try? String(contentsOf: extDir.appendingPathComponent(name), encoding: .utf8)) ?? "" }

// Minimal stand-in for the WebExtension APIs the scripts touch.
let shim = """
(() => {
  let store = { sdm: \(settingsJSON), sdmNative: {} };
  const listeners = [];
  globalThis.browser = {
    storage: {
      local: {
        get: async (keys) => { const o = {}; for (const k of [].concat(keys)) if (k in store) o[k] = store[k]; return o; },
        set: async (obj) => {
          const changes = {};
          for (const k in obj) { changes[k] = { oldValue: store[k], newValue: obj[k] }; store[k] = obj[k]; }
          listeners.forEach((l) => l(changes, 'local'));
        },
      },
      onChanged: { addListener: (f) => listeners.push(f) },
    },
    runtime: { onMessage: { addListener: () => {} } },
    tabs: {
      query: async () => [{ id: 1 }],
      sendMessage: async () => ({ host: 'en.wikipedia.org', active: true, nativeDark: false, siteMode: 'auto' }),
    },
  };
})();
"""

final class Runner: NSObject, WKNavigationDelegate {
    let web: WKWebView
    let window: NSWindow
    var done = false

    override init() {
        let cfg = WKWebViewConfiguration()
        if !noInject && !popup {
            let src = [shim, read("themes.js"), read("shared.js"), read("content.js")].joined(separator: "\n;\n")
            cfg.userContentController.addUserScript(WKUserScript(source: src, injectionTime: .atDocumentStart,
                                                                 forMainFrameOnly: true, in: .defaultClient))
        }
        if popup {
            cfg.userContentController.addUserScript(WKUserScript(source: shim, injectionTime: .atDocumentStart,
                                                                 forMainFrameOnly: true, in: .page))
        }
        web = WKWebView(frame: NSRect(x: 0, y: 0, width: width, height: height), configuration: cfg)
        window = NSWindow(contentRect: NSRect(x: -20000, y: -20000, width: width, height: height),
                          styleMask: [.borderless], backing: .buffered, defer: false)
        super.init()
        window.contentView = web
        window.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
        web.appearance = window.appearance
        web.navigationDelegate = self
        window.orderFrontRegardless()
    }

    func start() {
        if target.hasPrefix("http") {
            web.load(URLRequest(url: URL(string: target)!))
        } else {
            let u = URL(fileURLWithPath: target)
            web.loadFileURL(u, allowingReadAccessTo: popup ? extDir : u.deletingLastPathComponent())
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 30) { if !self.done { self.finish() } }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        DispatchQueue.main.asyncAfter(deadline: .now() + wait) { self.finish() }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        print("load failed: \(error.localizedDescription)"); finish()
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        print("load failed: \(error.localizedDescription)"); finish()
    }

    func finish() {
        guard !done else { return }
        done = true
        let snapshot = {
            let conf = WKSnapshotConfiguration()
            self.web.takeSnapshot(with: conf) { image, err in
                guard let image, let tiff = image.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
                      let png = rep.representation(using: .png, properties: [:]) else {
                    print("snapshot failed: \(String(describing: err))"); exit(1)
                }
                try! png.write(to: URL(fileURLWithPath: outPath))
                if let js = evalJS {
                    self.web.evaluateJavaScript(js, in: nil, in: .page) { result in
                        switch result {
                        case .success(let v): print("eval:", v)
                        case .failure(let e): print("eval error:", e)
                        }
                        exit(0)
                    }
                } else { exit(0) }
            }
        }
        if let px = scroll {
            web.evaluateJavaScript("window.scrollTo(0, \(px)); 1") { _, _ in
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.6, execute: snapshot)
            }
        } else { snapshot() }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let runner = Runner()
runner.start()
app.run()
