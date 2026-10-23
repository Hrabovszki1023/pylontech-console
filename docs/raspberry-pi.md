# Raspberry Pi installation

This guide installs Pylontech Console on a Raspberry Pi with a directly attached
USB-to-RS232 console cable. The application runs from the published
`linux/arm64` Docker image; Python does not need to be installed on the host.

## Verified reference setup

The procedure was verified on real hardware with:

- Raspberry Pi 4 Model B with 2 GB RAM;
- 32 GB microSD card;
- Raspberry Pi OS Lite 64-bit / Debian 13 (`trixie`);
- PoE HAT and wired Ethernet;
- FTDI FT231X USB-to-RS232 Pylontech console cable;
- two Pylontech US5000 modules;
- Docker Engine and Docker Compose;
- `hrabovszki/pylontech-console:main` for `linux/arm64`.

A Raspberry Pi 5 and other genuine USB-to-RS232 adapters may work but were not
part of this field test. USB-to-TTL and USB-to-RS485 adapters are not suitable.

## 1. Prepare the microSD card

Use Raspberry Pi Imager and select:

- device: Raspberry Pi 4;
- operating system: Raspberry Pi OS Lite (64-bit);
- storage: the target microSD card;
- hostname: for example `pylontech-console`;
- a dedicated username and a strong password;
- locale, time zone and keyboard layout appropriate for the installation;
- SSH enabled, preferably with public-key authentication;
- WLAN disabled when wired Ethernet or PoE is used;
- Raspberry Pi Connect disabled unless it is explicitly required.

Write the image, insert the card, connect Ethernet or PoE and allow the Pi to
boot. Find its address through DHCP or use mDNS:

```powershell
ssh <username>@pylontech-console.local
```

When mDNS is unavailable, use the assigned IP address instead.

## 2. Verify the platform

```bash
hostname
uname -m
cat /etc/os-release
free -h
df -h /
```

The architecture must be `aarch64`. A 64-bit operating system is required for
the published ARM64 image.

## 3. Install Docker Engine

The following commands use Docker's official Debian repository:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y ca-certificates curl git

sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: trixie
Components: stable
Architectures: arm64
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

sudo usermod -aG docker "$USER"
sudo systemctl enable --now docker
```

Log out and reconnect so that the new group membership takes effect:

```bash
exit
```

Verify Docker after reconnecting:

```bash
docker version
docker compose version
docker run --rm hello-world
```

## 4. Identify the USB-to-RS232 cable

Connect the adapter to the Raspberry Pi. Do not open it simultaneously with
PuTTY, a terminal program or another container.

```bash
lsusb
ls -l /dev/serial/by-id/
```

Always use the stable `/dev/serial/by-id/` path, not `/dev/ttyUSB0`. Resolve
the link before reading the device group:

```bash
stat -L -c '%g %G %a %n' /dev/serial/by-id/<adapter>
```

The verified FT231X adapter appeared as:

```text
/dev/serial/by-id/usb-FTDI_FT231X_USB_UART_<serial>-if00-port0
```

and used the `dialout` group with numeric GID `20`. Use the values reported
by the target Pi; do not assume that every system uses GID 20.

## 5. Configure Pylontech Console

```bash
cd ~
git clone https://github.com/Hrabovszki1023/pylontech-console.git
cd pylontech-console

cp .env.example .env
install -d -m 700 secrets
printf '%s\n' '<console-password>' \
  > secrets/pylontech-console-password.txt
chmod 644 secrets/pylontech-console-password.txt
```

The directory remains private (`700`). The password file must be readable by
the non-root user inside the published container because Compose bind-mounts
the local secret.

Add the exact adapter path and numeric group ID to `.env`:

```env
PYLONTECH_TRANSPORT=serial
PYLONTECH_SERIAL_DEVICE_HOST=/dev/serial/by-id/<adapter>
PYLONTECH_SERIAL_GID=<numeric-group-id>
PYLONTECH_SERIAL_BAUDRATE=115200
PYLONTECH_IMAGE_TAG=main
PYLONTECH_HTTP_PUBLISHED_PORT=8001
```

Validate the combined Compose configuration:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.serial.yml \
  config
```

The rendered configuration must map the stable host path to
`/dev/pylontech-console`, set `PYLONTECH_TRANSPORT=serial` and include the
numeric supplemental group.

## 6. Pull and start the container

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.serial.yml \
  pull

docker compose \
  -f docker-compose.yml \
  -f docker-compose.serial.yml \
  up -d

docker compose \
  -f docker-compose.yml \
  -f docker-compose.serial.yml \
  ps
```

The expected state is `Up ... (healthy)`. Docker starts during boot and the
service uses `restart: unless-stopped`, so the container starts automatically
after a normal Raspberry Pi restart.

A healthy container only confirms that the HTTP service responds. Before the
battery is connected, application health correctly reports `offline`.

## 7. Install at the battery rack

Shut the Raspberry Pi down before moving it:

```bash
sudo shutdown -h now
```

After the SSH connection closes and the Pi has stopped:

1. disconnect PoE or its power supply;
2. keep the USB adapter attached, or reconnect it before the next boot;
3. connect the RJ45 end to the Pylontech master module's **CONSOLE** port;
4. ensure no other client owns the console connection;
5. power the battery system according to its manufacturer documentation;
6. reconnect Ethernet/PoE to boot the Raspberry Pi.

The adapter must exist when Docker starts the container because it is an
explicit device mapping. If the adapter is unplugged or replaced while running,
reconnect it and recreate the service with the same `docker compose ... up -d`
command.

## 8. Verify operation

```bash
cd ~/pylontech-console

docker compose \
  -f docker-compose.yml \
  -f docker-compose.serial.yml \
  ps

curl -sS http://127.0.0.1:8001/api/v1/health \
  | python3 -m json.tool
```

Successful acquisition reports:

- `status: online`;
- `inventory.valid: true`;
- `rack.valid: true`;
- `console_session.mode: debug`;
- `console_session.authenticated: true`;
- valid module and cell counts;
- an empty `errors` list.

Open the Web UI at:

```text
http://pylontech-console.local:8001/
```

or use the Pi's IP address. Plain HTTP is expected for this local read-only
deployment; do not expose port 8001 directly to the Internet.

## Troubleshooting

Inspect the mapped device and process identity:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.serial.yml \
  exec pylontech-console \
  sh -c 'id; ls -l /dev/pylontech-console'
```

Read recent logs:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.serial.yml \
  logs --no-color --timestamps --tail=200 pylontech-console
```

If the Web UI is available but reports `CONSOLE NOT AUTHENTICATED`, check:

- the cable is connected to **CONSOLE**, not CAN, RS485 or LINKPORT;
- the master module is powered;
- the configured `/dev/serial/by-id/` path still exists;
- the numeric group ID matches `stat -L`;
- the password file contains only the console login password;
- no terminal application or second service has opened the adapter.

Recreate the container after reconnecting the adapter:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.serial.yml \
  up -d --force-recreate
```

## Updating

```bash
cd ~/pylontech-console
git pull --ff-only

docker compose \
  -f docker-compose.yml \
  -f docker-compose.serial.yml \
  pull

docker compose \
  -f docker-compose.yml \
  -f docker-compose.serial.yml \
  up -d
```
