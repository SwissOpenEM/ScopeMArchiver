# EMUploader

This will contain the complete set of components for the uploader for the
OpenEMNetwork project.  

So far only `mockarchiver` is here - a Python tool that mocks the LTS
tape archival and unarchival processes.

To get this running:

```bash
mkdir -p lts/final
mkdir -p lts/final.real
mkdir -p lts/replica
mkdir -p lts/archived
virtualenv venv
source venv/bin/activate
pip install -r mockarchiver/requirements.txt
cd mockarchiver
cp .env.example .env # shouldn't need editing
python mockarchiver.py
```

You can test the mock archiver like this:

```bash
$ cd lts
$ echo "one" > final/myfile
# Wait for the mock archiver to say the file has been archived
$ cat final/myfile
cat: final/myfile: Input/output error
# Repeat until unarchiving has finished
$ cat final/myfile
one
```



### Inside Docker Container

`docker-compose-development.yml` mounts the relative folder `emuploader/lts` into the container. Files written into `emuploader/lts/final` get archived as in the example above.

However, it needs to be touched inside the docker container

```bash
touch /mnt/lts/final/myfile
```

else it does not seem to appear inside the container, see [Issue](https://github.com/docker/for-mac/issues/5795)
