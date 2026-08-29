# YG98 Cross Ripple

A Windows RGB utility for the YG98/YG99 3-mode keyboard family.

The project implements a host-driven **cross-ripple RGB effect**: pressing a key creates a horizontal and vertical ripple. The center and outer ripple colors can be configured independently and blended with a smooth gradient.

> Status: early public release. The current physical LED mapping and special ripple paths were calibrated on one YG98 3M keyboard. Other firmware revisions / layouts may require additional device profiles.

## Features

- Multi-key cross ripples
- Smooth center-color -> outer-color RGB gradient
- Multiple color profiles
- Automatically remembers the last profile/settings
- Adjustable ripple speed, lifetime and gradient curve
- Windows notification-area (system tray) resident mode
- Closing the GUI keeps the RGB engine running
- Double-click the tray icon to reopen the GUI
- Optional Windows login auto-start
- `Ctrl + F12` completely exits the program
- Native HID control using the keyboard's real-time RGB report

## Current compatibility

### Confirmed / calibrated

- Windows
- YG98/YG99-family device observed as VID `05AC`, PID `024F`
- vendor-defined RGB/control HID collection
- 126-key LED matrix (`6 x 21`)
- USB wired mode used during protocol development

### 2.4 GHz / Bluetooth

The application also searches for matching YG98/YG99 / SINO WEALTH HID devices instead of relying only on the known wired VID/PID. Wireless RGB control is **not yet confirmed on every firmware**.

## Run from source

```powershell
py -m pip install -r requirements.txt
py .\src\yg98_cross_ripple.py
```

## Build the Windows EXE

Double-click `scripts\build_windows.bat`. The executable will be generated at `dist\YG98CrossRipple.exe`.

## Protocol notes

The current implementation uses a 520-byte HID Feature Report.

- Report ID: `0x07`
- command byte: `0x07`
- LED matrix length: `126`
- RGB data starts at byte offset `8`
- Red: `8 + index`
- Green: `8 + 126 + index`
- Blue: `8 + 252 + index`

## Contributing

Contributions for other YG98/YG99 revisions are welcome. For compatibility issues, include exact keyboard model, USB/2.4G/Bluetooth mode, VID/PID, HID interface/usage information if available, and which keys or LEDs are incorrect.

## Safety

This is an unofficial community project and is not affiliated with the keyboard manufacturer. It sends HID Feature Reports directly to compatible devices.

## License

No open-source license has been selected yet.

## 預計更新
 1. 亮度
 2. icon
 3. 加入別種特效(擴散:可自定義顏色)
 4. 目前每組合僅雙色，後續預計新增每組合可自由選要幾種顏色
 5. 2.4G、Bluetooth