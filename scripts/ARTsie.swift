import AppKit
import WebKit

final class Studio: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {
    var window: NSWindow!
    var server: Process?
    let root = Bundle.main.bundleURL.deletingLastPathComponent()
    let address = URL(string: "http://127.0.0.1:8743")!

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu()
        let item = NSMenuItem()
        menu.addItem(item)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "About ARTsie", action: #selector(about), keyEquivalent: "")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Quit ARTsie", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        item.submenu = appMenu
        let editItem = NSMenuItem()
        menu.addItem(editItem)
        let edit = NSMenu(title: "Edit")
        edit.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = edit
        NSApp.mainMenu = menu
        window = NSWindow(contentRect: NSRect(x: 0,y: 0,width: 1280,height: 920), styleMask: [.titled,.closable,.miniaturizable,.resizable], backing: .buffered, defer: false)
        window.title = "ARTsie"
        window.minSize = NSSize(width: 700,height: 600)
        window.center()
        window.setFrameAutosaveName("ARTsieStudio")
        let web = WKWebView(frame: window.contentView!.bounds)
        web.autoresizingMask = [.width,.height]
        web.navigationDelegate = self
        web.uiDelegate = self
        window.contentView = web
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        ensureServer(web, attempt: 0)
    }

    func ensureServer(_ web: WKWebView, attempt: Int) {
        var request = URLRequest(url: address.appendingPathComponent("api/status"))
        request.timeoutInterval = 1
        URLSession.shared.dataTask(with: request) { data, _, _ in
            DispatchQueue.main.async {
                if let data = data, let object = try? JSONSerialization.jsonObject(with: data) as? [String:Any], object["service"] as? String == "ARTsie" {
                    web.load(URLRequest(url: self.address))
                } else if attempt == 0 {
                    do {
                        let configData = try Data(contentsOf: self.root.appendingPathComponent("config/runtime.json"))
                        let config = try JSONSerialization.jsonObject(with: configData) as! [String:String]
                        let process = Process()
                        process.executableURL = URL(fileURLWithPath: config["python"]!)
                        process.arguments = [self.root.appendingPathComponent("artsie.py").path, "serve"]
                        process.currentDirectoryURL = self.root
                        let logURL = self.root.appendingPathComponent("logs/hub.log")
                        FileManager.default.createFile(atPath: logURL.path, contents: nil)
                        let log = try FileHandle(forWritingTo: logURL)
                        log.seekToEndOfFile()
                        process.standardOutput = log
                        process.standardError = log
                        try process.run()
                        self.server = process
                        DispatchQueue.main.asyncAfter(deadline: .now()+0.3) { self.ensureServer(web, attempt: 1) }
                    } catch { self.error(error.localizedDescription) }
                } else if attempt < 20 {
                    DispatchQueue.main.asyncAfter(deadline: .now()+0.3) { self.ensureServer(web, attempt: attempt+1) }
                } else {
                    self.error("The local hub could not start. Check logs/hub.log or whether port 8743 is already in use.")
                }
            }
        }.resume()
    }
    func error(_ message: String) { let alert=NSAlert(); alert.messageText="ARTsie couldn’t start";alert.informativeText=message;alert.runModal() }
    @objc func about() { let alert=NSAlert();alert.messageText="ARTsie";alert.informativeText="A local workspace for the ArtCraft suite.\n13 native apps, shared files and an MCP gateway.\nArtCraft apps are by the storytold team; licenses are included in sources/.";alert.runModal() }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    // Keep the loopback service alive so an LLM's editing session survives closing the hub.
    func applicationWillTerminate(_ notification: Notification) { }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url=navigationAction.request.url else { decisionHandler(.cancel); return }
        if url.host == "127.0.0.1" && url.port == 8743 { decisionHandler(.allow) }
        else { if ["https","http"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }; decisionHandler(.cancel) }
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url=navigationAction.request.url, url.scheme=="https" { NSWorkspace.shared.open(url) }; return nil
    }
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert=NSAlert();alert.messageText=message;alert.runModal();completionHandler()
    }
    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let alert=NSAlert();alert.messageText=prompt;alert.addButton(withTitle:"OK");alert.addButton(withTitle:"Cancel")
        let input=NSTextField(frame:NSRect(x:0,y:0,width:330,height:25));input.stringValue=defaultText ?? "";alert.accessoryView=input;alert.window.initialFirstResponder=input
        let result=alert.runModal();completionHandler(result == .alertFirstButtonReturn ? input.stringValue : nil)
    }
}
let app=NSApplication.shared
let delegate=Studio()
app.delegate=delegate
app.setActivationPolicy(.regular)
app.run()
