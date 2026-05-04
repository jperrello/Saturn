# qj5.6 — Edit-sent-message: truncate-and-regenerate

*2026-05-04T19:28:39Z by Showboat 0.6.1*
<!-- showboat-id: b8a9b66b-d647-4ea4-99bc-50a1434289f7 -->

Awaiting bead Saturn-qj5.6 merge to autonomous/promo-push. Capture flow:

    bash tests/harness/run.sh

    python3 -m saturn web --port 3000 &

    rodney shoot http://localhost:3000 --tab chat --output demo/recordings/qj5.6.png

Then `uvx showboat image "demo/recordings/qj5.6.md" demo/recordings/qj5.6.png` and a one-paragraph diff narrative.
