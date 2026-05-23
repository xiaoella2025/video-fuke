This folder holds image/video assets for the 25cm case.

It starts empty in the repo. To populate it, on a machine with normal internet access run:

    python3 scripts/build-course-data.py

That single command both rebuilds courseData.json AND downloads every image listed
in asset-manifest.json into this folder. Re-run it any time to retry missing files.

You can safely ignore this folder in `git status` — assets are large; commit them
only if you want every device to have a pre-populated copy.
