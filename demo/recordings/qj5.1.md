# qj5.1 — top-right style pill removed

*2026-05-04T19:28:37Z by Showboat 0.6.1*
<!-- showboat-id: 5a0b4eaf-75f2-4144-80aa-5c4af7b81344 -->

Awaiting bead Saturn-qj5.1 merge to autonomous/promo-push. Capture flow:

    bash tests/harness/run.sh

    python3 -m saturn web --port 3000 &

    rodney shoot http://localhost:3000 --tab chat --output demo/recordings/qj5.1.png

Then `uvx showboat image "demo/recordings/qj5.1.md" demo/recordings/qj5.1.png` and a one-paragraph diff narrative.
