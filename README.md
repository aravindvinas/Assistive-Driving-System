# Assistive Driving System

A Raspberry Pi prototype that measures short-range obstacle distance with an HC-SR04 ultrasonic sensor, provides buzzer alerts, and exposes a live phone-accessible dashboard.

## Repository contents

- `driving_assistant_allinone.py` — sensor polling, distance smoothing, alert-zone classification, buzzer control, and HTTP dashboard.
- `driving-assistant-allinone.service` — systemd unit for automatic startup.
- `install_driving_assistant.sh` — installs the application and service on Raspberry Pi OS and disables the two older services to avoid GPIO/port conflicts.
- `report/` — LaTeX report, BibTeX file, block diagram, dashboard screenshot, and service-log screenshot.

## Hardware and wiring

GPIO numbers use BCM numbering:

- HC-SR04 TRIG → GPIO24 (physical pin 18)
- HC-SR04 ECHO → GPIO23 (physical pin 16), **through a voltage divider or suitable level shifter**
- Buzzer signal → GPIO18 (physical pin 12)
- Common ground → Raspberry Pi GND (for example, physical pin 6)

**Important:** The HC-SR04 ECHO output can be 5 V. Never connect it directly to a Raspberry Pi GPIO input; Pi GPIO pins are 3.3 V tolerant. If the buzzer needs more current than a GPIO can safely provide, use a suitable transistor/driver circuit.

## Install on the Raspberry Pi

Copy `driving_assistant_allinone.py` and `install_driving_assistant.sh` to `/home/driver/` on the Pi. Then run:

```bash
chmod +x /home/driver/install_driving_assistant.sh
sudo bash /home/driver/install_driving_assistant.sh /home/driver/driving_assistant_allinone.py
```

Find the Pi's IP address:

```bash
hostname -I
```

Connect a phone to the same local network and open `http://PI-IP:5000`, replacing `PI-IP` with the Pi's address.

## Check status and logs

```bash
sudo systemctl status driving-assistant-allinone.service --no-pager
sudo journalctl -u driving-assistant-allinone.service -f
```

## Alert thresholds

- 30 cm or less: DANGER, continuous tone
- Over 30 cm to 60 cm: WARNING, fast intermittent beeps
- Over 60 cm to 100 cm: CAUTION, slower intermittent beeps
- Over 100 cm: SAFE, silent
- Invalid/no echo: UNKNOWN, silent

## Build the report

Open `report/Assistive_Driving_System_final.tex` in Overleaf and upload the complete `report/` folder, including `references.bib` and all three PNG images. The document uses BibTeX with `plain` style. Compile using LaTeX → BibTeX → LaTeX → LaTeX if citations or references do not appear on the first pass.

The title page references `Uppsala_University_seal_svg.png`. If you have that logo file, place it in `report/` too; otherwise comment out the corresponding `\includegraphics` line in the title page before compiling.

## Safety note

This is an experimental bench-tested prototype, not a certified automotive safety system. Do not rely on it as the sole means of detecting obstacles or replace direct observation and established vehicle safety systems.
