# qj5.3 — MCP TOOLS popup with Add-MCP flow

*2026-05-04T19:28:38Z by Showboat 0.6.1*
<!-- showboat-id: a5263221-0525-47ae-b1c3-f59ab3db2be7 -->

Awaiting bead Saturn-qj5.3 merge to autonomous/promo-push. Capture flow:

    bash tests/harness/run.sh

    python3 -m saturn web --port 3000 &

    rodney shoot http://localhost:3000 --tab chat --output demo/recordings/qj5.3.png

Then `uvx showboat image "demo/recordings/qj5.3.md" demo/recordings/qj5.3.png` and a one-paragraph diff narrative.
