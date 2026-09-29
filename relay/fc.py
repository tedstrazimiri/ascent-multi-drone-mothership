"""MSP telemetry and an explicit, reversible RAM-only bench failsafe change."""
import glob
import struct
import time
import threading
import serial

ARM_FLAGS = ('NO_GYRO FAILSAFE RX_FAILSAFE NOT_DISARMED BOXFAILSAFE RUNAWAY_TAKEOFF '
             'CRASH_DETECTED THROTTLE ANGLE BOOT_GRACE_TIME NOPREARM LOAD CALIBRATING '
             'CLI CMS_MENU BST MSP PARALYZE GPS RESC DSHOT_TELEM REBOOT_REQUIRED '
             'DSHOT_BITBANG ACC_CALIBRATION MOTOR_PROTOCOL CRASHFLIP ALTHOLD POSHOLD '
             'AUTOPILOT ARM_SWITCH').split()


def devices():
    return glob.glob('/dev/serial/by-id/usb-Betaflight_Betaflight_-_GEPRC_TAKER_H743_*-if00')


def request(port, command, payload=b''):
    if command == 76:
        if len(payload) != 8:
            raise ValueError('Failsafe configuration must contain exactly 8 bytes')
    elif command == 225:
        if len(payload) != 26:
            raise ValueError('GPS Rescue configuration must contain exactly 26 bytes')
    elif command not in (1, 2, 3, 34, 44, 75, 101, 105, 119, 130, 135, 238) or payload:
        raise ValueError('Unsupported MSP command')
    port.reset_input_buffer()
    checksum = len(payload) ^ command
    for byte in payload:
        checksum ^= byte
    port.write(b'$M<' + bytes([len(payload), command]) + payload + bytes([checksum]))
    deadline = time.monotonic() + .6
    data = bytearray()
    while time.monotonic() < deadline:
        data.extend(port.read(256))
        if b'$M!' in data:
            raise ValueError('FC rejected MSP command')
        start = data.find(b'$M>')
        if start < 0:
            continue
        frame = data[start:]
        if len(frame) < 6 or len(frame) < frame[3] + 6:
            continue
        frame = frame[:frame[3] + 6]
        checksum = 0
        for byte in frame[3:]:
            checksum ^= byte
        if checksum or frame[4] != command:
            raise ValueError('Invalid MSP reply')
        return bytes(frame[5:-1])
    raise TimeoutError('FC did not answer. Close the Betaflight configurator if it is connected.')


class Monitor:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.path = path
        self.port = serial.Serial(path, 115200, timeout=.01, write_timeout=.5, exclusive=True)
        try:
            if request(self.port, 119)[0] != 0:
                raise ValueError('Unsupported ARM mode order')
            self.provider = request(self.port, 44)[0]
            self.version = '.'.join(map(str, request(self.port, 3)[:3]))
        except BaseException:
            self.close()
            raise

    def close(self):
        with self.lock:
            self.port.close()

    def snapshot(self):
        with self.lock:
            return self._snapshot()

    def _snapshot(self):
        status = request(self.port, 101)
        rc = request(self.port, 105)
        battery = request(self.port, 130)
        if len(status) < 10 or len(battery) < 11 or len(rc) % 2:
            raise ValueError('Incomplete FC telemetry')
        channels = list(struct.unpack('<' + 'H' * (len(rc) // 2), rc))
        flag_offset = 16 + (status[15] & 15) if len(status) >= 16 else len(status)
        flags = struct.unpack_from('<I', status, flag_offset + 1)[0] if len(status) >= flag_offset + 5 else None
        return {'connected': True, 'firmware': self.version, 'sbus': self.provider == 2,
                'armed': bool(struct.unpack_from('<I', status, 6)[0] & 1),
                'arming_flags': flags,
                'arming_blockers': [name for bit, name in enumerate(ARM_FLAGS) if flags is not None and flags & (1 << bit)],
                'channels': channels, 'cells': battery[0],
                'voltage': struct.unpack_from('<H', battery, 9)[0] / 100,
                'battery_state': battery[8], 'updated': time.time()}

    def bench_profile(self):
        """Inspect first; callers must save the returned original before writing."""
        with self.lock:
            if self.version != '26.6.2' or self._snapshot()['armed']:
                raise ValueError('Connect the disarmed, verified Betaflight 2026.6.2 FC')
            modes = request(self.port, 34)
            active_arm = [modes[i:i+4] for i in range(0, len(modes), 4)
                          if modes[i] == 0 and modes[i+2] < modes[i+3]]
            if len(active_arm) != 1:
                raise ValueError('Expected one ARM range on AUX1')
            _, aux, lo, hi = active_arm[0]
            if aux != 0 or not (900 + lo*25 <= 2011 < 900 + hi*25) or 900 + lo*25 <= 987:
                raise ValueError('ARM must be AUX1 high, with AUX1 low disarming')
            extra = request(self.port, 238)
            for i in range(1, len(extra), 3):
                if extra[i] == 0 and extra[i+1:i+3] != b'\x00\x00':
                    raise ValueError('Linked ARM modes are unsupported for this bench test')
            original = request(self.port, 75)
            if len(original) != 8:
                raise ValueError('Unexpected failsafe configuration')
            gps_original = request(self.port, 135)
            if len(gps_original) != 26:
                raise ValueError('Unexpected GPS Rescue configuration')
            return original, original[:7] + b'\x01', gps_original, gps_original[:20] + b'\x01' + gps_original[21:]

    def profile_matches(self, failsafe, gps):
        with self.lock:
            return request(self.port, 75) == failsafe and request(self.port, 135) == gps

    def set_failsafe(self, data):
        with self.lock:
            if self._snapshot()['armed']:
                raise ValueError('Disarm before changing the bench failsafe')
            request(self.port, 76, data)
            if request(self.port, 75) != data:
                raise ValueError('Failsafe readback does not match')

    def set_gps_rescue(self, data):
        with self.lock:
            if self._snapshot()['armed']:
                raise ValueError('Disarm before changing the indoor GPS requirement')
            request(self.port, 225, data)
            if request(self.port, 135) != data:
                raise ValueError('GPS Rescue readback does not match')
