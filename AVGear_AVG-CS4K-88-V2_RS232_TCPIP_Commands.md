# AVGear AVG-CS4K-88-V2 — RS232 / TCP-IP Control (8×8 Matrix)

This document lists the ASCII control commands shown in the official **AVG-CS4K-88-V2** manual and explains how to send the same commands over **TCP/IP**.

> Source: AVG-CS4K-88-V2 manual (PDF).  
> Key notes: commands are **case-sensitive**; square brackets in the manual are **placeholders** and are **not typed**; commands must include their terminating symbol (often `.` or `;`).  

---

## 1) Quick start (TCP/IP)

### Default network settings
- **IP:** `192.168.0.178`
- **Subnet mask:** `255.255.255.0`
- **Gateway:** `192.168.0.1`
- **TCP port:** `4001` (cannot be changed)

### Send a command
1. Open a TCP connection to `192.168.0.178:4001`
2. Send the command as **ASCII text**, including the command's ending (e.g. `.` or `;`).
3. Read the response/feedback text (varies by command).

#### Examples

**Windows PowerShell**
```powershell
$ip   = "192.168.0.178"
$port = 4001
$cmd  = "01V02."   # route input 1 to output 2

$client = [System.Net.Sockets.TcpClient]::new($ip, $port)
$stream = $client.GetStream()
$writer = New-Object System.IO.StreamWriter($stream)
$writer.NewLine = "`r`n"      # often tolerated; command already contains '.' / ';'
$writer.AutoFlush = $true

$writer.WriteLine($cmd)

# read some feedback (non-blocking read patterns may be needed in real apps)
$reader = New-Object System.IO.StreamReader($stream)
Start-Sleep -Milliseconds 150
while ($stream.DataAvailable) { $reader.ReadLine() }

$client.Close()
```

**macOS/Linux (netcat)**
```bash
printf 'Status.' | nc 192.168.0.178 4001
```

**Python**
```python
import socket

ip, port = "192.168.0.178", 4001
cmd = b"Status."  # query routing status

with socket.create_connection((ip, port), timeout=2) as s:
    s.sendall(cmd)           # you can also try cmd + b"\r\n" if your client wants line endings
    s.settimeout(2)
    print(s.recv(4096).decode(errors="replace"))
```

> Tip: If you see no response, try appending `\r\n` after the command (some terminal tools do this automatically), but keep the command terminator (`.` or `;`) exactly as documented.

---

## 2) RS232 serial settings (local serial control)

The manual specifies:
- **Baud rate:** `9600`
- **Data bits:** `8`
- **Stop bits:** `1`
- **Parity:** `None`

### RS232 wiring
The unit uses a **3-pin Phoenix** RS232 connector and typically ships with a Phoenix-to-DB9 cable.

---

## 3) Command format rules (important)

From the manual notes:
- Commands are **case-sensitive**
- Brackets like `[x]` are **placeholders** for values and should **not** be typed
- Include the command ending symbols shown in the command itself (often `.` or `;`)
- Some commands use 2-digit channel numbers (`01`–`08`)

Placeholders used below:
- `x`, `x1`, `x2` = channel numbers (`01`–`08`) unless stated otherwise
- `Y` = preset number (`0`–`9`)
- `I/O` = input or output selector for certain commands

---

## 4) Command reference (ASCII)

### 4.1 System commands

| Command | Function | Typical feedback |
|---|---|---|
| `/*Type;` | Query model information | `XXXXX` |
| `/%Lock;` | Lock front panel buttons | `System Locked!` |
| `/%Unlock;` | Unlock front panel buttons | `System Unlock!` |
| `/^Version;` | Query firmware version | `VX.X.X` |
| `Demo.` | Demo mode: auto-switch sequence | `Demo Mode ...` |

### 4.2 Basic switching / routing

| Command | Function | Notes |
|---|---|---|
| `xAll.` | Route **input x** to **all outputs** | `x` is `01`–`08` |
| `All#.` | Route **input 1→out1, 2→out2, ...** | “All Through” |
| `All$.` | Switch off all outputs | “All Closed” |
| `x#.` | Route **input x** to the corresponding output **x** | “x Through” |
| `x$.` | Switch off output **x** | “x Closed” |
| `x@.` | Switch on output **x** | “x Open” |
| `All@.` | Switch on all outputs | “All Open” |
| `x1Vx2.` | Route **AV** from **input x1** to output(s) **x2** | Outputs can be comma-separated (e.g. `01V02,03.`) |
| `x1Bx2.` | Route **AV + IR** from **input x1** to output(s) **x2** | Outputs can be comma-separated |
| `x1Rx2.` | Route **IR** from **output x1** to **input x2** | Used for IR matrix behavior |
| `Statusx.` | Check I/O connection status of **output x** | |
| `Status.` | Query routing status for all outputs | |

> The manual uses bracketed forms like `[x1]V[x2].` — you type it without the brackets: `01V02.`

### 4.3 Presets & power modes

| Command | Function | Notes |
|---|---|---|
| `SaveY.` | Save current state to preset **Y** | `Y=0–9` |
| `RecallY.` | Recall preset **Y** | |
| `ClearY.` | Clear preset **Y** | |
| `PWON.` | Normal working mode | |
| `PWOFF.` | Standby and cut power to HDBaseT receivers | |
| `STANDBY.` | Standby (does **not** cut PoC power) | Press any button / send command to wake |

### 4.4 HDCP management

