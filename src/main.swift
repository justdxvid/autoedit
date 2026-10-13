// AutoEdit companion: a floating panel that behaves like a FilmCraft plugin.
// Lives in the menu bar, shows its panel whenever FilmCraft is running and hides it when FilmCraft quits.
import Cocoa
import WebKit

let home = NSString(string: "~/Library/Application Support/AutoEdit/app").expandingTildeInPath
let dir = ProcessInfo.processInfo.environment["AUTOEDIT_DIR"] ?? home
let uiURL = URL(string: "http://127.0.0.1:8765")!

func serverUp() -> Bool {
    var ok = false
    let sem = DispatchSemaphore(value: 0)
    var req = URLRequest(url: uiURL.appendingPathComponent("status")); req.timeoutInterval = 0.6
    URLSession.shared.dataTask(with: req) { d, _, _ in ok = d != nil; sem.signal() }.resume()
    _ = sem.wait(timeout: .now() + 1)
    return ok
}

func isFilmCraft(_ app: NSRunningApplication?) -> Bool { app?.localizedName == "FilmCraft" }

// Clicks must reach the page even when the panel isn't the focused window yet.
class ClickThroughWebView: WKWebView {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}

class Panel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

class Delegate: NSObject, NSApplicationDelegate, WKUIDelegate, NSWindowDelegate {
    var panel: NSPanel!
    var web: WKWebView!
    var status: NSStatusItem!
    var server: Process?

    func applicationDidFinishLaunching(_ n: Notification) {
        startServer()
        buildPanel()
        buildMenu()
        let ws = NSWorkspace.shared.notificationCenter
        ws.addObserver(forName: NSWorkspace.didLaunchApplicationNotification, object: nil, queue: .main) { [weak self] n in
            if isFilmCraft(n.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication) {
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) { self?.show() }
            }
        }
        ws.addObserver(forName: NSWorkspace.didTerminateApplicationNotification, object: nil, queue: .main) { [weak self] n in
            if isFilmCraft(n.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication) { self?.panel.orderOut(nil) }
        }
        if NSWorkspace.shared.runningApplications.contains(where: isFilmCraft) { show() }
    }

    func startServer() {
        if serverUp() { return }
        let py = ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"].first { FileManager.default.fileExists(atPath: $0) }!
        let p = Process()
        p.executableURL = URL(fileURLWithPath: py)
        p.arguments = ["app.py"]
        p.currentDirectoryURL = URL(fileURLWithPath: dir)
        var env = ProcessInfo.processInfo.environment; env["AUTOEDIT_NO_BROWSER"] = "1"; p.environment = env
        try? p.run(); server = p
        for _ in 0..<20 { if serverUp() { break }; Thread.sleep(forTimeInterval: 0.25) }
    }

    func buildPanel() {
        let screen = NSScreen.main!.visibleFrame
        let w: CGFloat = 400, h = min(780, screen.height - 40)
        panel = Panel(contentRect: NSRect(x: screen.maxX - w - 16, y: screen.maxY - h - 16, width: w, height: h),
                        styleMask: [.titled, .closable, .resizable, .utilityWindow],
                        backing: .buffered, defer: false)
        panel.title = "AutoEdit"
        panel.isFloatingPanel = true
        panel.level = .floating
        panel.hidesOnDeactivate = false
        panel.becomesKeyOnlyIfNeeded = false
        panel.isReleasedWhenClosed = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.setFrameAutosaveName("AutoEditPanel")   // remembers where you put it
        panel.delegate = self
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = .nonPersistent()          // no disk cache: always show the current page
        cfg.applicationNameForUserAgent = "AutoEdit"
        web = ClickThroughWebView(frame: panel.contentView!.bounds, configuration: cfg)
        web.autoresizingMask = [.width, .height]
        web.uiDelegate = self
        panel.contentView!.addSubview(web)
    }

    func buildMenu() {
        status = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        status.button?.image = NSImage(systemSymbolName: "scissors", accessibilityDescription: "AutoEdit")
        let m = NSMenu()
        m.addItem(withTitle: "Show AutoEdit Panel", action: #selector(showFromMenu), keyEquivalent: "")
        m.addItem(withTitle: "Open in Browser Instead", action: #selector(openBrowser), keyEquivalent: "")
        m.addItem(.separator())
        m.addItem(withTitle: "Quit AutoEdit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        status.menu = m
    }

    @objc func showFromMenu() { show() }
    @objc func openBrowser() { NSWorkspace.shared.open(uiURL) }

    func show() {
        startServer()
        web.load(URLRequest(url: uiURL, cachePolicy: .reloadIgnoringLocalAndRemoteCacheData))
        panel.orderFrontRegardless()
        panel.makeKey()
    }

    func windowShouldClose(_ w: NSWindow) -> Bool { panel.orderOut(nil); return false }   // close = hide

    func webView(_ w: WKWebView, runOpenPanelWith p: WKOpenPanelParameters, initiatedByFrame f: WKFrameInfo, completionHandler ch: @escaping ([URL]?) -> Void) {
        let o = NSOpenPanel(); o.allowsMultipleSelection = p.allowsMultipleSelection
        o.begin { r in ch(r == .OK ? o.urls : nil) }
    }

    func applicationWillTerminate(_ n: Notification) { server?.terminate() }
}

let app = NSApplication.shared
let d = Delegate(); app.delegate = d
app.setActivationPolicy(.accessory)   // menu-bar only, no Dock icon
app.run()
