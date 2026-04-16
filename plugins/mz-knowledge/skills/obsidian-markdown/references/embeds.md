# Embeds Reference

Source: Obsidian Flavored Markdown embeds. Grep this file for the specific embed variant you need — do not load the whole file.

## Basic Note Embed

```
![[Note Name]]                  — embed the full note
![[Note Name#Heading]]          — embed from heading to the next same-level heading
![[Note Name#^block-id]]        — embed a specific block
```

## Image Embed

```
![[image.png]]
![[image.png|200]]              — width in pixels
![[image.png|200x100]]          — width x height in pixels
```

## Audio Embed

```
![[audio.mp3]]
```

Supported formats: `.mp3`, `.webm`, `.wav`, `.m4a`, `.ogg`, `.3gp`, `.flac`.

## Video Embed

```
![[video.mp4]]
```

Supported formats: `.mp4`, `.webm`, `.ogv`, `.mov`, `.mkv`.

## PDF Embed

```
![[file.pdf]]
![[file.pdf#page=3]]            — open at page 3
![[file.pdf#height=400]]        — set embed height in pixels
```

## Block Embed (any note type)

```
![[Note#^block-id]]
```

## Search Query Embed

````
```query
search term
```
````

Creates a live search results embed in Reading View.

## Notes

- Embeds render in Reading View and in Obsidian's preview; in Source Mode they appear as plain wikilink syntax.
- Image size syntax is `|W` or `|WxH` placed after the filename, before the closing `]]`.
- Embeds can be nested, but deep nesting degrades rendering performance.
- Heading embeds capture everything from the target heading up to (but not including) the next heading of the same or shallower level.
