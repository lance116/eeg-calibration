import Foundation

/// Thread-safe CSV row sink. Accepts pre-formatted lines and flushes on close.
final class CSVWriter {
    private let handle: FileHandle
    private let lock = NSLock()

    init(path: String, header: [String]) throws {
        let fm = FileManager.default
        let dir = (path as NSString).deletingLastPathComponent
        if !dir.isEmpty { try? fm.createDirectory(atPath: dir, withIntermediateDirectories: true) }
        if !fm.createFile(atPath: path, contents: nil) {
            throw NSError(domain: "CSVWriter", code: 1, userInfo: [NSLocalizedDescriptionKey: "couldn't create \(path)"])
        }
        guard let h = FileHandle(forWritingAtPath: path) else {
            throw NSError(domain: "CSVWriter", code: 2, userInfo: [NSLocalizedDescriptionKey: "couldn't open \(path)"])
        }
        self.handle = h
        write(header.joined(separator: ",") + "\n")
    }

    func write(_ line: String) {
        lock.lock(); defer { lock.unlock() }
        if let d = line.data(using: .utf8) { handle.write(d) }
    }

    func close() {
        lock.lock(); defer { lock.unlock() }
        try? handle.close()
    }
}

func runStream(args: [String]) -> Int32 {
    var seconds: TimeInterval = 30.0
    var outPath: String? = nil
    var serial: String? = nil
    var quiet = false
    var i = 0
    while i < args.count {
        switch args[i] {
        case "--seconds":
            guard i + 1 < args.count, let v = TimeInterval(args[i + 1]) else { return usageStream() }
            seconds = v; i += 2
        case "--out":
            guard i + 1 < args.count else { return usageStream() }
            outPath = args[i + 1]; i += 2
        case "--serial":
            guard i + 1 < args.count else { return usageStream() }
            serial = args[i + 1]; i += 2
        case "--quiet": quiet = true; i += 1
        case "-h", "--help":
            print("usage: eegcli stream [--seconds N] [--out PATH] [--serial SN] [--quiet]")
            return 0
        default:
            FileHandle.standardError.write(Data("unknown arg: \(args[i])\n".utf8))
            return usageStream()
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
    print("Connected to \(info.name) (serial=\(info.serialNumber)); sampling at \(kBrainBitSampleRateHz) Hz")

    var csv: CSVWriter? = nil
    if let p = outPath {
        do {
            csv = try CSVWriter(path: p, header: ["t_host", "pack_num", "marker", "O1_uV", "O2_uV", "T3_uV", "T4_uV"])
        } catch {
            FileHandle.standardError.write(Data("\(error.localizedDescription)\n".utf8))
            return 1
        }
    }

    let counter = AtomicInt()

    bb.setSignalDataCallback { (samples: [NTBrainBitSignalData]) in
        let now = Date().timeIntervalSince1970
        var batch = ""
        batch.reserveCapacity(samples.count * 64)
        for s in samples {
            batch.append(String(format: "%.6f,%u,%u,%.3f,%.3f,%.3f,%.3f\n",
                                now, s.packNum, s.marker,
                                s.o1.doubleValue * 1e6,
                                s.o2.doubleValue * 1e6,
                                s.t3.doubleValue * 1e6,
                                s.t4.doubleValue * 1e6))
        }
        csv?.write(batch)
        counter.add(samples.count)
    }

    DispatchQueue.global().async {
        bb.execCommand(.startSignal)
    }

    let start = Date()
    var nextTick = start.addingTimeInterval(1.0)
    while true {
        let elapsed = Date().timeIntervalSince(start)
        if elapsed >= seconds { break }
        Thread.sleep(forTimeInterval: 0.05)
        if !quiet, Date() >= nextTick {
            let n = counter.value
            let expected = Int(elapsed) * kBrainBitSampleRateHz
            let drop = max(expected - n, 0)
            let line = String(format: "  t=%5.1fs  samples=%6d  drop=%4d", elapsed, n, drop)
            print(line, terminator: "\r")
            FileHandle.standardOutput.synchronizeFile()
            nextTick = nextTick.addingTimeInterval(1.0)
        }
    }
    if !quiet { print() }

    bb.execCommand(.stopSignal)
    bb.setSignalDataCallback(nil)
    bb.disconnect()
    csv?.close()

    let n = counter.value
    let elapsed = Date().timeIntervalSince(start)
    let rate = Double(n) / max(elapsed, 1e-9)
    print(String(format: "Captured %d samples in %.1fs (%.1f Hz effective)", n, elapsed, rate))
    if let p = outPath { print("Wrote \(p)") }
    return 0
}

private func usageStream() -> Int32 {
    FileHandle.standardError.write(Data("usage: eegcli stream [--seconds N] [--out PATH] [--serial SN] [--quiet]\n".utf8))
    return 2
}

final class AtomicInt {
    private var n = 0
    private let lock = NSLock()
    func add(_ k: Int) { lock.lock(); n += k; lock.unlock() }
    var value: Int { lock.lock(); defer { lock.unlock() }; return n }
}
