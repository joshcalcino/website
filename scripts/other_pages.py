"""Content and rendering for the outreach and astrophotography pages."""

from html import escape
from pathlib import Path
from string import Template


def _objects(data, key, source):
    """Allow an optional CMS list to be omitted, cleared, or left empty."""
    values = data.get(key)
    if values is None:
        values = data[key] = []
    if not isinstance(values, list):
        raise ValueError(f"{source}: {key} must be an array")
    if any(not isinstance(value, dict) for value in values):
        raise ValueError(f"{source}: every {key} entry must be an object")
    return values


def load_content(root, *, read_json, require_text, rich_text, image_path,
                 asset_path, link_url):
    """Read and validate both pages before the calling builder writes output."""
    root = Path(root)
    outreach = read_json(root / "content/outreach.json")
    source = "content/outreach.json"
    for key in ("title", "description", "heading"):
        require_text(outreach, key, source)
    image_path(outreach.get("background"), source + ": background")
    rich_text(outreach, "introduction", source)
    rich_text(outreach, "testimonials_intro", source, allow_empty=True, optional=True)
    for index, testimonial in enumerate(_objects(outreach, "testimonials", source)):
        rich_text(testimonial, "quote", f"{source}: testimonial {index + 1}")
    for index, section in enumerate(_objects(outreach, "event_sections", source)):
        label = f"{source}: event section {index + 1}"
        require_text(section, "heading", label)
        for event_index, event in enumerate(_objects(section, "events", label)):
            event_label = f"{label}: event {event_index + 1}"
            require_text(event, "date", event_label)
            rich_text(event, "description", event_label)

    photography = read_json(root / "content/photography.json")
    source = "content/photography.json"
    for key in ("title", "description", "heading"):
        require_text(photography, key, source)
    rich_text(photography, "introduction", source)
    intro_image = photography.get("intro_image")
    if not isinstance(intro_image, dict):
        raise ValueError(f"{source}: intro_image must be an object")
    image_path(intro_image.get("src"), source + ": introduction image")
    require_text(intro_image, "alt", source + ": introduction image")
    for index, photo in enumerate(_objects(photography, "gallery", source)):
        label = f"{source}: photograph {index + 1}"
        image_path(photo.get("image"), label)
        require_text(photo, "alt", label)
        if photo.get("original") in (None, ""):
            photo["original"] = ""
        else:
            image_path(photo["original"], label + ": original")
        if photo.get("caption") is None:
            photo["caption"] = ""
        require_text(photo, "caption", label, allow_empty=True)
    return {"outreach": outreach, "photography": photography}


def render(data, *, root, document, dimension_attributes):
    """Render page bodies with the site's shared document and image helpers."""
    root = Path(root)
    templates = {
        name: Template((root / "templates" / (name + ".html")).read_text(encoding="utf-8"))
        for name in ("outreach", "photography", "gallery-item")
    }
    outreach = data["outreach"]
    testimonials = "".join(
        "<blockquote>" + item["quote"] + "</blockquote>"
        for item in outreach["testimonials"]
    )
    event_sections = []
    for section in outreach["event_sections"]:
        events = "".join(
            '<div class="event"><dt>' + escape(event["date"]) + "</dt><dd>"
            + event["description"] + "</dd></div>"
            for event in section["events"]
        )
        event_sections.append(
            '<section class="event-section"><h2>' + escape(section["heading"])
            + "</h2><dl>" + events + "</dl></section>"
        )
    outreach_body = templates["outreach"].substitute(
        heading=escape(outreach["heading"]), introduction=outreach["introduction"],
        testimonials_intro=outreach["testimonials_intro"], testimonials=testimonials,
        event_sections="".join(event_sections),
    )

    photography = data["photography"]
    intro_image = photography["intro_image"]
    gallery = []
    for index, photo in enumerate(photography["gallery"], start=1):
        gallery.append(templates["gallery-item"].substitute(
            href=escape(photo["original"] or photo["image"], quote=True),
            image=escape(photo["image"], quote=True),
            dimensions=dimension_attributes(photo["image"]),
            caption=escape(photo["caption"], quote=True),
            alt=escape(photo["alt"], quote=True),
            label=escape(f"View photograph {index}: {photo['alt']}", quote=True),
        ))
    photography_body = templates["photography"].substitute(
        heading=escape(photography["heading"]), introduction=photography["introduction"],
        intro_image=escape(intro_image["src"], quote=True),
        intro_dimensions=dimension_attributes(intro_image["src"]),
        intro_alt=escape(intro_image["alt"], quote=True), gallery="".join(gallery),
    )
    return {
        Path("public-outreach/index.html"): document(
            outreach["title"], outreach["description"], "/public-outreach/", outreach_body,
            body_class="photo-background outreach", background=outreach["background"],
        ),
        Path("astrophotography/index.html"): document(
            photography["title"], photography["description"], "/astrophotography/", photography_body,
            body_class="photography",
        ),
    }
