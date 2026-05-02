// Bridging header for the BrainBit ObjC SDK.
// Imports just what we need; NTUtils.h is intentionally skipped because it
// includes a non-vendored "cmn_type.h" and we don't use anything from it.

#ifndef EEGCLI_SHIM_H
#define EEGCLI_SHIM_H

#import "NTTypes.h"
#import "NTSensor.h"
#import "NTScanner.h"
#import "NTBrainBit.h"

#endif
