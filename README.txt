Josh Calcino - personal website

The website has a visual browser editor at https://app.pagescms.org.
You can edit the pages, photos, figures, profile links, and PDFs without editing HTML.
The editor is configured in .pages.yml; editable page content lives under content/.
Shared styling and gallery behavior are in assets/site.css and assets/site.js.
Images are served locally.

Live site: https://joshcalcino.github.io/website/

Everyday editing:
  1. Open https://app.pagescms.org and select joshcalcino/website, branch main.
  2. Choose the page or Site settings in the sidebar and edit the fields.
     Formatted text uses a visual toolbar for headings, links, and images.
     Expand a list item to edit it; drag items to change their order.
  3. Save. Pages CMS saves to GitHub, and the Publish website workflow rebuilds
     and publishes the site automatically. Allow the workflow to finish before
     checking the live site.
Your existing Pages CMS connection to this repository works for all these editors;
no extra authorization is needed. GitHub Pages publishes through GitHub Actions.

What each editor changes:
  Home: your name, tagline, portrait, background, biography, interests, CV/resume
    downloads, and profile links. Each tagline line appears on a separate line.
  Public Outreach: introduction, background, audience comments, talks, and other
    activities. Add, edit, or reorder event sections and individual events.
  Astrophotography: introduction, its accompanying image, and the photo gallery.
    Add or remove gallery items and drag them to change their order. Each photo
    has an image description and optional caption. An optional full-size image
    opens in the enlarged view; otherwise the gallery image is used.
  Site settings: the site name, mobile header, footer, navigation links, default
    image for shared links, Research background, and page-not-found message.
  Research articles: writing, figures, captions, references, and videos. Use
    Article sections to add or reorder Text, Figure, and Video sections.
    Keep Published off while drafting and turn it on when an article is ready.
  Research introduction: the heading and introductory text on the Research page.
Each page also has a browser tab title and a short description for search results.

Images and PDFs:
  Images and figures contains the existing image library. General image uploads
    go to assets/images; Research figure uploads go to assets/research. The
    optional full-size photography picker opens assets/originals.
  CV and resume PDFs contains the downloadable documents under assets/cv.
    Upload a PDF there, then select it in Home > CV and resume links. To replace
    a linked PDF without changing its address, keep the existing filename.
    Upload renaming is disabled for PDFs.
  Existing public PDF filenames:
    Josh_Calcino_Academic_CV.pdf          Full academic CV
    Josh_Calcino_Data_Science_Resume.pdf  One-page data science resume
  Use a neutral document title in each PDF's metadata; do not use an
    employer-specific application filename.

Local builds use Python 3.12 or newer and the standard library; no packages needed:
  python3 scripts/build_site.py
Run this after changing content locally. It regenerates the website HTML and
includes research drafts in the local preview. The older command
python3 scripts/build_research.py remains available for compatibility.
For the separate complete site output used by GitHub Actions:
  python3 scripts/build_site.py --output _site
This production build excludes unpublished articles and their overview links.

To preview from this repository directory:
  python3 -m http.server 8000 --bind 127.0.0.1 --directory ..
Then open http://127.0.0.1:8000/website/ (keep the directory named website).

Content and design reconstructed from archived joshcalcino.com pages. Original prose
is preserved. The separate infall article includes the newer AB Aur research draft.
The IRS48 simulation video was recovered from the original Wix page data.

Photography copyright Josh Calcino except images with an explicit credit.
Research sky image credit: ESO/S. Guisard.
