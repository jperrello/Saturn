# Banner (Navigation Bar)

Top-level navigation bar persistent across all pages.

## Structure
- **Tab buttons**: Discover, Start, Chat — centered with equal spacing across the full width
- No brand label or logo in the nav bar

## Behavior
- Clicking a tab adds `.active` to that tab and its corresponding `<section>` page
- Removes `.active` from all other tabs and pages
- Discover tab is active by default on load

## HTML
```html
<nav class="tabs">
  <button class="tab active" data-tab="discover">Discover</button>
  <button class="tab" data-tab="start">Start</button>
  <button class="tab" data-tab="chat">Chat</button>
</nav>
```

Tab switching is handled by a `data-tab` attribute that matches the `id` of the target `<section>`.
