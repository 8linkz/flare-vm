# Upstream PR Review Log

This fork tracks open pull requests on [mandiant/flare-vm](https://github.com/mandiant/flare-vm/pulls).
Each upstream PR is reviewed once; valid changes are cherry-picked into this fork
(one branch per PR, named `pr-<number>-<slug>`), invalid ones are recorded here so
they are not re-reviewed.

Verdicts: **APPLIED** (cherry-picked into this fork) · **REJECTED** (not taken) · **DEFERRED** (needs upstream changes first).

| PR | Title | Verdict | Fork branch | Reviewed |
|----|-------|---------|-------------|----------|
| [#748](https://github.com/mandiant/flare-vm/pull/748) | Update README.md (add Windows 11 ISO link) | APPLIED | `pr-748-readme-win11` | 2026-08-15 |
| [#744](https://github.com/mandiant/flare-vm/pull/744) | Improve documentation about Windows Defender blocking malware (#442) | REJECTED | – | 2026-08-15 |

## Notes

### #748 – Update README.md
- Pure docs change (3 lines): replaces the single Windows 10 ISO link in "Pre-installation"
  with a list of Windows 10 and Windows 11 download links.
- Correct and harmless; the Windows 11 URL is the official Microsoft download page.
- Only stuck upstream because the author has not signed the Google CLA.
- Minor nits not worth fixing: "windows" lowercased, 5-space indent (renders fine).

### #744 – Windows Defender still blocking malware
- Adds a generic "Windows Defender still blocking malware" troubleshooting section plus
  unintended whitespace changes (extra blank line before the parameters block, trailing
  spaces on `## Legal Notice`).
- Rejected because:
  - No added value: the Requirements section already states that Tamper Protection and
    Defender must be disabled (preferably via GPO) and links four concrete methods.
  - The listed "workarounds" are trivial or unverified: "run inside an isolated VM"
    (FLARE-VM *is* the VM), "use Windows 10 21H2 before upgrading" (single 2023 user
    report from issue #442), "disable via Group Policy" (already documented).
  - Upstream maintainer (PrajeetGuha) requested specific troubleshooting steps and a
    Windows 11 check; the author has not responded since March 2026.
- The only useful nugget from issue #442 is "verify Defender is really off with the
  EICAR test file after each reboot; on recent Windows builds it may take several
  attempts". If ever documented in this fork, add that single sentence to the
  Requirements section instead of a new chapter.

## Remaining open upstream PRs (as of 2026-08-15)

- #740 Fix installer pre-check UI layout by using scrollable panel
- #733 Another option to disable Defender - by using dummy antivirus
- #731 [install.sh] Update Test-WebConnection function to check connectivity more robustly
- #723 Add configurable categories to GUI FLARE-VM Installer
- #710 fix(install): add null check for package feed entries to prevent errors on empty or malformed XML
