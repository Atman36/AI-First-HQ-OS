# Now

## Current Focus

- Prepare HQ for public GitHub publication as an AI-first operating system.
- Keep tracked history limited to reusable framework files, prompts, agents, scripts, tests, and public-safe example docs.
- Enforce a hard boundary between tracked project files and private runtime data under `.hq/`.

## This Month

- Ship a public-safe baseline for the repository.
- Keep the control plane validated and the board rendered from `05 AI Control Plane/active-work.json`.
- Add automated checks that block private runtime artifacts, secrets, and sensitive local files from entering git history.

## This Week

- Rewrite `README.md` for public readers.
- Sanitize tracked example planning and decision files.
- Add a publication-safety gate to local validation and GitHub Actions.
- Keep private user, customer, and personal data outside tracked history.

## Success Criteria

- The repository can be opened publicly without exposing live company state or private runtime data.
- `Task Board.md` is rendered from `active-work.json`, not edited by hand.
- Public-safe example docs remain useful as a template for new users.
- Validation fails when `.hq/`, credentials, or blocked private artifacts are tracked.
