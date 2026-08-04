# VOSK Icon System Prototype

Prototype for the VOSK Android/Kivy icon system. This directory is a design artifact only; the app code, KV files, versions, APK build, TEST and PRODUCTION releases are not wired to these assets yet.

## Structure

- `svg/system/` - 24x24 UI/navigation/action/payment symbols.
- `svg/categories/` - 64x64 section/category icons.
- `png/light/` - exported PNG checks for light surfaces.
- `png/dark/` - exported PNG checks for dark/navy surfaces.
- `png/previews/` - contact sheets for visual review.

## Grids And Stroke

### System Icons

- `viewBox="0 0 24 24"`
- Primary display size: 24 dp
- Allowed display sizes: 20, 22, 24 dp
- Stroke width: 1.8
- `stroke-linecap="round"`
- `stroke-linejoin="round"`
- Safe area: at least 2 px
- Background: transparent
- Fill: none, except deliberate symbol construction details

### Category Icons

- `viewBox="0 0 64 64"`
- Primary display size: 40-48 dp
- Preview/export sizes: 48, 96, 192 px
- Stroke width: 2-2.5 px
- Safe area: at least 5 px
- Simple fills, no texture, no raster, no inner shadow, no heavy 3D

## Palette

### System, Light Theme

- Primary: `#171A16`
- Secondary: `#687064`
- Disabled: primary at 38% opacity

### System, Dark/Navy Theme

- Primary: `#F5F6F2`
- Secondary: `#AEB5AA`
- Disabled: primary at 40% opacity

### Category

- Olive: `#718238`
- Light olive: `#9CAB59`
- Dark olive: `#344019`
- Outline: `#1D2410`
- Khaki detail: `#B3A36F`

## Icon Intent

### System Icons

- `back.svg` - screen navigation back.
- `chevron_right.svg` - list/card forward affordance.
- `copy.svg` - copy promo code or structured text.
- `close.svg` - dismiss modal, sheet, or inline panel.
- `promo_code.svg` - promo code/tag action.
- `ruble.svg` - ruble payment symbol. The ruble mark is built from paths, not a font glyph.
- `ct_coin.svg` - CT payment coin. The CT mark is constructed from strokes, not a font dependency.
- `gift.svg` - gift/free item marker.

### Category Icons

- `my_orders.svg` - closed parcel box, not a clipboard.
- `uniform.svg` - front-facing short-sleeve uniform/t-shirt.
- `gear.svg` - front-facing compact backpack with handle and front pocket.
- `chevrons.svg` - three upward military chevrons, no star/shield/crest.

## Recoloring Rules

- System SVGs use `currentColor`; they may be recolored by theme/state.
- Category SVGs use fixed prototype palette for visual review; production can later be tokenized if needed.
- Category icons should not be recolored randomly per section.
- Payment symbols may use system active/muted colors but must stay circular signs.

## Future Category Medallions

For `office_kit.svg`, `new_vkpo.svg`, and `old_vkpo.svg`, use a separate medallion subtype:

- circular olive medallion background;
- dark contour;
- object inside medallion;
- office kit = chair;
- new VKPO = soldier in helmet and vest;
- old VKPO = tactical vest only.

Do not mix medallions into the top-level Voentorg category icons unless the whole group is redesigned together.

## Export Commands

Preferred production export when tooling is installed:

```bash
# System icons
for f in svg/system/*.svg; do
  name=$(basename "$f" .svg)
  rsvg-convert -w 24 -h 24 "$f" -o "png/light/${name}_24.png"
  rsvg-convert -w 48 -h 48 "$f" -o "png/light/${name}_48.png"
  rsvg-convert -w 96 -h 96 "$f" -o "png/light/${name}_96.png"
done

# Category icons
for f in svg/categories/*.svg; do
  name=$(basename "$f" .svg)
  rsvg-convert -w 48 -h 48 "$f" -o "png/light/${name}_48.png"
  rsvg-convert -w 96 -h 96 "$f" -o "png/light/${name}_96.png"
  rsvg-convert -w 192 -h 192 "$f" -o "png/light/${name}_192.png"
done
```

If `rsvg-convert` is unavailable, use `cairosvg` or Inkscape with equivalent sizes.

## License Notes

No external icon library geometry was copied into this prototype. Shapes are authored for VOSK from simple SVG primitives and paths inspired by the provided interface references.

## Constraints

- No embedded rasters in SVG.
- No base64.
- No external URLs.
- No emoji.
- No mixed Material/Cupertino/Feather/Heroicons set.
- No hard dependency on a system font for ruble or CT signs.
- No elements outside the viewBox.
- File names must stay lowercase snake_case.
