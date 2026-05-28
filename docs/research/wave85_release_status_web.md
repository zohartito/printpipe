# Wave 85 - Release Status in Local Web UI

## Question

Can the local browser UI show the same final release gates as the
`printpipe release-status` CLI?

## Change

Wave 85 adds:

- `GET /release-status.json`
- a home-page `Release status` panel
- a `Release status JSON` link in the home page service section

The panel uses `build_release_status_report()` so it includes:

- release bundle integrity
- macOS distribution gate
- Windows distribution gate
- physical validation
- dependency readiness
- Bambu Studio readiness
- Bambu profile folder readiness
- filesystem readiness
- signing readiness

## Browser Smoke

After implementation, a local server was started on `127.0.0.1:8895`.

- `/` rendered `Release status`, `macOS distribution`, `Windows distribution`,
  and `Release status JSON`.
- `/release-status.json` returned `overall_status=action_required` with
  `release_bundle`, `macos_distribution`, and `windows_distribution` gate IDs.

## Boundary

This is a read-only visibility layer. It does not build a release folder,
notarize a DMG, sign a Windows installer, or create physical evidence packets.
