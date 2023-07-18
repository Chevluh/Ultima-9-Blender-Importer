# Ultima 9 model importer
A Blender importer for models used in the 1999 game *Ultima IX: Ascension*

Features
--------

This can import most models used in Ultima 9, with reasonable approximations of the in-game shaders for Eevee and Cycles. Overall it should allow for a fairly faithful viewing experience.

Two importers are provided. The terrain importer can read the terrain files in the *static* directory, which are textured terrain heightmaps. The mode importer can read the fixed files in the *static* directory and nonfixed files in the *runtime* directory. Those file contain map objects in the same space as their respective terrains, so importing the fixed, nonfixed and terrain fiels of a given map will give you a pretty faithful reconstruction.

The model importer has a second mode, if you choose to open the *sappear.flx* model archive file directly. The importer will ask you for a model ID and, optionally, a range. This can be used to import a single model, or several models in one go using the range to specify how many models should be imported in one go. The model IDs range from 0 to 3764. However, some of the entries are invalid. Placeholder cubes are filtered but other script objects are not.

Terrains are imported as single meshes. Models are segmented by limb, each parented to an empty. If a model has LODs, they currently all reside within the same hierarchy.

A listing of the maps can be found at https://wiki.ultimacodex.com/wiki/Unused_Ultima_IX_maps
Some notable maps are 14 (the Avatar's house), 9 (the entirety of Britannia) and 98 (The E3 demo). Some interesting models are 3223 (Avatar in scale armor), 3225 (Avatar in a loincloth) 1805 (Lord British), 1834 (the Guardian), 1869 and 2865(Raven), 2 (a sergeant), 1793 (Lord British's throne).

Known problems
--------

- Blender performance degrades as more objects are imported. The full Britannia map with static and runtime objects can take up to an hour to import, while the map plus static objects is much more manageable.
- Alpha blended textures aren't properly displayed
-some objects appear, that do not show in-game (e.g. extra lamppposts in the Avatar's driveway), likely flagged as hidden
-some objects appear in-game and not on the imports (e.g. the gate on the Avatar's driveway

Planned features
--------

- Proper armatures and separated LODs
- Putting script objects in their own collections
- Animations
- Alpha blended textures
- Some performance optimization by only importing LOD 0 on maps

Installation & Usage
--------

- Put the python files in Blender's addon directory and restart Blender
- Activate the add-ons under *Edit > Preferences > Add-ons > Import-Export: import Ultima 9 models* and *import Ultima 9 terrain*
- "Ultima 9 models (fixed.*, nonfixed.*, sappear.flx)" and "Ultima 9 terrain (terrain.*)" should appear in the import menu
- The scripts expect the directory structure to be that of a standard Ultima 9 install (both original and GOG versions) and will look for the *types.dat*, *bitmap16.flx* and *sappear.flx* files in the appropriate relative folders.

Have fun exploring!

None of this would have been possible without the hard work of everyone in the Ultima community who figured out most aspects of the format used here, and the Ultima Codex that compiled the resulting information at https://wiki.ultimacodex.com/wiki/Ultima_IX_internal_formats
