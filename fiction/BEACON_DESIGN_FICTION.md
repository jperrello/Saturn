# Saturn Beacon Design Fiction

## Meet Jordan, The Developer Who Learned Fear

Jordan's team had The Incident last year. An intern's laptop got stolen. With it: API keys hard-coded in config files, Slack DMs, browser bookmarks, and one very embarrassing sticky note.

The 2 AM response:
- Emergency key rotation across every system
- Security audit (keys found in 47 different places, including one in a commented-out test)
- New workflow: Weekly manual rotation, separate keys per person/device/environment
- Jordan's new title: "Person Who Worries About Credentials Now"

This workflow is secure. It's also a full-time job.

**At a conference, someone mentions Saturn Beacons. Jordan's response: "Hard pass."**

"Network-based credentials? That's just shared WiFi passwords with extra steps."

But beacons aren't WiFi passwords. Here's what they actually do:

The beacon generates ephemeral JWTs from DeepInfra with a 10-minute expiration. It rotates them every 5 minutes. It broadcasts them via mDNS (local network only). Clients discover the beacon automatically, extract the current JWT, and use it to call AI APIs directly.

Laptop stolen? The key expires in less than 10 minutes. Employee leaves the company? They leave the network, credentials die automatically. No revocation lists. No emergency 2 AM rotations. No keys persisted in configs, DMs, or sticky notes.

Jordan runs a beacon on a Raspberry Pi in the server closet. Setup time: 5 minutes. Ongoing maintenance: zero. Security incidents since deployment: also zero.

**Jordan still worries about credentials. But now they worry significantly less.**
