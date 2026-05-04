# qj5.2 — Saturn SVG → Settings button + per-chat popup

*2026-05-04T19:28:37Z by Showboat 0.6.1*
<!-- showboat-id: fe35050d-a8fc-424d-8c46-d2dc5b8a3eee -->

Awaiting bead Saturn-qj5.2 merge to autonomous/promo-push. Capture flow:

    bash tests/harness/run.sh

    python3 -m saturn web --port 3000 &

    rodney shoot http://localhost:3000 --tab chat --output demo/recordings/qj5.2.png

Then `uvx showboat image "demo/recordings/qj5.2.md" demo/recordings/qj5.2.png` and a one-paragraph diff narrative.
