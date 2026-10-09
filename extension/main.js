// SPDX-License-Identifier: Apache-2.0
/* Packet Tracer script engine. Only structured, named tools are dispatched. */
var agentWindow = null;
var agentMenuId = "";
var cliTasks = {};
var agentExpanded = false;

function main() {
    var menu = ipc.appWindow().getMenuBar().getExtensionsPopupMenu();
    agentMenuId = menu.insertItem("", "Packet Tracer Agent");
    menu.getMenuItemByUuid(agentMenuId).registerEvent("onClicked", null, openAgent);
    openAgent();
}

function openAgent() {
    var alive = false;
    if (agentWindow) {
        try { alive = webViewManager.getWebView(agentWindow.getWebViewId()) != null; } catch (e) {}
    }
    if (!alive) {
        agentExpanded = false;
        agentWindow = webViewManager.createWebView("Packet Tracer Agent", "this-sm:index.html", 680, 720);
        try { agentWindow.setMinimumSize(480, 540); agentWindow.setPreferredSize(680, 720); } catch (e) {}
        try { agentWindow.dockToMainViewArea(); } catch (e) { dprint("Dock unavailable; opening an in-app window: " + e); }
    }
    agentWindow.show();
}

function expandAgent() {
    if (!agentWindow) return;
    try {
        if (agentExpanded) {
            agentWindow.showNormal();
            agentWindow.setPreferredSize(680, 720);
            agentWindow.dockToMainViewArea();
            agentExpanded = false;
        } else {
            agentWindow.undockFromMainViewArea();
            agentExpanded = true;
            agentWindow.showMaximized();
        }
        agentWindow.show();
        agentWindow.evaluateJavaScriptAsync("window.agentWindowState(" + agentExpanded + ")");
    } catch (e) {
        agentWindow.evaluateJavaScriptAsync("window.agentWindowState(" + agentExpanded + ")");
        dprint("Could not resize Agent window: " + e);
    }
}

function cleanUp() {
    for (var id in cliTasks) { if (cliTasks.hasOwnProperty(id)) cliTasks[id].finish(true); }
    try { if (agentMenuId) ipc.appWindow().getMenuBar().getExtensionsPopupMenu().removeItemUuid(agentMenuId); } catch (e) {}
    try { if (agentWindow) agentWindow.close(); } catch (e) {}
    agentWindow = null;
}

function deliver(id, result) {
    if (agentWindow) agentWindow.evaluateJavaScriptAsync("window.agentResult(" + JSON.stringify(id) + "," + JSON.stringify(result) + ")");
}

function optionalRead(obj, method) {
    try { var value = obj[method](); return value === undefined ? null : value; } catch (e) { return null; }
}

function findDevice(name) {
    var d = ipc.network().getDevice(name);
    if (!d) throw new Error("Device does not exist: " + name);
    return d;
}

function describeDevice(d, detail) {
    var info = {name: d.getName(), model: d.getModel(), type: d.getType(), power: d.getPower(),
                x: d.getXCoordinate(), y: d.getYCoordinate(), ports: []};
    var count = d.getPortCount();
    for (var i = 0; i < count; i++) {
        var p = d.getPortAt(i);
        var item = {name: p.getName(), up: optionalRead(p, "isPortUp"), protocol_up: optionalRead(p, "isProtocolUp"),
                    peer_port: ""};
        try {
            var link = p.getLink();
            item.connected = Boolean(link);
        } catch (e) {}
        if (detail) {
            item.address = optionalRead(p, "getIpAddress");
            item.mask = optionalRead(p, "getSubnetMask");
            // HostPort exposes setDefaultGateway, but no getter in PT 9.
            // Read host gateways with ipconfig instead of an unsupported IPC call.
            item.gateway = null;
            item.mac = optionalRead(p, "getMacAddress");
        }
        info.ports.push(item);
    }
    if (detail) {
        try {
            var cl = d.getCommandLine();
            info.cli = {mode: cl.getMode(), prompt: cl.getPrompt()};
            try { info.cli.recent_output = cl.getOutput().slice(-2000); } catch (e) {}
        } catch (e) { info.cli = null; }
    }
    return info;
}

