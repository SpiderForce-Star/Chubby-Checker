# Ascent Shipper Checker — Brand Assets

**Official name:** Ascent Shipper Checker  
**Code name:** Chubby Checker

## Required files in this folder

Place the official Ascent Buildings logo here:

| File | Purpose |
|------|--------|
| `ascent_logo.png` | Master logo (preferred) |
| `ascent_logo.jpg` | Alternate master |
| `app_icon.png` | 256×256 app icon |
| `icon_256.png` | Standard mid-size icon |
| `ascent_chubby.ico` | Windows Desktop shortcut icon (**Ascent Chubby**) |
| `ascent_shipper_checker.ico` | Alternate Windows application icon |
| `software_banner.png` | Banner with software name |

## How to add the logo (GitHub web UI)

1. Open the repo on GitHub.
2. Go to `assets/branding/` (create folders if needed via **Add file → Create new file** with path `assets/branding/README.md`).
3. Click **Add file → Upload files**.
4. Drag in `ascent_logo.png` (and optional icon sizes).
5. Commit to `main` with message: `Add Ascent Buildings logo branding assets`.

## How to add via git (local)

```bash
git clone https://github.com/SpiderForce-Star/Chubby-Checker.git
cd Chubby-Checker
mkdir -p assets/branding
# copy your logo files into assets/branding/
cp /path/to/ascent_buildings_llc_logo.jpg assets/branding/ascent_logo.jpg
cp /path/to/ascent_logo.png assets/branding/ascent_logo.png
# optional icons
cp /path/to/app_icon.png assets/branding/app_icon.png

git add assets/branding/
git commit -m "Add Ascent Buildings logo branding assets"
git push origin main
```

## Usage in the software

- **PDF reports** embed `assets/branding/ascent_logo.png` in the header when the file exists.
- **Desktop / installer icons** should use `app_icon.png` or `ascent_shipper_checker.ico`.
- **README** can display the logo with:

```markdown
![Ascent Shipper Checker](assets/branding/ascent_logo.png)
```
