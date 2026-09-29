# Source audit

No real source has been approved in V0.1 yet.

For every candidate source, record the following evidence before crawling:

- source ID, site name, base/list/detail/PDF URLs;
- content owner or publisher;
- exam types and years;
- whether answers are official, third-party, or absent;
- login, CAPTCHA and paywall status;
- date and result of robots review;
- terms URL, review date and relevant restriction summary;
- licence evidence and one of `allowed`, `research_only`, `unknown`,
  `restricted`;
- separate redistribution decision;
- approver, approval time, collector and notes.

`approved` permits the configured collection workflow. It does not override
`redistribution_allowed: false`. Unknown or research-only material remains out
of a public dataset release.
