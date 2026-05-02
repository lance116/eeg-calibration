import Foundation

func runScan(args: [String]) -> Int32 {
    var seconds: TimeInterval = 5.0
    var i = 0
    while i < args.count {
        switch args[i] {
        case "--seconds":
            guard i + 1 < args.count, let v = TimeInterval(args[i + 1]) else {
                FileHandle.standardError.write(Data("usage: eegcli scan [--seconds N]\n".utf8))
                return 2
            }
            seconds = v; i += 2
        case "-h", "--help":
            print("usage: eegcli scan [--seconds N]")
            return 0
        default:
            FileHandle.standardError.write(Data("unknown arg: \(args[i])\n".utf8))
            return 2
        }
    }

    print("Scanning for \(Int(seconds))s...")
    let (_, sensors) = scanForBrainBits(seconds: seconds)
    if sensors.isEmpty {
        print("No headbands found.")
        print("- Make sure the device is powered on and in range.")
        print("- Approve the macOS Bluetooth permission prompt for your terminal.")
        return 1
    }
    print("Found \(sensors.count) device(s):")
    for s in sensors {
        print("  - \(s.name)  serial=\(s.serialNumber)  addr=\(s.address)  rssi=\(s.rssi) dBm")
    }
    return 0
}
