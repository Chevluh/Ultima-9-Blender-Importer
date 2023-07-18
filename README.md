# Ultima 9 model importer
A Blender importer for models used in the 1999 game *Ultima IX: Ascension*

Features
--------

This can import most models used in Ultima 9, with reasonable approximations of the in-game shaders for Eevee and Cycles. Overall it should allow for a fairly faithful viewing experience.

Two importers are provided. The **terrain importer** can read the terrain files in the *static* directory, which are textured terrain heightmaps. The **model importer** can read the fixed files in the *static* directory and nonfixed files in the *runtime* directory. Those file contain map objects in the same space as their respective terrains, so importing the fixed, nonfixed and terrain files of a given map will give you a pretty faithful reconstruction.

The model importer has a second mode, when opening the *sappear.flx* model archive file directly. The importer will ask for a model ID and, optionally, a range. This can be used to import a single model, or several models in one go using the range to specify how many models should be imported in one go. The model IDs range from 0 to 3764. However, some of the entries are invalid. Placeholder cubes are filtered but other script objects are not. MEshes are labeled with their model ID so the ranged import can be used to hunt for interesting IDs. It is however not advised to import the whole range in one go as performance can degrade fast.

Terrains are imported as single meshes. Models are segmented by limb, each parented to an empty. If a model has LODs, they currently all reside within the same hierarchy. Water planes are not imported

A listing of the maps can be found at https://wiki.ultimacodex.com/wiki/Unused_Ultima_IX_maps

Some notable maps are **14** (the Avatar's house), **9** (the entirety of Britannia) and **98** (The E3 demo). Some interesting and/or random models to start with are **3223** (Avatar in scale armor), **3225** (Avatar in a loincloth), **1805** (Lord British), **1834** (the Guardian), **1869** and **2865**(Raven), **2** (a sergeant), **1793** (Lord British's throne).

Known problems
--------

- Blender performance degrades as more objects are imported. The full Britannia map with static and runtime objects can take up to an hour to import, while the map plus static objects is much more manageable.
- Alpha blended textures aren't properly decoded (e.g. moongates, waterfalls and clouds)
- Objects appear, that do not show in-game (e.g. extra lamppposts in the Avatar's driveway), likely flagged as hidden
- Objects appear in-game and not on the imports (e.g. the gate on the Avatar's driveway)
- Script objects that use exclusively invisible materials can only be seen in wireframe or solid mode

Planned features
--------

- Proper armatures and separated LODs
- Putting script objects in their own collections for easy sorting
- Animations
- Alpha blended textures
- Some performance optimization by only importing LOD 0 on maps and avoiding creating useless empties

Installation & Usage
--------

- Put the python files in Blender's addon directory and restart Blender
- Activate the add-ons under *Edit > Preferences > Add-ons > Import-Export: import Ultima 9 models* and *import Ultima 9 terrain*
- "Ultima 9 models (fixed.*, nonfixed.*, sappear.flx)" and "Ultima 9 terrain (terrain.*)" should appear in the import menu
- The scripts expect the directory structure to be that of a standard Ultima 9 install (both original and GOG versions work fine) and will look for the *types.dat*, *bitmap16.flx* and *sappear.flx* files in the appropriate relative folders.
- Setting the light type to _sun_ and light power to 3 provides a good initial experience in render preview mode 

Have fun exploring!

None of this would have been possible without the hard work of everyone in the Ultima community who figured out most aspects of the formats used in the importers, and the Ultima Codex that compiled the resulting information at https://wiki.ultimacodex.com/wiki/Ultima_IX_internal_formats
