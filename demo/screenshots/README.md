# Web UI screenshots — BLOCKED

The Web UI is not currently functional. `Web-UI/index.html` (post
hardener fix `896c56d`) loads `app.js` as a classic script:

```html
<script src="app.js"></script>
```

But `Web-UI/app.js:1-3` begins with ES module imports:

```js
import * as THREE from 'three'
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js'
```

The browser parses `app.js` as a classic script, fails on the first
`import`, and runs none of the app code. Result: tab buttons render
but switching tabs does nothing, the scan button has no listener, and
the discover/chat/system panels never populate. The backend
(`/api/discover`, `/api/services`, `/api/admin/auth`) is fine.

`web-ui-blocked.png` is a representative shot of what the page looks
like in this state (admin gate visible, all panels inert).

Tracked as **bd issue Saturn-kul** (P0). Once that lands, re-run:

```sh
saturn web --port 3030 &
saturn ollama &
rodney start
rodney open http://127.0.0.1:3030/
# unlock with default password 'saturn', then screenshot each tab
```

The four target screenshots — discover with a Saturn service visible,
chat mid-conversation, system tab, tools tab — should be added here
under `01-discover.png`, `02-chat.png`, `03-system.png`,
`04-tools.png`.
