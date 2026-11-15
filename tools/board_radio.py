#!/usr/bin/env python3
"""Keeps the radio beside the chip of a board at the esp_hosted version of the program, as a step of the flash.

Usage: board_radio.py BUILD_DIR/board_radio.json      (the flash target of the component runs it; the port is ESPPORT)

The firmware of the radio is never kept in the flash of the board. When the radio may run another version, the
step writes a small update program into the place of the program's app (with the program's own bootloader and
partition table, so NVS and the other partitions stay), asks the radio its version over USB, and when it differs
sends the image of the radio, built from the esp_hosted the program's build took. The flash of the program follows
and takes its place back.

The version the radio was found running is kept by the MAC of the board in
$XDG_STATE_HOME/jef-sure-boards/radios.json: while the program asks for that version, the step only reads the MAC.
A radio changed by something else than this step is not seen; BOARD_RADIO_FORCE=1 checks it again. The same file
remembers the hardware each board was flashed as: a build for other hardware stops here (BOARD_RADIO_FORCE=1 goes on).
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time

SAYS = "board_radio: "
CHUNK = 1400  # the piece the update program passes to the radio in one write
AHEAD = 2  # pieces sent before the first confirmation: two fit the USB buffer of the update program
BAUD = "460800"  # when ESPBAUD names none; the USB of the chip itself does not depend on it
ESPRESSIF_USB_JTAG = (0x303A, 0x1001)  # its USB serial number is the MAC of the chip
VERSION_WAIT_S = 30  # the update program boots, resets the radio and asks it
RESTART_WAIT_S = 40  # the radio boots its new firmware, the update program starts again
STEP_WAIT_S = 10  # a confirmation of a piece, or the start of a transfer
HERE = os.path.dirname(os.path.abspath(__file__))
RADIO_DIR = os.path.join(os.path.dirname(HERE), "radio")
STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "jef-sure-boards", "radios.json")


def say(text):
    print(SAYS + text, flush=True)


def esptool(port, *args, chip=None):
    command = [sys.executable, "-m", "esptool", "-p", port, "-b", os.environ.get("ESPBAUD") or BAUD, *(("--chip", chip) if chip else ()), *args]
    r = subprocess.run(command, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"esptool {' '.join(args)}: {r.returncode}\n{r.stdout[-800:]}{r.stderr[-800:]}")
    return r.stdout


def board_mac(port):
    from serial.tools import list_ports

    device = os.path.realpath(port)
    for p in list_ports.comports():
        if p.device == device and (p.vid, p.pid) == ESPRESSIF_USB_JTAG and p.serial_number:
            return p.serial_number.upper()
    # a USB-UART bridge has no serial number of the board (a CP2102 says 0001 on every board): ask the chip
    found = re.search(r"MAC:\s+([0-9a-fA-F:]{17})", esptool(port, "read-mac"))
    if not found:
        raise RuntimeError(f"esptool read-mac on {port} gave no MAC")
    return found.group(1).upper()


def recall():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def remember(mac, **facts):
    state = recall()
    state[mac] = {**state.get(mac, {}), **facts, "checked": datetime.datetime.now().isoformat(timespec="seconds")}
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + ".tmp", "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    os.replace(STATE + ".tmp", STATE)


def write_if_changed(path, text):
    """Writes a file only when its content changes, so the build of the copy stays incremental."""
    try:
        with open(path) as f:
            if f.read() == text:
                return False
    except OSError:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    return True


def build(name, target, facts, extra_lines):
    """Builds radio/<name> for target in BUILD/board_radio/<name>, with the esp_hosted of the program's build; returns the bin."""
    work = os.path.join(facts["build_dir"], "board_radio", name)
    source = os.path.join(work, "src")
    changed = False
    for root, _, files in os.walk(os.path.join(RADIO_DIR, name)):
        for file in files:
            original = os.path.join(root, file)
            with open(original) as f:
                changed |= write_if_changed(os.path.join(source, os.path.relpath(original, os.path.join(RADIO_DIR, name))), f.read())
    # the version too: the folder of esp_hosted keeps its path from one version to the next, and the files of an archive
    # keep their old times, so ninja alone would see nothing to build again
    manifest = (f"# esp_hosted {facts['esp_hosted']['version']}\ndependencies:\n  idf:\n    version: \">=5.5\"\n"
                f"  espressif/esp_hosted:\n    override_path: \"{facts['esp_hosted']['dir']}\"\n")
    changed |= write_if_changed(os.path.join(source, "main", "idf_component.yml"), manifest)
    changed |= write_if_changed(os.path.join(source, "sdkconfig.defaults.program"), "".join(line + "\n" for line in extra_lines))
    binary = os.path.join(work, "build", f"board_radio_{name}.bin")
    if changed:
        # a setting that came from the program's build changed: the configuration starts again from the defaults
        # (the lock of the copy too: it would keep the esp_hosted of before)
        shutil.rmtree(os.path.join(work, "build"), ignore_errors=True)
        for stale in (os.path.join(work, "sdkconfig"), os.path.join(source, "dependencies.lock")):
            if os.path.exists(stale):
                os.remove(stale)
    env = {key: value for key, value in os.environ.items() if key not in ("IDF_TARGET", "SDKCONFIG", "SDKCONFIG_DEFAULTS", "ESPPORT", "ESPBAUD")}
    if not os.path.exists(os.path.join(work, "build", "build.ninja")):
        say(f"building the {name} for {target}, once")
        defaults = ";".join(os.path.join(source, file) for file in ("sdkconfig.defaults", "sdkconfig.defaults.program"))
        configure = ["cmake", "-S", source, "-B", os.path.join(work, "build"), "-G", "Ninja", f"-DIDF_TARGET={target}",
                     f"-DSDKCONFIG={os.path.join(work, 'sdkconfig')}", f"-DSDKCONFIG_DEFAULTS={defaults}", f"-DPYTHON={sys.executable}"]
        run(configure, env, f"the configuration of the {name}")
    run(["cmake", "--build", os.path.join(work, "build")], env, f"the build of the {name}")
    return binary


