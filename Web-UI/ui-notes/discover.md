# Discover Page

Default landing page. Two-column layout.

## Left Column — Saturn Visualization

Animated Saturn using textmode.js. Falls back to ASCII art `<pre>` if library fails to load. Canvas renders at 24fps.

### Planet
- Rotated 45 degrees
- Rings overlaid on top of the planet body with gaps — space background visible through both the rings and the planet, so the rings appear to surround the planet rather than stick out like arms

### Stars
- 50 stars with sine-wave brightness

### Moons
- Number of orbiting moons = number of online services on the network
- All moons orbit by default (neutral color)
- When a user checks a service in the right column, the corresponding moon turns green
- Only selected services' moons are green; the rest remain neutral

### Scanning Animation
- Triggered when "Discover" button is pressed
- Stars pulse faster/brighter, ring glows, horizontal scan line sweeps vertically
- Scan line and glow are **green** (not yellow/golden)

## Right Column

### Discover Button
- Single "Discover" button at the top
- No heading or description text above it
- Always remains as "Discover" — no state change to "Refresh"
- Can be pressed at any time to re-scan

### Service Checklist
- Empty until first scan completes
- After scan, a checklist drops in below the button
- Each item has a checkbox, name, and colored status label (green = online, red = offline)

## Mock Services
| Name | Status |
|---|---|
| derrick-LLMBuffet | online |
| OpenRouter-Proxy | online |
| OLLAMA-local | online |
| lab-gpu-cluster | offline |

## Interaction Flow
1. User lands on page — right column has only the "Discover" button, left column animation is idle
2. User clicks "Discover" — left column enters scanning mode (green glow/scan line), 2-second mock scan
3. After scan — service checklist drops in below the button, moons appear (one per online service)
4. User checks services — corresponding moons turn green
5. User can click "Discover" again at any time to re-scan

## Reference Images
- `references/01-discover.jpeg`
