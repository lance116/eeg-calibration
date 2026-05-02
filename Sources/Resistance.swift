import Foundation

private func formatOhms(_ ohms: Double?) -> String {
    guard let v = ohms else { return "  --   " }
    if v >= 1e6 { return String(format: "%5.2f MΩ", v / 1e6) }
    return String(format: "%5.0f kΩ", v / 1e3)
}

private func quality(_ ohms: Double?) -> String {
    guard let v = ohms else { return "?  " }
    if v < 750e3 { return "OK " }
    if v < 2e6   { return "ok " }
    return "BAD"
}

func runResist(args: [String]) -> Int32 {
    var seconds: TimeInterval = 20.0
    var serial: String? = nil
    var i = 0
    while i < args.count {
        switch args[i] {
        case "--seconds":
            guard i + 1 < args.count, let v = TimeInterval(args[i + 1]) else { return usageResist() }
            seconds = v; i += 2
        case "--serial":
            guard i + 1 < args.count else { return usageResist() }
            serial = args[i + 1]; i += 2
        case "-h", "--help":
            print("usage: eegcli resist [--seconds N] [--serial SN]")
            return 0
        default:
            FileHandle.standardError.write(Data("unknown arg: \(args[i])\n".utf8))
            return usageResist()
        }
    }

    let scanner: NTScanner
    let bb: NTBrainBit
    let info: NTSensorInfo
    do {
        (scanner, bb, info) = try connectBrainBit(serial: serial)
    } catch {
        FileHandle.standardError.write(Data("\(error)\n".utf8))
        return 1
    }
    _ = scanner  // keep alive for the duration of this run
    print("Connected to \(info.name) (serial=\(info.serialNumber))")

    var latest: [String: Double?] = ["O1": nil, "O2": nil, "T3": nil, "T4": nil]
    let lock = NSLock()

    bb.setResistCallback { (data: NTBrainBitResistData) in
        lock.lock()
        latest["O1"] = data.o1.doubleValue
        latest["O2"] = data.o2.doubleValue
        latest["T3"] = data.t3.doubleValue
        latest["T4"] = data.t4.doubleValue
        lock.unlock()
    }

    DispatchQueue.global().async {
        bb.execCommand(.startResist)
    }

    let deadline = Date().addingTimeInterval(seconds)
    while Date() < deadline {
        lock.lock()
        let row = kBrainBitChannels.map { c -> String in
            let v = latest[c] ?? nil
            return "\(c): \(formatOhms(v)) \(quality(v))"
        }.joined(separator: "  ")
        lock.unlock()
        print(row, terminator: "\r")
        FileHandle.standardOutput.synchronizeFile()
        Thread.sleep(forTimeInterval: 0.25)
    }
    print()

    bb.execCommand(.stopResist)
    bb.setResistCallback(nil)
    bb.disconnect()
    return 0
}

private func usageResist() -> Int32 {
    FileHandle.standardError.write(Data("usage: eegcli resist [--seconds N] [--serial SN]\n".utf8))
    return 2
}
