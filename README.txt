Josh Calcino - personal website

Research pages have a visual browser editor at https://app.pagescms.org.
You can edit their writing, figures, captions, and references without editing HTML.
The editor is configured in .pages.yml; research content lives under content/.
Shared styling and gallery behavior are in assets/site.css and assets/site.js.
Images are served locally.

Live site: https://joshcalcino.github.io/website/

One-time editor setup:
  1. Sign in to https://app.pagescms.org with GitHub.
  2. Install/authorize the Pages CMS GitHub App for the selected repository
     joshcalcino/website, then open that repository and its main branch.
GitHub Pages is configured to publish through GitHub Actions.

For everyday editing, open a research article in Pages CMS. Use Article sections
to add, reorder, or edit Text, Figure, and Video sections. Text has a formatting
toolbar; figures have an upload field and caption. Save your changes to main.
Keep Published switched off while drafting. Switch it on when the article is ready.
Changes to published articles go live after the Publish website workflow succeeds
in GitHub Actions. The infall article remains an unpublished draft.

Local builds use Python 3.12 or newer and the standard library; no packages needed:
  python3 scripts/build_research.py
Run this after changing research content locally. It regenerates the research HTML
and includes drafts in the local preview.
For the separate complete site output used by GitHub Actions:
  python3 scripts/build_research.py --output _site
This production build excludes unpublished articles and their overview links.

Small text links beneath About Me point to two public PDFs under assets/cv/:
  Josh_Calcino_Academic_CV.pdf       Full academic CV
  Josh_Calcino_Data_Science_Resume.pdf  One-page data science resume
Keep these public filenames stable when replacing the PDFs. Use a neutral
document title in each PDF's metadata; do not use an employer-specific
application filename.

To preview from this repository directory:
  python3 -m http.server 8000 --bind 127.0.0.1 --directory ..
Then open http://127.0.0.1:8000/website/ (keep the directory named website).

Content and design reconstructed from archived joshcalcino.com pages. Original prose
is preserved. The separate infall article includes the newer AB Aur research draft.
The IRS48 simulation video was recovered from the original Wix page data.

Photography copyright Josh Calcino except images with an explicit credit.
Research sky image credit: ESO/S. Guisard.
