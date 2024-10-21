
slowLODGen is a tool to generate merged LOD meshes per cell for drastically increased performance. The tool fully supersedes the existing TES4LODGen and is a fully automated (almost) one-click solution.

**If you don't want to read instructions, at least read this: LOAD ORDER IS EXTREMELY IMPORTANT. Oblivion LOD system relies on full FormIDs of base objects for LOD objects. As base objects for merged meshes are defined in MergedLOD.esm, it is essential that you don't change its load order position after generation. If it happens, you can regenerate LOD files without going through full merged meshes generation by changing skip_mesh_generation to True in the config or just placing the esm back where it is supposed to be.**

Discord for support: https://discord.gg/77tgjpvGZ3

## **FAQ**

**OH NO MY LOD IS GONE**

Re-read the instructions. Go into Wrye Bash or any other mod manager and check that the position of MergedLOD.esm matches the position stated in the description. If you use the bsa packing feature, check that MergedLOD.esp is active.

**I don't see any improvements in performance; how can I ensure that the script has worked correctly?**

Disable MergedLOD.esm and load into the game: if your LOD has disappeared, then the script has worked correctly and either you have some other performance bottleneck (for instance, you are GPU-bounded because of 400 ENBs slapped on top), or you predominantly use non-atlassed shapes that don’t merge well.

**There are a lot of errors during mesh generation, is it bad?**

Usually not, especially during mesh generation. Unfortunately, the quality of mod meshes for Oblivion is *not that good*, so these messages serve as a useful datapoint if you actually run into some issues and have to debug them. That said, if you experience any issues with meshes that result in visual problems, feel free to report them to us. Additionally, if there are error like “can’t open a NIF file, not a NIF file”, first try opening it in Nifskope, if you can’t – write to the NIF mod author, it is not our responsibility to create workaround for completely broken meshes.

**I get tons of warnings about HITMEs and duplicated IDs for my mods.**

Not a problem for this tool, but you really need to reconsider using these mods on your setup for general potential stability issues so that's why the tool throws warnings.

**Can I get rid of the esm/esp? Can I merge them? I need to install all Ilovekyciliazabi's so I need esp slots.**

ESM you can’t merge (unless you are ready to write a binary patcher for the .lod files). Esp is a bit trickier. First, you don't need the esp if you don't use the bsa as it is only used for bsa loading. Second, you can load the bsa with any other esp, though I highly recommend this esp to be late in the load order as there are known instances of mods packing their own \*.lod files (or some mods like Hackdirt Alive packing .lod files for the author's setup for locations completely unrelated to Hackdirt, so you end up with seeing flying towers in Jeral Mountains).

**The script immediately crashes with some sort of “found unknown escape character" or "no such directory" error.**

If you changed something in the config file, read carefully the description of the settings. You need to use double slashes "\\" for all paths in the config. Also, make sure that you provided the correct paths, path to the Data folder and full path to plugins.txt – the examples are provided in the config.

**Why the need for an esm in the first place?**

Mostly to reduce the number of user reports claiming that their LOD is gone and reduce the maintenance time for users who change their LO often. .lod files save the information about object's base load-order dependent FormID – that means that any changes in MergedLOD.esm LO will break LOD. If it is placed very high in the LO, there is a little chance that any other LO changes would move the file.

**Why can't you provide a single exe executable like Wrye Bash?**

No real need to. Also, we use PyPy instead of CPython as it is 2-3x times faster for that particular script – popular and stable exe packing tools do not support PyPy.

**I don't like using some random bundled binaries, can I just run it on my python instance?**

Yes, all dependencies are installable from PyPI.
