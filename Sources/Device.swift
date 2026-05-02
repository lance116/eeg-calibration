import Foundation

let kBrainBitChannels = ["O1", "O2", "T3", "T4"]
let kBrainBitSampleRateHz = 250

/// Scan for BrainBit headbands for `seconds`.
/// The returned scanner is still alive — keep a reference to it for the
/// lifetime of any sensors you create from it.
func scanForBrainBits(seconds: TimeInterval = 5.0) -> (NTScanner, [NTSensorInfo]) {
    let scanner = NTScanner(sensorFamily: [
        NSNumber(value: NTSensorFamily.leBrainBit.rawValue)
    ])!

    var seen: [String: NTSensorInfo] = [:]
    let lock = NSLock()

    scanner.setSensorsCallback { (sensors: [NTSensorInfo]) in
        lock.lock(); defer { lock.unlock() }
        for s in sensors { seen[s.address] = s }
    }

    scanner.startScan()
    Thread.sleep(forTimeInterval: seconds)
    scanner.stopScan()
    scanner.setSensorsCallback(nil)

    if let cached = scanner.sensors {
        lock.lock()
        for s in cached { seen[s.address] = s }
        lock.unlock()
    }

    return (scanner, Array(seen.values))
}

/// Pick the SensorInfo matching `serial`, or the first one if `serial` is nil.
func pickHeadband(_ sensors: [NTSensorInfo], serial: String?) -> NTSensorInfo? {
    guard !sensors.isEmpty else { return nil }
    guard let serial = serial else { return sensors[0] }
    return sensors.first { $0.serialNumber == serial }
}

/// Scan, pick a device, create+connect the sensor. Caller is responsible for
/// holding the returned scanner alive and calling Disconnect when done.
func connectBrainBit(serial: String?, scanSeconds: TimeInterval = 5.0) throws -> (NTScanner, NTBrainBit, NTSensorInfo) {
    let (scanner, sensors) = scanForBrainBits(seconds: scanSeconds)
    guard let info = pickHeadband(sensors, serial: serial) else {
        throw EEGError.noDevice(serial: serial, scanSeconds: scanSeconds)
    }
    let sensor = scanner.createSensor(info)
    guard let bb = sensor as? NTBrainBit else {
        throw EEGError.wrongDeviceType(name: info.name)
    }
    return (scanner, bb, info)
}

enum EEGError: Error, CustomStringConvertible {
    case noDevice(serial: String?, scanSeconds: TimeInterval)
    case wrongDeviceType(name: String)

    var description: String {
        switch self {
        case .noDevice(let serial, let s):
            let suffix = serial.map { " with serial \($0)" } ?? ""
            return "No BrainBit found\(suffix) after \(Int(s))s scan."
        case .wrongDeviceType(let name):
            return "Connected to \(name) but it didn't expose the BrainBit interface."
        }
    }
}