| Command | Function | Parameters |
|---|---|---|
| `/%Y/X:Z.` | Set HDCP compliance status | `Y=I` (input) or `O` (output); `X` is port number or `ALL`; `Z=1` (compliant) or `0` (not compliant) |

Example:
- Make input 3 HDCP compliant: `/%I/03:1.`
- Make all outputs non-compliant: `/%O/ALL:0.`

### 4.5 Digital audio enable/disable

| Command | Function | Parameters |
|---|---|---|
| `DigitAudioONx.` | Enable HDMI audio output of port x | `x=1–8`, `x=9` = all ports |
| `DigitAudioOFFx.` | Disable HDMI audio output of port x | `x=1–8`, `x=9` = all ports |

### 4.6 RS232 pass-through to HDBaseT receivers (device control)

| Command | Function | Parameters / notes |
|---|---|---|
| `/+Y/X:******.` | Send RS232 data from the matrix to receiver(s) | `Y` selects receiver (1–8), `9`=all, and mode-dependent ranges `A–H` / `a–h` in PWON/PWOFF; `X` selects baud rate `1–7` (1=2400, 2=4800, 3=9600, 4=19200, 5=38400, 6=57600, 7=115200); `******` is payload (max 48 bytes) |

> This is for controlling a third-party device connected to a receiver’s RS232 port.

### 4.7 EDID management

| Command | Function | Notes |
|---|---|---|
| `EDIDHxB y.` | Input `y` learns EDID from output `x` | Manual shows forms like `EDIDH4B3` |
| `EDIDPCMx.` | Force audio section of input `x` EDID to PCM | |
| `EDIDGx.` | Get EDID data from output `x` | Returns EDID hex dump |
| `EDIDMInit.` | Restore factory default EDID for every input | |
| `EDIDMxBy.` | Manual EDID switching: enable input `y` to learn EDID of output `x` | |
| `EDIDUpgradex.` | Upgrade EDID via RS232 | Disconnect twisted pairs before use (manual note) |
| `EDID/x/y.` | Set EDID of input `x` to built-in EDID number `y` | `y=1–6` |
| `UpgradeIntEDIDx.` | Upgrade one of embedded EDID slots | `x` selects EDID slot (see list below) |
| `GetInPortEDIDX` | Return embedded EDID of input `X` | `X=1–8` |
| `GetIntEDIDx.` | Return embedded EDID slot `x` | `x=1–6` |

Embedded EDID slots for `UpgradeIntEDIDx.`:
1. 1080P 2D 2CH  
2. 1080P 3D 2CH  
3. 1080P 2D Multichannel  
4. 1080P 3D Multichannel  
5. 3840×2160 2D (30Hz)  
6. 3840×2160 2D (60Hz)

### 4.8 IR carrier / factory reset

| Command | Function |
|---|---|
| `%0801.` | Auto HDCP management; activate carrier native mode |
| `%0900.` | Switch to carrier native mode |
| `%0901.` | Switch to force carrier mode |
| `%0911.` | Factory reset |

### 4.9 Query / diagnostics commands

| Command | Function | Typical feedback |
|---|---|---|
| `%9951.`–`%9958.` | Check command sent by port 1–8 when `PWON.` | `Port n:data when PWON` |
| `%9941.`–`%9948.` | Check command sent by port 1–8 when `PWOFF.` | `Port n:data when PWOFF` |
| `%9961.` | Check system lock status | `System Locked/Unlock!` |
| `%9962.` | Check power status | `STANDBY / PWOFF / PWON` |
| `%9963.` | Check IR carrier mode | `Carrier native / Force carrier` |
| `%9964.` | Query unit IP address | e.g. `IP:192.168.0.178` |
| `%9971.` | Check connection status of inputs | |
| `%9972.` | Check connection status of outputs | |
| `%9973.` | Check HDCP status of inputs | |
| `%9974.` | Check HDCP status of outputs | |
| `%9975.` | Check I/O connection status | |
| `%9976.` | Check output resolution | |
| `%9977.` | Check digital audio status for outputs | |
| `%9978.` | Check HDCP compliance status of inputs | |

### 4.10 Channel lock controls

| Command | Function |
|---|---|
| `I-LockX.` | Lock channel/output X (`X=1–8`) |
| `I-UnLockX.` | Unlock channel/output X (`X=1–8`) |
| `A-Lock.` | Lock all channels |
| `A-UnLock.` | Unlock all channels |
| `Lock-Sta.` | Query lock status of all channels |

---

## 5) CEC commands (reference only)

The manual lists the following (hex) as reference CEC sequences:

| Hex command | Function |
|---|---|
| `43 45 43 01 44 6C 2E` | Turn off display devices |
| `43 45 43 01 04 2E` + `43 45 43 01 44 6D 2E` | Turn on display devices |
| `43 45 43 01 44 41 2E` | Volume Up |
| `43 45 43 01 44 42 2E` | Volume Down |

---

## 6) Practical tips for automation

- Use a **single persistent TCP connection** and send multiple commands (less overhead than reconnecting each time).
- Add a small **inter-command delay** (e.g. 50–150ms) if your controller is blasting many routes quickly.
- Treat feedback text as *best-effort*: some commands respond with a full line; others may respond with short tokens or not at all.
- If you build an integration (e.g. Crestron/Control4/Home Assistant), implement:
  - reconnect logic
  - per-command timeout
  - optional CR/LF line ending support

---

## 7) Disclaimer

This is a convenience transcription of the command table as shown in the manufacturer manual. If AVGear releases a newer firmware/manual revision, behavior and feedback strings may change.
