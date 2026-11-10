# CU-200 WebAR demo

Static site. No build step.

## Deploy
1. Push this folder to a new GitHub repo.
2. Vercel → Add New Project → import the repo → Framework preset: Other → Deploy.
3. Open the deployed URL on desktop. The page shows a QR code. Scan it with a phone.
4. Tap "View in your space".

AR needs HTTPS and a real phone. Android uses Scene Viewer / WebXR; iPhone uses AR Quick Look.

## Swap in a real machine
Replace `cu200.glb` with your own GLB (same file name).
- Export from CAD (SolidWorks/Fusion/Onshape → glTF/GLB), or convert STEP via Blender.
- For the exploded view, bake one animation named `Explode` in Blender:
  assembled at 0.8 s, fully exploded at 2.6 s, reassembled by 5.6 s, loop ends at 7.0 s.
  Or change `T0`/`T1` in index.html to match your own timing.
- Update the `parts` array in index.html: `mat` must match a material name in the GLB.
- Keep the file under ~10 MB for fast loading on mobile data.

## Regenerate the stand-in model
`python3 make_glb.py cu200.glb` (no dependencies).