function parsePing(output, timedOut) {
    if (timedOut) return {passed: null, status: "unknown", reason: "Command timed out"};
    var ios = /Success rate is\s+(\d+)\s*percent/i.exec(output);
    var pc = /Sent\s*=\s*(\d+)\s*,\s*Received\s*=\s*(\d+)/i.exec(output);
    if (ios) return {passed: Number(ios[1]) === 100, status: Number(ios[1]) === 100 ? "passed" : "failed", success_percent: Number(ios[1])};
    if (pc) {
        var allReceived = Number(pc[1]) > 0 && Number(pc[1]) === Number(pc[2]);
        return {passed: allReceived, status: allReceived ? "passed" : "failed", sent: Number(pc[1]), received: Number(pc[2])};
    }
    return {passed: null, status: "unknown", reason: "No complete ping summary in terminal output"};
}

function startCli(job, ping) {
    var d = findDevice(job.args.device);
    var cl = d.getCommandLine();
    if (!cl) throw new Error("Device has no CLI: " + job.args.device);
    var command = ping ? "ping " + job.args.address : job.args.command;
    if (/[\r\n\x00;]/.test(command)) throw new Error("Use a single command");
    var initialMode = String(cl.getMode()), initialPrompt = String(cl.getPrompt());
    if (!initialMode || initialMode === "logout") {
        var startupReply = /\[yes\/no\]/i.test(initialPrompt) && /^(yes|no)$/i.test(command.trim());
        if (command !== "" && command !== "\x03" && !startupReply) {
            throw new Error("CLI is not ready for commands (mode: " + initialMode + ", prompt: " + initialPrompt +
                "). Wait for boot, answer the startup yes/no prompt, or send an empty command to press Return. Cancel a setup wizard with Ctrl+C before configuring.");
        }
    }
    var before = "", buffer = "", interval = null, ended = false, done = false, sourceUuid = null, commandStatus = null;
    var canRead = true;
    try { before = String(cl.getOutput()); } catch (e) { canRead = false; }
    var started = new Date().getTime(), lastRead = 0, pages = 0, pagerSignature = null;
    var oldPrompt = String(cl.getPrompt());
    function onOutput(src, args) { sourceUuid = src.objectUuid; if (args.newOutput !== undefined) buffer = (buffer + String(args.newOutput)).slice(-30000); }
    function onEnded(src, args) { sourceUuid = src.objectUuid; if (String(args.inputCommand) === command) { ended = true; commandStatus = args.status; } }
    function onTerminal(src, args) { sourceUuid = src.objectUuid; if (args.updatedStr !== undefined && !canRead) buffer = (buffer + String(args.updatedStr)).slice(-30000); }
    function commandOutput(now) {
        if (now.indexOf(before) === 0) return now.substring(before.length);
        // PT can rotate or redraw terminal history. Never parse an older
        // ping summary or CLI error as evidence for the current command.
        if (buffer) return buffer;
        var tail = before.slice(-1000), overlap = tail ? now.lastIndexOf(tail) : -1;
        if (overlap >= 0) return now.substring(overlap + tail.length);
        if (now !== before && now.indexOf(command + "\n") === 0) return now;
        return "";
    }
    function unreg(event, fn) {
        try { if (sourceUuid) _ScriptModule.unregisterIpcEventByID("TerminalLine", sourceUuid, event, null, fn); } catch (e) {}
    }
    function finish(timedOut) {
        if (done) return;
        done = true;
        if (interval) clearInterval(interval);
        unreg("outputWritten", onOutput); unreg("commandEnded", onEnded); unreg("terminalUpdated", onTerminal);
        delete cliTasks[job.id];
        var full = buffer;
        if (canRead) {
            try {
                var now = String(cl.getOutput());
                full = commandOutput(now);
            } catch (e) {}
        }
        var result = {ok: !timedOut && (commandStatus === null || Number(commandStatus) === 0), device: job.args.device, command: command, output: full.slice(-20000),
                      output_truncated: full.length > 20000, timed_out: timedOut, prompt: String(cl.getPrompt()), mode: String(cl.getMode())};
        result.command_status = commandStatus;
        result.output_pages_advanced = pages;
        if (ping) result.test = parsePing(full, timedOut);
        if (/%\s*(Invalid input|Incomplete command|Ambiguous command|Please answer|No defaulting allowed)|Unknown command/i.test(full)) result.ok = false;
        if (timedOut) result.error = "Command completion was not observed; do not assume success";
        deliver(job.id, result);
    }
    cliTasks[job.id] = {finish: finish};
    try { cl.registerEvent("outputWritten", null, onOutput); } catch (e) {}
    try { cl.registerEvent("commandEnded", null, onEnded); } catch (e) {}
    try { cl.registerEvent("terminalUpdated", null, onTerminal); } catch (e) {}
    try { cl.enterCommand(command); } catch (e) { finish(true); return; }
    interval = setInterval(function() {
        var elapsed = new Date().getTime() - started;
        // Most commands emit commandEnded. Read their output once at completion
        // rather than repeatedly transferring the whole terminal history over IPC.
        if (!ping && ended && elapsed >= 300) { finish(false); return; }
        if (elapsed - lastRead < 600) return;
        lastRead = elapsed;
        var output = buffer;
        if (canRead) {
            try { var now = String(cl.getOutput()); output = commandOutput(now); } catch (e) {}
        }
        var prompt = String(cl.getPrompt());
        var atPager = /--More--\s*$/.test(output);
        var signature = output.length + ":" + output.slice(-500);
        if (atPager && pages < 40 && signature !== pagerSignature) {
            pages++; pagerSignature = signature;
            try { cl.enterCommand(" "); } catch (e) { finish(true); }
            return;
        }
        if (!atPager) pagerSignature = null;
        var atPrompt = prompt && output.replace(/\s+$/, "").slice(-prompt.length) === prompt;
        var pingComplete = !ping || parsePing(output, false).status !== "unknown" || (commandStatus !== null && Number(commandStatus) !== 0);
        if (elapsed >= 300 && pingComplete && (ended || atPrompt || (prompt !== oldPrompt && !ping))) finish(false);
        else if (elapsed >= 25000) finish(true);
    }, 300);
}

