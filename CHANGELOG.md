# Changelog

## v1.1.0 - 2026-08-30

- Added a per-profile effect selector to the existing GUI
- Added host-rendered radial ripples with physical YG98 key coordinates
- Reused multi-color, brightness, speed, lifetime, and gradient controls across effects
- Added a follower effect with sequential colors and per-key smooth fade-out
- Made the control window resizable with an expanding color list
- Moved the persistent usage notes from the bottom of the window into a Help menu
- Added the current application version to the Help menu
- Added a right-side page scrollbar and mouse-wheel scrolling for compact windows

## v3.4 - Dynamic colors and brightness

- Added per-profile 0–100% brightness control
- Added arbitrary multi-color gradients from center to outer edge
- Added color enable/disable, reorder, add, and delete controls
- Added automatic migration for legacy two-color profiles

## v0.1.0 - Initial public development version

- Calibrated 126-LED YG98 matrix
- Added Windows low-level keyboard hook
- Added multi-key cross-ripple rendering
- Added RGB center-to-outer gradient
- Added configurable color profiles
- Added persistent settings
- Added Windows login auto-start option
- Added Windows notification-area resident mode
- Fixed Python 3.13 `ctypes.wintypes.WNDCLASS` incompatibility
