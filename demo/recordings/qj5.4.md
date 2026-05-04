# qj5.4 — + menu replaces 5 unlabeled icons

*2026-05-04T19:28:39Z by Showboat 0.6.1*
<!-- showboat-id: 6cc15a63-befd-40e2-8471-4e7dc0d6c718 -->

Awaiting bead Saturn-qj5.4 merge to autonomous/promo-push. Capture flow:

    bash tests/harness/run.sh

    python3 -m saturn web --port 3000 &

    rodney shoot http://localhost:3000 --tab chat --output demo/recordings/qj5.4.png

Then `uvx showboat image "demo/recordings/qj5.4.md" demo/recordings/qj5.4.png` and a one-paragraph diff narrative.
