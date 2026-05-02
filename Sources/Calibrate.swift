import Foundation

// BrainBit's docs say resistance > 1 MΩ means reseat the headband.
private let kResistBadThresholdOhms: Double = 1e6

func runCalibrate(args: [String]) -> Int32 {
    var outPath: String = "data/baseline.csv"
    var openSeconds: TimeInterval = 60.0
    var closedSeconds: TimeInterval = 60.0
    var resistSeconds: TimeInterval = 8.0
    var serial: String? = nil
    var i = 0
    while i < args.count {
        switch args[i] {
        case "--out":
            guard i + 1 < args.count else { return usageCalibrate() }
            outPath = args[i + 1]; i += 2
        case "--open-seconds":
            guard i + 1 < args.count, let v = TimeInterval(args[i + 1]) else { return usageCalibrate() }
            openSeconds = v; i += 2
        case "--closed-seconds":
            guard i + 1 < args.count, let v = TimeInterval(args[i + 1]) else { return usageCalibrate() }
            closedSeconds = v; i += 2
        case "--resist-seconds":
            guard i + 1 < args.count, let v = TimeInterval(args[i + 1]) else { return usageCalibrate() }
            resistSeconds = v; i += 2
        case "--serial":
            guard i + 1 < args.count else { return usageCalibrate() }
            serial = args[i + 1]; i += 2
        case "-h", "--help":
            print("usage: eegcli calibrate [--out PATH] [--open-seconds N] [--closed-seconds N] [--resist-seconds N] [--serial SN]")
            return 0
        default:
            FileHandle.standardError.write(Data("unknown arg: \(args[i])\n".utf8))
            return usageCalibrate()
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
    _ = scanner
    print("Connected to \(info.name) (serial=\(info.serialNumber))")

    // 1. Resistance pass.
    print("\n[1/3] Contact check (\(Int(resistSeconds))s) — sit still...")
    let readings = resistancePass(bb: bb, seconds: resistSeconds)
    var bad: [String] = []
    for c in kBrainBitChannels {
        let v = readings[c] ?? nil
        let isBad = (v == nil) || (v! > kResistBadThresholdOhms)
        if isBad { bad.append(c) }
        let str = v.map { String(format: ($0 >= 1e6 ? "%5.2f MΩ" : "%5.0f kΩ"), $0 >= 1e6 ? $0 / 1e6 : $0 / 1e3) } ?? "  --   "
        print("    \(c): \(str)  \(isBad ? "BAD" : "ok ")")
    }
    if !bad.isEmpty {
        print("  WARNING: \(bad.joined(separator: ",")) above 1 MΩ. Reseat / dampen those electrodes; recording anyway.")
    }

    // 2/3. Open + closed phases into a single CSV.
    let csv: CSVWriter
    do {
        csv = try CSVWriter(path: outPath, header: ["t_host", "phase", "pack_num", "marker", "O1_uV", "O2_uV", "T3_uV", "T4_uV"])
    } catch {
        FileHandle.standardError.write(Data("\(error.localizedDescription)\n".utf8))
        bb.disconnect()
        return 1
    }

    print("\n[2/3] Eyes OPEN, fixate softly. Press ENTER to start \(Int(openSeconds))s.")
    _ = readLine()
    let nOpen = recordPhase(bb: bb, csv: csv, phase: "open", seconds: openSeconds)

    print("\n[3/3] Eyes CLOSED. Press ENTER to start \(Int(closedSeconds))s.")
    _ = readLine()
    let nClosed = recordPhase(bb: bb, csv: csv, phase: "closed", seconds: closedSeconds)

    csv.close()
    bb.disconnect()

    print("\nDone. open=\(nOpen) samples, closed=\(nClosed) samples")
    print("Wrote \(outPath)")
    return 0
}

private func resistancePass(bb: NTBrainBit, seconds: TimeInterval) -> [String: Double?] {
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
    DispatchQueue.global().async { bb.execCommand(.startResist) }
    Thread.sleep(forTimeInterval: seconds)
    bb.execCommand(.stopResist)
    bb.setResistCallback(nil)
    return latest
}

private func recordPhase(bb: NTBrainBit, csv: CSVWriter, phase: String, seconds: TimeInterval) -> Int {
    let counter = AtomicInt()
    bb.setSignalDataCallback { (samples: [NTBrainBitSignalData]) in
        let now = Date().timeIntervalSince1970
        var batch = ""
        batch.reserveCapacity(samples.count * 72)
        for s in samples {
            batch.append(String(format: "%.6f,%@,%u,%u,%.3f,%.3f,%.3f,%.3f\n",
                                now, phase as NSString, s.packNum, s.marker,
                                s.o1.doubleValue * 1e6,
                                s.o2.doubleValue * 1e6,
                                s.t3.doubleValue * 1e6,
                                s.t4.doubleValue * 1e6))
        }
        csv.write(batch)
        counter.add(samples.count)
    }
    DispatchQueue.global().async { bb.execCommand(.startSignal) }

    let start = Date()
    while Date().timeIntervalSince(start) < seconds {
        let elapsed = Date().timeIntervalSince(start)
        let n = counter.value
        let line = String(format: "  [%@] t=%5.1f/%.0fs  samples=%d", phase as NSString, elapsed, seconds, n)
        print(line, terminator: "\r")
        FileHandle.standardOutput.synchronizeFile()
        Thread.sleep(forTimeInterval: 0.1)
    }
    print()

    bb.execCommand(.stopSignal)
    bb.setSignalDataCallback(nil)
    return counter.value
}

private func usageCalibrate() -> Int32 {
    FileHandle.standardError.write(Data("usage: eegcli calibrate [--out PATH] [--open-seconds N] [--closed-seconds N] [--resist-seconds N] [--serial SN]\n".utf8))
    return 2
}
