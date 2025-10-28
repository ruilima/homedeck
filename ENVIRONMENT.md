# Environment Variables Configuration

HomeDeck uses **systemd EnvironmentFile** for secure configuration management. This is more secure than using `.env` files and prevents parsing errors.

## Quick Start

The installer (`install-service.sh`) automatically creates and configures the environment file. But if you need to configure manually:

### 1. Create the configuration file

```bash
sudo mkdir -p /etc/homedeck
sudo cp homedeck.env.example /etc/homedeck/homedeck.env
sudo chmod 600 /etc/homedeck/homedeck.env
```

### 2. Edit the configuration

```bash
sudo nano /etc/homedeck/homedeck.env
```

Configure at minimum:
- `HA_HOST` - Your Home Assistant WebSocket URL
- `HA_ACCESS_TOKEN` - Your long-lived access token

### 3. Restart the service

```bash
sudo systemctl restart homedeck.service
```

---

## Required Variables

### `HA_HOST`
**Home Assistant WebSocket URL**

Format: `ws://IP:PORT` or `wss://IP:PORT`

Examples:
```bash
# Local network (unencrypted)
HA_HOST=ws://192.168.1.100:8123

# With SSL (encrypted)
HA_HOST=wss://homeassistant.local:8123

# External domain
HA_HOST=wss://ha.example.com
```

### `HA_ACCESS_TOKEN`
**Long-Lived Access Token from Home Assistant**

To create a token:
1. Open Home Assistant
2. Click on your **Profile** (bottom left)
3. Scroll down to **"Long-Lived Access Tokens"**
4. Click **"Create Token"**
5. Give it a name (e.g., "HomeDeck")
6. Copy the token and paste it here

Example:
```bash
HA_ACCESS_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

⚠️ **Important:** Token must be on a **single line** with no spaces or line breaks!

---

## Optional Variables

### `TIMEZONE`
Timezone for date/time display

Default: System timezone

Example:
```bash
TIMEZONE=Europe/Lisbon
TIMEZONE=America/New_York
TIMEZONE=Asia/Tokyo
```

Find your timezone: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

### `MDNS_SERVICE_ID`
Unique identifier for mDNS discovery

Default: Uses IP address

Example:
```bash
MDNS_SERVICE_ID=livingroom-deck
MDNS_SERVICE_ID=kitchen_streamdeck
```

Accepted characters: `A-Z`, `a-z`, `0-9`, `-`, `_`, spaces

### `ENABLE_CACHE`
Enable icon caching for faster startup

Default: `1` (enabled)

```bash
ENABLE_CACHE=1  # Enabled (recommended)
ENABLE_CACHE=0  # Disabled
```

### `ENABLE_OPTIPNG`
Enable image optimization with optipng

Default: `0` (disabled for performance)

```bash
ENABLE_OPTIPNG=0  # Disabled (faster, recommended)
ENABLE_OPTIPNG=1  # Enabled (smaller files, slower)
```

---

## Security Best Practices

### File Permissions

The environment file should be readable **only by root**:

```bash
sudo chown root:root /etc/homedeck/homedeck.env
sudo chmod 600 /etc/homedeck/homedeck.env
```

Verify permissions:
```bash
ls -la /etc/homedeck/homedeck.env
# Should show: -rw------- 1 root root
```

### Never Commit Secrets

**Never** commit the environment file to git:

```bash
# Already in .gitignore
/etc/homedeck/homedeck.env
homedeck.env
```

### Token Rotation

Regularly rotate your Home Assistant access token:
1. Create a new token in Home Assistant
2. Update `/etc/homedeck/homedeck.env`
3. Restart the service: `sudo systemctl restart homedeck.service`
4. Delete the old token from Home Assistant

---

## Troubleshooting

### Check if environment is loaded

```bash
sudo systemctl show homedeck.service -p Environment
```

### Test environment file syntax

```bash
# Should not output any errors
sudo bash -c 'source /etc/homedeck/homedeck.env && echo "Syntax OK"'
```

### View loaded environment in logs

```bash
sudo journalctl -u homedeck.service -n 50 | grep -E "HA_HOST|TIMEZONE"
```

### Common Issues

#### Issue: "Python-dotenv could not parse statement"
**Solution:** Don't use `.env` file anymore. Use `/etc/homedeck/homedeck.env` instead.

#### Issue: "AttributeError: 'NoneType' object has no attribute 'rstrip'"
**Solution:** `HA_HOST` is not set. Check `/etc/homedeck/homedeck.env`

#### Issue: "Token must be on a single line"
**Solution:** Remove any line breaks or spaces from `HA_ACCESS_TOKEN`

#### Issue: "Permission denied"
**Solution:**
```bash
sudo chmod 600 /etc/homedeck/homedeck.env
```

---

## Example Configuration

Complete example of `/etc/homedeck/homedeck.env`:

```bash
# Home Assistant Configuration
HA_HOST=ws://192.168.1.100:8123
HA_ACCESS_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhYmNkZWYxMjM0NTYiLCJpYXQiOjE3MDk1NjI0MDAsImV4cCI6MjAyNDkyMjQwMH0.abcdef123456

# Optional Settings
TIMEZONE=Europe/Lisbon
MDNS_SERVICE_ID=
ENABLE_CACHE=1
ENABLE_OPTIPNG=0
```

---

## Migration from .env

If you're migrating from the old `.env` file:

```bash
# 1. Create new environment file
sudo mkdir -p /etc/homedeck
sudo cp .env /etc/homedeck/homedeck.env

# 2. Fix permissions
sudo chown root:root /etc/homedeck/homedeck.env
sudo chmod 600 /etc/homedeck/homedeck.env

# 3. Reinstall service
sudo ./install-service.sh

# 4. (Optional) Remove old .env
rm .env
```

The old `.env` file is still supported for local development, but systemd service uses `/etc/homedeck/homedeck.env` for better security.

---

## References

- [systemd EnvironmentFile](https://www.freedesktop.org/software/systemd/man/systemd.exec.html#EnvironmentFile=)
- [Home Assistant Long-Lived Access Tokens](https://www.home-assistant.io/docs/authentication/)
- [Systemd Service Hardening](https://www.freedesktop.org/software/systemd/man/systemd.exec.html)