def run(command, env, what):
    r = subprocess.run(command, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{what} failed ({r.returncode}):\n{(r.stdout + r.stderr)[-3000:]}")


class Link:
    """The USB of the update program; a reset of the chip takes the port away for a moment."""

    def __init__(self, port, log):
        self.port, self.log, self.s, self.pending = port, log, None, b""

    def open(self, deadline):
        import serial

        while time.time() < deadline:
            try:
                s = serial.Serial()
                s.port, s.baudrate, s.timeout = self.port, 115200, 0.1
                s.dtr = s.rts = False  # set before open: a change of these lines resets the chip
                s.open()
                self.s = s
                return
            except (serial.SerialException, OSError):
                time.sleep(0.1)
        raise RuntimeError(f"{self.port} did not come back")

    def said(self, deadline):
        """The next line of the update program, without its prefix; None at the deadline."""
        import serial

        while time.time() < deadline:
            if b"\n" in self.pending:
                line, self.pending = self.pending.split(b"\n", 1)
                text = line.decode(errors="replace").rstrip("\r")
                self.log.write(text + "\n")
                if text.startswith(SAYS):
                    return text[len(SAYS):]
                continue
            try:
                if self.s is None:
                    self.open(deadline)
                self.pending += self.s.read(max(1, self.s.in_waiting))  # returns once a byte is there
            except (serial.SerialException, OSError):
                self.s = None
        return None

    def expect(self, prefix, seconds):
        deadline = time.time() + seconds
        while True:
            text = self.said(deadline)
            if text is None:
                raise RuntimeError(f'no "{prefix}" from the update program in {seconds} s')
            if text.startswith(prefix):
                return text
            if text.startswith(("failed", "no ")):
                raise RuntimeError(f"the update program: {text}")

    def write(self, data):
        self.s.write(data)
        self.s.flush()

    def close(self):
        if self.s is not None:
            self.s.close()


def app_partition_size(build_dir, offset):
    """The size of the app partition at offset in the program's partition table, by ESP-IDF's own reader."""
    sys.path.insert(0, os.path.join(os.environ["IDF_PATH"], "components", "partition_table"))
    import gen_esp32part

    with open(os.path.join(build_dir, "partition_table", "partition-table.bin"), "rb") as f:
        table = gen_esp32part.PartitionTable.from_binary(f.read())
    for partition in table:
        if partition.offset == offset:
            return partition.size
    raise RuntimeError(f"the partition table of the program has no partition at {offset:#x}")


def updater_flash(facts, flasher, updater):
    """The program's own flash, with the update program in the place of the app."""
    app = flasher["app"]
    files = [item for offset, path in flasher["flash_files"].items()
             for item in (offset, updater if offset == app["offset"] else os.path.join(facts["build_dir"], path))]
    size = os.path.getsize(updater)
    room = app_partition_size(facts["build_dir"], int(app["offset"], 0))
    if size > room:
        raise RuntimeError(f"the update program is {size} bytes, the app partition of the program {room}")
    return ["--after", "hard-reset", "write-flash", *flasher["write_flash_args"], *files]


def update(facts, port, mac, log):
    """Writes the update program, reads the version, sends the image when it differs. Returns the version the radio runs."""
    want = facts["esp_hosted"]["version"]
    with open(os.path.join(facts["build_dir"], "flasher_args.json")) as f:
        flasher = json.load(f)
    updater = build("updater", facts["host"]["target"], facts, facts["host"]["lines"])
    t0 = time.time()
    esptool(port, *updater_flash(facts, flasher, updater), chip=facts["host"]["target"])
    link = Link(port, log)
    try:
        runs = link.expect("runs ", VERSION_WAIT_S)[len("runs "):]
        say(f"the radio of {mac} runs esp_hosted {runs}, the program has {want} ({time.time() - t0:.1f} s)")
        remember(mac, runs=runs, hardware=facts["hardware"], board=facts["board"])
        if runs != want:
            image = build("coprocessor", facts["radio"]["target"], facts, [])
            with open(image, "rb") as f:
                data = f.read()
            t1 = time.time()
            link.write(f"send {len(data)}\n".encode())
            link.expect("go", STEP_WAIT_S)
            pieces = [data[at:at + CHUNK] for at in range(0, len(data), CHUNK)]
            for piece in pieces[:AHEAD]:
                link.write(piece)
            for n in range(AHEAD, len(pieces) + AHEAD):
                link.expect("ok ", STEP_WAIT_S)
                if n < len(pieces):
                    link.write(pieces[n])
            link.expect("sent ", STEP_WAIT_S)
            runs = link.expect("runs ", RESTART_WAIT_S)[len("runs "):]
            say(f"{len(data)} bytes sent in {time.time() - t1:.1f} s: the radio runs esp_hosted {runs}")
            remember(mac, runs=runs)
        link.write(b"skip\n")
        link.expect("done", STEP_WAIT_S)
    finally:
        link.close()
    return runs


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1]) as f:
        facts = json.load(f)
    radio = facts["radio"]
    if radio["firmware"] != "program":
        say(f"the radio has firmware of its own ({radio['firmware']}): it is not checked")
        return 0
    if radio["transport"] != "sdio":
        say(f"a radio on {radio['transport']} is not brought to the program's version yet: it is not checked")
        return 0
    port = os.environ.get("ESPPORT")
    if not port or port == "detect":  # the ESP-IDF extension of VS Code says detect when no port was chosen
        say("no port named: the radio is not checked (idf.py -p PORT flash names one)")
        return 0
    force = os.environ.get("BOARD_RADIO_FORCE") == "1"
    want = facts["esp_hosted"]["version"]
    try:
        mac = board_mac(port)
    except RuntimeError as err:
        say(f"the board on {port} does not answer, the radio is not checked: {err}")
        return 0
    known = recall().get(mac, {})
    if known.get("hardware") and known["hardware"] != facts["hardware"] and not force:
        say(f"the board on {port} ({mac}) was flashed as {known['hardware']} from this computer, and this build is for "
            f"{facts['hardware']}: choose the board or the port of the build. BOARD_RADIO_FORCE=1 flashes it anyway.")
        return 1
    if known.get("runs") == want and not force:
        say(f"the radio of {mac} runs esp_hosted {want}, as found on {known['checked']}")
        return 0
    app_copy = os.path.join(facts["build_dir"], f"{facts['project_name']}_flashed.bin")
    if os.path.exists(app_copy):
        # the update program takes the place of the app: the fast reflash of idf.py must write the app whole
        os.remove(app_copy)
    with open(os.path.join(facts["build_dir"], "board_radio.log"), "w") as log:
        try:
            runs = update(facts, port, mac, log)
            if runs != want:
                say(f"the radio still runs esp_hosted {runs}, not {want}: see {log.name}")
        except (RuntimeError, OSError) as err:
            # the program is flashed next in any case: the update program must not stay in its place
            say(f"the radio was not brought to {want}: {err}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
