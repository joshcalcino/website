"""Validate editable homepage content and render it with the shared document shell."""

from html import escape
from pathlib import Path
from string import Template


def load_content(root, *, read_json, require_text, rich_text, image_path, asset_path, link_url):
    source = "content/home.json"
    data = read_json(root / source)
    if not isinstance(data, dict):
        raise ValueError(f"{source}: expected a JSON object")
    for key in ("title", "description", "name", "about_heading"):
        require_text(data, key, source)
    data["background"] = image_path(data.get("background"), source + ": background")
    portrait = data.get("portrait")
    if not isinstance(portrait, dict):
        raise ValueError(f"{source}: portrait must be an object")
    portrait["src"] = image_path(portrait.get("src"), source + ": portrait")
    require_text(portrait, "alt", source + ": portrait")
    if data.get("tagline") is None:
        data["tagline"] = ""
    require_text(data, "tagline", source, allow_empty=True)
    rich_text(data, "biography", source)
    if data.get("interests") is None:
        data["interests"] = ""
    rich_text(data, "interests", source, allow_empty=True)

    for key in ("downloads", "social_links"):
        if data.get(key) is None:
            data[key] = []
        if not isinstance(data[key], list):
            raise ValueError(f"{source}: {key} must be an array")
    for index, download in enumerate(data["downloads"]):
        label = f"{source}: download {index + 1}"
        if not isinstance(download, dict):
            raise ValueError(f"{label}: expected an object")
        require_text(download, "label", label)
        download["file"] = asset_path(download.get("file"), label + ": file", extensions={".pdf"})
    for index, social in enumerate(data["social_links"]):
        label = f"{source}: social link {index + 1}"
        if not isinstance(social, dict):
            raise ValueError(f"{label}: expected an object")
        require_text(social, "label", label)
        social["url"] = link_url(social.get("url"), label + ": url")
        if social.get("icon") in (None, ""):
            social["icon"] = "none"
        if social["icon"] not in ("github", "linkedin", "none"):
            raise ValueError(f"{label}: icon must be github, linkedin, or none")
    return data


def render(data, *, root, document, dimension_attributes):
    template = Template((root / "templates/home.html").read_text(encoding="utf-8"))
    links = []
    for download in data["downloads"]:
        links.append('<a href="' + escape(download["file"], quote=True) + '">' + escape(download["label"]) + ' <span>(PDF)</span></a>')
    for social in data["social_links"]:
        icon = ""
        if social["icon"] != "none":
            icon = (root / "templates/icons" / (social["icon"] + ".svg")).read_text(encoding="utf-8").rstrip("\n")
        links.append('<a class="profile-link" href="' + escape(social["url"], quote=True) + '">' + icon + escape(social["label"]) + '</a>')
    separator = '<span class="cv-separator" aria-hidden="true">·</span>'
    link_row = '<p id="cv" class="cv-links">' + separator.join(links) + '</p>' if links else ""
    tagline = escape(data["tagline"]).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    body = template.substitute(
        portrait=escape(data["portrait"]["src"], quote=True),
        portrait_dimensions=dimension_attributes(data["portrait"]["src"]),
        portrait_alt=escape(data["portrait"]["alt"], quote=True),
        name=escape(data["name"]), tagline=tagline,
        about_heading=escape(data["about_heading"]),
        biography=data["biography"], interests=data["interests"], link_row=link_row,
    )
    return {Path("index.html"): document(
        data["title"], data["description"], "/", body,
        body_class="home photo-background", background=data["background"], image=data["background"],
    )}
