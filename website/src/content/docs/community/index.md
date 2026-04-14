---
title: Community
description: Where to ask questions, find collaborators, and follow Magellon development.
---

import { Card, CardGrid, LinkCard } from '@astrojs/starlight/components';

Magellon is developed openly. There are a few places to plug in depending on what you need.

<CardGrid>
    <LinkCard
        title="Source Code"
        description="The full Magellon repository on GitHub — issues, pull requests, releases."
        href="https://github.com/sstagg/Magellon"
    />
    <LinkCard
        title="Discussion Group"
        description="Connect with other Magellon users and developers."
        href="https://www.magellon.org/groups"
    />
    <LinkCard
        title="CryoSift"
        description="Companion tool for cryo-EM data triage from the same group."
        href="https://www.cryosift.org"
    />
</CardGrid>

## Getting help

- **Bug or feature request?** Open an issue on [GitHub](https://github.com/sstagg/Magellon/issues).
- **General question?** Post in the [discussion group](https://www.magellon.org/groups) so the answer helps the next person too.
- **Security report?** Email the maintainers privately rather than filing a public issue.

## Contributing

Pull requests are welcome — small fixes, documentation tweaks, and new plugins all land through the same flow:

1. Fork the repo and create a topic branch.
2. Make your change with tests where applicable.
3. Open a PR against `main` describing what changed and why.

For a new plugin, see the [Plugins guide](/usage/plugins/) — the framework handles discovery, schema exposure, and progress streaming, so most of the work is the science itself.
