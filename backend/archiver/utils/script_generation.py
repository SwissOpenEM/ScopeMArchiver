

from typing import Dict


header = "#!/bin/bash"
download_folder = "DOWNLOAD_FOLDER=."
extraction_folder = "EXTRACTION_FOLDER=$DOWNLOAD_FOLDER"

error_handling = """if [ ! -d \"$DOWNLOAD_FOLDER\" ]; then
  echo \"Error: Download directory '$DOWNLOAD_FOLDER' does not exist.\" >&2
  exit 1
fi

if [ ! -d \"$EXTRACTION_FOLDER\" ]; then
  echo \"Error: Extraction directory '$EXTRACTION_FOLDER' does not exist.\">&2
  exit 1
fi\n\n
"""

comment_template = "# Dataset {dataset_id}"
echo_curl_template = "echo \"Downloading {datablock_name} to $DOWNLOAD_FOLDER\""
curl_template = "curl -C - --output $DOWNLOAD_FOLDER/{datablock_name} \"{url}\""
echo_extract_template = "\necho Extracting {datablock_name} to $EXTRACTION_FOLDER"
extract_tempalte = "tar -xf $DOWNLOAD_FOLDER/{datablock_name} -C $EXTRACTION_FOLDER"
done_message = "echo \"Downloaded and extracted all datablocks.\""

def generate_download_script(dataset_to_datablocks: Dict[str,str]) -> str:
  script = "\n".join([
    header,
    download_folder,
    extraction_folder,
    "\n\n",
    error_handling
  ])

  for dataset, datablocks in dataset_to_datablocks.items():

    # add data header
    script = "\n".join([
      script,
      comment_template.format(dataset_id=dataset),
    ])

    # add all datablocks
    for datablock in datablocks:
      script = "\n".join([
        script,
        echo_curl_template.format(datablock_name=datablock["name"]),
        curl_template.format(datablock_name=datablock["name"], url=datablock["url"]),
        echo_extract_template.format(datablock_name=datablock["name"]),
        extract_tempalte.format(datablock_name=datablock["name"]),
        "\n"
      ])

  script = script + done_message
  return script
