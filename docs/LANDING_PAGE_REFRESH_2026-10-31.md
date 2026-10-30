# Mainspring landing page refresh — 31 October 2026

Chat: [Compare app update history](codex://threads/01a18ebd-4c43-7303-af9a-9fbdca9cf32d).

The user requested a new landing page that feels less AI-designed and draws on Figma, Wix or Shopify templates. They selected **clean software: real app screenshots, crisp type, restrained colour**. The earlier landing-page chat also requested navy/white/blue, real product captures and no Minit logo; these preferences were retained.

## Implementation and review

- Isolated checkout: `C:/Users/samme/mainspring-landing-page-20261031`, branch `codex/landing-page-20261031`, based on GitHub main `91442165` (the verified live web build when this work began).
- Local preview: `http://127.0.0.1:5178/` (run `npm run dev -- --host 127.0.0.1 --port 5178 --strictPort` from its `frontend` directory if stopped).
- Replaced `frontend/src/pages/LandingPage.tsx`; added route-scoped `LandingPage.css` and four JPEGs in `frontend/public/marketing/product/`.
- White/navy/blue page; real product screen switcher with keyboard navigation, accessible native enlargement dialog, mobile menu, trade pages, pricing, FAQs and functional privacy/account-deletion/repair-tracking links.
- Retains signed-in dashboard redirect, existing routes, pricing and trial/card disclosures. No invented testimonials, customer logos, success metrics or fabricated product panels.
- Screenshots captured on 31 October from the existing public demo: watch job list, mobile job list, invoices and watch repair ticket. Records are demo/sample records. Captures show the actual UI and retain its own colours; no real-shop customer records were used.
- Initially delivered as a local preview. The user subsequently approved pushing the completed landing page to main (see below). No additional Google Play update was performed.

## Template references and provenance

Reviewed [Wix SaaS templates](https://www.wix.com/website/templates/refine/saas-company), including [Bright](https://www.wix.com/website-template/view/html/4261) and [Luminous](https://www.wix.com/website-template/view/html/3831), plus [Figma's landing-page examples](https://www.figma.com/resource-library/landing-page-examples/) and its [Trustworthy app download template](https://www.figma.com/community/file/1498087976362579412/trustworthy-app-download).

These are **visual references**, not imported template source. This implementation is original React/CSS within Mainspring. No paid template was bought, no Wix/Shopify theme code or stock assets were copied, and the site has not been moved to another hosting platform. Reference screenshots are kept in the local artifacts folder, outside the shipped assets.

## Verification

- Production TypeScript/Vite build passed; targeted ESLint passed.
- Existing legal-page and route-registration checks: 10 tests passed.
- Browser checks: product tabs, Home-key tab navigation, enlargement dialog, Escape dismissal, FAQ expansion and mobile navigation. Mobile enlarged images scroll at readable width.
- Responsive checks at 320, 390, 768 and 1440 px: all images loaded, no document horizontal overflow. Desktop and full-page mobile visually inspected.
- Preview captures: `artifacts/landing-page-2026-10-31/desktop-hero.jpg`, `desktop.jpg`, `mobile.jpg` in the isolated checkout. Build output log is in the same directory.

Further visual feedback should be applied to this isolated checkout; preserve the central workspace's unrelated work.

## Accepted revision

The user liked the preview and requested removing FAQs. Removed the FAQ content, navigation link, data and unused styles. Pricing now leads directly into the closing call to action.

## Final polish

The user accepted adding Track a repair to the header, tightening the hero description and replacing small-screen desktop previews with genuine phone screenshots. Captured fresh watch-list, mobile-services and invoice phone screens from the public demo. Header tracking stays visible on phones; login remains available in the mobile menu. Browser verified all phone sources load, desktop still uses the wide capture, and 320/390/1440 layouts have no horizontal overflow.

## Main publication approval

The user approved pushing this landing page to main on 31 October 2026. The branch contains commits ebc8bed1 and 4274291e, with the FAQ removed and the final navigation/mobile polish included. Production build, targeted ESLint and diff checks passed; remote main was still 91442165 immediately before pushing. Local research/QA artifacts are excluded. Live deployment is separate from Git push and must be verified before calling the page live.
