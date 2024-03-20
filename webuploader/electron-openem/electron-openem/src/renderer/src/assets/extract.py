import hyperspy
import zipfile
import json

zip_name = "input.zip"
zip_ref = zipfile.ZipFile(zip_name, "r")
zip_ref.extractall()

filename = zip_ref.namelist()[0]
f = hyperspy.api.load(filename)
for el in f:
    print(el)

# f is a list of hyperspy classes of different acquisitions/technics
# .metadata and .original_metadata are of type 'hyperspy.misc.utils.DictionaryTreeBrowser'

# we keep the general metadata from the first EDSTEMSpectrum
# we keep Scan, Stage, Optics, Detectors and Instrument metadata for each Signal

spect = None
metadata_dict = {}

for el in f:
    if not spect and isinstance(el, hyperspy._signals.eds_tem.EDSTEMSpectrum):
        spect = el
        metadata_dict[
            el.metadata.get_item("General").get_item("title")
        ] = {
            "General": spect.metadata.get_item("General").as_dictionary(),
            "Sample": spect.metadata.get_item("Sample").as_dictionary()
        }
    elif isinstance(el, hyperspy._signals.signal2d.Signal2D):
        metadata_dict[
            el.metadata.get_item("General").get_item("title")
        ] = {
            "Scan": el.original_metadata.get_item("Scan").as_dictionary(),
            "Stage": el.original_metadata.get_item("Stage").as_dictionary(),
            "Optics": el.original_metadata.get_item("Optics").as_dictionary(),
            "Detectors": el.original_metadata.get_item("Detectors").as_dictionary(),
            "Instrument": el.original_metadata.get_item("Instrument").as_dictionary()
        }

with open("sample_metadata.json", "w") as outfile:
    json.dump(metadata_dict, outfile, indent=4)
