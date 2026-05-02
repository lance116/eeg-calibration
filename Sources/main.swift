import Foundation

func usage() {
    let text = """
    usage: eegcli <command> [options]

    commands:
      scan        discover BrainBit headbands in range
      resist      live electrode contact-quality readout
      stream      record signal to CSV
      calibrate   contact check + eyes-open / eyes-closed baseline

    Run `eegcli <command> --help` for command-specific options.
    """
    print(text)
}

let argv = CommandLine.arguments
guard argv.count >= 2 else { usage(); exit(2) }

let cmd = argv[1]
let rest = Array(argv.dropFirst(2))

switch cmd {
case "scan":      exit(runScan(args: rest))
case "resist":    exit(runResist(args: rest))
case "stream":    exit(runStream(args: rest))
case "calibrate": exit(runCalibrate(args: rest))
case "-h", "--help", "help": usage(); exit(0)
default:
    FileHandle.standardError.write(Data("unknown command: \(cmd)\n".utf8))
    usage()
    exit(2)
}
