A library to merge nif geometry for Oblivion across shapes and according to in-game position. Collision boxes are also merged. Pay attention to the parameters in the class header -- right now it is tuned for LOD. Supports geometry in NiTriShape/Strips and most typical Oblivion collision types.

Example usage:
```
offsets = [-60000, 96000, 16000]
txt_path = r"S:\\IC LOD Project\\resources\\\ChorrolCastle.txt"
nifprocessor = NifProcessor()
nifprocessor.GenerateCombinedNif(txt_path, offsets[0], offsets[1], offsets[2], os.path.join(r"S:\IC LOD Project\resources", "BC_ChorrolCastle_far" + ".nif"), r"S:\IC LOD Project\out Chorrol\meshes")
```