function dispatchAgentJob(text) {
    var job;
    try {
        job = JSON.parse(text);
        if (!job || !job.id || !job.args) throw new Error("Invalid job");
        var a = job.args, result;
        if (job.tool === "inspect_topology") {
            var net = ipc.network(), devices = [];
            var n = net.getDeviceCount();
            if (n > 400) throw new Error("This version supports up to 400 devices per inspection");
            for (var i = 0; i < n; i++) devices.push(describeDevice(net.getDeviceAt(i), false));
            result = {ok: true, version: ipc.appWindow().getVersion(), device_count: n, link_count: net.getLinkCount(), devices: devices};
        } else if (job.tool === "inspect_device") {
            result = {ok: true, device: describeDevice(findDevice(a.device), true)};
        } else if (job.tool === "run_cli" || job.tool === "test_ping") {
            startCli(job, job.tool === "test_ping"); return;
        } else if (job.tool === "configure_host") {
            var host = findDevice(a.device);
            if (host.getType() !== 8 && host.getType() !== 9 && host.getType() !== 18) throw new Error("Use CLI to configure this device type");
            var port = host.getPort(a.port);
            if (!port) throw new Error("Port does not exist");
            var previous = {address: optionalRead(port, "getIpAddress"), mask: optionalRead(port, "getSubnetMask"), dhcp: optionalRead(port, "isDhcpClientOn")};
            port.setDhcpClientFlag(false);
            port.setIpSubnetMask(a.address, a.mask); port.setDefaultGateway(a.gateway);
            result = {ok: true, previous: previous, device: describeDevice(host, true)};
        } else if (job.tool === "add_device") {
            if (ipc.network().getDevice(a.name)) throw new Error("Name already exists: " + a.name);
            var lw = ipc.appWindow().getActiveWorkspace().getLogicalWorkspace();
            var created = lw.addDevice(a.type, a.model, a.x, a.y);
            if (!created) throw new Error("Packet Tracer could not create that device model/type");
            var added = findDevice(created); added.setName(a.name);
            result = {ok: true, device: describeDevice(added, true)};
        } else if (job.tool === "connect_devices") {
            var pa = findDevice(a.device_a).getPort(a.port_a), pb = findDevice(a.device_b).getPort(a.port_b);
            if (!pa || !pb) throw new Error("One of the ports does not exist");
            if (pa.getLink() || pb.getLink()) throw new Error("A selected port already has a cable");
            var linked = ipc.appWindow().getActiveWorkspace().getLogicalWorkspace().createLink(a.device_a, a.port_a, a.device_b, a.port_b, a.cable_type);
            result = {ok: Boolean(linked), message: linked ? "Cable created; wait for convergence and test connectivity" : "Packet Tracer rejected the cable"};
        } else throw new Error("Unsupported tool: " + job.tool);
        deliver(job.id, result);
    } catch (e) {
        if (job && job.id) deliver(job.id, {ok: false, error: String(e)});
        else dprint("Agent job error: " + e);
    }
}
