# UtilityForge CSV Studio — Hosted Pilot

A stand-alone browser-only CSV cleaning and conversion utility. Free-to-use tool with no analytics, logins, uploads, backend, or payment integration.

## Run

Open `site/index.html` directly in any modern browser (no package installation). Or run `python3 -m http.server 8080 --directory site` inside this folder.

## Tests

```sh
node --test tests/smoke.test.cjs
```

## Release safety

Dedicated branch: `utilityforge-deploy` in the existing Build repository. Original `main` is unaffected. Render static-site publish directory: `utilityforge/site`. Static HTML is intentional; no paid resources or dependencies are required.

The hosted pilot has no paid checkout until a separate payment-provider merchant account and delivery test are confirmed. No revenue, traffic, or indexing claims are made. Never commit proprietary paid bundles to this public branch.

The fully featured local source package and separately licensed batch cleaning template pack are maintained as offline deliverables, not this public branch. Automated tests cover data transformations and source controls, not live buyer conversion.
